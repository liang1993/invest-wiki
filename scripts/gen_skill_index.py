#!/usr/bin/env python3
"""从各 skills/*/SKILL.md frontmatter 生成 AGENTS.md 的 skill 索引块（标记块内）。

给不支持 skill 自动触发的 harness（OpenCode / Hermes Agent / …）当路由表。**单一生成源**
（避免在 skills/ 目录、.claude 符号链接之外出现第三个手工登记点漂移）。`bootstrap.sh`
调用本脚本刷新；幂等——重跑无 diff。

用法：
  python3 scripts/gen_skill_index.py          # 写入/刷新 AGENTS.md 标记块
  python3 scripts/gen_skill_index.py --check   # 只校验是否最新（不一致退出码 1，不写）
"""
import os
import re
import sys
import glob

import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AGENTS = os.path.join(REPO, "AGENTS.md")
BEGIN = "<!-- skill-index:begin -->"
END = "<!-- skill-index:end -->"
MAXLEN = 100  # 触发场景节选上限（字符）


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def parse_frontmatter(path):
    """返回 (name, description)。用 YAML 解析 frontmatter 首块。

    不能用正则取字段：description 允许写成带引号的 YAML 字符串（Hermes 侧摄入
    要求），引号内的 `\\"` 转义靠 `.strip('"')` 剥不掉，会把反斜杠漏进索引表。
    """
    text = _read(path)
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    try:
        fm = yaml.safe_load(m.group(1)) if m else None
    except yaml.YAMLError as e:
        print(f"[警告] {path} frontmatter 解析失败：{e}", file=sys.stderr)
        fm = None
    if not isinstance(fm, dict):
        return (None, "")
    return (fm.get("name"), str(fm.get("description") or ""))


def short_trigger(desc):
    """取描述的首句作触发场景节选，截断到 MAXLEN，并转义表格管道符。"""
    d = desc
    for sep in ("。", ". "):
        i = d.find(sep)
        if 0 <= i <= MAXLEN:
            d = d[:i]
            break
    d = d.strip()
    if len(d) > MAXLEN:
        d = d[:MAXLEN].rstrip() + "…"
    return d.replace("|", "\\|").replace("\n", " ")


def build_index():
    rows = []
    for skill_md in sorted(glob.glob(os.path.join(REPO, "skills", "*", "SKILL.md"))):
        skill_dir = os.path.basename(os.path.dirname(skill_md))
        if skill_dir == "_shared":
            continue
        _, desc = parse_frontmatter(skill_md)
        rows.append(f"| `{skill_dir}` | {short_trigger(desc)} |")
    return "| skill | 触发场景（节选，完整见各 SKILL.md） |\n|---|---|\n" + "\n".join(rows)


def render_block(index):
    return f"{BEGIN}\n\n{index}\n\n{END}"


def main():
    check = "--check" in sys.argv[1:]
    text = _read(AGENTS)
    pat = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    if not pat.search(text):
        print(f"[错误] AGENTS.md 中找不到 {BEGIN} … {END} 标记块", file=sys.stderr)
        sys.exit(2)
    index = build_index()
    n = index.count("| `")  # 索引块内的 skill 行数（不误数映射表里的 backtick 单元格）
    new_text = pat.sub(lambda _: render_block(index), text)
    if check:
        if new_text != text:
            print("[过期] AGENTS.md skill 索引块与 SKILL.md 不一致，请跑 gen_skill_index.py", file=sys.stderr)
            sys.exit(1)
        print(f"[最新] skill 索引块已是最新（{n} 个 skill）")
        sys.exit(0)
    if new_text != text:
        with open(AGENTS, "w", encoding="utf-8") as f:
            f.write(new_text)
        print(f"[已刷新] AGENTS.md skill 索引块（{n} 个 skill）")
    else:
        print(f"[无变化] skill 索引块已是最新（{n} 个 skill）")


if __name__ == "__main__":
    main()
