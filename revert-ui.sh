#!/usr/bin/env bash
# 回到 v1.1-stable 界面与逻辑（功能验证过的版本）
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
git checkout v1.1-stable -- dictation.py
echo "已恢复 dictation.py 到 v1.1-stable。请重新打开应用。"
