#!/usr/bin/env python3
"""媒体下载工具（Douyin + Apple Podcasts）

用法：
    python3 fetch.py <URL> [--target DIR]

支持平台（按 URL 自动分流）：
- Douyin（v.douyin.com / www.douyin.com）：Playwright + headless Chromium
- Apple Podcasts（podcasts.apple.com）：iTunes Search API + 直接 HTTP

输出：终端最后一行 `MEDIA_PATH=<absolute path>`，便于下游 skill 串联。
"""
from __future__ import annotations  # 注解 lazy evaluated，兼容 Python 3.7+（macOS 自带 3.9 也能跑）

import argparse
import asyncio
import datetime
import json
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_TARGET = Path.home() / "Downloads/media-fetch"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Douyin CDN 识别（2026-05 起长视频走 DASH 分流，域名不再固定为 douyinvod.com）
DOUYIN_REAL_CDN_HOSTS = ("douyinvod.com", "zjcdn.com", "aweme.snssdk.com")
DOUYIN_PLACEHOLDER_HOSTS = ("douyinstatic.com",)  # 抖音 H265 探测 / 静态资源
DOUYIN_PLACEHOLDER_KEYWORDS = ("uuu_265",)
MIN_VIDEO_SIZE = 500_000  # bytes；过滤碎片 / 探测流


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


def _is_douyin_media_url(u: str) -> bool:
    """过滤 placeholder（uuu_265 H265 探测）+ 静态域名，只放行真实 CDN 视频流。"""
    if any(h in u for h in DOUYIN_PLACEHOLDER_HOSTS):
        return False
    if any(k in u for k in DOUYIN_PLACEHOLDER_KEYWORDS):
        return False
    if not any(h in u for h in DOUYIN_REAL_CDN_HOSTS):
        return False
    return "/video/tos/" in u or u.endswith(".mp4") or "mime_type=video" in u


