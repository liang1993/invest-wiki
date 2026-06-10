#!/usr/bin/env python3
"""verify-cli —— L3 / value-invest / arbiter 零上下文校验的 harness 无关实现。

替代 Claude Code 的「Agent 工具 spawn general-purpose 校验员」，让任何能跑 bash 的
harness（OpenCode / Hermes Agent / …）跑等价的零上下文事后校验，且支持**异构模型**
（校验员 ≠ 主笔模型，误差不相关）。

模板单一事实源（运行时读取，不复制粘贴成第二份）：
  --template l3            → docs/data-discipline.md §数据校验 Agent prompt 模板
  --template value-invest  → skills/value-invest-verify/prompt-template.md（七项框架）
  --template arbiter       → skills/value-invest-verify/arbiter-prompt.md（层次 2 仲裁）

后端：OpenAI 兼容 chat-completions + function calling。配置 ~/.config/invest-wiki/llm.json
（仓库外，schema 见同目录 llm.json.example）。`verifier` map 按 --template 选 backend，
实现"按 spawn 点定档"（L3→便宜快档 / value-invest·arbiter→强推理档）。

用法：
  l3:           run_verify.py --template l3 --files <wiki…> --sections "<新增/修改章节>" [--raw <路径/URL…>]
  value-invest: run_verify.py --template value-invest --file <个股wiki>
  arbiter:      run_verify.py --template arbiter --diff <分歧描述文件>
  通用：        [--dry-run] [--backend <名>] [--out <报告路径>]

退出码：0=全✓（无 ✗/⚠️）；1=有 ✗/⚠️；2=执行失败（配置缺失 / API 错误 / 模板缺失）。
"""
import os
import re
import sys
import json
import argparse
import datetime
import subprocess

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "skills", "_shared"))  # 供 import webtools

CONFIG_PATH = os.path.expanduser("~/.config/invest-wiki/llm.json")
TODAY = datetime.date.today().isoformat()

# 预算（完整继承现纪律）+ max-steps 总闸防失控
BUDGETS = {
    "l3": {"search": 10, "fetch": 6},            # data-discipline.md:124（search≤10）
    "value-invest": {"search": 8, "fetch": 3},   # SKILL.md:233 / prompt-template.md:228
    "arbiter": {"search": 6, "fetch": 5},         # 至少 2 独立来源，给足余量
}
MAX_STEPS = {"l3": 28, "value-invest": 34, "arbiter": 24}


# ─────────────────────────── 模板提取（运行时读原文）───────────────────────────

def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def extract_l3_template(text):
    """data-discipline.md「## 数据校验 Agent prompt 模板」下的 ``` 围栏块内容。"""
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if l.startswith("## 数据校验 Agent prompt 模板"):
            fs = next(j for j in range(i + 1, len(lines)) if lines[j].strip() == "```") + 1
            fe = next(k for k in range(fs, len(lines)) if lines[k].strip() == "```")
            return "\n".join(lines[fs:fe]).strip()
    raise RuntimeError("未找到 L3 prompt 模板章节")


def extract_body_template(text):
    """prompt-template.md / arbiter-prompt.md「## 模板正文」与「## 模板填充字段」间的正文。"""
    lines = text.splitlines()
    start = end = None
    for i, l in enumerate(lines):
        if l.startswith("## 模板正文"):
            start = next(j for j in range(i + 1, len(lines)) if lines[j].strip() == "---") + 1
            break
    for i, l in enumerate(lines):
        if l.startswith("## 模板填充字段"):
            end = next(j for j in range(i - 1, -1, -1) if lines[j].strip() == "---")
            break
    if start is None or end is None:
        raise RuntimeError("未找到模板正文边界")
    return "\n".join(lines[start:end]).strip()


# ─────────────────────────── 渲染（填充字段）───────────────────────────

def render_l3(files, sections, raw):
    body = extract_l3_template(_read(os.path.join(REPO, "docs", "data-discipline.md")))
    raw_txt = ", ".join(raw) if raw else "无"
    files_txt = ", ".join(files) + f"（关键章节定位：{sections}）"
    body = re.sub(r"\[列出 raw/articles[^\]]*\]", raw_txt, body)
    body = re.sub(r"\[文件路径[^\]]*\]", files_txt, body)
    return body


