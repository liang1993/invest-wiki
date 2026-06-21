#!/usr/bin/env python3
"""批量下载选中作品到 workdir/media/，复用 media-fetch；并发2+重试3+抖动+断点续传。

用法：
    python3.14 download.py --workdir DIR (--ids-file selection.txt | --ids id1,id2,...)

selection.txt：每行一个 aweme_id（由 LLM 从 enumerate 的免费候选里挑选后写入）。
付费(VIP)作品 has_paid=0 时只有预览，按需跳过（见 SKILL.md）。
"""
import argparse, glob, random, subprocess, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO = Path(__file__).resolve().parents[3]          # skills/douyin-distill/scripts/ → repo root
FETCH = REPO / "skills/media-fetch/scripts/fetch.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--ids-file")
    ap.add_argument("--ids")
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    media = Path(a.workdir) / "media"; media.mkdir(parents=True, exist_ok=True)
    if a.ids:
        ids = [x.strip() for x in a.ids.split(",") if x.strip()]
    elif a.ids_file:
        ids = [x.strip() for x in Path(a.ids_file).read_text().splitlines() if x.strip()]
    else:
        print("ERROR: 需要 --ids 或 --ids-file", file=sys.stderr); sys.exit(1)

    have = lambda aid: bool(glob.glob(str(media / f"*_{aid}.mp4")))

    def dl(aid):
        if have(aid):
            return aid, "skip(exists)"
        url = f"https://www.douyin.com/video/{aid}"
        for attempt in range(3):
            time.sleep(random.uniform(0.5, 2.5))
            try:
                r = subprocess.run(["python3.14", str(FETCH), url, "--target", str(media)],
                                   capture_output=True, text=True, timeout=240)
                if have(aid):
                    return aid, "ok"
                if attempt == 2:
                    tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:]
                    return aid, f"FAIL {tail}"
            except subprocess.TimeoutExpired:
                if attempt == 2:
                    return aid, "FAIL timeout"
        return aid, "FAIL"

    print(f"待下载 {len(ids)} 条 → {media}", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed({ex.submit(dl, x): x for x in ids}):
            aid, st = f.result(); done += 1
            print(f"[{done}/{len(ids)}] {aid} → {st}", flush=True)
    print(f"完成：media/ 下 {len(list(media.glob('*.mp4')))} 个 mp4", flush=True)


if __name__ == "__main__":
    main()
