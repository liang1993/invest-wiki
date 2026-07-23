#!/usr/bin/env python3
"""每日检查一组 Apple Podcasts 是否有新一集，有则下载 + 转写，输出结果 JSON。

**机械层**：只负责"枚举各节目最新集 → 比对已见 → 下载 + 转写新集 → 更新已见状态"，
不做摘要、不发通知。摘要 + 投递交给上层（Claude 定时任务，原生 LLM + lark-cli）。

对标 skills/douyin-distill/scripts/watch.py（抖音版），本脚本是 Apple Podcasts 版。
复用 media-fetch/fetch.py（下载）+ asr/transcribe.py（转写），均 subprocess 调用。

用法：
    python3 watch_podcasts.py               # 正常跑：枚举→比对→下载转写新集→更新状态→输出 JSON
    python3 watch_podcasts.py --seed        # 仅建立基线：把各节目当前最新标记为已见，不下载
    python3 watch_podcasts.py --check-only  # 只枚举+比对，不下载、不改状态（测试用）
    python3 watch_podcasts.py --max 4       # 单次最多处理几集新内容（默认 4，防暴增）

Apple Podcasts 走公开 iTunes Search API，**无登录态**；枚举纯标准库，任意解释器可跑。
下载/转写子进程用 brew python（transcribe.py 需 funasr/torch；fetch.py 对 podcast 路径不重入）。
状态落 ~/.podcast-watch/seen.json，输出落 media-fetch / asr 默认目录，均不入 git。
stdout 末行是 RESULT_JSON=<一行 json>；其余进度走 stderr。
"""
from __future__ import annotations
import argparse
import datetime
import html
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# ---- 配置（6 档投资/商业播客）----
REPO = Path("/Users/bytedance/liang/invest-wiki")
PY = "/opt/homebrew/bin/python3"           # funasr/torch 所在解释器（下载+转写子进程）
FETCH = REPO / "skills/media-fetch/scripts/fetch.py"
ASR = REPO / "skills/asr/scripts/transcribe.py"
STATE_DIR = Path.home() / ".podcast-watch"
STATE_FILE = STATE_DIR / "seen.json"

# (podcast_id, 显示名)。顺序即摘要展示顺序。
PODCASTS = [
    ("1634356920", "张小珺Jùn｜商业访谈录"),
    ("1689350648", "厚雪长波"),
    ("1686741064", "面基"),
    ("1607724726", "起朱楼宴宾客"),
    ("1586616450", "市场透视 Moving Markets"),
    ("1581271335", "无人知晓"),
]

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def strip_html(s: str | None, limit: int = 800) -> str:
    """节目简介常含 HTML（<p>/<a>…）→ 去标签 + 反转义 + 压空白，截断防爆。"""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def enumerate_episodes(podcast_id: str, limit: int) -> list[dict]:
    """iTunes lookup 拿某节目最近若干集（按发布时间倒序）。与 fetch.py 同一 API。"""
    api = "https://itunes.apple.com/lookup?" + urllib.parse.urlencode(
        {"id": podcast_id, "entity": "podcastEpisode", "limit": limit + 2})
    req = urllib.request.Request(api, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    eps = [e for e in data.get("results", []) if e.get("kind") == "podcast-episode"]
    recs = []
    for e in eps:
        tid = e.get("trackId")
        if not tid:
            continue
        rd = e.get("releaseDate") or ""      # ISO8601 → 字符串即可字典序倒排
        recs.append({
            "track_id": str(tid),
            "title": e.get("trackName", ""),
            "date": rd[:10],
            "release_ts": rd,
            "duration_min": round((e.get("trackTimeMillis") or 0) / 60000, 1),
            "description": strip_html(e.get("description")),
            # fetch.py 只需 URL 里有 /id{NUM} 和 ?i={trackId}，slug 可省
            "source_url": f"https://podcasts.apple.com/cn/podcast/id{podcast_id}?i={tid}",
        })
    recs.sort(key=lambda r: r["release_ts"], reverse=True)
    return recs[:limit]


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"seen": {}, "last_run": None, "last_status": None}


def save_state(st: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    st["last_run"] = datetime.datetime.now().isoformat(timespec="seconds")
    STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2))


def run_capture(cmd: list, key: str, timeout: int) -> str | None:
    """跑子进程，从 stdout 抓 '<key>=<path>' 末行契约值。"""
    log(f"   $ {' '.join(str(c) for c in cmd)}")
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        log(f"   ✗ 子进程超时 {timeout}s")
        return None
    if r.returncode != 0:
        log(f"   ✗ 退出码 {r.returncode}: {(r.stderr or '')[-300:]}")
        return None
    for line in reversed(r.stdout.strip().splitlines()):
        if line.startswith(f"{key}="):
            return line[len(key) + 1:].strip()
    log(f"   ✗ stdout 未见 {key}=")
    return None


