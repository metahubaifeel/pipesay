#!/usr/bin/env bash
# 安装 Lab 版到应用菜单（与稳定版并列）
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APP_DIR"
chmod +x "$DIR/run-lab.sh"
cp "$DIR/coco-dictation-lab.desktop" "$APP_DIR/"
update-desktop-database "$APP_DIR" 2>/dev/null || true
echo "已安装: $APP_DIR/coco-dictation-lab.desktop"
echo "在应用菜单搜索: 语音转文字 Lab"
