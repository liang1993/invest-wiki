# media-fetch — 一次性安装说明

## Python 依赖

```bash
pip3 install --break-system-packages playwright
python3 -m playwright install chromium
```

> 用户机器为 Homebrew Python（PEP 668 保护），所以需要 `--break-system-packages`。这是 invest-wiki 仓库其他 skill（akshare/yfinance/funasr）的既有约定。

第二行下载 Chromium 浏览器到 `~/Library/Caches/ms-playwright/`，约 150MB，仅首次需要。

## 验证

```bash
python3 -c "from playwright.async_api import async_playwright; print('OK')"
ls ~/Library/Caches/ms-playwright/ | grep chromium
```

## 已知问题

- **图文作品、直播回放不支持**：本 skill 只处理普通视频
- **抓到的 mp4 URL 是 CDN signed URL**：通常分钟级有效，要立刻下载；如发现 403 重新拉一次即可
- **首次 chromium 下载可能因网络慢失败**：重试 `python3 -m playwright install chromium`

## 历史 / 选型

2026-05 之前用 `douyin-tiktok-scraper`（基于反向工程 API 签名）。抖音持续升级反爬后，固定的 msToken / X-Bogus 签名失效，包作者也长期未更新。改用 Playwright 启动真实 Chromium：
- ✅ 抖音页面自然加载，cookies / 签名由浏览器自动签发
- ✅ 监听网络响应直接抓 mp4 URL，不依赖任何反向工程的 API 字段
- ✅ 反爬升级时 Chromium 跟着更新即可（`python3 -m playwright install chromium`）
- ⚠ 启动一次 Chromium 约 5-10 秒，比 API 慢但更稳

如未来 Playwright 路径也失效，备选：
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)（社区维护更勤的视频下载器，支持 cookies-from-browser）
- 飞书妙记同事手动下载后用 `asr` skill 直接转写本地文件
