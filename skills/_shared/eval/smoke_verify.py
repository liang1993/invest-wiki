#!/usr/bin/env python3
"""verify-cli smoke —— 三模板 dry-run 渲染检查（Phase 3，零 API）。

通过真实 CLI 入口（subprocess --dry-run）验证：模板正文渲染、工具映射前言注入、
占位符替换、arbiter 盲化前言、L3 --sections 必填。实跑（调 LLM）需 llm.json + key，
不在 smoke 范围（见 docs/harness-setup.md 冒烟 #4）。

退出码：全过 → 0；任一失败 → 1。用法：python3 skills/_shared/eval/smoke_verify.py
"""
import os
import sys
import tempfile
import subprocess

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RV = os.path.join(REPO, "skills", "_shared", "verify", "run_verify.py")

n_fail = 0


def run(args):
    return subprocess.run([sys.executable, RV] + args, capture_output=True, text=True, cwd=REPO)


def check(name, cond, detail=""):
    global n_fail
    if cond:
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name}: {detail}")
        n_fail += 1


# ── L3 ──────────────────────────────────────────────────────
print("── L3 模板 ──")
r = run(["--template", "l3", "--files", "wiki/example.md",
         "--sections", "金价区间; 持仓建议", "--raw", "raw/x.md", "--dry-run"])
check("l3 dry-run 退出码 0", r.returncode == 0, r.stderr[:200])
check("l3 工具映射前言 + 预算", "工具映射" in r.stdout and "run_search ≤ 10" in r.stdout)
check("l3 模板正文渲染", "数据校验员" in r.stdout)
check("l3 章节定位替换（占位符消失）",
      "金价区间" in r.stdout and "[文件路径" not in r.stdout and "[列出 raw" not in r.stdout)

# ── value-invest ────────────────────────────────────────────
print("── value-invest 模板 ──")
r = run(["--template", "value-invest", "--file", "wiki/stocks/financial/招商银行.md", "--dry-run"])
check("vi dry-run 退出码 0", r.returncode == 0, r.stderr[:200])
check("vi 七项框架 + 预算前言", "七项校验框架" in r.stdout and "run_fetch ≤ 3" in r.stdout)
check("vi 占位符替换", "{wiki_file_path}" not in r.stdout and "招商银行" in r.stdout)

# ── arbiter ─────────────────────────────────────────────────
print("── arbiter 模板 ──")
with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
    f.write("**标的**：招商银行（600036）\n**争议数据点**：2026Q1 NIM\n"
            "版本A：NIM YoY -5bp\n版本B：NIM YoY -8bp（主张 -5bp 是净利差）\n")
    diff = f.name
try:
    r = run(["--template", "arbiter", "--diff", diff, "--dry-run"])
    check("arb dry-run 退出码 0", r.returncode == 0, r.stderr[:200])
    check("arb 仲裁正文 + 代码层盲化前言",
          "分歧仲裁员" in r.stdout and "禁止 read_file 读取" in r.stdout)
    check("arb 分歧注入（占位符消失）",
          "版本A：NIM YoY -5bp" in r.stdout and "{version_A_claim}" not in r.stdout)
finally:
    os.unlink(diff)

# ── L3 --sections 必填 ──────────────────────────────────────
print("── 参数校验 ──")
r = run(["--template", "l3", "--files", "wiki/x.md", "--dry-run"])  # 故意缺 --sections
check("l3 缺 --sections → 报错退出码 2", r.returncode == 2,
      f"退出码={r.returncode}")

print(f"\n{'=' * 50}")
if n_fail == 0:
    print("smoke 通过：verify-cli 三模板渲染 + 工具映射 + 参数校验正常（实跑需 llm.json）")
    sys.exit(0)
else:
    print(f"smoke 失败：{n_fail} 项")
    sys.exit(1)
