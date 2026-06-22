#!/usr/bin/env python3
"""每日检查某抖音博主主页是否有新作品，有则下载 + 转写，输出结果 JSON。

**机械层**：只负责"枚举最新 → 比对已见 → 下载 + 转写新作品 → 更新已见状态"，
不做摘要、不发通知。摘要 + 投递交给上层（Claude 定时任务，原生 LLM + lark-cli）。

为什么不用 enumerate.py：那个滚到底全量枚举（几分钟 + 全量窗口）；本脚本只抓首屏
最新若干条做"有没有新的"判断，约 15-20s 关窗。登录态 / 付费判定逻辑与 enumerate.py 一致。

用法：
    python3 watch.py                # 正常跑：枚举→比对→下载转写新作品→更新状态→输出 JSON
    python3 watch.py --seed         # 仅建立基线：把当前最新全标记为已见，不下载
    python3 watch.py --check-only   # 只枚举+比对，不下载、不改状态（测试用）
    python3 watch.py --max 5        # 单次最多处理几条新作品（默认 5，防暴增）

依赖 brew python（playwright + funasr）：/opt/homebrew/bin/python3
状态/输出落 ~/.douyin-watch 与 media-fetch/asr 默认目录，均不入 git。
stdout 末行是 RESULT_JSON=<一行 json>；其余进度走 stderr。
"""
from __future__ import annotations
import argparse, asyncio, json, sys, subprocess, datetime
from pathlib import Path
from playwright.async_api import async_playwright

# ---- 配置（艾丽的无废话财经）----
CREATOR_NAME = "艾丽的无废话财经"
CREATOR_URL = "https://www.douyin.com/user/MS4wLjABAAAA_hkYGrUP3d2i3JodCLwrplan05tJ9xl1D6lZySbNC0Q"
REPO = Path("/Users/bytedance/liang/invest-wiki")
PY = "/opt/homebrew/bin/python3"           # playwright + funasr 所在解释器
FETCH = REPO / "skills/media-fetch/scripts/fetch.py"
ASR = REPO / "skills/asr/scripts/transcribe.py"
STATE_DIR = Path.home() / ".douyin-watch"
# 监控专用登录态（与蒸馏流程隔离，互不干扰）；过期时由 login.py 重扫
USERDATA = STATE_DIR / "userdata"
STATE_FILE = STATE_DIR / "ellie_seen.json"
STALE_DAYS = 5   # 最新作品超过这么多天 → 疑似登录过期（她日更）

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
POST_API = "/aweme/v1/web/aweme/post/"
STEALTH = (
    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    "Object.defineProperty(navigator,'languages',{get:()=>['zh-CN','zh']});"
    "window.chrome={runtime:{}};"
)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def is_paid(item: dict, has_free_play: bool) -> bool:
    ci = item.get("charge_info") or {}
    if ci.get("is_charge_content"):
        return True
    mix = item.get("mix_info") or {}
    if (mix.get("charge_info") or {}) or mix.get("paid_episodes"):
        if not has_free_play:
            return True
    return not has_free_play


def clear_stale_locks():
    """profile 空闲时清掉残留单例锁，避免上次异常退出导致本次启动失败。"""
    for n in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        p = USERDATA / n
        try:
            if p.exists() or p.is_symlink():
                p.unlink()
        except Exception:
            pass


async def enumerate_latest(limit: int) -> tuple[list[dict], bool]:
    """抓主页首屏最新作品（不滚到底）。返回 (按发布时间倒序的 recs, 是否疑似登录墙)。"""
    items: dict[str, dict] = {}
    logged_out = False

    async def on_response(resp):
        if POST_API not in resp.url:
            return
        try:
            data = json.loads(await resp.text())
        except Exception:
            return
        for it in (data.get("aweme_list") or []):
            if it.get("aweme_id"):
                items[it["aweme_id"]] = it

    clear_stale_locks()
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(USERDATA), headless=False, locale="zh-CN", user_agent=UA,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"])
        await ctx.add_init_script(STEALTH)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        # 强时效：禁用缓存，否则共用 userdata 会命中旧的 post 接口响应，漏掉最新作品
        try:
            cdp = await ctx.new_cdp_session(page)
            await cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
        except Exception as e:
            log(f"   (CDP 禁缓存失败，忽略: {e})")
        page.on("response", lambda r: asyncio.create_task(on_response(r)))
        log(f"→ 打开 {CREATOR_NAME} 主页")
        await page.goto(CREATOR_URL, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(5000)
        # 首屏一般已含最新 ~18 条（CDP 已禁缓存→新鲜）；轻滚 3 次补全分页即停（不滚到底）
        last = -1
        for i in range(3):
            if len(items) >= limit:
                break
            await page.mouse.wheel(0, 4000)
            await page.wait_for_timeout(2200)
            log(f"   scroll {i}: 已枚举 {len(items)}")
            if len(items) == last:
                break
            last = len(items)
        # 首轮 0 条多为瞬时（XHR 未在等待窗内返回）→ reload 重试一次（不清空已抓到的）
        if not items:
            log("   首轮 0 作品，reload 重试…")
            await page.reload(wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(6000)
            for i in range(2):
                if items:
                    break
                await page.mouse.wheel(0, 4000)
                await page.wait_for_timeout(2500)
        try:
            body = await page.inner_text("body")
            logged_out = ("扫码登录" in body) or ("立即登录" in body) or \
                         ("登录" in body and "二维码" in body)
        except Exception:
            pass
        await ctx.close()

    recs = []
    for aid, it in items.items():
        v = it.get("video") or {}
        has_play = bool((v.get("play_addr") or {}).get("url_list"))
        ct = it.get("create_time")
        recs.append({
            "aweme_id": aid, "desc": it.get("desc", ""),
            "date": datetime.datetime.fromtimestamp(ct).strftime("%Y-%m-%d") if ct else None,
            "create_time": ct or 0, "duration_s": round((v.get("duration") or 0) / 1000, 1),
            "has_free_play": has_play, "is_paid": is_paid(it, has_play),
            "video_page": f"https://www.douyin.com/video/{aid}",
        })
    recs.sort(key=lambda r: r["create_time"], reverse=True)
    return recs[:limit], logged_out


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"creator": CREATOR_NAME, "seen": [], "last_run": None, "last_status": None}


def save_state(st: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    st["last_run"] = datetime.datetime.now().isoformat(timespec="seconds")
    STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2))


