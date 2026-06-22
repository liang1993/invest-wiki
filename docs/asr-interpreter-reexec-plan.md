# 方案：asr / media-fetch 解释器自愈（bare `python3` 即可跑）

> 工程改动（脚本层），走 AGENTS.md「工程改动工作流」双门 review。不碰 `wiki/`。

## 问题

文档里写的调用方式是：

```bash
python3 skills/asr/scripts/transcribe.py <FILE> ...
python3 skills/media-fetch/scripts/fetch.py "<URL>" ...
```

但本机 `python3` 解析顺序是 `/usr/bin/python3`（Xcode 自带 **3.9.6**，pip 21.2.4 连 `--break-system-packages` 都不支持），**没有** funasr / torch / playwright。真正装了依赖的是 `/opt/homebrew/bin/python3`（**3.14.3**，funasr 1.3.1 + torch 2.11.0 + torchaudio + pyyaml + playwright 全在）。

实测确认：

| 解释器 | funasr/torch | playwright | 说明 |
|---|---|---|---|
| `python3` → `/usr/bin/python3` (3.9.6) | ✗ | ✗ | Xcode 自带，bare `python3` 命中它 |
| `/opt/homebrew/bin/python3` (3.14.3) | ✓ | ✓ | 依赖实际所在 |
| `python3.14`（PATH）→ homebrew 同一份 | ✓ | ✓ | 与上同 |

结果：

- **transcribe.py** 启动 `check_deps()` 报 `缺少依赖：['funasr', 'torch']` 直接退出。
- **fetch.py** 的 **Douyin 路径**需要 playwright，bare `python3` 同样跑不了；**Apple Podcasts 路径**是纯标准库（urllib+json），Xcode 3.9.6 也能跑。

现状下只有手动 `/opt/homebrew/bin/python3 ...` 或 `python3.14 ...` 才行。仓库内的调用方（`douyin-distill/scripts/watch.py` 硬编码 `PY=/opt/homebrew/bin/python3`，`download.py` 用 `python3.14`）已各自绕开——但**文档化的标准调用就是坏的**，且每个新调用方都要重复踩坑（见 auto-memory「asr/media-fetch python 解释器坑」）。

## 目标

让文档化的 `python3 skills/.../*.py` **开箱即用**，且：
- 不破坏 media-fetch 的 Apple Podcasts 纯标准库路径（它要能在任意解释器跑，包括只有 Xcode python 的机器）。
- 不回归仓库内已有调用方（watch.py / download.py 传的就是对的解释器）。
- 留一个显式逃生口（CI / 别的机器上路径不同）。

## 方案（采用 a+b+c 三合一）

任务给的三个选项，取**最简且能彻底解决**的组合：

- **(a) 启动自愈再 exec**：脚本启动时若当前解释器缺依赖，自动在常见位置找一个**实测 import 成功**的解释器并 `os.execv` 重入自己。
- **(b) 显式覆盖**：环境变量 `INVEST_WIKI_PY` 作为候选列表第一名（逃生口 / CI 固定）。
- **(c) 文档**：README + SKILL 说明「依赖必须装在跑脚本的那个解释器里」+ 自动绕行行为 + 覆盖变量。

### 共享 helper：`skills/_shared/interp.py`

放 `_shared/` 符合仓库约定（跨 skill 工具统一入口；7+ 脚本已用 `sys.path.insert(.../_shared)` 的引入模式）。两处调用点逻辑字节级一致，DRY + 可被 eval 冒烟覆盖。helper 只用标准库（os/sys/subprocess/shutil/importlib），Xcode 3.9.6 下也能 import。

公开 API：

```python
def ensure_interpreter(modules: list[str], *, env_var: str = "INVEST_WIKI_PY") -> None:
    """当前解释器缺 modules 时，找一个装了的解释器重入自己（os.execv）。

    - 当前解释器已能 import 全部 modules → 直接 return（零开销，无子进程）。
    - 设置了重入哨兵环境变量且仍缺 → return（防 execv 死循环，交回 check_deps 报错）。
    - 候选解释器顺序：$INVEST_WIKI_PY → /opt/homebrew/bin/python3 →
      shutil.which(python3.14..3.10) → glob(/opt/homebrew/bin/python3.1*)，去重保序。
    - 对每个候选先 `cand -c "import m1, m2"` 实测（returncode==0）再 execv；
      跳过 realpath==当前 sys.executable 的候选（不重入自己）。
    - 全部候选都不满足 → return（不 execv，交回脚本自己的 check_deps 打印安装提示）。
    """
```

