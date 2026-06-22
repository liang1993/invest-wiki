#!/usr/bin/env python3
"""抖音扫码登录 → 持久化会话到 workdir/userdata，供 enumerate/download 复用。

抖音主页（作品列表）对未登录态返回空 body（status 200 len 0）——必须登录。
打开有头浏览器停在主页，等用户用【抖音 App】扫码；检测到 sessionid cookie 即成功。

用法：
    python3.14 login.py <user_home_url> [--workdir DIR]

依赖：playwright（python3.14 -m playwright install chromium）
注意：userdata 内含登录会话，属隐私，蒸馏完应清理（见 SKILL.md）。
"""
from __future__ import annotations
import argparse, asyncio, sys
from pathlib import Path
from playwright.async_api import async_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
LOGIN_COOKIES = {"sessionid", "sessionid_ss", "sid_guard", "uid_tt"}
STEALTH = (
    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    "Object.defineProperty(navigator,'languages',{get:()=>['zh-CN','zh']});"
    "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});"
    "window.chrome={runtime:{}};"
)


async def main(url: str, workdir: Path):
    userdata = workdir / "userdata"
    userdata.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(userdata), headless=False, locale="zh-CN", user_agent=UA,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"])
        await ctx.add_init_script(STEALTH)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        if {c["name"] for c in await ctx.cookies()} & LOGIN_COOKIES:
            print("✓ 已是登录态（userdata 已有会话），无需扫码", file=sys.stderr)
            await ctx.close(); print("LOGIN=already"); return
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        print("→ 浏览器已打开，请用【抖音 App】扫码登录（最多 180s）…", file=sys.stderr)
        ok = False
        for i in range(60):
            await page.wait_for_timeout(3000)
            if {c["name"] for c in await ctx.cookies()} & LOGIN_COOKIES:
                ok = True; break
            if i % 5 == 0:
                print(f"   等待扫码… {i*3}s", file=sys.stderr)
        await page.wait_for_timeout(2000)
        await ctx.close()
        print("✓ 登录成功，会话已持久化" if ok else "✗ 超时未检测到登录", file=sys.stderr)
        print("LOGIN=ok" if ok else "LOGIN=timeout")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="抖音用户主页 URL (www.douyin.com/user/...)")
    ap.add_argument("--workdir", default=str(Path.home() / "liang/douyin-distill/_inbox"))
    a = ap.parse_args()
    asyncio.run(main(a.url, Path(a.workdir)))
