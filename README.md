# Coco Dictation

Linux 桌面语音转文字工具：对着麦克风说话，实时出字，停录定稿，自动复制。

## 选哪个版本

| 分支 / 标签 | 说明 |
|-------------|------|
| **`master`** / **`v1.3-stable`** | 稳定版，日常推荐（当前满意版） |
| **`experiment/drag-drop`** / **`v1.3-lab`** | Lab：拖动手柄 + Wayland 复制 + 与稳定版相同的麦/录音修复 |

```bash
# 稳定版
git checkout master   # 或 git checkout v1.2-stable

# Lab 拖放实验版
git checkout experiment/drag-drop
```

## 新电脑安装（Linux）

```bash
git clone https://github.com/metahubaifeel/coco-dictation.git
cd coco-dictation
git checkout v1.3-stable          # 稳定版（推荐）
# git checkout experiment/drag-drop  # 或 Lab 版

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Lab 版额外依赖
# .venv/bin/pip install -r requirements-lab.txt

# Soniox API Key（二选一）
echo "你的KEY" > ~/.soniox_key
# 或 cp your-key.txt .soniox_key

chmod +x run.sh
./run.sh
```

Lab 版用 `./run-lab.sh`（可与稳定版并行，PID/日志独立）。

## 本地 Whisper（可选）

```bash
.venv/bin/pip install -r requirements-local.txt
```

## 桌面快捷方式

```bash
# 编辑 .desktop 里 Exec= 路径为本机 clone 路径，然后：
cp coco-dictation.desktop ~/.local/share/applications/
# Lab: cp coco-dictation-lab.desktop ~/.local/share/applications/
```

## 版本标签

- `v1.3-stable` — 修复录音卡顿/麦克风异常检测、按钮反馈、`--test-ui` 自检
- `v1.3-lab` — Lab 实验版（含 v1.3 稳定版修复 + 拖放/复制）
- `v1.2-stable` — 实时滚动、复制实时、本地 Whisper 说明
- `v1.1-stable` — 实时转写 UX 稳定版
- `v1.0-stable` — 早期稳定版