内部可测函数（供冒烟 import，不触发 execv）：
- `_have_locally(modules) -> bool`：用 `importlib.util.find_spec` 逐个判存在（不真正 import，零副作用）。
- `_probe(py, modules) -> bool`：子进程 `py -c "import ..."`，returncode==0。
- `_candidates(env_var) -> list[str]`：产出去重保序的候选解释器绝对路径列表。

重入实现：`os.execv(cand, [cand, *sys.argv])`（`sys.argv[0]` 是脚本路径，cwd 不变 → 相对 `--target` 仍解析正确）。execv 前 `os.environ[guard]="1"`。

### transcribe.py 接线

`main()` 第一行（在 `parse_args()` / `check_deps()` 之前）：

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_shared"))
from interp import ensure_interpreter
ensure_interpreter(["funasr", "torch"])
```

execv 后 argv 保留 → `parse_args()` 重跑一次（在最终解释器里，仅一次）。`check_deps()` 保留不动，作为「自愈也找不到」时的清晰报错出口；顺手在其错误信息里加一句「已尝试自动切换解释器，仍未找到；可设 `INVEST_WIKI_PY` 指定」。

> 注：symlink 兼容——脚本经 `~/.claude/skills/asr/`（目录符号链接）调用时，`os.path.abspath(__file__)` 经目录链接仍落到真实仓库路径，`../../_shared` 成立；execv 传 `sys.argv[0]` 原样即可。

### fetch.py 接线（只对 Douyin 触发）

Apple Podcasts 必须保持解释器无关。故**先 `parse_args()` + `detect_platform()`，仅当 `platform == "douyin"` 才 `ensure_interpreter(["playwright"])`**，紧接现有 `check_douyin_deps()`：

```python
platform = detect_platform(args.url)
if platform == "douyin":
    sys.path.insert(0, .../_shared); from interp import ensure_interpreter
    ensure_interpreter(["playwright"])
    check_douyin_deps()
    ...
