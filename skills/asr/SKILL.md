---
name: asr
description: 本地中文 ASR 工具。接收本地 audio/video 文件路径，使用 SenseVoice-Small（funasr 包）输出中文逐字稿 markdown 到 ~/Downloads/asr-output/。Use when 用户已经有本地媒体文件并要转文字，或被 media-fetch 串联触发。支持普通话/粤语/英日韩。
---

# asr Skill

把任意本地 audio/video 文件转成中文逐字稿 markdown。

## 文件结构

```
skills/asr/
├── SKILL.md                  # 本文件
├── scripts/transcribe.py     # 主流程：ffmpeg 抽音 + SenseVoice 转写 + markdown 渲染
└── README.md                 # 一次性安装说明
```

## When to Use

- 用户提供本地媒体路径（mp3 / mp4 / wav / m4a / mov / ...）说"转文字"/"逐字稿"/"提取文案"
- `media-fetch` 完成后自动衔接（拿到 `MEDIA_PATH=...` 后调本 skill）
- 任何已有本地媒体（B 站下载、播客 mp3、Zoom 录像、电话录音）想转字的场景

## 依赖（首次使用前一次性配置）

```bash
brew install ffmpeg                                                  # 抽音必需
pip3 install --break-system-packages funasr torch torchaudio pyyaml  # ASR runtime + 渲染
```

首次运行脚本会自动从 ModelScope 下载 SenseVoiceSmall（~893MB）到 `~/.cache/modelscope/`，后续完全离线。

## 执行

```bash
python3 skills/asr/scripts/transcribe.py <FILE> [--target DIR] [--language zh|auto|en|yue|ja|ko]
```

参数：
- `<FILE>`：本地 audio/video 路径，ffmpeg 能解的格式都行（mp3/mp4/wav/m4a/mov/...）
- `--target`：输出目录，**默认 `~/Downloads/asr-output/`**（不入 wiki）；想直接入 wiki 时传 `raw/articles/_inbox/` 等仓库内路径
- `--language`：语言代码（默认 `zh`；粤语用 `yue`；混合内容用 `auto`）

## stdout 契约

成功时**最后一行**输出：
```
TRANSCRIPT_PATH=/absolute/path/to/2026-05-12_<basename>.md
```

进度提示走 stderr 不污染契约。

## 输出 markdown 格式

遵循 invest-wiki `raw/articles/` frontmatter 规范（详见 CLAUDE.md 的「WebSearch 归档」段）：

```markdown
---
source: file:///absolute/path/to/source.mp4
fetched: 2026-05-12
title: 视频文件名（不含扩展名）
publisher: (本地媒体)
published: null
stocks: []
topics: []
verified: unverified            # ASR 产物本质是机器转写，不等同 verified 原文
asr_engine: funasr / SenseVoiceSmall
conflicts: []
---

# <title>

## 逐字稿

<整段连贯文本，含标点和数字规整>
```

**关键标签**：`verified: unverified` 必须保留——ASR 是机器转写，不能等同 verified 原文。后续 ingest 流程消化时人工校对再标 `partial` 或 `true`。

## 模型与精度

- **模型**：SenseVoice-Small（阿里达摩院开源，893MB）
- **中文 CER**：比 Whisper-Large 低 30-50%（论文+第三方实测）
- **速度**：M4 Pro CPU 上 3 分钟视频约 5-10 秒，30 分钟播客约 50-100 秒
- **语言**：中文 / 粤语 / 英文 / 日文 / 韩文
- **不支持**：speaker diarization（不区分说话人）、时间戳（本期未启用，全文输出）


## 衔接 media-fetch

如果用户给的是 URL 而非本地文件，先触发 `media-fetch` 拿到 `MEDIA_PATH`，再调本 skill：

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
| `ModuleNotFoundError: funasr` | 未安装 | `pip3 install --break-system-packages funasr` |
| `ffmpeg: command not found` | 未安装 | `brew install ffmpeg` |
| 模型下载卡住 | ModelScope 拥堵 / 网络问题 | 等待重试；持续失败时手动从 [ModelScope iic/SenseVoiceSmall](https://www.modelscope.cn/models/iic/SenseVoiceSmall) 下载 `model.pt` 到 `~/.cache/modelscope/hub/models/iic/SenseVoiceSmall/`（脚本会自动识别该本地路径并跳过下载） |
| 输出大量乱码 / 重复 | 视频音频质量太差 / 强 BGM | 用 ffmpeg 预处理增强音频；或接受小段失真 |
| 内存爆涨 / OOM | 极长音频（> 1h）+ VAD 未生效 | 检查 `transcribe.py` 中 `vad_model="fsmn-vad"` 是否启用；必要时手动 chunk 切片再分别转写 |

## 不做什么

- ❌ **不做 LLM 二次结构化**：用户要的是逐字稿原料，摘要/观点提取交给 `value-invest` / `stock-deep-dive` 等下游 skill
- ❌ **不做 speaker diarization**：SenseVoice 单流输出，不区分谁说的
- ❌ **不做实时流式 ASR**：本 skill 是离线批处理
- ❌ **不做热词增强 / 财经术语词典**：依赖模型本身的训练数据，必要时由用户后续人工修正
- ❌ **不感知 URL 或网络**：纯本地，输入必须是本地文件路径
