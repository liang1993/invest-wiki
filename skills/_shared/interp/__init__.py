"""解释器自愈：缺依赖时自动重入一个装了依赖的 Python。

为什么需要：本仓库 skill 脚本文档化的调用是 `python3 skills/.../x.py`，但本机
bare `python3` 命中 Xcode 自带 `/usr/bin/python3`(3.9.6)，没有 funasr/torch/
playwright 这类重依赖——它们装在 `/opt/homebrew/bin/python3`(3.14)。
`ensure_interpreter()` 在脚本启动时若发现当前解释器缺指定模块，就在常见位置找一个
**实测 import 成功**的解释器并 `os.execv` 重入自己，让文档化调用开箱即用。

只用标准库（Xcode 3.9.6 也能 import 本模块）。所有提示走 **stderr**，绝不写
stdout——下游靠脚本末行 `TRANSCRIPT_PATH=` / `MEDIA_PATH=` 契约 grep 结果。
"""
from __future__ import annotations

import glob
import importlib.util
import os
import shutil
import subprocess
import sys

GUARD_ENV = "INVEST_WIKI_PY_REEXEC"   # 防 execv 死循环的哨兵
DEFAULT_OVERRIDE = "INVEST_WIKI_PY"   # 显式覆盖：指向某个 python3（逃生口 / CI 固定）


def _realpath(p: str) -> str:
    try:
        return os.path.realpath(p)
    except OSError:
        return ""


def _have_locally(modules: list[str]) -> bool:
    """当前解释器能否定位全部 modules（find_spec 快判，不真正 import）。

    find_spec 对点状名且父包缺失会抛 ModuleNotFoundError/ValueError，吞掉判 False。
    注意：find_spec 只判可发现性、不判可导入性；半装 / 版本错配仍可能 True，由调用
    脚本自身的真 import 依赖检查（check_deps / check_douyin_deps）兜底——非对称是有意的。
    """
    for m in modules:
        try:
            if importlib.util.find_spec(m) is None:
                return False
        except (ModuleNotFoundError, ValueError, ImportError):
            return False
    return True


def _probe(py: str, modules: list[str]) -> bool:
    """子进程实测 `py -c "import m1, m2"`，returncode==0 才认这个解释器可用。"""
    try:
        r = subprocess.run(
            [py, "-c", "import " + ", ".join(modules)],
            capture_output=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


def _candidates(env_var: str) -> list[str]:
    """去重保序的候选解释器绝对路径：$override → homebrew python3 → python3.14..10 → glob。

    只保留实际存在、可执行、且非当前解释器的项（realpath 去重）。
    """
    raw: list[str] = []
    override = os.environ.get(env_var)
    if override:
        override = os.path.expanduser(override)
        raw.append(shutil.which(override) or override)   # 容忍裸名（走 PATH）/ 全路径
    raw.append("/opt/homebrew/bin/python3")
    for minor in range(14, 9, -1):                        # python3.14 → python3.10
        w = shutil.which(f"python3.{minor}")
        if w:
            raw.append(w)
    raw.extend(sorted(glob.glob("/opt/homebrew/bin/python3.1[0-9]"), reverse=True))

    cur = _realpath(sys.executable)
    out: list[str] = []
    seen: set[str] = set()
    for p in raw:
        rp = _realpath(p)
        if not rp or rp == cur:                           # 不存在 / 就是当前解释器 → 跳
            continue
        if not (os.path.isfile(rp) and os.access(rp, os.X_OK)):
            continue
        if rp in seen:
            continue
        seen.add(rp)
        out.append(rp)
    return out


def ensure_interpreter(modules: list[str], *, env_var: str = DEFAULT_OVERRIDE) -> None:
    """当前解释器缺 modules 时，重入一个装了依赖的解释器。

    - 当前解释器已能定位全部 modules → 直接返回（零子进程开销，正常路径）。
    - 已重入过仍缺（哨兵已设）→ 返回，交回调用脚本依赖检查报错，防 execv 死循环。
    - 否则按 _candidates 顺序探测，第一个 `import` 成功的解释器 `os.execv` 重入自己；
      argv 用**绝对脚本路径**（`sys.argv[0]`，cwd 不变 → 相对 --target 仍解析正确）。
    - 全部候选都不满足 → 返回（不重入），交回调用脚本打印安装提示。
    """
    if _have_locally(modules):
        return
    if os.environ.get(GUARD_ENV):
        return
    script = os.path.abspath(sys.argv[0])
    for cand in _candidates(env_var):
        if _probe(cand, modules):
            print(
                f"→ 当前解释器（{sys.executable}）缺 {modules}，切到 {cand} 重跑…",
                file=sys.stderr, flush=True,
            )
            os.environ[GUARD_ENV] = "1"
            os.execv(cand, [cand, script, *sys.argv[1:]])
    # 没找到：静默返回，让调用脚本的 check_deps / check_douyin_deps 打印安装提示
