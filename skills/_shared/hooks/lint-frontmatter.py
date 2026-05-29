#!/usr/bin/env python3
"""PostToolUse hook：wiki 页面 frontmatter 必填字段校验（warn-only）

页面模板要求 frontmatter 含 tags 与 updated（CLAUDE.md「页面模板」）。本 hook
在写入后校验，把"忘加 frontmatter / 忘更新 updated"从靠自觉变成确定性提示。

退出码：0 通过 / 1 非阻断警告 / 2 阻断。现为 warn-only（exit 1）。

注册：python3 "$CLAUDE_PROJECT_DIR/skills/_shared/hooks/lint-frontmatter.py"
"""

import json
import os
import re
import sys

# 仅校验"页面"类 md（个股/基金/宏观/行业/策略），排除日志与索引（结构不同）
SKIP_BASENAMES = {"log.md", "index.md"}


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    fp = (data.get("tool_input") or {}).get("file_path", "")
    if not fp or not re.search(r"wiki/.+\.md$", fp):
        sys.exit(0)
    if os.path.basename(fp) in SKIP_BASENAMES:
        sys.exit(0)
    if not os.path.exists(fp):
        sys.exit(0)

    try:
        text = open(fp, encoding="utf-8").read()
    except Exception:
        sys.exit(0)

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
        print(
            f"⚠️ frontmatter lint（warn-only）：{os.path.relpath(fp)} 缺 {', '.join(missing)}"
            f"（模板要求 tags + updated，见 CLAUDE.md「页面模板」）。",
            file=sys.stderr,
        )
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
