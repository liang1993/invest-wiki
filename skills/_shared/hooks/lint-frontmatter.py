#!/usr/bin/env python3
"""PostToolUse hook：wiki 页面 frontmatter 必填字段校验（warn-only）

页面模板要求 frontmatter 含 tags 与 updated（CLAUDE.md「页面模板」）。本 hook
在写入后校验，把"忘加 frontmatter / 忘更新 updated"从靠自觉变成确定性提示。

退出码：0 通过 / 1 非阻断警告 / 2 阻断。现为 warn-only（exit 1）。

双入口：无 argv → 读 stdin JSON（PostToolUse）；有 argv → 每个 argv 当 wiki 文件路径
校验（pre-commit 调用，commit 时兜底）。共用一份逻辑，warn-only 语义一致。

注册：python3 "$CLAUDE_PROJECT_DIR/skills/_shared/hooks/lint-frontmatter.py"
"""

import json
import os
import re
import sys

# 仅校验"页面"类 md（个股/基金/宏观/行业/策略），排除日志与索引（结构不同）
SKIP_BASENAMES = {"log.md", "index.md"}


def lint_file(fp):
    """校验单个 wiki 文件 frontmatter，返回告警字符串（None = 无问题 / 不适用）。"""
    if not fp or not re.search(r"wiki/.+\.md$", fp):
        return None
    if os.path.basename(fp) in SKIP_BASENAMES:
        return None
    if not os.path.exists(fp):
        return None
    try:
        text = open(fp, encoding="utf-8").read()
    except Exception:
        return None

    missing = []
    if not text.startswith("---"):
        missing.append("frontmatter 块缺失")
    else:
        # 取第一个 --- 与第二个 --- 之间的 YAML
        parts = text.split("---", 2)
        fm = parts[1] if len(parts) >= 3 else ""
        if not re.search(r"^\s*tags\s*:", fm, re.M):
            missing.append("tags")
        if not re.search(r"^\s*updated\s*:", fm, re.M):
            missing.append("updated")

    if missing:
        return (f"⚠️ frontmatter lint（warn-only）：{os.path.relpath(fp)} 缺 {', '.join(missing)}"
                f"（模板要求 tags + updated，见 CLAUDE.md「页面模板」）。")
    return None


def main():
    # argv 模式（pre-commit）：逐个 argv 当文件；无 argv 走 stdin JSON（PostToolUse）
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        try:
            data = json.load(sys.stdin)
        except Exception:
            sys.exit(0)
        fp = (data.get("tool_input") or {}).get("file_path", "")
        files = [fp] if fp else []

    warned = False
    for fp in files:
        msg = lint_file(fp)
        if msg:
            print(msg, file=sys.stderr)
            warned = True
    sys.exit(1 if warned else 0)


if __name__ == "__main__":
    main()
