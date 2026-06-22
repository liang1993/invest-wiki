#!/usr/bin/env python3
"""interp smoke —— 解释器自愈 helper 内部决策函数自检（不触发真 execv）。

只测纯决策函数（_have_locally / _probe / _candidates）与 ensure_interpreter 的
「本地有依赖时不动」分支；真正的 os.execv 重入由 transcribe.py / fetch.py 的端到端
跑验证（见 docs/asr-interpreter-reexec-plan.md 验收）。

退出码：全过 → 0；任一断言失败 → 1。
用法：python3 skills/_shared/eval/smoke_interp.py
"""
import os
import shutil
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "skills", "_shared"))

from interp import (  # noqa: E402
    _candidates,
    _have_locally,
    _probe,
    ensure_interpreter,
)

n_fail = 0


def check(name: str, cond: bool) -> None:
    global n_fail
    print(("  ✅ " if cond else "  ❌ ") + name)
    if not cond:
        n_fail += 1


# ── _have_locally ────────────────────────────────────────────
print("── _have_locally ──")
check("stdlib 在位 → True", _have_locally(["os", "sys"]))
check("缺失模块 → False", not _have_locally(["__definitely_absent_xyz__"]))
check("点状名父包缺失 → False（不抛）", not _have_locally(["__no_parent_xyz__.sub"]))

# ── _probe ───────────────────────────────────────────────────
print("── _probe ──")
check("自解释器 import os → True", _probe(sys.executable, ["os"]))
check("自解释器 import 缺失 → False", not _probe(sys.executable, ["__absent_xyz__"]))
check("不存在的解释器 → False", not _probe("/no/such/python", ["os"]))

# ── _candidates ──────────────────────────────────────────────
print("── _candidates ──")
cands = _candidates("INVEST_WIKI_PY")
check("元素都是可执行文件", all(os.path.isfile(c) and os.access(c, os.X_OK) for c in cands))
check("不含 *-config（非解释器）", all("-config" not in c for c in cands))
check("已去重", len(cands) == len(set(cands)))
check("不含当前解释器", os.path.realpath(sys.executable) not in cands)

# override 进候选首位（用一个真实存在的非 python 可执行做哨兵——只验位置不验探测）
other = shutil.which("ls")
os.environ["INVEST_WIKI_PY"] = other
c_ovr = _candidates("INVEST_WIKI_PY")
check("$INVEST_WIKI_PY 排候选首位", bool(c_ovr) and c_ovr[0] == os.path.realpath(other))
del os.environ["INVEST_WIKI_PY"]

# ── ensure_interpreter 本地有依赖时不动 ───────────────────────
print("── ensure_interpreter（本地有依赖）──")
ensure_interpreter(["os", "sys"])  # 必然本地有 → 立即返回；若误 exec 进程会被替换，下一行不会打印
check("本地有依赖时不 exec、不抛", True)

print(f"\n{'=' * 50}")
if n_fail == 0:
    print("smoke 通过：interp helper 决策函数地板可用")
    sys.exit(0)
print(f"smoke 失败：{n_fail} 项断言失败")
sys.exit(1)
