# PipeSay Launch 包

**可以 launch 了。** 仓库公开、CI 绿、README 有 GIF/截图、MIT 协议、桌面入口已统一为 PipeSay。

仓库：**https://github.com/metahubaifeel/pipesay**

---

## Launch 前 30 秒自检

- [x] GitHub 公开仓库 + README
- [x] `docs/assets/` 演示 GIF + 三态截图
- [x] CI `--test-ui` 通过
- [x] 应用菜单仅 **PipeSay** / **PipeSay Lab**
- [x] 本机录一条 **15～30 秒实机演示**（`docs/assets/demo-real.gif`）
- [ ] Soniox Key 说明写清楚：**需自行注册，按量计费**

---

## 素材清单

| 文件 | 用途 |
|------|------|
| `docs/assets/demo-real.gif` | GitHub / 推特 / 即刻动图（实机录屏） |
| `docs/assets/demo-synthetic.gif` | 脚本生成的三态示意（可选，非主推） |
| `docs/assets/demo-live.png` | 实时转写截图 |
| `docs/assets/demo-done.png` | 定稿复制截图 |
| `docs/assets/launch-banner.png` | 推特/X/知乎头图（1200×630） |
| `docs/assets/launch-square.png` | 小红书/朋友圈方图（1080×1080） |

重新生成全部素材：

```bash
.venv/bin/pip install pillow
.venv/bin/python scripts/generate_readme_assets.py
```

### 实机 GIF（已就绪）

当前主推：`docs/assets/demo-real.gif`（GNOME 录屏 → ffmpeg 转 GIF）。

用 OBS / 系统录屏录 15～30 秒：打开 PipeSay → 说话 → 实时出字 → 停录 → Ctrl+V 贴进编辑器。

```bash
# mp4 或 webm 均可
ffmpeg -i 你的录屏.webm -vf "fps=12,scale=960:-1" -y docs/assets/demo-real.gif
```

---

## 核心故事（三档）

### 一句话

> **PipeSay：在 Linux Wayland 上，对着麦克风说话，字就落在屏幕上，停录自动复制。**

### 30 秒版（社交媒体）

听写不新鲜，但在 Linux + Wayland 上，我想要一个常驻小窗、**实时出字**、停录即复制的小工具。系统听写绑死在桌面环境，云端 API 又要自己搓 UI。于是有了 **PipeSay**——名字来自 **PipeWire**，把声音顺畅地说进 Cursor、浏览器和聊天框。不是世界上第一个 STT，是按我自己键盘习惯打磨出来的。**MIT 开源**，欢迎 Linux 用户试用反馈。

### 2 分钟版（知乎 / 专栏）

**背景**：每天写代码、写文档，手敲太慢，Whisper / 各类 API 也试过，但在 Wayland 桌面上总差点意思——要么没有实时出字，要么复制进 Cursor 要折腾剪贴板。

**PipeSay 做什么**：
- 小窗常驻，Soniox 实时 WebSocket，边说边出字
- 停录定稿，自动复制（Wayland 下走 `wl-copy`）
- PipeWire 采集，空格开始/停止
- Lab 分支实验拖动手柄，稳定版每天自用

**诚实边界**：
- 实时转写依赖 Soniox 云端（需 API Key）
- 本地 Whisper 可选，但是录完再识别，不是实时
- 在 AMD ACP 声卡上验证过；其他硬件表现因机器而异

**开源**：https://github.com/metahubaifeel/pipesay

---

## 各渠道文案（复制即用）

### 即刻 / Jike

```
发布了 PipeSay 🎙️

Linux 桌面实时听写小工具：
说话 → 实时出字 → 停录自动复制
Wayland 下 wl-copy，Cursor 里 Ctrl+V 就能贴

不是第一个 STT，是在 PipeWire + Wayland 上
按自己习惯打磨的 MIT 开源项目

https://github.com/metahubaifeel/pipesay

#Linux #开源 #Wayland #语音转文字
```

配图：`demo-real.gif`

---

### 推特 / X（中英）

```
PipeSay — live dictation for Linux desktops 🎙️

Speak → see words in real time → auto-copy on stop.
Built for Wayland + PipeWire. MIT licensed.

Not the first STT tool — one shaped by daily use on Linux.

https://github.com/metahubaifeel/pipesay

#Linux #OpenSource #Wayland #SpeechToText
```

配图：`launch-banner.png` + `demo-real.gif`

---

### V2EX

**标题**：`[分享] PipeSay - Linux Wayland 桌面实时听写，开源 MIT`

**正文**：

```
在 Linux + Wayland 上写东西，想要一个常驻小窗、实时出字、停录复制的听写工具。
Whisper / 系统听写 / 各类 API 都试过，总有一两块不顺手，就自己搓了 PipeSay。

功能：
- Soniox 实时转写（需 API Key）
- 停录定稿 + 自动复制，Wayland 走 wl-copy
- 空格开始/停止，PipeWire 采集
- 可选本地 Whisper（录完识别，非实时）

GitHub：https://github.com/metahubaifeel/pipesay
License：MIT

踩过的坑都写进代码了：麦克风 -32768 卡死、录音卡顿、Wayland 剪贴板等。
欢迎同 Linux 桌面的朋友试用提 issue。
```

---

### 知乎（想法 / 文章摘要）

```
为什么又在 Linux 上做一个听写工具？

因为听写不新鲜，但 Linux + Wayland 的「实时出字 + 一键复制进 Cursor」
这个组合，用起来顺手的并不多。

PipeSay 名字来自 PipeWire——把声音说进工作流。
MIT 开源，稳定版自用，Lab 分支做拖放实验。

项目地址：https://github.com/metahubaifeel/pipesay

技术栈：Python + Tkinter + Soniox RT WebSocket + PipeWire
```

配图：`launch-banner.png` + `demo-live.png`

---

### 小红书

```
标题：Linux 党必备｜说话自动变文字 PipeSay 开源了

正文：
在 Ubuntu Wayland 上写代码写文档，
终于有一个顺手的听写小窗了 🎙️

✅ 实时出字（不是录完再等）
✅ 停录自动复制
✅ Cursor 里 Ctrl+V 直接贴
✅ MIT 开源免费

GitHub 搜 pipesay 或看主页链接
Linux only · 需要 Soniox API Key

#Linux #程序员 #开源项目 #效率工具 #语音转文字
```

配图：`launch-square.png` + 实机录屏（竖屏更好）

---

### B 站动态

```
【开源】PipeSay - Linux 桌面实时听写

Wayland + PipeWire 上的小工具，说话实时出字，停录复制。
自己每天在用的 MIT 开源项目，欢迎 Star 和 Issue。

仓库：https://github.com/metahubaifeel/pipesay
```

配图：`demo-real.gif`

---

### Discord / 社群

```
PipeSay is live — Linux live dictation, MIT OSS

🎙️ Real-time text while you speak
📋 Auto-copy on stop (wl-copy on Wayland)
🐧 Built for PipeWire desktops

https://github.com/metahubaifeel/pipesay
```

---

## 发布顺序建议

1. **GitHub** — 确认 README 首屏 `demo-real.gif` 正常
2. **即刻 / V2EX** — 技术向，反馈快
3. **推特/X** — 带 banner + GIF
4. **知乎** — 长故事版
5. **小红书 / B站** — 补一条实机录屏后再发，转化更好

---

## 必须写清楚的免责

- 需要 **Soniox API Key**（注册与费用见 soniox.com）
- **Linux only**，Wayland 推荐装 `wl-clipboard`
- 不是商业产品，按现状提供（as-is）

---

*Built on Linux, for people who type with their voice.*
