#!/bin/bash
# invest-wiki 摄入辅助脚本
# 用法：
#   ./scripts/ingest.sh report 研报文件.pdf    # 摄入研报
#   ./scripts/ingest.sh article 文章.md        # 摄入文章
#   ./scripts/ingest.sh note 笔记.md           # 摄入笔记
#   ./scripts/ingest.sh url https://...        # 摄入网页（需要在 Claude Code 中处理）

set -e

WIKI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TYPE="$1"
SOURCE="$2"

if [ -z "$TYPE" ] || [ -z "$SOURCE" ]; then
    echo "用法: $0 <report|article|note|url> <文件路径或URL>"
    exit 1
fi

case "$TYPE" in
    report)
        TARGET_DIR="$WIKI_ROOT/raw/reports"
        ;;
    article)
        TARGET_DIR="$WIKI_ROOT/raw/articles"
        ;;
    note)
        TARGET_DIR="$WIKI_ROOT/raw/notes"
        ;;
    url)
        echo "URL 摄入请在 Claude Code 中执行："
        echo "  cd $WIKI_ROOT && claude"
        echo "  然后输入：请摄入这篇文章 $SOURCE"
        exit 0
        ;;
    *)
        echo "未知类型: $TYPE（支持 report/article/note/url）"
        exit 1
        ;;
esac

if [ ! -f "$SOURCE" ]; then
    echo "文件不存在: $SOURCE"
    exit 1
fi

FILENAME="$(basename "$SOURCE")"
cp "$SOURCE" "$TARGET_DIR/$FILENAME"
echo "已复制到 $TARGET_DIR/$FILENAME"
echo ""
echo "下一步：在 invest-wiki 目录启动 Claude Code 执行摄入："
echo "  cd $WIKI_ROOT && claude"
echo "  然后输入：请摄入 raw/${TYPE}s/$FILENAME"
