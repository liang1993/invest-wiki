#!/usr/bin/env bash
# 一键接线（幂等）—— 每个 clone / 换机 / 接入新 harness 跑一次，把 README 与
# skills/_shared/hooks/README.md 里散落的"本地接线"步骤收敛成一条命令。
#
#   bash scripts/bootstrap.sh
#
# 做四件事：① git pre-commit 隐私闸门 ② 重建 .claude/skills 符号链接
#          ③ 刷新 AGENTS.md skill 索引块 ④ 检查 python 依赖。
# 各 harness 鉴权/模型 + verify-cli 配置见 docs/harness-setup.md。
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

echo "== 1/4 git pre-commit 隐私闸门 =="
git config core.hooksPath skills/_shared/hooks
echo "   core.hooksPath = $(git config --get core.hooksPath)"

echo "== 2/4 重建 .claude/skills 符号链接（遍历 skills/ 排除 _shared）=="
mkdir -p .claude/skills
# 只删符号链接，绝不碰真实文件/目录
find .claude/skills -maxdepth 1 -type l -delete 2>/dev/null || true
n=0
for d in skills/*/; do
  name="$(basename "$d")"
  [ "$name" = "_shared" ] && continue
  [ -f "${d}SKILL.md" ] || continue
  ln -sf "../../skills/$name" ".claude/skills/$name"
  n=$((n + 1))
done
echo "   重建 $n 个 skill 链接"

echo "== 3/4 刷新 AGENTS.md skill 索引块 =="
python3 scripts/gen_skill_index.py

echo "== 4/4 python 依赖检查 =="
miss=""
for m in akshare pandas requests pypdf; do
  if python3 -c "import $m" 2>/dev/null; then
    echo "   ✓ $m"
  else
    echo "   ✗ $m（必需）"
    miss="$miss $m"
  fi
done
for m in trafilatura pdfplumber; do
  if python3 -c "import $m" 2>/dev/null; then
    echo "   ✓ $m（可选）"
  else
    echo "   – $m（可选：缺则 webtools 降级 bs4/pypdf，质量略低）"
  fi
done
if [ -n "$miss" ]; then
  echo "   → 安装缺失必需项：pip install --break-system-packages$miss"
fi

echo "== bootstrap 完成。各 harness 鉴权/模型 + verify-cli(llm.json) 配置见 docs/harness-setup.md =="
