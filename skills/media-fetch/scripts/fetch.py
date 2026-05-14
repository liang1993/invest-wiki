#!/usr/bin/env python3
"""抖音视频下载工具

用法：
    python3 fetch.py <URL> [--target DIR]

通过 Playwright 启动 headless Chromium 打开分享链接，监听网络请求抓取无水印
mp4 → 下载并写 metadata。默认输出到 ~/Downloads/media-fetch/，传 --target
才放到指定目录（如 raw/media/_inbox/）。
输出：终端最后一行 `MEDIA_PATH=<absolute path>`，便于下游 skill 串联。

历史：2026-05 之前用 douyin-tiktok-scraper，因抖音 API 签名/msToken 失效而废弃。
"""
import argparse
import asyncio
import datetime
import json
import re
import sys
import urllib.request
from pathlib import Path

DEFAULT_TARGET = Path.home() / "Downloads/media-fetch"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def parse_args():
    p = argparse.ArgumentParser(description="抖音视频本地下载（无水印 mp4 + metadata）")
    p.add_argument("url", help="抖音分享 URL（v.douyin.com/xxx 或完整 URL）")
    p.add_argument(
        "--target",
        help=f"输出目录（默认 {DEFAULT_TARGET}；传相对路径如 raw/media/_inbox/ 可入 wiki）",
    )
    return p.parse_args()


def check_deps():
    """检查 playwright + chromium 是否就位。"""
    try:
        import playwright  # noqa: F401
        from playwright.async_api import async_playwright  # noqa: F401
    except ImportError:
        print(
            "ERROR: 缺少依赖 playwright\n"
            "  pip3 install --break-system-packages playwright\n"
            "  python3 -m playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)


async def fetch_video(url: str) -> dict:
    """启动 headless Chromium，访问 share URL，捕获视频网络请求 + 页面元数据。

    返回 dict：{aweme_id, title, video_url, candidates, cookies}
    """
    from playwright.async_api import async_playwright

    video_urls: list[str] = []
    page_title = ""
    aweme_id = ""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=UA,
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        def on_response(resp):
            u = resp.url
            if "douyinvod.com" in u and (u.endswith(".mp4") or "mime_type=video_mp4" in u):
                video_urls.append(u)

        page.on("response", on_response)

        print(f"→ 解析 {url}", file=sys.stderr)
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            await page.wait_for_selector("video", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(5000)

        page_title = await page.title()
        m = re.search(r"/video/(\d+)", page.url)
        if m:
            aweme_id = m.group(1)

        try:
            src = await page.eval_on_selector("video", "v => v.src || v.currentSrc")
            if src and not src.startswith("blob:"):
                video_urls.append(src)
        except Exception:
            pass

        cookies = await context.cookies()
        await browser.close()

    seen = set()
    candidates = []
    for u in video_urls:
        if u in seen or u.startswith("blob:"):
            continue
        seen.add(u)
        candidates.append(u)

    if not candidates:
        raise RuntimeError("未捕获到视频网络请求（可能是图文 / 直播 / 抖音页面结构变更）")

    return {
        "aweme_id": aweme_id or "unknown",
        "title": page_title,
        "video_url": candidates[0],
        "candidates": candidates,
        "cookies": cookies,
    }


def download_to(url: str, dest: Path, cookies: list):
    """带 Cookie/Referer/UA 头流式下载到目标文件。"""
    cookie_header = "; ".join(
        f"{c['name']}={c['value']}" for c in cookies if "douyin" in c.get("domain", "")
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": "https://www.douyin.com/",
            "Cookie": cookie_header,
        },
    )
    total = 0
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
    return total


def main():
    args = parse_args()
    check_deps()
    target = Path(args.target) if args.target else DEFAULT_TARGET
    target.mkdir(parents=True, exist_ok=True)

    try:
        data = asyncio.run(fetch_video(args.url))
    except Exception as e:
        print(f"ERROR: 解析失败：{e}", file=sys.stderr)
        print(
            "  可能原因：URL 不合法 / 视频已删除 / 抖音页面结构变更\n"
            "  调试：python3 -m playwright install chromium ; 或 headed 模式人工查看",
            file=sys.stderr,
        )
        sys.exit(1)

    date = datetime.date.today().isoformat()
    mp4_path = target / f"{date}_douyin_{data['aweme_id']}.mp4"
    info_path = target / f"{date}_douyin_{data['aweme_id']}.info.json"

    print(f"→ 下载到 {mp4_path}", file=sys.stderr)
    try:
        bytes_written = download_to(data["video_url"], mp4_path, data["cookies"])
    except Exception as e:
        print(f"ERROR: 下载失败：{e}", file=sys.stderr)
        sys.exit(1)
    print(f"→ 写入 {bytes_written / 1024 / 1024:.2f} MB", file=sys.stderr)

    info = {
        "aweme_id": data["aweme_id"],
        "title": data["title"],
        "platform": "douyin",
        "source_url": args.url,
        "video_url": data["video_url"],
        "candidates": data["candidates"],
        "fetched_at": datetime.datetime.now().isoformat(),
    }
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"MEDIA_PATH={mp4_path.resolve()}")


if __name__ == "__main__":
    main()
