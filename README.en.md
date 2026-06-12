# PipeSay

**Speak on Linux. See words land.**

[中文 README](README.md)

PipeSay is a real-time speech-to-text app for Linux desktops: speak into the mic, watch words appear live in a small window, then stop to finalize and auto-copy to the clipboard. The **Pipe** in the name nods to **PipeWire**—on Wayland, pipe your voice straight into your workflow.

<p align="center">
  <img src="docs/assets/demo-real.gif" alt="PipeSay demo: speak → live text → copy on stop" width="520">
</p>

---

## UI at a glance

| Ready | Live transcription (Soniox RT) | Stop · finalize · auto-copy |
|:---:|:---:|:---:|
| ![Idle](docs/assets/demo-idle.png) | ![Live](docs/assets/demo-live.png) | ![Done](docs/assets/demo-done.png) |
| Mic level meter; Space to start/stop | **Live** pane streams partial/final tokens; on Wayland, copy uses `wl-copy` | **Result** pane holds finalized lines; auto-copy when enabled |

**How it maps to the code:**

- **Input path**: PipeWire capture → resample to 16 kHz → Soniox WebSocket streaming tokens
- **UI split**: `live_frame` shows in-progress partial/final text only; `text_area` appends finalized lines after you stop
- **Session isolation**: each recording gets a fresh `_rt_token` so stale WebSocket callbacks cannot bleed into the current UI
- **Wayland**: on stop (and “copy live”), writes both the Tk clipboard and `wl-copy` (use Ctrl+V in Cursor / browsers)

---

## Why this project?

Dictation is not new—Whisper, cloud APIs, and OS dictation all exist. On **Linux + Wayland**, I still wanted:

- A small always-on window with **live text** (not “record first, wait later”)
- Stop → finalize → **one-click copy** (with `wl-copy` on Wayland)
- UI and shortcuts I control, not tied to one desktop environment
- Experimental features (e.g. drag handles) on a **Lab branch**, without destabilizing daily use

PipeSay is not “the world’s first STT tool.” It is **a dictation app shaped by my own keyboard habits**. The stable branch is what I use every day; fixes for real bugs (mic stuck at `-32768`, recording stutter, status bar covering button feedback) are in the code and release notes.

---

## Quick start

**Use `master` or the latest stable tag `v1.4-stable`.**

```bash
git clone https://github.com/metahubaifeel/pipesay.git
cd pipesay
# Already on master by default; or pin a release:
# git checkout v1.4-stable

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Soniox API key (real-time cloud STT — register at soniox.com, usage-based billing)
# Any one of: in-app **Set Key** button, or:
echo "YOUR_KEY" > ~/.soniox_key
# or: export SONIOX_API_KEY=YOUR_KEY

chmod +x run.sh install-desktop.sh
./run.sh
```

**App menu entry:** `./install-desktop.sh` (writes your local clone path automatically—no hand-editing `.desktop` files)

On Wayland, install `wl-copy` (usually from the `wl-clipboard` package). Without it, Ctrl+V in some apps (Cursor, browsers) may not see the clipboard.

### Optional: local Whisper

```bash
.venv/bin/pip install -r requirements-local.txt
```

### Lab build (drag-handle experiment)

`requirements-lab.txt` and `run-lab.sh` live on the **Lab branch** only:

```bash
git fetch origin experiment/drag-drop
git checkout experiment/drag-drop   # or tag v1.4-lab
.venv/bin/pip install -r requirements-lab.txt
./run-lab.sh
./install-desktop.sh
```

Lab and stable use separate PID files and logs—you can run both at once.

---

## Branches & tags

| Branch / tag | Notes |
|--------------|-------|
| **`master`** / **`v1.4-stable`** | Stable, recommended daily driver (PipeSay rebrand + Wayland clipboard) |
| `experiment/drag-drop` / **`v1.4-lab`** | Lab: draggable handle on the live pane |
| `v1.3-stable` / `v1.3-lab` | Pre-rebrand snapshot (Coco Dictation era), historical reference |
| `v1.0.0` | First public release under the PipeSay name |

---

## Requirements

- Linux (Wayland or X11)
- Python 3.10+
- Microphone (PipeWire / PulseAudio)
- [Soniox](https://soniox.com/) API key (real-time cloud STT; online; billed by the provider)
- Wayland recommended: `wl-clipboard` (provides `wl-copy`)

### Known limitations

- **Mic routing** was validated on some ACP devices (e.g. `hw_acp63`); other machines use PipeWire’s default device—behavior varies by hardware.
- **On recognition failure**, debug WAVs may be written under `~/.local/share/pipesay/` (local only—mind privacy).
- **Real-time STT depends on Soniox cloud**; local Whisper is an optional offline add-on, not real-time, and loads slowly the first time.
- Do not run `revert-ui.sh` by mistake—it rolls `dictation.py` back to a very old `v1.1-stable` UI.

---

## Self-check

```bash
.venv/bin/python dictation.py --test-mic 3
.venv/bin/python dictation.py --test-rt-e2e    # requires ~/.soniox_key
.venv/bin/python dictation.py --test-ui        # runs without a key
```

CI runs `--test-ui` on push (see `.github/workflows/ui-smoke.yml`).

---

## License

MIT — see [LICENSE](LICENSE).