def _derive_raw_articles(wiki_file):
    name = os.path.splitext(os.path.basename(wiki_file))[0]
    cand = os.path.join(REPO, "raw", "articles", "stocks", name)
    return cand if os.path.isdir(cand) else "（无对应归档，可不填）"


def render_value_invest(wiki_file):
    body = extract_body_template(
        _read(os.path.join(REPO, "skills", "value-invest-verify", "prompt-template.md")))
    return (body
            .replace("{wiki_file_path}", os.path.abspath(wiki_file))
            .replace("{raw_articles_path}", _derive_raw_articles(wiki_file))
            .replace("{YYYY-MM-DD}", TODAY))


def render_arbiter(diff_file):
    body = extract_body_template(
        _read(os.path.join(REPO, "skills", "value-invest-verify", "arbiter-prompt.md")))
    diff = _read(diff_file).strip()
    # 把含占位符的「## 待仲裁的分歧」整块替换为主 agent 提供的分歧描述
    body = re.sub(r"## 待仲裁的分歧.*?(?=## 仲裁流程)",
                  "## 待仲裁的分歧\n\n" + diff + "\n\n", body, flags=re.DOTALL)
    return body.replace("{YYYY-MM-DD}", TODAY)


# ─────────────────────────── 工具映射前言（注入 prompt 头部，不改模板原文）─────────

def tool_preamble(template):
    b = BUDGETS[template]
    arbiter_note = ""
    if template == "arbiter":
        arbiter_note = ("- 🚫 本环境已在**代码层**禁止 read_file 读取 `wiki/**`（盲化设计）——"
                        "你只能用上方两个 claim 描述 + 自己独立查的原始数据源\n")
    return f"""==== 运行环境：verify-cli（非 Claude Code）· 工具映射 ====
下方校验任务模板原文以 Claude Code 工具名书写。本环境通过 function calling 提供等价工具，
**按此表映射，纪律语义不变**。模板里出现的工具名一律按此表翻译：

| 模板里写的 | 本环境调用 | 说明 |
|---|---|---|
| Read（读 wiki / raw 文件） | read_file(path) | 仅限仓库内路径 |
| WebFetch（抓原文核对） | run_fetch(url) | 取回原文正文；**[观测] 必须用它核对原 URL，禁止用搜索摘要替代** |
| WebSearch（搜索） | run_search(query) | 返回 title/url/snippet 列表 |
| Bash 跑取数脚本（如 fetch_data.py） | run_script(cmd) | 仅白名单只读取数脚本 |
| Grep（扫描数字 / 叙事词） | 无专用函数 → 用 read_file 读全文后**自行扫描** |

**预算硬上限**（达上限后该类工具返回"已达配额"，请总结剩余可疑项交主 agent 自查，不要硬闯）：
- run_search ≤ {b['search']} 次
- run_fetch ≤ {b['fetch']} 次
{arbiter_note}**无 URL / 无原始材料引用的判断本身不可信**——每个 ✗ / ⚠️ / Fail 必须附 run_search 的 URL 或 run_fetch 回的原文摘录。
查证完成后**直接输出最终校验报告**（不要再调工具），格式严格遵守下方模板要求。
====================================================================

"""


def build_prompt(template, args):
    if template == "l3":
        body = render_l3(args.files, args.sections, args.raw or [])
    elif template == "value-invest":
        body = render_value_invest(args.file)
    elif template == "arbiter":
        body = render_arbiter(args.diff)
    else:
        raise RuntimeError(f"未知模板 {template}")
    return tool_preamble(template) + body


# ─────────────────────────── 工具实现（tool-loop 内 dispatch）───────────────────

def _safe_repo_path(path):
    ap = os.path.abspath(path if os.path.isabs(path) else os.path.join(REPO, path))
    if os.path.commonpath([ap, REPO]) != REPO:
        return None
    return ap


def tool_read_file(args, template):
    path = args.get("path", "")
    ap = _safe_repo_path(path)
    if ap is None:
        return f"[拒绝] 路径越出仓库范围：{path}"
    # arbiter 盲化：代码层禁止读 wiki/**
    rel = os.path.relpath(ap, REPO)
    if template == "arbiter" and rel.startswith("wiki" + os.sep):
        return ("[拒绝] arbiter 模式禁止读 wiki/**（盲化设计）——"
                "请只用分歧描述 + 独立查原始数据源")
    if not os.path.isfile(ap):
        return f"[未找到] {rel}"
    try:
        return _read(ap)[:40000]
    except Exception as e:  # noqa: BLE001
        return f"[读取失败] {type(e).__name__}: {e}"