def emit(obj: dict):
    print("RESULT_JSON=" + json.dumps(obj, ensure_ascii=False))
    # 同时落盘：长播客转写可能几十分钟，上层用后台跑本脚本，退出后读此文件最稳
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / "last_result.json").write_text(
            json.dumps(obj, ensure_ascii=False, indent=2))
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="仅建立基线，标记各节目当前最新为已见，不下载")
    ap.add_argument("--check-only", action="store_true", help="只枚举+比对，不下载不改状态")
    ap.add_argument("--max", type=int, default=4, help="单次最多处理新集数（跨节目全局上限）")
    ap.add_argument("--per-show", type=int, default=2, help="单节目单次最多处理几集（防单档暴增）")
    ap.add_argument("--list", type=int, default=8, help="每档考察最新多少集")
    ap.add_argument("--fetch-timeout", type=int, default=900, help="单集下载超时秒（默认 15min）")
    ap.add_argument("--asr-timeout", type=int, default=3600, help="单集转写超时秒（默认 60min，长播客用）")
    a = ap.parse_args()

    st = load_state()
    seen = st.get("seen", {})

    # 逐档枚举，单档失败不影响其它档（收集到 enum_errors）
    enum_errors, per_show = [], {}
    for pid, name in PODCASTS:
        try:
            per_show[pid] = enumerate_episodes(pid, a.list)
            log(f"→ {name}: 最新 {len(per_show[pid])} 集"
                + (f"（{per_show[pid][0]['date']}）" if per_show[pid] else ""))
        except Exception as e:
            enum_errors.append({"podcast": name, "podcast_id": pid, "error": str(e)})
            per_show[pid] = []
            log(f"   ✗ 枚举失败 {name}: {e}")

    if sum(len(v) for v in per_show.values()) == 0:
        st["last_status"] = "error: 全部节目枚举为空"
        save_state(st)
        emit({"status": "error", "stage": "enumerate",
              "error": "所有节目枚举为空（疑似网络故障或 iTunes API 变更）", "errors": enum_errors})
        return

    # 首次或显式 --seed：建立基线，不下载
    if a.seed or not seen:
        newseen, preview = {}, []
        for pid, name in PODCASTS:
            recs = per_show.get(pid, [])
            newseen[pid] = sorted(set(seen.get(pid, [])) | {r["track_id"] for r in recs})
            if recs:
                preview.append({"podcast": name, "date": recs[0]["date"], "title": recs[0]["title"]})
        st["seen"] = newseen
        st["last_status"] = "seeded"
        if not a.check_only:
            save_state(st)
        emit({"status": "seeded", "baseline_count": sum(len(v) for v in newseen.values()),
              "latest": preview, "errors": enum_errors})
        return

    # 找新集：逐档 diff 已见，单档截断 per-show，汇总后按发布时间倒序、全局截断 max
    new = []
    for pid, name in PODCASTS:
        seen_ids = set(seen.get(pid, []))
        fresh = [r for r in per_show.get(pid, []) if r["track_id"] not in seen_ids][:a.per_show]
        for r in fresh:
            new.append({**r, "podcast": name, "podcast_id": pid})
    new.sort(key=lambda r: r["release_ts"], reverse=True)
    new = new[:a.max]

    if a.check_only:
        emit({"status": "check_only", "new_count": len(new),
              "new": [{"podcast": r["podcast"], "date": r["date"], "title": r["title"]} for r in new],
              "errors": enum_errors})
        return

    if not new:
        st["last_status"] = "no_update"
        save_state(st)
        emit({"status": "no_update", "errors": enum_errors})
        return

    # 下载 + 转写每集新内容
    out, proc_errors = [], []
    for r in new:
        pid, tid = r["podcast_id"], r["track_id"]
        log(f"▶ 处理 {r['podcast']} [{r['date']}] {r['title'][:40]} ({r['duration_min']}min)")
        media = run_capture([PY, FETCH, r["source_url"]], "MEDIA_PATH", a.fetch_timeout)
        if not media:
            proc_errors.append({"podcast": r["podcast"], "title": r["title"], "stage": "download"})
            continue
        tr = run_capture([PY, ASR, media], "TRANSCRIPT_PATH", a.asr_timeout)
        if not tr:
            proc_errors.append({"podcast": r["podcast"], "title": r["title"],
                                "stage": "transcribe", "media": media})
            continue
        # 转写成功 = 内容已安全落盘 → 标记已见（下载/转写失败则留待下次重试）
        seen.setdefault(pid, [])
        if tid not in seen[pid]:
            seen[pid] = sorted(seen[pid] + [tid])
        st["seen"] = seen
        save_state(st)
        out.append({"podcast": r["podcast"], "podcast_id": pid, "track_id": tid,
                    "title": r["title"], "date": r["date"], "duration_min": r["duration_min"],
                    "media_path": media, "transcript_path": tr,
                    "description": r["description"], "source_url": r["source_url"]})

    if out:
        st["last_status"] = f"processed {len(out)}, errors {len(proc_errors)}"
        save_state(st)
        emit({"status": "ok", "new": out, "errors": enum_errors + proc_errors})
    else:
        st["last_status"] = f"all {len(new)} new failed"
        save_state(st)
        emit({"status": "error", "stage": "process",
              "error": f"{len(new)} 集新内容全部下载/转写失败",
              "errors": enum_errors + proc_errors})


if __name__ == "__main__":
    main()
