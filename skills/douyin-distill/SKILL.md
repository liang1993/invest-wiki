---
name: douyin-distill
description: 把一个抖音博主蒸馏成可复用的"人设 skill"——给定博主主页 URL，自动跑通【扫码登录→旁路枚举全部作品→识别会员/付费视频→选样下载→批量转写→读稿蒸馏成 skill→独立校验】整条流水线，产出 skills/<persona>/（SKILL.md + references 三件套）。Use when 用户给一个抖音用户主页链接（www.douyin.com/user/...）说"把这个博主蒸馏成 skill / 提取他的人设 / 根据主页链接做成 skill / 学一下这个博主的风格 / 把这个号做成解读层"，或想批量提取某博主作品文字稿再提炼方法论与声纹。这是**生成器/工程流程层**：产出的人设 skill（如 macro-ellie / stock-kuaidao / invest-tusi）才是解读层。下载单条视频走 media-fetch，转写走 asr，本 skill 负责"主页级枚举 + 选样 + 蒸馏 + 校验"的编排。
---

# douyin-distill — 抖音博主 → 人设 skill 蒸馏流水线

给一个抖音主页 URL，产出一个"像他一样分析"的人设 skill。已用此法产出 `macro-ellie`（艾丽·无废话财经）、`stock-kuaidao`（快刀斩股）、`invest-tusi`（土斯土耶夫斯基）。

## 定位

- **是**：一条把"公开抖音博主"转成"可调用解读层 skill"的工程流水线 + 一套"怎么蒸馏才忠实"的方法论。
- **不是**：取数/估值工具，也不是解读层本身。下载单条视频 → [`media-fetch`](../media-fetch/SKILL.md)；转写 → [`asr`](../asr/SKILL.md)；产出的人设 skill 才负责"用他的视角分析"。

## 依赖（首次一次性）

```bash
pip3 install --break-system-packages playwright funasr torch torchaudio pyyaml
python3.14 -m playwright install chromium        # 有头浏览器（登录+枚举需要）
brew install ffmpeg
```
> 运行用 **python3.14**（playwright + funasr 装在此环境；系统 python3=3.9 没有）。脚本默认工作区 `~/liang/douyin-distill/<slug>/`（与 repo 同级、**不入任何 git**，不要放 ~/Downloads），**语料（媒体/逐字稿/登录态）一律不入 repo**，只有蒸馏产出的 skill 进 git。

## 流水线（7 步）

设 `URL=博主主页`，`WD=~/liang/douyin-distill/<slug>`（slug 自取，如 tusi）。

### 1. 扫码登录（人工一步）
抖音主页对未登录态返回空 body——**必须登录**。脚本开有头浏览器，用户用抖音 App 扫码：
```bash
python3.14 skills/douyin-distill/scripts/login.py "$URL" --workdir "$WD"
```
会话持久化到 `$WD/userdata`，后续步骤复用。⚠️ 登录态属隐私，蒸馏完清理（见末节）。

### 2. 枚举全部作品 + 识别 VIP（+可选关注股扫描）
```bash
python3.14 skills/douyin-distill/scripts/enumerate.py "$URL" --workdir "$WD" [--focus 茅台,腾讯,平安]
```
旁路监听 `/aweme/v1/web/aweme/post/`（不破签名），滚动分页枚举。产出 `enum.json`/`free.json`/`paid.json` + 摘要（总数/日期/免费vs付费/系列分布）。**VIP 判定**：`charge_info.is_charge_content` 或付费合集或无免费播放地址。

### 3. 判断会员视频能否获取
看 `enum.json` 里付费项的 `charge_info.has_paid`：登录账号**已购/已开会员**才是 true → 可下全片；否则只有 3–10min 预览。**拿不到全片就跳过会员视频**（大多数情况）。

### 4. 选样（LLM 判断）
从 `free.json` 真视频（duration>0）里挑 **~12–18 条均衡样本**：覆盖他的各招牌系列 + 方法论篇 + 代表性个案，**别全选**（蒸馏要的是声纹+方法论，不是全集）。把选中 aweme_id 写入 `$WD/selection.txt`（每行一个）。

### 5. 下载 + 转写
```bash
python3.14 skills/douyin-distill/scripts/download.py   --workdir "$WD" --ids-file "$WD/selection.txt"
python3.14 skills/douyin-distill/scripts/transcribe.py --workdir "$WD"     # 模型只加载一次
```
两步都可后台跑、断点续传。产出 `$WD/transcripts/*.md`（~每篇数千字）。

### 6. 内容过滤 + 蒸馏（LLM 核心工作）
- **过滤**：确认每篇都是本人内容（feed 推荐偶混广告/他人视频，扫营销词 + 主题词自检）。
- **蒸馏**：主 agent **通读全部逐字稿**，提炼 → 写 `skills/<persona>/`（SKILL.md + 三个 reference）。**产出结构、声纹 grep 方法、范式模板见 [`references/蒸馏方法论.md`](references/蒸馏方法论.md)——必读。**
- 接线：`ln -sf ../../skills/<persona> .claude/skills/` + `python3 scripts/gen_skill_index.py` 刷新索引。

