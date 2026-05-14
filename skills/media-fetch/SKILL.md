---
name: media-fetch
description: 抖音视频本地下载工具。接收抖音分享 URL，通过 Playwright 启动 headless Chromium 抓取无水印 mp4 + metadata 到 ~/Downloads/media-fetch/。Use when 用户提供抖音链接说"下载这条"/"保存视频"/"准备转字"，或作为 asr skill 的前置步骤。
---

# media-fetch Skill

把抖音分享 URL 落成本地 mp4 + 同名 `.info.json`，供后续 asr 或人工查阅复用。

## 文件结构

```
skills/media-fetch/
├── SKILL.md              # 本文件
├── scripts/fetch.py      # 下载逻辑
└── README.md             # 一次性安装说明
```

## When to Use

- 用户提供抖音分享 URL 且需要本地副本（无论后续是否做 ASR）
- `asr` skill 被调用但用户只给了 URL 没给本地文件——先触发本 skill 拿到 `MEDIA_PATH`，再传给 asr

## 依赖（首次使用前一次性配置）

```bash
pip3 install --break-system-packages playwright
python3 -m playwright install chromium
```

脚本启动时会检查依赖，缺失会给出明确的 pip 命令提示。

> 历史：2026-05 之前用 `douyin-tiktok-scraper`，因抖音 API 签名/msToken 失效而废弃；改用 Playwright 启动真实 Chromium，让抖音页面自然加载并签出 cookies，再监听网络请求拿无水印 mp4 URL。这个路径对反爬升级有较强韧性。

## 执行

```bash
python3 skills/media-fetch/scripts/fetch.py "<抖音分享 URL>" [--target DIR]
```

参数：
- `<URL>`：抖音分享链接，形如 `https://v.douyin.com/abcdef/` 或完整页面 URL
- `--target`：输出目录，**默认 `~/Downloads/media-fetch/`**（不入 wiki）；想直接入 wiki 时传 `raw/media/_inbox/` 等仓库内路径

## stdout 契约

成功时**最后一行**输出：
```
MEDIA_PATH=/absolute/path/to/2026-05-12_douyin_<aweme_id>.mp4
```

下游 skill（如 `asr`）通过 grep 这行拿到文件路径。所有进度提示走 stderr 不污染契约。

## 落库产物

每次调用写两个文件：
- `<YYYY-MM-DD>_douyin_<aweme_id>.mp4`：无水印视频
- `<YYYY-MM-DD>_douyin_<aweme_id>.info.json`：完整 metadata（aweme_id、desc、author、source_url、nwm_url、原始 raw dict）

## 衔接 asr

如果用户的真实意图是"转文字"，本 skill 完成后**自动接 asr skill**：

```
用户：转文字 https://v.douyin.com/xxx/
  ↓
触发 media-fetch → MEDIA_PATH=~/Downloads/media-fetch/2026-05-12_douyin_yyy.mp4
  ↓
触发 asr 传入该路径 → TRANSCRIPT_PATH=~/Downloads/asr-output/2026-05-12_douyin_yyy.md
```

## Error Handling

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `未捕获到视频网络请求` | URL 不合法 / 视频已删除 / 是图文/直播 / 抖音页面结构变更 | 浏览器手动打开 URL 确认可播；若可播仍失败，临时改 headed 模式（去掉 `headless=True`）人工查看 |
| `下载失败 403` | 防盗链 / mp4 URL 过期（CDN signed URL 通常分钟级有效） | 立即重试；超过几分钟需重新拉一次 |
| `ModuleNotFoundError: playwright` | playwright 未安装 | 按上方"依赖"段一次性安装 |
| `Executable doesn't exist` | 装了 playwright 包但没装 chromium | `python3 -m playwright install chromium` |

## 不做什么

- 不做 ASR / 转写（交给 `asr` skill）
- 不抓评论 / 点赞 / 互动数据
- 不下载图文 / 直播流（仅普通视频）
- 不维护持久化的 douyin cookie——每次都用全新 browser context 让抖音自己签发
