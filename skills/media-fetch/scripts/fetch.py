#!/usr/bin/env python3
"""媒体下载工具（Douyin + Apple Podcasts）

用法：
    python3 fetch.py <URL> [--target DIR]

支持平台（按 URL 自动分流）：
- Douyin（v.douyin.com / www.douyin.com）：Playwright + headless Chromium
- Apple Podcasts（podcasts.apple.com）：iTunes Search API + 直接 HTTP

输出：终端最后一行 `MEDIA_PATH=<absolute path>`，便于下游 skill 串联。
"""
import argparse
import asyncio
import datetime
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_TARGET = Path.home() / "Downloads/media-fetch"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def detect_platform(url: str) -> str:
    if "douyin.com" in url or "iesdouyin.com" in url:
        return "douyin"
    if "podcasts.apple.com" in url:
        return "applepodcast"
    raise ValueError(f"不支持的 URL：{url}（目前支持 Douyin / Apple Podcasts）")


# ===== Douyin =====

def check_douyin_deps():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print(
            "ERROR: 缺少依赖 playwright\n"
            "  pip3 install --break-system-packages playwright\n"
            "  python3 -m playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)


async def fetch_douyin(url: str) -> dict:
    """启动 headless Chromium，捕获视频网络请求 + DOM <video>.src。"""
    from playwright.async_api import async_playwright

    video_urls: list[str] = []
    page_title = ""
    aweme_id = ""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 800})
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

    cookie_header = "; ".join(
        f"{c['name']}={c['value']}" for c in cookies if "douyin" in c.get("domain", "")
    )
    return {
        "platform": "douyin",
        "id": aweme_id or "unknown",
        "title": page_title,
        "media_url": candidates[0],
        "ext": "mp4",
        "candidates": candidates,
        "extra": {},
        "headers": {
            "User-Agent": UA,
            "Referer": "https://www.douyin.com/",
            "Cookie": cookie_header,
        },
    }


# ===== Apple Podcasts =====

def parse_apple_podcast_url(url: str) -> tuple[str, str | None]:
    """从 Apple Podcasts URL 提取 (podcast_id, episode_track_id|None)。"""
    m = re.search(r"/id(\d+)", url)
    if not m:
        raise ValueError(f"无法从 URL 提取 podcast id：{url}")
    podcast_id = m.group(1)
    qs = urllib.parse.urlparse(url).query
    episode_id = urllib.parse.parse_qs(qs).get("i", [None])[0]
    return podcast_id, episode_id


def fetch_apple_podcast(url: str) -> dict:
    """iTunes Search API → episode 元数据 + 直链 mp3/m4a。"""
    podcast_id, episode_id = parse_apple_podcast_url(url)
    print(
        f"→ 解析 Apple Podcast (podcast={podcast_id}, episode={episode_id or 'latest'})",
        file=sys.stderr,
    )

    api = "https://itunes.apple.com/lookup?" + urllib.parse.urlencode(
        {"id": podcast_id, "entity": "podcastEpisode", "limit": 200}
    )
    with urllib.request.urlopen(api, timeout=15) as resp:
        data = json.loads(resp.read())

    results = data.get("results", [])
    episodes = [r for r in results if r.get("kind") == "podcast-episode"]
    if not episodes:
        raise RuntimeError(f"iTunes API 未返回任何 episode（podcast_id={podcast_id}）")

    if episode_id:
        episode = next((e for e in episodes if str(e.get("trackId")) == episode_id), None)
        if not episode:
            raise RuntimeError(
                f"episode_id={episode_id} 不在最近 200 集内（iTunes API hard cap）；"
                f"如需更老的集，需要 RSS 回退方案"
            )
    else:
        episode = episodes[0]

    media_url = episode.get("episodeUrl")
    if not media_url:
        raise RuntimeError("episode 没有 episodeUrl 字段，无法下载")

    path = urllib.parse.urlparse(media_url).path
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else "mp3"
    if ext not in ("mp3", "m4a", "aac", "ogg", "wav"):
        ext = "mp3"

    return {
        "platform": "applepodcast",
        "id": f"{podcast_id}_{episode.get('trackId')}",
        "title": episode.get("trackName", ""),
        "media_url": media_url,
        "ext": ext,
        "candidates": [media_url],
        "extra": {
            "podcast_id": podcast_id,
            "podcast_name": episode.get("collectionName"),
            "episode_track_id": str(episode.get("trackId")),
            "release_date": episode.get("releaseDate"),
            "feed_url": episode.get("feedUrl"),
            "track_time_millis": episode.get("trackTimeMillis"),
            "description": episode.get("description"),
        },
        "headers": {"User-Agent": UA},
    }


# ===== Generic download =====

def download_to(url: str, dest: Path, headers: dict) -> int:
    """带自定义 headers 流式下载到目标文件，返回写入字节数。"""
    req = urllib.request.Request(url, headers=headers)
    total = 0
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
    return total


def parse_args():
    p = argparse.ArgumentParser(description="本地媒体下载（Douyin / Apple Podcasts）")
    p.add_argument("url", help="Douyin 分享 URL 或 Apple Podcasts URL")
    p.add_argument(
        "--target",
        help=f"输出目录（默认 {DEFAULT_TARGET}；传相对路径如 raw/media/_inbox/ 可入 wiki）",
    )
    return p.parse_args()


def main():
    args = parse_args()
    target = Path(args.target) if args.target else DEFAULT_TARGET
    target.mkdir(parents=True, exist_ok=True)

    try:
        platform = detect_platform(args.url)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if platform == "douyin":
            check_douyin_deps()
            data = asyncio.run(fetch_douyin(args.url))
        elif platform == "applepodcast":
            data = fetch_apple_podcast(args.url)
        else:
            raise RuntimeError(f"未实现的 platform：{platform}")
    except Exception as e:
        print(f"ERROR: 解析失败：{e}", file=sys.stderr)
        sys.exit(1)

    date = datetime.date.today().isoformat()
    out_path = target / f"{date}_{platform}_{data['id']}.{data['ext']}"
    info_path = out_path.with_suffix(".info.json")

    print(f"→ 下载到 {out_path}", file=sys.stderr)
    try:
        bytes_written = download_to(data["media_url"], out_path, data["headers"])
    except Exception as e:
        print(f"ERROR: 下载失败：{e}", file=sys.stderr)
        sys.exit(1)
    print(f"→ 写入 {bytes_written / 1024 / 1024:.2f} MB", file=sys.stderr)

    info = {
        "platform": platform,
        "id": data["id"],
        "title": data["title"],
        "source_url": args.url,
        "media_url": data["media_url"],
        "candidates": data["candidates"],
        "extra": data["extra"],
        "fetched_at": datetime.datetime.now().isoformat(),
    }
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"MEDIA_PATH={out_path.resolve()}")


if __name__ == "__main__":
    main()
