---
name: media-fetch
description: 本地媒体下载工具，按 URL 自动分流。Douyin 走 Playwright + headless Chromium 抓无水印 mp4；Apple Podcasts 走 iTunes Search API 抓 mp3/m4a 直链。落到 ~/Downloads/media-fetch/。Use when 用户提供抖音链接 / Apple Podcasts 链接说"下载"/"保存"/"准备转字"，或作为 asr skill 的前置步骤。
---

# media-fetch Skill

把媒体 URL 落成本地音视频 + 同名 `.info.json`，供后续 asr 或人工查阅复用。

## 文件结构

```
skills/media-fetch/
├── SKILL.md              # 本文件
├── scripts/fetch.py      # 下载逻辑（按 URL 分流）
└── README.md             # 一次性安装说明
```

## When to Use

- 用户提供 Douyin / Apple Podcasts URL 且需要本地副本（无论后续是否做 ASR）
- `asr` skill 被调用但用户只给了 URL 没给本地文件——先触发本 skill 拿到 `MEDIA_PATH`，再传给 asr

## 支持平台

| 平台 | URL 形态 | 解析路径 | 输出 |
|---|---|---|---|
| **Douyin** | `v.douyin.com/xxx` / `www.douyin.com/video/xxx` | Playwright 启动 headless Chromium，监听 `douyinvod.com` 域 mp4 网络响应 + DOM `<video>.src` 双路径 | `.mp4` 无水印视频 |
| **Apple Podcasts** | `podcasts.apple.com/{country}/podcast/{slug}/id{NUM}[?i={trackId}]` | iTunes Search API（`lookup?id={podcast_id}&entity=podcastEpisode`）拿 episode 元数据 + `episodeUrl` 直链 | `.mp3` 或 `.m4a`（保留原始扩展名）|

## 依赖（首次使用前一次性配置）

```bash
pip3 install --break-system-packages playwright
python3 -m playwright install chromium
```

> Apple Podcasts 路径**不需要 Playwright**——iTunes API 公开 + HTTP 直下，纯标准库。但 fetch.py 启动时仍会 import playwright 检查；如果只用 podcast 不用抖音，可以略过 chromium 下载。

> 历史：2026-05 之前 douyin 用 `douyin-tiktok-scraper`，因抖音 API 签名/msToken 失效而废弃；改用 Playwright 让抖音页面自然加载并签出 cookies，再监听网络请求拿无水印 mp4 URL。

## 执行

```bash
python3 skills/media-fetch/scripts/fetch.py "<URL>" [--target DIR]
```

参数：
- `<URL>`：Douyin 分享 URL 或 Apple Podcasts URL，自动按域名分流
- `--target`：输出目录，**默认 `~/Downloads/media-fetch/`**（不入 wiki）；想直接入 wiki 时传 `raw/media/_inbox/` 等仓库内路径

## stdout 契约

成功时**最后一行**输出：
```
MEDIA_PATH=/absolute/path/to/<file>
```

下游 skill（如 `asr`）通过 grep 这行拿到文件路径。所有进度提示走 stderr 不污染契约。

## 落库产物

每次调用写两个文件，文件名格式 `<YYYY-MM-DD>_<platform>_<id>.<ext>`：

| 平台 | 文件命名示例 | id 构成 |
|---|---|---|
| Douyin | `2026-05-14_douyin_7638154883836824883.mp4` | `aweme_id` |
| Apple Podcast | `2026-05-14_applepodcast_1500662719_1000766866358.m4a` | `{podcast_id}_{episode_track_id}` |

同名 `.info.json` 含：`platform / id / title / source_url / media_url / candidates / extra / fetched_at`。Apple Podcasts 的 `extra` 字段额外含 `podcast_name / release_date / feed_url / track_time_millis / description`（节目简介，对后续 wiki 摘要很有用）。

## 衔接 asr

如果用户的真实意图是"转文字"，本 skill 完成后**自动接 asr skill**：

```
用户：转文字 https://podcasts.apple.com/cn/podcast/xxx/idNNN?i=MMM
  ↓
触发 media-fetch → MEDIA_PATH=~/Downloads/media-fetch/2026-05-14_applepodcast_NNN_MMM.m4a
  ↓
触发 asr 传入该路径 → TRANSCRIPT_PATH=~/Downloads/asr-output/2026-05-14_applepodcast_NNN_MMM.md
```

## Error Handling

通用：

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `不支持的 URL` | 不是 Douyin / Apple Podcasts 域名 | 检查 URL；若是新平台，按本 skill 扩展模式新增 `fetch_<platform>()` |

Douyin 特有：

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `未捕获到视频网络请求` | 视频已删除 / 是图文/直播 / 抖音页面结构变更 | 浏览器手动打开 URL 确认可播；若可播仍失败，临时改 headed 模式（去掉 `headless=True`）人工查看 |
| `下载失败 403` | 防盗链 / mp4 URL 过期（CDN signed URL 通常分钟级有效） | 立即重试；超过几分钟需重新拉一次 |
| `ModuleNotFoundError: playwright` | playwright 未安装 | `pip3 install --break-system-packages playwright` |
| `Executable doesn't exist` | 装了 playwright 包但没装 chromium | `python3 -m playwright install chromium` |

Apple Podcasts 特有：

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `iTunes API 未返回任何 episode` | podcast_id 不存在 / 该地区下架 | 用 `country=us` 参数重试（脚本未暴露，需改代码）；或换 Apple Podcasts 其他地区入口 URL |
| `episode_id 不在最近 200 集内` | iTunes lookup hard cap 200 集，老节目可能漏 | 短期：用节目首页 URL（不带 `?i=`）拿最新一集；长期：fetch.py 加 RSS 回退路径（解析 feedUrl 的 XML） |
| `下载失败` | 媒体 CDN 临时不可达 / 节目下架 | 浏览器直接打开 `info.json` 里 `media_url` 验证；持续失败说明该集已下架 |

## 不做什么

- 不做 ASR / 转写（交给 `asr` skill）
- 不抓评论 / 点赞 / 互动数据
- Douyin 不下载图文 / 直播流（仅普通视频）
- Apple Podcasts 不批量下整档节目（单次只下一集；批量需用户脚本循环调用）
- 不维护持久化的 douyin cookie——每次都用全新 browser context 让抖音自己签发