```

execv 后 argv 保留 → 再次 parse/detect（廉价）→ douyin 分支再次 ensure（playwright 已在 → return）。podcast 路径全程不碰 ensure_interpreter，纯标准库照跑。

### 文档 (c)

- `asr/README.md` + `asr/SKILL.md`、`media-fetch/README.md` + `media-fetch/SKILL.md`：
  - 加「依赖必须装进**将要运行脚本的那个解释器**」一句；推荐 `/opt/homebrew/bin/python3 -m pip install --break-system-packages ...`（bare `pip3` 在本机指向 homebrew，恰好对，但显式更稳）。
  - 说明 bare `python3` 可能是 Xcode 3.9.6；脚本会**自动绕行**到装了依赖的解释器，无需手动改命令。
  - `INVEST_WIKI_PY=/path/to/python3` 覆盖逃生口。
  - media-fetch 注明：Apple Podcasts 路径纯标准库、任意解释器可跑，不触发绕行。

### 冒烟测试：`skills/_shared/eval/smoke_interp.py`

匹配现有 `smoke_*.py` 风格。不触发真 execv（测内部决策）：
- `_have_locally(["os","sys"])` → True；`_have_locally(["__definitely_absent__"])` → False。
- `_probe(sys.executable, ["os"])` → True；`_probe(sys.executable, ["__absent__"])` → False。
- `_candidates("INVEST_WIKI_PY")` 在设/不设环境变量时，返回的都是去重保序、且元素都是存在的可执行文件。
- `ensure_interpreter(["os"])`（必然本地有）→ 立即返回、不抛、不 exec。

## 不做 / 边界

- **不改** `douyin-distill/watch.py`、`download.py`、`SKILL.md` 里的硬编码解释器——它们传的就是对的解释器，接线后 `_have_locally` 立即 True、零 execv、无回归。改它们属 scope creep。
- 不动 `_shared/webtools/*.py`（本任务只点名 asr + media-fetch；它们目前由各 skill import 或另有调用约定，单独评估）。
- 不碰 `wiki/`。本改动是代码，不触发 L1/L2/L3 数据纪律（那是 wiki 数字写入纪律）。

## 验收（每 phase 带检查）

- **P1 helper**：`python3.14 skills/_shared/eval/smoke_interp.py` 全绿；`/usr/bin/python3` 下 import interp 不报错（3.9.6 兼容）。
- **P2 transcribe 接线**：`python3 skills/asr/scripts/transcribe.py <短clip>`（bare python3，由 `say` 生成几秒语音）→ 末行 `TRANSCRIPT_PATH=...`，产物 md 含逐字稿。证明 Xcode python → 自动重入 homebrew python → 全链路跑通。
- **P3 fetch 接线**：
  - Apple Podcasts：`python3 fetch.py <podcast-url>` 仍在 bare python3（不重入）跑通（或离线场景下证明 detect→无 playwright 要求路径）。
  - Douyin：`python3 fetch.py <douyin-url>` 观察 stderr 出现 playwright 启动（证明已重入 homebrew python），实际下载成功或因 signed-url 时效失败均可接受（关键是解释器已切换、playwright import 成功）。
- **P4 文档**：4 个 md 更新，措辞与现有风格一致。
- **回归**：`watch.py` / `download.py` 调用路径不回归（传 homebrew/3.14 → 零 execv）。

## Git

feature 分支 `infra/skill-interpreter-reexec`（off `main`@2e97f7a）。逐 phase 独立 commit。Gate 2 review `main..HEAD` diff。用户说「合」才 merge + push。commit message 结尾带 Co-Authored-By。

---

## Gate 1 review 结论与修订（对抗式 subagent + 主 agent 复核）

subagent 判定「minor rework，非重设计」，核心方案（find_spec 快路 → 子进程探测 → `os.execv` 重入 + 哨兵防循环 + fetch 仅 douyin 触发）成立，零回归声明经实测为真。以下修订纳入实现（主 agent 已逐条复核）：

1. **[改] execv 用绝对脚本路径**：subagent 提议 `os.path.abspath(__file__)` —— **复核发现其建议有误**：helper 内 `__file__` 是 `interp` 包自身，不是入口脚本。正确实现是 `os.path.abspath(sys.argv[0])`（入口脚本，cwd 不变 → 相对路径安全）。
2. **[改] `_have_locally` 的 find_spec 包 try/except**：实测 `find_spec("torch")`→None（不抛，本任务三个模块都是顶层，安全），但点状名 `find_spec("a.b")` 在父包缺失时**抛 ModuleNotFoundError**；防御性 `except (ModuleNotFoundError, ValueError): return False`。当前解释器只用 find_spec 快判（torch+funasr 真 import ~7s），真实可用性由脚本原有 `check_deps()` / `check_douyin_deps()`（真 import）兜底——非对称是有意的。
3. **[改] glob 收紧为 `python3.1[0-9]`**：实测 `/opt/homebrew/bin/python3.1*` 会匹配到 `python3.14-config`（非解释器）；收紧避免无效探测。realpath 去重会把 `python3.14` 与 `/opt/homebrew/bin/python3` 折叠。
4. **[改] 落 `_shared` 子包而非顶层平铺模块**：复核确认 `_shared` 下所有**被 import** 的成员都是带 `__init__.py` 的子包（`marketdata`/`webtools`/`verify`），无顶层平铺 `.py` 先例（`eval`/`hooks` 是直接运行非 import）。故落 `skills/_shared/interp/__init__.py`，导出 `ensure_interpreter`，调用方 `from interp import ensure_interpreter`，与 `from webtools import fetch` 同构，规避平铺模块的 `sys.path` 影子碰撞。
5. **[改] transcribe.py 把 ensure_interpreter 移到 `parse_args()` 之后**：`--help` / 错参在 bare python3 下不必先付 ~7s 重入，argparse 先响应；与 fetch.py 顺序对称。
6. **[改] 重入前打 stderr 提示**：`→ 当前解释器缺 X，切到 <cand> 重跑…`（仅 stderr，绝不污染 `TRANSCRIPT_PATH=`/`MEDIA_PATH=` stdout 末行契约），避免 7s 探测期看着像卡死。
7. **[加] shared@N=2 与 shebang 的取舍说明**：shebang 失效因文档调用是 `python3 script.py`（显式解释器，shebang 被忽略）；env-only / docs-only 不满足「开箱即用」。inline 两段是真竞品，但 auto-memory 已记此为「反复踩的坑」、第三个调用方可期，且可被 eval 覆盖——故落 `_shared` 共享。
8. **[加] smoke 负路径断言**：`_have_locally(["a.b.absent"])`→False（守 #2）、`_candidates` 不含 `*-config`（守 #3）。
9. **[记] 哨兵环境变量泄漏给子进程**：execv 前设的 guard 会被后续子进程继承；transcribe 只 spawn ffmpeg（非 python，无害），watch.py 扇出时跑在 homebrew python 不设 guard。记录不工程化。
10. **[复核为真] 零回归**：`watch.py`(PY=/opt/homebrew/bin/python3) / `download.py`(python3.14) 调用方依赖齐全 → `_have_locally` 立即 True → 零 execv 零探测。stdout 契约与 `run_capture` 反向扫描不受影响。
