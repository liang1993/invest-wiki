# media-fetch — 一次性安装说明

## Python 依赖（仅 Douyin 路径需要）

```bash
# playwright 须装进 *运行脚本的那个* 解释器；bare python3 常是缺它的 Xcode 3.9.6
/opt/homebrew/bin/python3 -m pip install --break-system-packages playwright
/opt/homebrew/bin/python3 -m playwright install chromium
```

> playwright 装在 Homebrew Python `/opt/homebrew/bin/python3`(3.14)。`fetch.py` 命中 Douyin 时若当前解释器缺 playwright 会**自动重入**装了依赖的解释器（见 `skills/_shared/interp`），故 `python3 fetch.py ...` 开箱即用；自动找不到时设 `INVEST_WIKI_PY=/path/to/python3`。**Apple Podcasts 路径纯标准库**，任意解释器（含 Xcode python）可跑、不触发重入。
>
> 用 `--break-system-packages` 是因 Homebrew Python 的 PEP 668 保护——invest-wiki 其他 skill（akshare/yfinance/funasr）的既有约定。

第二行下载 Chromium 浏览器到 `~/Library/Caches/ms-playwright/`，约 150MB，仅首次需要。

## 验证

```bash
/opt/homebrew/bin/python3 -c "from playwright.async_api import async_playwright; print('OK')"
ls ~/Library/Caches/ms-playwright/ | grep chromium
```

## 已知问题

Douyin：
- **图文作品、直播回放不支持**：本 skill 只处理普通视频
- **抓到的 mp4 URL 是 CDN signed URL**：通常分钟级有效，要立刻下载；如发现 403 重新拉一次即可
- **首次 chromium 下载可能因网络慢失败**：重试 `python3 -m playwright install chromium`

Apple Podcasts：
- **iTunes lookup hard cap 200 集**：长寿命节目（如 Lex Fridman 497 集）只能拿到最近 200 集，老集需要 RSS 回退（未实现）
- **不批量下载整档**：每次调用只下一集；要全档需用户脚本循环
- **不支持 country 切换**：脚本默认走当前 URL 里的 country 段，且不依赖此参数；若节目在某地区下架，需换其他地区入口 URL

## 历史 / 选型

**Douyin**：2026-05 之前用 `douyin-tiktok-scraper`（基于反向工程 API 签名）。抖音持续升级反爬后，固定的 msToken / X-Bogus 签名失效，包作者也长期未更新。改用 Playwright 启动真实 Chromium：
- ✅ 抖音页面自然加载，cookies / 签名由浏览器自动签发
- ✅ 监听网络响应直接抓 mp4 URL，不依赖任何反向工程的 API 字段
- ✅ 反爬升级时 Chromium 跟着更新即可
- ⚠ 启动一次 Chromium 约 5-10 秒，比 API 慢但更稳

如未来 Playwright 路径也失效，备选：
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)（社区维护更勤的视频下载器，支持 cookies-from-browser）

**Apple Podcasts**（2026-05 新增）：评估过 yt-dlp 的 `ApplePodcasts` extractor，但当前报 "No video formats found" 已退化。直接用 iTunes Search API：
- ✅ `itunes.apple.com/lookup` 完全公开无 auth，标准 JSON 响应
- ✅ `episodeUrl` 字段就是节目方原始 mp3/m4a URL（不是 Apple 转码副本）
- ✅ 不需要 Playwright，纯 Python 标准库（urllib + json）
- ⚠ Hard cap 200 集，老节目需 RSS 回退（feedUrl 在响应里也有，未来扩展点）
