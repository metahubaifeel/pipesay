# PipeSay

**Speak on Linux. See words land.**

PipeSay 是一款面向 Linux 桌面的实时语音转文字工具：对着麦克风说话，文字即时出现在窗口里；停录定稿，自动复制到剪贴板。名字里的 **Pipe** 来自日常用的 **PipeWire**——在 Wayland 桌面上，把声音顺畅地「说」进你的工作流。

---

## 为什么做这个项目？

听写并不新鲜，Whisper、各类云端 API、系统听写早就存在。但在 **Linux + Wayland** 上，我仍想要一个：

- 常驻小窗、**实时出字**（不是录完再等）
- 停录即定稿、**一键复制**
- 自己掌控 UI 和快捷键，而不是绑死在某个桌面环境
- 实验功能（拖动手柄、Wayland 剪贴板）放在 **Lab 分支**，不拖累日常稳定版

PipeSay 不是「世界上第一个 STT」，而是 **按我自己的键盘习惯打磨出来的听写工具**。稳定版每天在用；踩过的坑（麦克风 `-32768`、录音卡顿、状态栏盖住按钮反馈）都写进了代码和标签里。

---

## 快速开始

```bash
git clone https://github.com/metahubaifeel/pipesay.git
cd pipesay
git checkout v1.3-stable

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Soniox API Key（实时转写）
echo "你的KEY" > ~/.soniox_key

chmod +x run.sh
./run.sh
```

**应用菜单：** `./install-desktop.sh`（安装前请把 `pipesay.desktop` 里的 `Exec=` 改成你的 clone 路径）

### 可选：本地 Whisper

```bash
.venv/bin/pip install -r requirements-local.txt
```

### Lab 版（拖放实验）

```bash
git checkout experiment/drag-drop   # 或标签 v1.3-lab
.venv/bin/pip install -r requirements-lab.txt
./run-lab.sh
```

Lab 与稳定版 PID / 日志独立，可同时运行。

---

## 分支与标签

| 分支 / 标签 | 说明 |
|-------------|------|
| `master` / `v1.3-stable` | 稳定版，日常推荐 |
| `experiment/drag-drop` / `v1.3-lab` | Lab：实时区拖动手柄 + Wayland `wl-copy` 备用复制 |

---

## 环境

- Linux（Wayland 或 X11）
- Python 3.10+
- 麦克风（PipeWire / PulseAudio）
- [Soniox](https://soniox.com/) API Key（实时云端转写）

---

## 自检

```bash
.venv/bin/python dictation.py --test-mic 3
.venv/bin/python dictation.py --test-rt-e2e
.venv/bin/python dictation.py --test-ui
```

---

## License

MIT（见仓库内 LICENSE 文件；若尚未添加，launch 后补全。）

---

*Built on Linux, for people who type with their voice.*
