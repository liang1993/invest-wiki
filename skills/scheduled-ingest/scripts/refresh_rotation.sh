#!/bin/sh
# 申万行业轮动: 拉数缓存 + 出图。launchd 盘后调用, 也可手动跑。
# launchd 不读 shell profile, 故 python 用绝对路径(带 akshare 的 homebrew python)。
PY=/opt/homebrew/bin/python3
DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="$HOME/Downloads/invest-charts"
mkdir -p "$OUT"
LOG="$OUT/refresh.log"
{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') refresh start ==="
  "$PY" "$DIR/fetch_sw_indices.py" && "$PY" "$DIR/chart_industry_rotation.py"
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') refresh done (exit $?) ==="
} >> "$LOG" 2>&1
