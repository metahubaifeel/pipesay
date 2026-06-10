# PipeSay Lab

拖放实验版，与稳定版 **完全独立**。日常请继续用 [`../stt_tool`](../stt_tool)（`v1.3-stable`）。本分支标签 **`v1.3-lab`**。

## 启动

```bash
cd /home/amd/下载/dev/coco-dictation-lab
./run-lab.sh
```

或从应用菜单打开 **「PipeSay Lab」**：

```bash
./install-desktop.sh
```

## 与稳定版的区别

| | 稳定版 | PipeSay Lab |
|--|--------|-------------|
| 目录 | `stt_tool/` | `coco-dictation-lab/`（本地 worktree 名可自定） |
| 启动 | `run.sh` | `run-lab.sh` |
| PID | `pipesay.pid` | `pipesay-lab.pid` |
| 日志 | `~/.local/share/pipesay/` | `~/.local/share/pipesay-lab/` |
| 新功能 | — | 实时转写 **⋮⋮ 拖动** 手柄 |

两个版本 **可同时运行**，互不抢单实例锁。

## 拖放怎么用

1. 开始录音，等「实时转写」区有文字
2. 点 **⋮⋮ 拖动** 手柄，拖到浏览器 / 编辑器 / 聊天输入框
3. **松手** → 文字应出现在目标处

备用方案（拖动开始时已自动复制到剪贴板）：

- **Wayland**：优先 `wl-copy`；部分应用（Cursor、浏览器）请 **Ctrl+V**
- **Discord** 等 Electron 应用：拖放通常可直接用

## 依赖

```bash
.venv/bin/pip install -r requirements-lab.txt
```

## 与 v1.3-stable 的关系

Lab 分支在 `experiment/drag-drop` 上迭代；麦克风异常、录音卡顿等修复与稳定版同步。满意后再考虑合并或发新 tag。

## 移除 worktree（可选）

```bash
cd /home/amd/下载/dev/stt_tool
git worktree remove ../coco-dictation-lab
```
