# Coco Dictation Lab

拖放实验版，与稳定版 **完全独立**。日常请继续用 [`../stt_tool`](../stt_tool)（`v1.3-stable`）。本分支标签 **`v1.3-lab`**。

## 启动

```bash
cd /home/amd/下载/dev/coco-dictation-lab
./run-lab.sh
```

或从应用菜单打开 **「语音转文字 Lab」**（需自行安装 desktop 文件，见下）。

### 安装菜单快捷方式（可选）

```bash
./install-desktop.sh
# 或手动：cp coco-dictation-lab.desktop ~/.local/share/applications/
```

## 与稳定版的区别

| | 稳定版 `stt_tool` | Lab 实验版 |
|--|-------------------|------------|
| 目录 | `stt_tool/` | `coco-dictation-lab/` |
| 启动 | `run.sh` | `run-lab.sh` |
| PID | `coco-dictation.pid` | `coco-dictation-lab.pid` |
| 日志 | `~/.local/share/coco-dictation/` | `~/.local/share/coco-dictation-lab/` |
| 新功能 | — | 实时转写 **⋮⋮ 拖动** 手柄 |

两个版本 **可同时运行**，互不抢单实例锁。

## 拖放怎么用

1. 开始录音，等「实时转写」区有文字
2. 点 **⋮⋮ 拖动** 手柄，拖到浏览器 / 编辑器 / 聊天输入框
3. **松手** → 文字应出现在目标处

备用方案（拖动开始时已自动复制到剪贴板）：

- 若目标应用不接受拖放 → **Ctrl+V** 粘贴
- 或点 **「复制实时」** / 停录后 **自动复制**

## 依赖安装

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-lab.txt
```

`requirements-lab.txt` 额外包含 `tkinterdnd2`（Linux XDND 跨应用拖放）。

Soniox API Key 配置方式与稳定版相同：`~/.soniox_key` 或项目内 `.soniox_key`。

## PM 验收清单

- [ ] 录音 → 实时区有字 → 拖手柄到 **浏览器文本框** → 松手插入
- [ ] 拖到 **Cursor / VS Code 编辑器**
- [ ] 空内容时拖手柄 → 提示「还没有可拖动的文字」，不崩溃
- [ ] 稳定版 `./run.sh` 仍正常，与 Lab 并行无冲突

## 桌面环境说明

- **X11**：跨应用文本拖放成功率较高
- **Wayland**（当前常见默认）：部分应用可能 **只接受粘贴、不接受跨窗拖放**。此时状态栏会提示「文字已在剪贴板，可 Ctrl+V」——这是预期 fallback，不是 bug

## 分支与回退

- Git 分支：`experiment/drag-drop`（worktree 自 `v1.2-stable`）
- 实验不满意：直接继续用稳定版，删除本目录即可：

```bash
cd /home/amd/下载/dev/stt_tool
git worktree remove ../coco-dictation-lab
git branch -D experiment/drag-drop   # 可选
```

实验满意后，再决定是否 merge 回 `master`。