def tool_run_fetch(args, counters, budget):
    if counters["fetch"] >= budget["fetch"]:
        return f"[已达配额] run_fetch 已用满 {budget['fetch']} 次，请总结剩余可疑项交主 agent 自查"
    counters["fetch"] += 1
    from webtools import fetch as fetchmod
    try:
        r = fetchmod.fetch_url(args.get("url", ""), timeout=20)
        return f"# HTTP {r['status']} | 抽取器 {r['extractor']}\n{r['text']}"
    except Exception as e:  # noqa: BLE001
        return f"[fetch 失败] {type(e).__name__}: {str(e)[:200]}"


def tool_run_search(args, counters, budget):
    if counters["search"] >= budget["search"]:
        return f"[已达配额] run_search 已用满 {budget['search']} 次，请总结剩余可疑项交主 agent 自查"
    counters["search"] += 1
    from webtools import search as searchmod
    try:
        res = searchmod.search(args.get("query", ""), n=args.get("n", 5))
        if not res:
            return "（无结果）"
        return "\n".join(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet'][:300]}"
                         for i, r in enumerate(res, 1))
    except searchmod.SearchKeyMissing:
        return "[search 不可用] 未配置 TAVILY_API_KEY —— 该项无法独立核对，请如实标'无法核对'"
    except Exception as e:  # noqa: BLE001
        return f"[search 失败] {type(e).__name__}: {str(e)[:200]}"


_SCRIPT_OK = re.compile(r"^python3?\s+[\w./\-]+\.py(\s+[\w./\-=,:]+)*\s*$")


def tool_run_script(args):
    cmd = args.get("cmd", "").strip()
    # 白名单：python3 <仓库内 scripts/ 或 _shared/marketdata 下的 .py> + 无 shell 元字符
    if not _SCRIPT_OK.match(cmd) or any(c in cmd for c in ";|&`$><\n"):
        return f"[拒绝] 仅允许 python3 跑仓库内只读取数脚本（无 shell 元字符）：{cmd[:80]}"
    parts = cmd.split()
    script = _safe_repo_path(parts[1])
    if script is None or not os.path.isfile(script):
        return f"[拒绝] 脚本不在仓库内或不存在：{parts[1]}"
    rel = os.path.relpath(script, REPO)
    if "/scripts/" not in "/" + rel and "_shared/marketdata" not in rel:
        return f"[拒绝] 仅白名单取数脚本（*/scripts/*.py 或 _shared/marketdata）：{rel}"
    try:
        out = subprocess.run(["python3", script] + parts[2:], cwd=REPO,
                             capture_output=True, text=True, timeout=90)
        return (out.stdout or "")[-8000:] + (f"\n[stderr] {out.stderr[-1000:]}" if out.stderr else "")
    except Exception as e:  # noqa: BLE001
        return f"[脚本失败] {type(e).__name__}: {str(e)[:200]}"


def dispatch_tool(name, args, template, counters, budget):
    if name == "read_file":
        return tool_read_file(args, template)
    if name == "run_fetch":
        return tool_run_fetch(args, counters, budget)
    if name == "run_search":
        return tool_run_search(args, counters, budget)
    if name == "run_script":
        return tool_run_script(args)
    return f"[未知工具] {name}"