async def fetch_douyin(url: str) -> dict:
    """启动 headless Chromium，捕获视频网络请求 + DOM <video>.src。

    抖音 2026-05 起长视频使用 DASH 分流：
    - `media-video-avc1` / `hvc1`：纯视频流（无音轨）
    - `media-audio-und-mp4a`：纯音频流
    本函数同时捕获两路流；下游 main() 检测到 `audio_media_url` 不为 None
    时会用 ffmpeg merge。短视频通常音视频合一，只捕获 video 流即可。
    """
    from playwright.async_api import async_playwright

    media_log: list[tuple[str, int, bool]] = []  # (url, size, is_audio)
    page_title = ""
    aweme_id = ""

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception as e:
            if "Executable doesn't exist" in str(e):
                raise RuntimeError(
                    "Chromium 未安装，请运行：python3 -m playwright install chromium"
                ) from e
            raise
        context = await browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        def on_response(resp):
            u = resp.url
            if not _is_douyin_media_url(u):
                return
            try:
                cl = int(resp.headers.get("content-length") or 0)
            except (TypeError, ValueError):
                cl = 0
            is_audio = "media-audio-" in u
            media_log.append((u, cl, is_audio))

        page.on("response", on_response)

        print(f"→ 解析 {url}", file=sys.stderr)
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            await page.wait_for_selector("video", timeout=15000)
        except Exception:
            pass
        # 触发播放,让 CDN 开始供流
        try:
            await page.evaluate(
                "const v = document.querySelector('video');"
                "if (v) { v.muted = true; v.play().catch(()=>{}); }"
            )
        except Exception:
            pass
        # 循环等待直到捕到至少一条 size > MIN_VIDEO_SIZE 的流（长视频 metadata 加载慢）
        for _ in range(12):  # 最多 60s
            await page.wait_for_timeout(5000)
            if any(cl >= MIN_VIDEO_SIZE for _, cl, _ in media_log):
                break

        page_title = await page.title()
        m = re.search(r"/video/(\d+)", page.url)
        if m:
            aweme_id = m.group(1)

        try:
            src = await page.eval_on_selector("video", "v => v.src || v.currentSrc")
            if src and not src.startswith("blob:") and _is_douyin_media_url(src):
                media_log.append((src, 0, False))  # DOM <video>.src 必然是视频流
        except Exception:
            pass

        cookies = await context.cookies()
        await browser.close()

    # 按 size 排序选最大的 video / audio 流（同一资源有多次 range request，取最大那条）
    videos: list[tuple[str, int]] = []
    audios: list[tuple[str, int]] = []
    for u, cl, is_audio in media_log:
        (audios if is_audio else videos).append((u, cl))
    videos.sort(key=lambda x: -x[1])
    audios.sort(key=lambda x: -x[1])

    if not videos:
        raise RuntimeError("未捕获到视频网络请求（可能是图文 / 直播 / 抖音页面结构变更）")

    video_url = videos[0][0]
    audio_url = audios[0][0] if audios else None

    cookie_header = "; ".join(
        f"{c['name']}={c['value']}" for c in cookies if "douyin" in c.get("domain", "")
    )
    candidates = [u for u, _ in videos[:5]]
    if audio_url:
        candidates.append(audio_url)
    return {
        "platform": "douyin",
        "id": aweme_id or "unknown",
        "title": page_title,
        "media_url": video_url,
        # 非 None = DASH 分流，main() 会下载两路再用 ffmpeg merge
        "audio_media_url": audio_url,
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

def download_to(url: str, dest: Path, headers: dict, timeout: int = 600) -> int:
    """带自定义 headers 流式下载到目标文件，返回写入字节数。

    先写入 `.part` 临时文件，成功后原子 rename 到 dest；失败清理临时文件，
    避免半成品 mp4 误导下游（ASR / 用户手动检查）。
    timeout 是整个 GET 的上限（urllib 不支持 per-chunk timeout），默认 600s。
    """
    req = urllib.request.Request(url, headers=headers)
    tmp = dest.with_suffix(dest.suffix + ".part")
    total = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as f:
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
        tmp.replace(dest)
        return total
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


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

    audio_url = data.get("audio_media_url")
    if audio_url:
        # DASH 路径：分别下载 video / audio 流到临时文件，用 ffmpeg merge
        with tempfile.TemporaryDirectory() as tmp:
            v_tmp = Path(tmp) / "video.mp4"
            a_tmp = Path(tmp) / "audio.m4a"
            print(f"→ DASH 下载视频流", file=sys.stderr)
            try:
                v_bytes = download_to(data["media_url"], v_tmp, data["headers"])
                print(f"→ DASH 下载音频流", file=sys.stderr)
                a_bytes = download_to(audio_url, a_tmp, data["headers"])
            except Exception as e:
                print(f"ERROR: 下载失败：{e}", file=sys.stderr)
                sys.exit(1)
            print(f"→ ffmpeg 合并 → {out_path.name}", file=sys.stderr)
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(v_tmp), "-i", str(a_tmp),
                     "-c", "copy", str(out_path)],
                    check=True, capture_output=True,
                )
            except FileNotFoundError:
                print("ERROR: 未找到 ffmpeg（brew install ffmpeg）", file=sys.stderr)
                sys.exit(1)
            except subprocess.CalledProcessError as e:
                err = e.stderr.decode(errors="ignore")[:500] if e.stderr else "(no stderr)"
                print(f"ERROR: ffmpeg 合并失败：{err}", file=sys.stderr)
                sys.exit(1)
            bytes_written = out_path.stat().st_size
            print(
                f"→ 写入 {bytes_written/1024/1024:.2f} MB"
                f"（视频 {v_bytes/1024/1024:.2f}MB + 音频 {a_bytes/1024/1024:.2f}MB）",
                file=sys.stderr,
            )
    else:
        # 短视频 / podcast 路径：音视频合一，直接下载
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
        "audio_media_url": audio_url,
        "candidates": data["candidates"],
        "extra": data["extra"],
        "fetched_at": datetime.datetime.now().isoformat(),
    }
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"MEDIA_PATH={out_path.resolve()}")


if __name__ == "__main__":
    main()
