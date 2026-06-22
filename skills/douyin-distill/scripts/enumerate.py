#!/usr/bin/env python3
"""枚举抖音博主全部作品 + 识别会员/付费(VIP) + 可选关注股扫描。

旁路监听主页发出的 /aweme/v1/web/aweme/post/ 响应（不破签名，让页面自己签名），
滚动到底分页枚举。**必须先 login.py 登录**（未登录主页返回空）。

用法：
    python3.14 enumerate.py <user_home_url> [--workdir DIR] [--focus 茅台,腾讯,...]

产出：
    workdir/enum.json   全部作品 {aweme_id,desc,date,duration_s,is_paid,has_free_play,video_page}
    workdir/free.json / paid.json   分类清单
    stdout 摘要：总数/日期范围/免费vs付费/系列分布/(focus 命中)
"""
from __future__ import annotations
import argparse, asyncio, json, re, sys, datetime, collections
from pathlib import Path
from playwright.async_api import async_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
POST_API = "/aweme/v1/web/aweme/post/"
STEALTH = (
    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    "Object.defineProperty(navigator,'languages',{get:()=>['zh-CN','zh']});"
    "window.chrome={runtime:{}};"
)


def is_paid(item: dict, has_free_play: bool) -> bool:
    """付费判定：charge_info.is_charge_content / 付费合集 / 无免费播放地址。"""
    ci = item.get("charge_info") or {}
    if ci.get("is_charge_content"):
        return True
    mix = item.get("mix_info") or {}
    if (mix.get("charge_info") or {}) or mix.get("paid_episodes"):
        # 仅当该合集确有付费集时才算（粗判，配合 has_free_play）
        if not has_free_play:
            return True
    return not has_free_play


async def enumerate_works(url: str, workdir: Path) -> list[dict]:
    userdata = workdir / "userdata"
    items: dict[str, dict] = {}

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

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(userdata), headless=False, locale="zh-CN", user_agent=UA,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"])
        await ctx.add_init_script(STEALTH)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        page.on("response", lambda r: asyncio.create_task(on_response(r)))
        print(f"→ 打开 {url}", file=sys.stderr)
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(5000)
        last, stable = -1, 0
        for i in range(80):
            await page.mouse.wheel(0, 5000)
            await page.wait_for_timeout(2200)
            n = len(items)
            if n == last:
                stable += 1
                if stable >= 6:
                    break
            else:
                last, stable = n, 0
            if i % 5 == 0:
                print(f"   scroll {i}: 已枚举 {n}", file=sys.stderr)
        header = None
        try:
            m = re.search(r"作品\s*(\d+)", await page.inner_text("body"))
            header = int(m.group(1)) if m else None
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
            "create_time": ct, "duration_s": round((v.get("duration") or 0) / 1000, 1),
            "has_free_play": has_play, "is_paid": is_paid(it, has_play),
            "video_page": f"https://www.douyin.com/video/{aid}",
        })
    recs.sort(key=lambda r: r["create_time"] or 0, reverse=True)
    print(f"\nheader「作品」={header}  实际枚举={len(recs)}", file=sys.stderr)
    return recs


def series_of(desc: str) -> str:
    m = re.match(r"\s*([一-鿿]{2,10}日记|[一-鿿]{2,8}好公司|[一-鿿]{2,8}之路|[一-鿿]{2,10}备忘录)", desc)
    return m.group(1) if m else "(散篇/其它)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--workdir", default=str(Path.home() / "liang/douyin-distill/_inbox"))
    ap.add_argument("--focus", default="", help="逗号分隔的关注词，扫描标题命中（如 茅台,腾讯,平安）")
    a = ap.parse_args()
    wd = Path(a.workdir); wd.mkdir(parents=True, exist_ok=True)
    recs = asyncio.run(enumerate_works(a.url, wd))
    if not recs:
        print("⚠️ 0 作品——多半未登录（先跑 login.py）或被风控；headless 也会被风控，本脚本已用有头。", file=sys.stderr)
        sys.exit(2)
    free = [r for r in recs if not r["is_paid"]]
    paid = [r for r in recs if r["is_paid"]]
    real_free = [r for r in free if r["duration_s"] > 0]
    (wd / "enum.json").write_text(json.dumps(recs, ensure_ascii=False, indent=2), encoding="utf-8")
    (wd / "free.json").write_text(json.dumps(free, ensure_ascii=False, indent=2), encoding="utf-8")
    (wd / "paid.json").write_text(json.dumps(paid, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== 摘要 ===")
    dates = sorted(r["date"] for r in recs if r["date"])
    print(f"总数 {len(recs)}  日期 {dates[0]}~{dates[-1]}  免费 {len(free)}(真视频{len(real_free)}) / 付费 {len(paid)}")
    ser = collections.Counter(series_of(r["desc"]) for r in recs)
    print("系列分布:", dict(ser.most_common(8)))
    print(f"\n免费真视频最近 20 条（蒸馏选样候选）：")
    for r in [x for x in real_free][:20]:
        print(f"  {r['aweme_id']} [{r['date']}] {r['duration_s']:.0f}s | {r['desc'][:48]}")
    if a.focus:
        words = [w.strip() for w in a.focus.split(",") if w.strip()]
        print(f"\n=== focus 命中（{','.join(words)}）===")
        for r in recs:
            hit = [w for w in words if w in r["desc"]]
            if hit:
                tag = "付费🔒" if r["is_paid"] else "免费✅"
                print(f"  [{r['date']}] {tag} {'/'.join(hit)} | {r['desc'][:46]}")
    print(f"\n→ 写出 enum.json / free.json / paid.json 到 {wd}")


if __name__ == "__main__":
    main()
