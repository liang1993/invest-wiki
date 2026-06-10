#!/usr/bin/env python3
"""PostToolUse hook：个股 wiki 区间术语白名单校验（warn-only）

把 value-invest「区间术语规范」从写前自检（最易在叙事流中跳过）变成写后
确定性校验。只管个股 wiki（wiki/stocks/<sector>/<name>.md）。

退出码语义（Claude Code）：
  0 = 通过；1 = 非阻断警告（stderr 提示用户、继续执行）；2 = 阻断。
本 hook 现为 **warn-only（exit 1）**——grace 期只报不拦；确认零误报后改 exit 2。

双入口：无 argv → 读 stdin JSON（PostToolUse，Claude Code）；有 argv → 把每个 argv
当 wiki 文件路径校验（pre-commit 调用，commit 时兜底，见 pre-commit 段 C）。两入口
共用同一份 lint 逻辑，warn-only 语义一致（exit 1 = 有告警）。

注册（settings.local.json PostToolUse, matcher Write|Edit|MultiEdit）：
  python3 "$CLAUDE_PROJECT_DIR/skills/_shared/hooks/lint-interval-terms.py"
"""

import json
import os
import re
import sys

# 个股 wiki 中的非白名单档位（value-invest SKILL.md 区间术语规范）
# 注：`深度买入区间` 暂不纳入——泡泡玛特.md 等存量页面有既成使用，与 SKILL.md
#     "买入区间(已跌破 B×0.85)" 写法冲突，留待人工裁定后再决定是否纳入。
BANNED = ["加仓区间", "高估区间", "低估区间"]


def lint_file(fp):
    """校验单个 wiki 文件，返回告警字符串（None = 无问题 / 不适用）。"""
    # 仅个股页：wiki/stocks/<sector>/<name>.md（含 focus 软链，自动 follow）
    # 排除 stocks 下一级的索引文件（如 价格区间总览.md）
    if not re.search(r"wiki/stocks/[^/]+/[^/]+\.md$", fp):
        return None
    if fp.endswith("价格区间总览.md"):
        return None
    if not os.path.exists(fp):
        return None
    try:
        text = open(fp, encoding="utf-8").read()
    except Exception:
        return None

    hits = [(b, text.count(b)) for b in BANNED if b in text]
    if hits:
        detail = "；".join(f"{b}×{n}" for b, n in hits)
        return (
            f"⚠️ 区间术语 lint（warn-only）：{os.path.relpath(fp)} 含非白名单档位 {detail}\n"
            f"   应映射到 6 档白名单：买入/关注/持有/谨慎/减仓/清仓区间"
            f"（如 加仓区间→买入区间、高估区间→清仓区间）。见 value-invest SKILL.md「区间术语规范」。"
        )
    return None


def main():
    # argv 模式（pre-commit）：逐个 argv 当文件；无 argv 走 stdin JSON（PostToolUse）
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        try:
            data = json.load(sys.stdin)
        except Exception:
            sys.exit(0)  # 拿不到输入不阻断
        fp = (data.get("tool_input") or {}).get("file_path", "")
        files = [fp] if fp else []

    warned = False
    for fp in files:
        msg = lint_file(fp)
        if msg:
            print(msg, file=sys.stderr)
            warned = True
    sys.exit(1 if warned else 0)  # warn-only：非阻断


if __name__ == "__main__":
    main()
