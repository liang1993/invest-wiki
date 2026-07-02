# 受版控的 hook 逻辑 + 本地接线说明

> **为什么逻辑在这里**：`.claude/` 整目录被 `.gitignore`（`.gitignore:3,5`），放那里的 hook
> 换机即丢、不可版控。故 hook **逻辑**放本受版控目录；**接线**（git config / settings.local.json）
> 是每个 clone 一次性的本地步骤，照下方复现即可。

## Hook 清单

| 文件 | 类型 | 触发 | 作用 | 当前模式 |
|---|---|---|---|---|
| `pre-commit` | git hook | `git commit` | 敏感信息（key/手机/邮箱/身份证/卡号/私钥/密码）→ 阻止提交；**段 C 另对 staged wiki 跑两 lint 的 argv 模式兜底** | **block**（A）+ **warn**（C） |
| `lint-interval-terms.py` | PostToolUse **+ pre-commit(argv)** | Write/Edit 个股 wiki · commit 时 | 非白名单区间档位（加仓/高估/低估区间）告警 | **warn-only**（exit 1） |
| `lint-frontmatter.py` | PostToolUse **+ pre-commit(argv)** | Write/Edit wiki 页 · commit 时 | frontmatter 缺 tags/updated 告警 | **warn-only**（exit 1） |

退出码语义（Claude Code hook）：`0`=通过；`2`=阻断（stderr 回喂 Claude）；其它非 0=非阻断、stderr 提示用户、继续。
warn-only 用 `exit 1`；grace 期确认零误报后，把对应脚本的 `sys.exit(1)` 改 `sys.exit(2)` 即升为阻断。

> **lint 双栈（Phase 4，多 harness）**：两个 lint 既是 Claude Code 的 PostToolUse hook（stdin JSON 入参），
> 也被 `pre-commit` 段 C 以 argv 模式（`lint-x.py <file>…`）调用——非 Claude Code harness 无 PostToolUse，
> 靠 commit 时这道兜底守同一地板。两入口共用一份 `lint_file()` 逻辑，均 warn-only（`|| true` 不阻断提交）。
> **pre-commit 因此成为混用下唯一对所有 agent 生效的机械纪律点**（前提：堵住 `--no-verify` 旁路，见下）。

## 本地接线（每个 clone 跑一次）

### 1. git pre-commit（隐私闸门）
```bash
git config core.hooksPath skills/_shared/hooks
```
`core.hooksPath` 让 git 在本受版控目录找 `pre-commit`（git 2.9+）。验证：
```bash
printf 'token = "supersecrettoken12345"\n' > _t.txt && git add _t.txt
git commit -m test   # 应被拦
git reset -q _t.txt && rm _t.txt
```

### 2. PostToolUse lint（区间术语 + frontmatter）
在 `.claude/settings.local.json` 加（与既有 `permissions` 同级）：
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/skills/_shared/hooks/lint-interval-terms.py\""},
          {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/skills/_shared/hooks/lint-frontmatter.py\""}
        ]
      }
    ]
  }
}
```
注：全局 `~/.claude/settings.json` 已有同 matcher 的遥测 hook，项目级与之**叠加执行**，不冲突。

## 设计边界

- **Hook 守确定性地板**：可机械判定的纪律（隐私模式串、术语白名单、字段存在性）。
- **判断型不进 hook**：`[观测]` 是否与原文一致、计算链反推、口径混用——这些靠 CLAUDE.md L1/L2/L3 + `value-invest-verify`（Eval）。
- 检测器脚本天然含检测模式（如 `pre-commit` 里的 `PRIVATE KEY`），故 `pre-commit` 的通用扫描用 git pathspec 排除 `skills/_shared/hooks/` 自身，避免自指假阳。
- **URL 内数字已豁免**：研报/财报链接常含 18 位文档号（如 `pdf.dfcfw.com/pdf/H301_AP202209301578810023_1.pdf`），会被身份证（规则 4）/银行卡（规则 5）的「连续 N 位数字」启发式误判。故规则 4/5 检测前先用 `sed -E 's#https?://[^[:space:]]+##g'` 把 `http(s)://…` 至空白的整段 URL token 从待检文本剔除；URL 外的真实 PII（前后为中文/空格/标点，不在 URL token 内）不受影响。仅规则 4/5 用剔除后的文本，其余规则仍扫原文。
- **残留启发式误报**：身份证/银行卡检测本质仍是「连续 17–19 位数字」启发式（继承自原脚本）。**非 URL** 的超长裸数字串（罕见）仍会被拦——这是保守的安全侧。命中且确为误报时，**agent 须停下、把拦截输出原样转给用户，由用户人工决定是否 `git commit --no-verify`；agent 一律禁止自行使用**（pre-commit stderr 会回喂模型，等于把逃生门钥匙递给被拦的 agent，隐私真阳场景不可接受，见 AGENTS.md 混用协议 7）；未来可进一步收紧为「卡号常见前缀 + Luhn 校验」。
