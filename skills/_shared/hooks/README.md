# 受版控的 hook 逻辑 + 本地接线说明

> **为什么逻辑在这里**：`.claude/` 整目录被 `.gitignore`（`.gitignore:3,5`），放那里的 hook
> 换机即丢、不可版控。故 hook **逻辑**放本受版控目录；**接线**（git config / settings.local.json）
> 是每个 clone 一次性的本地步骤，照下方复现即可。

## Hook 清单

| 文件 | 类型 | 触发 | 作用 | 当前模式 |
|---|---|---|---|---|
| `pre-commit` | git hook | `git commit` | 敏感信息（key/手机/邮箱/身份证/卡号/私钥/密码）+ wiki 引用 private/ → 阻止提交 | **block**（exit 1） |
| `lint-interval-terms.py` | PostToolUse | Write/Edit 个股 wiki | 非白名单区间档位（加仓/高估/低估区间）告警 | **warn-only**（exit 1） |
| `lint-frontmatter.py` | PostToolUse | Write/Edit wiki 页 | frontmatter 缺 tags/updated 告警 | **warn-only**（exit 1） |

退出码语义（Claude Code hook）：`0`=通过；`2`=阻断（stderr 回喂 Claude）；其它非 0=非阻断、stderr 提示用户、继续。
warn-only 用 `exit 1`；grace 期确认零误报后，把对应脚本的 `sys.exit(1)` 改 `sys.exit(2)` 即升为阻断。

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