### 7. 独立校验（强制，防虚构）
蒸馏靠 LLM 读稿，**易脑补/夸大频次/错配他博主特征**。spawn 一个零上下文 subagent（`general-purpose`，`model=sonnet`）通读逐字稿核对保真度，揪 ✗虚构/⚠️弱支撑 → 修正。**Prompt 模板见 [`references/蒸馏方法论.md`](references/蒸馏方法论.md#校验-subagent-prompt-模板)。**

## 踩坑（都踩过）

| 坑 | 真相 / 对策 |
|---|---|
| 主页 WebFetch/headless 抓不到 | 抖音主页前端渲染 + 未登录返回空 → **必须扫码登录 + 有头浏览器**（headless 也被风控返回 len=0） |
| `status 200 len 0` | 风控空响应（签名没错才会空，否则是 error json）→ 登录态 + 有头 + stealth init |
| 登录墙封历史 | 旧期常被作者下架，登录也找不回——只能蒸馏当前公开作品 |
| 会员视频 has_paid=0 | 账号没买就只有预览，**蒸馏跳过会员视频** |
| feed 推荐混入广告 | 枚举/下载后逐条确认是本人内容（曾混入财税软件广告 817KB） |
| 全集太大 | 19min×全集没必要，选 12–18 条均衡样本即可 |
| 逐字稿 ASR 错别字 | 人名/术语机器转写会错（霍华德·马克思→花华的马克思），蒸馏时用正确写法并在声纹 ref 记备忘 |

## 增量监控：watch.py（博主更新 → 每日摘要）

蒸馏是"一次性把博主提炼成 skill"；**watch.py 是"持续盯一个已蒸馏博主有没有新作品"**——给定主页，检测新作品则下载+转写，输出结果 JSON，供上层（Claude 定时任务）读稿→摘要→发飞书。机械层不做摘要/不发通知。

```bash
/opt/homebrew/bin/python3 skills/douyin-distill/scripts/watch.py              # 正常：枚举→比对→下载转写新作品→输出 JSON
/opt/homebrew/bin/python3 skills/douyin-distill/scripts/watch.py --seed       # 建基线（标记当前最新为已见，不下载）
/opt/homebrew/bin/python3 skills/douyin-distill/scripts/watch.py --check-only # 只枚举+比对，不下载不改状态
```

输出 `RESULT_JSON=<json>`，`status` ∈ `ok`(有新作品，含 transcript_path) / `no_update` / `login_required` / `seeded` / `error`。

**与蒸馏流程的区别**（避免混淆）：
- 独立 **轻量枚举**：只抓首屏最新 ~25 条做"有没有新的"判断（不滚到底全量），约 15-20s 关窗；CDP 禁缓存保证时效。
- 独立 **登录态** `~/.douyin-watch/userdata`（与蒸馏 `$WD/userdata` 隔离，互不干扰），状态 `~/.douyin-watch/<creator>_seen.json`，**均不入 repo**。
- **登录失效判定**比蒸馏更严：0 作品 / 登录墙文本 / 最新作品超 `STALE_DAYS`(默认5) 天 任一即报 `login_required`——因为撞登录墙时抖音返回**滞后的公开快照**（非空），只判"0 条"会漏报。

**定时任务接线**（Claude app 本地定时，非 launchd——launchd 里 `claude -p` 因 OAuth token 被主程序轮换而认证不了）：用 `scheduled-tasks` MCP 建每日任务，prompt 让 Claude 跑 watch.py → 读 `transcript_path` → 写结构化中文摘要 → `lark-cli im +messages-send --as bot --user-id <open_id> --markdown` 发飞书。已部署：`艾丽的无废话财经` 每早 8:55（任务 `watch-ellie-douyin`）。

**登录过期处理**：任务检测到 `login_required` 会把重登命令发飞书；手动扫码一次即可：
```bash
/opt/homebrew/bin/python3 skills/douyin-distill/scripts/login.py "<主页URL>" --workdir ~/.douyin-watch
```

## 边界与隐私

- **语料不入 repo**：`$WD`（媒体/逐字稿/userdata）留本地 `~/liang/douyin-distill/`（与 repo 同级、非 git），只 commit `skills/<persona>/`。监控的 `~/.douyin-watch/`（登录态+已见状态）同理不入 repo。
- **登录态清理**：蒸馏完 `rm -rf "$WD/userdata"`（含用户抖音会话）；不需要的媒体也可删。
- **忠实优先**：声纹频次必须 grep 实测、框架/信条/案例必须有逐字稿原文支撑；第 7 步校验不可省。
- 产出的人设 skill 是**解读/风格层**，须在其 SKILL.md 里写清"数字仍走取数 skill 核实、不预测点位、不荐股"。

## references/

- [`references/蒸馏方法论.md`](references/蒸馏方法论.md) — 人设 skill 产出结构（SKILL.md + 三 reference 模板）、声纹 grep 蒸馏法、四范式抽象、校验 subagent prompt 模板
