# PipeSay 发文包（复制即用）

素材目录：`docs/assets/` 与 `docs/assets/social/`

重新生成配图：

```bash
.venv/bin/pip install pillow
.venv/bin/python scripts/generate_readme_assets.py
.venv/bin/python scripts/generate_social_assets.py
```

---

## 素材对照表

| 文件 | 尺寸 | 用在哪 |
|------|------|--------|
| `docs/assets/demo-real.gif` | 960×1427 | X / 即刻 / GitHub 动图 |
| `docs/assets/social/demo-xhs.mp4` | 1080 竖屏 | **小红书视频**（优先） |
| `docs/assets/social/xhs-01-cover.png` … `xhs-05-cta.png` | 1080×1440 | 小红书图文轮播（第 2 张为使用场景） |
| `docs/assets/social/x-card.png` | 1200×675 | X 主推配图 |
| `docs/assets/launch-banner.png` | 1200×630 | X 第二条 / 知乎头图 |
| `docs/assets/launch-square.png` | 1080×1080 | 朋友圈 / 备用方图 |
| `docs/assets/demo-live.png` | — | 评论区补图 |

---

## X（Twitter）

### 主推帖（带图）

**配图：** `docs/assets/social/x-card.png`（或 `launch-banner.png` + `demo-real.gif` 二选一，别一次塞太多）

**正文：**

```
PipeSay — live dictation for Linux 🎙️

Speak → see words in real time → auto-copy when you stop.

Built for PipeWire + Wayland desktops. Not the first STT tool — one I shaped for daily use on Linux.

MIT licensed · https://github.com/metahubaifeel/pipesay

#Linux #OpenSource #Wayland #SpeechToText #PipeWire
```

### Thread（可选，连发 4 条）

**1/4**（附 x-card.png）

```
Shipped PipeSay — a small Linux dictation window I've been using daily.

Real-time text while you speak. Copy on stop. Works with Cursor via wl-copy on Wayland.
```

**2/4**

```
Why another STT tool?

Whisper/APIs exist. System dictation exists. On Linux + Wayland I still wanted:
• live partial text (not wait-until-done)
• auto-copy into editors
• a UI I control
```

**3/4**

```
Stack: Python + Tkinter + Soniox RT WebSocket + PipeWire

Honest limits:
• needs Soniox API key (cloud, pay-as-you-go)
• Linux only
• local Whisper optional, not real-time
```

**4/4**

```
https://github.com/metahubaifeel/pipesay

Star / issue welcome if you're on Linux. Lab branch experiments with drag handles.
```

---

## 小红书

### 方案 A：视频（推荐）

**视频：** `docs/assets/social/demo-xhs.mp4`  
**封面：** `docs/assets/social/xhs-01-cover.png`（上传时选自定义封面）

**标题：**

```
Linux 小窗听写｜Web Coding、上课、看课都能用 PipeSay 了
```

**正文：**

```
不是又一个「录完再等」的听写工具。
PipeSay 是 Linux 上常驻的小窗——**边说边出字**，停录自动复制。

我每天都在用的三个场景 👇

💻 **Web Coding / Vibe Coding**
Cursor 旁边挂着 PipeSay，思路来了直接说，
实时区出字 → 停录 → Ctrl+V 贴进编辑器。
不用为了打一行字打断 flow。

🎓 **上课、听讲座、开组会**
网课或线下分享，眼睛和耳朵跟着讲者走，
口述笔记实时变文字，比低头狂敲键盘轻松很多。

📺 **看网课、刷视频、录屏做笔记**
小窗一直开着，边看边把想法说出来；
录屏做分享、口述旁白也能实时出字，
不用暂停 → 切窗口 → 打字 → 再找回进度。

——
Linux · Wayland · PipeWire · MIT 开源
需要 Soniox API Key（云端实时，按量计费）
Wayland 建议装 wl-clipboard

GitHub：github.com/metahubaifeel/pipesay

#Linux #程序员 #开源项目 #效率工具 #语音转文字 #WebCoding #Cursor #Wayland
```

### 方案 B：图文轮播（5 张）

按顺序上传：

1. `xhs-01-cover.png` — 封面
2. `xhs-02-scenarios.png` — **三个使用场景**（Web Coding / 上课 / 看课）
3. `xhs-03-live.png` — 实时转写
4. `xhs-04-done.png` — 停录复制
5. `xhs-05-cta.png` — GitHub + 免责

**标题**（偏场景，二选一）：

```
Linux 小窗听写｜Web Coding、上课、看课都能用 PipeSay 了
```

或短一点：

```
Web Coding 不用狂敲键盘了｜Linux 听写小工具开源
```

**正文**用上面「方案 A」同一段。

---

## 即刻

**配图：** `demo-real.gif`

```
发布了 PipeSay 🎙️

Linux 桌面实时听写：
说话 → 实时出字 → 停录自动复制

Wayland 下走 wl-copy，Cursor 里 Ctrl+V 就能贴。
不是第一个 STT，是在 PipeWire + Wayland 上按自己习惯打磨的 MIT 开源。

https://github.com/metahubaifeel/pipesay

#Linux #开源 #Wayland #语音转文字
```

---

## V2EX

**标题：** `[分享] PipeSay - Linux Wayland 桌面实时听写，MIT 开源`

**正文：**

```
在 Linux + Wayland 上写东西，想要常驻小窗、实时出字、停录复制的听写工具。
Whisper / 系统听写 / 各类 API 都试过，总有一两块不顺手，就自己做了 PipeSay。

• Soniox 实时转写（需 API Key）
• 停录定稿 + 自动复制，Wayland 走 wl-copy
• 空格开始/停止，PipeWire 采集
• 可选本地 Whisper（录完识别，非实时）

https://github.com/metahubaifeel/pipesay
License: MIT

踩过的坑写进代码了：麦克风 -32768、录音卡顿、Wayland 剪贴板等。
欢迎同 Linux 桌面的朋友试用提 issue。
```

配图：`demo-real.gif` 或 `demo-live.png`

---

## 知乎（想法）

**配图：** `launch-banner.png` + `demo-live.png`

```
为什么又在 Linux 上做一个听写工具？

听写不新鲜，但 Linux + Wayland 上「实时出字 + 一键复制进 Cursor」
这个组合，用起来顺手的并不多。

PipeSay 名字来自 PipeWire——把声音说进工作流。
小窗常驻，Soniox 实时 WebSocket，停录走 wl-copy。

MIT 开源：https://github.com/metahubaifeel/pipesay

需要 Soniox API Key · Linux only · 本地 Whisper 可选但非实时
```

---

## B 站动态

**配图：** `demo-real.gif`

```
【开源】PipeSay - Linux 桌面实时听写

Wayland + PipeWire 小工具，说话实时出字，停录复制。
自己每天在用的 MIT 项目，欢迎 Star 和 Issue。

https://github.com/metahubaifeel/pipesay
```

---

## 发布顺序建议

1. **X** — x-card.png + 主推帖（欧美时区下午更易被看到）
2. **即刻 / V2EX** — 技术向，反馈快
3. **小红书** — 视频优先，封面用 xhs-01
4. **知乎 / B 站** — 补长文或动态

---

## 必须写清楚的免责（各平台一句带过即可）

- 需要 **Soniox API Key**（soniox.com 注册，按量计费）
- **Linux only**，Wayland 推荐 `wl-clipboard`
- 非商业产品，按现状提供（as-is）