TOOLS_SCHEMA = [
    {"type": "function", "function": {
        "name": "read_file", "description": "读取仓库内文件内容（wiki / raw / docs 等）。仅限仓库内相对或绝对路径。",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "run_fetch", "description": "抓取一个 URL 的原文正文，用于核对 [观测] 数字。返回 HTTP 状态 + 正文。",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "run_search", "description": "网页搜索，返回 title/url/snippet 列表，用于横向对标 / 时效数据核对。",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}, "n": {"type": "integer", "default": 5}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "run_script", "description": "跑仓库内只读取数脚本（如 python3 skills/value-invest/scripts/fetch_data.py <code>）独立核对财务/行情。",
        "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}},
]


# ─────────────────────────── 后端 + tool-loop ───────────────────────────

def load_config():
    if not os.path.isfile(CONFIG_PATH):
        raise RuntimeError(
            f"未找到 {CONFIG_PATH}（schema 见 skills/_shared/verify/llm.json.example）。"
            "verify-cli 实跑需先配置后端；仅渲染请加 --dry-run")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def pick_backend(cfg, template, override):
    name = override or cfg.get("verifier", {}).get(template) or cfg.get("verifier", {}).get("default")
    if not name or name not in cfg.get("backends", {}):
        raise RuntimeError(f"llm.json 中找不到 backend '{name}'（template={template}）")
    return name, cfg["backends"][name]


def run_tool_loop(prompt, backend, template):
    import requests
    api_key = os.environ.get(backend.get("api_key_env", ""), "")
    if not api_key:
        raise RuntimeError(f"环境变量 {backend.get('api_key_env')} 未设置（API key）")
    url = backend["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    messages = [{"role": "user", "content": prompt}]
    counters = {"search": 0, "fetch": 0}
    budget = BUDGETS[template]
    for _ in range(MAX_STEPS[template]):
        payload = {"model": backend["model"], "messages": messages,
                   "tools": TOOLS_SCHEMA, "tool_choice": "auto",
                   "temperature": backend.get("temperature", 0)}
        resp = requests.post(url, headers=headers, json=payload, timeout=180)
        resp.raise_for_status()
        msg = resp.json()["choices"][0]["message"]
        messages.append({"role": "assistant", "content": msg.get("content") or "",
                         "tool_calls": msg.get("tool_calls")})
        tcs = msg.get("tool_calls")
        if not tcs:
            return msg.get("content") or ""
        for tc in tcs:
            try:
                a = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                a = {}
            result = dispatch_tool(tc["function"]["name"], a, template, counters, budget)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})
    return (messages[-1].get("content") or "") + "\n\n[注] max-steps 总闸触发，校验可能未完成，建议主 agent 复查。"


def report_exit_code(report):
    if "❌" in report or "✗" in report:
        return 1
    if "⚠️" in report or "⚠" in report:
        return 1
    return 0


# ─────────────────────────── CLI ───────────────────────────

def main():
    ap = argparse.ArgumentParser(description="verify-cli —— 零上下文数据校验（harness 无关）")
    ap.add_argument("--template", required=True, choices=["l3", "value-invest", "arbiter"])
    ap.add_argument("--files", nargs="+", help="[l3] 本次新增/修改的 wiki 文件")
    ap.add_argument("--sections", help="[l3] 关键章节定位（必填，防全页扫描失焦）")
    ap.add_argument("--raw", nargs="*", help="[l3] 原始材料路径/URL")
    ap.add_argument("--file", help="[value-invest] 个股 wiki 文件")
    ap.add_argument("--diff", help="[arbiter] 分歧描述文件")
    ap.add_argument("--backend", help="覆盖 llm.json verifier map 选定的 backend")
    ap.add_argument("--dry-run", action="store_true", help="只渲染 prompt 不调 API")
    ap.add_argument("--out", help="把报告落盘到此路径（默认仅 stdout）")
    args = ap.parse_args()

    # 参数校验（L3 --sections 必填）
    try:
        if args.template == "l3":
            if not args.files or not args.sections:
                ap.error("--template l3 需要 --files 与 --sections（章节定位必填）")
        elif args.template == "value-invest" and not args.file:
            ap.error("--template value-invest 需要 --file")
        elif args.template == "arbiter" and not args.diff:
            ap.error("--template arbiter 需要 --diff")
        prompt = build_prompt(args.template, args)
    except Exception as e:  # noqa: BLE001
        print(f"[渲染失败] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)

    if args.dry_run:
        print(prompt)
        print(f"\n[dry-run] 模板={args.template} 预算={BUDGETS[args.template]} "
              f"max_steps={MAX_STEPS[args.template]}（未调 API）", file=sys.stderr)
        sys.exit(0)

    try:
        cfg = load_config()
        name, backend = pick_backend(cfg, args.template, args.backend)
        print(f"[verify-cli] backend={name} model={backend.get('model')} template={args.template}",
              file=sys.stderr)
        report = run_tool_loop(prompt, backend, args.template)
    except Exception as e:  # noqa: BLE001
        print(f"[执行失败] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)

    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[已落盘] {args.out}", file=sys.stderr)
    sys.exit(report_exit_code(report))


if __name__ == "__main__":
    main()
