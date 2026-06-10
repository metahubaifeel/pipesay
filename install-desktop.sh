#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APP_DIR"
chmod +x "$DIR/run.sh"
sed "s|@INSTALL_DIR@|$DIR|g" "$DIR/pipesay.desktop" > "$APP_DIR/pipesay.desktop"
update-desktop-database "$APP_DIR" 2>/dev/null || true
echo "已安装: $APP_DIR/pipesay.desktop"
echo "Exec=$DIR/run.sh"
echo "在应用菜单搜索: PipeSay"
