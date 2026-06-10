#!/usr/bin/env bash
# 安装 Lab 版到应用菜单（与稳定版并列）
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APP_DIR"
chmod +x "$DIR/run-lab.sh"
sed "s|@INSTALL_DIR@|$DIR|g" "$DIR/pipesay-lab.desktop" > "$APP_DIR/pipesay-lab.desktop"
update-desktop-database "$APP_DIR" 2>/dev/null || true
echo "已安装: $APP_DIR/pipesay-lab.desktop"
echo "Exec=$DIR/run-lab.sh"
echo "在应用菜单搜索: PipeSay Lab"