def run_capture(cmd: list[str], key: str, timeout: int) -> str | None:
    """跑子进程，从 stdout 抓 '<key>=<path>' 末行契约值。"""
    log(f"   $ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="仅建立基线，标记当前最新为已见，不下载")
    ap.add_argument("--check-only", action="store_true", help="只枚举+比对，不下载不改状态")
    ap.add_argument("--max", type=int, default=5, help="单次最多处理新作品数")
    ap.add_argument("--list", type=int, default=25, help="考察最新多少条")
    a = ap.parse_args()

    st = load_state()
    seen = set(st.get("seen", []))

    relogin_hint = ("抖音 web 登录态过期。重登（扫码）：/opt/homebrew/bin/python3 "
                    f"{REPO}/skills/douyin-distill/scripts/login.py '{CREATOR_URL}' "
                    f"--workdir {STATE_DIR}")

    try:
        recs, logged_out = asyncio.run(enumerate_latest(a.list))
    except Exception as e:
        st["last_status"] = f"enumerate_error: {e}"
        save_state(st)
        emit({"status": "error", "stage": "enumerate", "error": str(e), "creator": CREATOR_NAME})
        return

    # 登录失效判定：0 作品 / 登录墙文本 / 最新作品过旧（她日更）。三者任一即报需重登，
    # 避免撞墙返回滞后快照时被误判为“无更新”而静默漏报。
    newest_ts = recs[0]["create_time"] if recs else 0
    stale_days = (datetime.datetime.now().timestamp() - newest_ts) / 86400 if newest_ts else 999
    if not recs or logged_out or stale_days > STALE_DAYS:
        st["last_status"] = "login_required"
        save_state(st)
        emit({"status": "login_required", "creator": CREATOR_NAME,
              "reason": ("空作品列表" if not recs else "登录墙文本" if logged_out
                         else f"最新作品已 {stale_days:.0f} 天前（疑似过期）"),
              "newest_seen": recs[0]["date"] if recs else None,
              "hint": relogin_hint})
        return

    log(f"枚举到最新 {len(recs)} 条，已见 {len(seen)} 条")

    # 首次或显式 seed：建立基线，不下载
    if a.seed or not st.get("seen"):
        all_ids = [r["aweme_id"] for r in recs]
        st["seen"] = sorted(set(seen) | set(all_ids))
        st["last_status"] = "seeded"
        if not a.check_only:
            save_state(st)
        emit({"status": "seeded", "creator": CREATOR_NAME, "baseline_count": len(all_ids),
              "latest": [{"aweme_id": r["aweme_id"], "date": r["date"], "title": r["desc"][:60]} for r in recs[:5]]})
        return

    # 找新作品（免费真视频，倒序，截断 max）
    new = [r for r in recs if r["aweme_id"] not in seen
           and not r["is_paid"] and r["has_free_play"] and r["duration_s"] > 0]
    new = new[:a.max]

    if a.check_only:
        emit({"status": "check_only", "creator": CREATOR_NAME, "new_count": len(new),
              "new": [{"aweme_id": r["aweme_id"], "date": r["date"], "title": r["desc"][:60]} for r in new]})
        return

    if not new:
        st["last_status"] = "no_update"
        save_state(st)
        emit({"status": "no_update", "creator": CREATOR_NAME})
        return

    # 下载 + 转写每条新作品
    out, errors = [], []
    for r in new:
        aid = r["aweme_id"]
        log(f"▶ 处理新作品 {aid} [{r['date']}] {r['desc'][:40]}")
        media = run_capture([PY, FETCH, r["video_page"]], "MEDIA_PATH", timeout=240)
        if not media:
            errors.append({"aweme_id": aid, "stage": "download"})
            continue
        tr = run_capture([PY, ASR, media], "TRANSCRIPT_PATH", timeout=600)
        if not tr:
            errors.append({"aweme_id": aid, "stage": "transcribe", "media": media})
            continue
        # 转写成功 = 内容已安全落盘，标记已见
        seen.add(aid)
        st["seen"] = sorted(seen)
        save_state(st)
        out.append({"aweme_id": aid, "date": r["date"], "title": r["desc"],
                    "duration_s": r["duration_s"], "video_page": r["video_page"],
                    "media_path": media, "transcript_path": tr})

    st["last_status"] = f"processed {len(out)}, errors {len(errors)}"
    save_state(st)
    emit({"status": "ok", "creator": CREATOR_NAME, "new": out, "errors": errors})


if __name__ == "__main__":
    main()
