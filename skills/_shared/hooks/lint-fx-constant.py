#!/usr/bin/env python3
"""PostToolUse hook：wiki 正文硬编码汇率常量告警（warn-only）

**为什么需要**：2026-07-28 复盘——腾讯页写死 `1 RMB = 1.08 HKD`、小米页 1.087、
美团页曾写 0.92（方向反了）。查官方中间价，这三个值**在各自成文当天就已经错了**
（2026-05-13 实为 1.1441、05-27 实为 1.1475），导致港币计价 EPS 与四档锚点系统性
低估 6-7%。同一根因在三页独立发生三次 → 不是个人疏忽，是缺机械拦截点。

硬编码汇率的危险在于**静默衰减**：写下那天可能对，几个月后一定错，而错了不报警，
且改动后的数字仍然自洽，肉眼与 L1 自检都极难发现。

**本 lint 不禁止提汇率**，只要求汇率断言必须带时点。两条触发规则：
  1. 出现汇率断言但**同行/上一行没有日期** → 无法判断是否过期 → 告警
  2. 出现**已知陈旧值**（1.08/1.087/1.09/0.92 这几个历史踩坑值）→ 告警

修法：改用 `skills/_shared/marketdata/fx.py`（官方中间价唯一来源），并把换算移到
计算链末端只做一次（建模用报表货币，展示用港币）。见 AGENTS.md「多币种口径规则」。

退出码：0 通过 / 1 非阻断警告 / 2 阻断。现为 warn-only（exit 1）。

双入口：无 argv → 读 stdin JSON（PostToolUse）；有 argv → 每个 argv 当 wiki 文件路径。

注册：python3 "$CLAUDE_PROJECT_DIR/skills/_shared/hooks/lint-fx-constant.py"
"""

import json
import os
import re
import sys

SKIP_BASENAMES = {"log.md", "index.md"}

# 历史上真实踩过坑的陈旧值（CNY↔HKD 方向）。命中即告警，无论有无日期。
KNOWN_STALE = {"1.08", "1.087", "1.09", "0.92"}

# 汇率断言——只认高精度形态，避免把"换算倍数""双币种 EPS 并列"误判为汇率：
#   ① 显式单位等式：1 RMB = 1.1544 HKD / 1 人民币 ≈ 1.15 港币（含反向）
#   ② 币种对记法后紧跟数字：HKD/CNY 0.866、RMB→HKD 1.1544
#   ③「汇率」二字后 ≤4 字符内紧跟数字：汇率 1.1544 / 汇率为 0.866
# 三者均再过一道"数值落在真实汇率区间"的过滤（见 _in_fx_band）。
FX_PATTERNS = [
    re.compile(r"1\s*(?:个)?\s*(人民币|RMB|CNY)\s*[≈=:：]\s*(\d\.\d{2,4})\s*(港[币元]|HKD)"),
    re.compile(r"1\s*(?:个)?\s*(港[币元]|HKD)\s*[≈=:：]\s*(\d\.\d{2,4})\s*(人民币|RMB|CNY)"),
    re.compile(r"(?:HKD\s*/\s*CNY|CNY\s*/\s*HKD|港[币元]\s*/\s*人民币|人民币\s*/\s*港[币元])"
               r"[^。\n]{0,6}?(\d\.\d{2,4})"),
    re.compile(r"(?:RMB|人民币)\s*(?:→|->|兑)\s*(?:HKD|港[币元])[^。\n]{0,6}?(\d\.\d{2,4})"),
    re.compile(r"汇率[^\d\n]{0,4}(\d\.\d{2,4})"),
]

# 真实汇率区间：CNY↔HKD 约 0.86 / 1.15；CNY↔USD 约 6.8。区间外的数字（换算倍数、
# 每股收益、利润率等）一律不当汇率处理。
FX_BANDS = ((0.80, 0.95), (1.05, 1.30), (6.0, 8.0))


def _in_fx_band(num: str) -> bool:
    v = float(num)
    return any(lo <= v <= hi for lo, hi in FX_BANDS)

DATE_RE = re.compile(r"20\d{2}\s*[-/年]\s*\d{1,2}")
# 已被显式标注为"旧值/已订正"的行不再告警（避免历史留痕反复报）
EXEMPT_RE = re.compile(r"更正|订正|校正|已修|陈旧|过时|旧汇率|错误|~~|历史观察|曾写|前值")


def _numbers(line):
    out = []
    for pat in FX_PATTERNS:
        for m in pat.finditer(line):
            for g in m.groups():
                if g and re.fullmatch(r"\d\.\d{2,4}", g) and _in_fx_band(g):
                    out.append(g)
    return out


def lint_file(fp):
    """返回告警字符串（None = 无问题 / 不适用）。"""
    if not fp or not re.search(r"wiki/.+\.md$", fp):
        return None
    if os.path.basename(fp) in SKIP_BASENAMES:
        return None
    if not os.path.exists(fp):
        return None
    try:
        lines = open(fp, encoding="utf-8").read().split("\n")
    except Exception:
        return None

    hits = []
    for i, line in enumerate(lines):
        nums = _numbers(line)
        if not nums:
            continue
        if EXEMPT_RE.search(line):
            continue
        ctx = line + ("\n" + lines[i - 1] if i else "")
        stale = [n for n in nums if n in KNOWN_STALE]
        if stale:
            hits.append((i + 1, f"已知陈旧值 {'/'.join(sorted(set(stale)))}"))
        elif not DATE_RE.search(ctx):
            hits.append((i + 1, f"汇率 {'/'.join(sorted(set(nums)))} 未标时点"))

    if hits:
        detail = "；".join(f"L{ln}: {why}" for ln, why in hits[:5])
        more = f"（另有 {len(hits) - 5} 处）" if len(hits) > 5 else ""
        return (f"⚠️ 汇率 lint（warn-only）：{os.path.relpath(fp)} {detail}{more}。"
                f"硬编码汇率会静默衰减——改用 skills/_shared/marketdata/fx.py 取当日中间价，"
                f"并把换算移到计算链末端只做一次（见 AGENTS.md「多币种口径规则」）。")
    return None


def main():
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
