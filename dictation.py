#!/usr/bin/env python3
"""
PipeSay Lab — Linux 桌面实时语音转文字（拖放实验版）
Soniox 实时云端 / 本地 Whisper 离线
"""
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import wave
import signal
from datetime import datetime

import numpy as np
import tkinter as tk
from tkinter import scrolledtext, ttk

from ui.clipboard_util import set_clipboard
from ui.dnd_handle import DND_AVAILABLE, attach_drag_handle

try:
    from tkinterdnd2 import TkinterDnD
except ImportError:
    TkinterDnD = None

SONIOX_TARGET_RATE = 16000
CHUNK_MS = 120
SONIOX_KEY_FILE = os.path.expanduser("~/.soniox_key")
SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
APP_NAME = "PipeSay Lab"
LOG_DIR = os.path.expanduser("~/.local/share/pipesay-lab")
CONFIG_DIR = os.path.expanduser("~/.config/pipesay")
MIC_CONFIG_FILE = os.path.join(CONFIG_DIR, "mic.json")
LOG_FILE = os.path.join(LOG_DIR, "dictation.log")
PID_BASENAME = "pipesay-lab.pid"
KNOWN_MIC_LABELS = (
    ("hw_acp63__source", 48000, "内置数字麦克风 (acp63)"),
    ("hw_Generic_1__source", 44100, "模拟麦克风 (ALC257)"),
)
RAISE_SIGNAL = signal.SIGUSR1

BG = "#09090b"
PANEL = "#141416"
CARD = "#1c1c1f"
CARD2 = "#252529"
BORDER = "#2e2e33"
TEXT = "#f4f4f5"
MUTED = "#71717a"
ACCENT = "#6366f1"
ACCENT2 = "#4f46e5"
GREEN = "#22c55e"
ORANGE = "#f59e0b"
GRAY = MUTED
BTN_BG = "#ef4444"
BTN_ON = "#b91c1c"
WHITE = TEXT

_sd = None


def _sounddevice():
    """Lazy import so --test-ui can run without PortAudio on CI."""
    global _sd
    if _sd is None:
        import sounddevice as sd_mod

        _sd = sd_mod
    return _sd


def log(msg):
    os.makedirs(LOG_DIR, exist_ok=True)
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def get_soniox_key():
    key = os.environ.get("SONIOX_API_KEY")
    if key:
        return key.strip()
    for path in (
        SONIOX_KEY_FILE,
        os.path.join(os.path.dirname(__file__), ".soniox_key"),
    ):
        if os.path.exists(path):
            with open(path) as f:
                key = f.read().strip()
                if key:
                    return key
    return None


def save_soniox_key(key: str):
    """Write Soniox API key to ~/.soniox_key (mode 0600). Returns error text or None."""
    key = (key or "").strip()
    if not key:
        return "Key 不能为空"
    try:
        with open(SONIOX_KEY_FILE, "w") as f:
            f.write(key + "\n")
        os.chmod(SONIOX_KEY_FILE, 0o600)
        return None
    except OSError as exc:
        return str(exc)


def friendly_connect_error(message: str) -> str:
    msg = (message or "").lower()
    if "ssl" in msg or "eof" in msg or "handshake" in msg or "ssleof" in msg:
        return "网络 SSL 失败 — 检查 WiFi/VPN，等 10 秒后重试"
    if "name resolution" in msg or "errno -3" in msg or "name or service" in msg:
        return "DNS 解析失败 — 网络未就绪，请检查 WiFi"
    if "timeout" in msg or "timed out" in msg:
        return "连接 Soniox 超时 — 请检查网络后再试"
    if "max retries" in msg or "connectionpool" in msg:
        return "无法连接 Soniox 服务器 — 请检查网络"
    if len(message or "") > 80:
        return "网络错误 — 请检查 WiFi 后重试"
    return message or "连接失败"


def network_error_blocks_transcription(message: str) -> bool:
    """True when offline/API unreachable — async fallback won't help either."""
    msg = (message or "").lower()
    return any(
        k in msg
        for k in (
            "ssl",
            "eof",
            "ssleof",
            "name resolution",
            "errno -3",
            "max retries",
            "connection refused",
            "timed out",
            "timeout",
        )
    )


def find_other_pipesay_pid(my_basename):
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    my_pid = os.getpid()
    for name in ("pipesay.pid", "pipesay-lab.pid"):
        if name == my_basename:
            continue
        path = os.path.join(runtime, name)
        try:
            with open(path) as f:
                pid = int(f.read().strip())
        except (OSError, ValueError):
            continue
        if pid != my_pid:
            try:
                os.kill(pid, 0)
                return pid
            except OSError:
                pass
    return None


def soniox_error_is_disconnect(message: str) -> bool:
    """True for network/WS drop; False for billing/audio-quality server errors."""
    low = (message or "").lower()
    if any(
        x in low
        for x in (
            "402",
            "400",
            "408",
            "no audio",
            "decode timeout",
            "balance exhausted",
            "invalid api",
        )
    ):
        return False
    return any(
        x in low
        for x in (
            "1000",
            "ssl",
            "eof",
            "close frame",
            "connection",
            "reset",
            "name resolution",
            "recv error",
            "send error",
        )
    ) or "timed out" in low


def friendly_soniox_error(message: str) -> str:
    msg = (message or "").lower()
    if "balance exhausted" in msg:
        return "Soniox 余额不足，请登录 soniox.com 充值"
    if "invalid" in msg and "api" in msg:
        return "Soniox API Key 无效，请点「API Key」检查"
    if "408" in msg or "timeout" in msg or "decode" in msg:
        return "麦克风无有效音频（可能卡死 -32768，请停录后重试或重启 PipeWire）"
    return message or "未知错误"


def render_tokens(final_tokens, non_final_tokens):
    parts = []
    for token in final_tokens + non_final_tokens:
        text = token.get("text") or ""
        if text in ("<end>", "<fin>"):
            continue
        parts.append(text)
    return "".join(parts)


def parse_soniox_tokens(session_final_tokens, message_tokens):
    """Merge one Soniox WS response into accumulated finals + current partials."""
    non_final = []
    for token in message_tokens:
        if not token.get("text"):
            continue
        if token.get("is_final"):
            session_final_tokens.append(token)
        else:
            non_final.append(token)
    return render_tokens(session_final_tokens, non_final)


def resample_to_16k(audio, src_rate):
    if src_rate == SONIOX_TARGET_RATE:
        return audio.astype(np.int16, copy=False)
    if audio.ndim > 1:
        audio = audio[:, 0]
    n_out = max(1, int(len(audio) * SONIOX_TARGET_RATE / src_rate))
    x = np.arange(len(audio), dtype=np.float64)
    xp = np.linspace(0, len(audio) - 1, n_out)
    return np.interp(xp, x, audio.astype(np.float64)).astype(np.int16)


def discover_pipewire_sources():
    sources = []
    try:
        out = subprocess.run(
            ["pw-cli", "list-objects", "Node"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except Exception as exc:
        log(f"pw-cli failed: {exc}")
        return sources

    block = {}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("id "):
            if block.get("name") and block.get("class") == "Audio/Source":
                sources.append(block)
            block = {"id": line.split(",")[0].split()[-1]}
        elif "node.name =" in line:
            block["name"] = line.split("=", 1)[1].strip().strip('"')
        elif "media.class =" in line:
            block["class"] = line.split("=", 1)[1].strip().strip('"')
    if block.get("name") and block.get("class") == "Audio/Source":
        sources.append(block)
    return sources


def load_mic_config():
    """None = follow system; str = pinned PipeWire source name."""
    try:
        with open(MIC_CONFIG_FILE) as f:
            data = json.load(f)
        source = data.get("source")
        if source in (None, "", "system"):
            return None
        return str(source)
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def save_mic_config(source):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(MIC_CONFIG_FILE, "w") as f:
        json.dump({"source": source}, f, indent=2)
        f.write("\n")


def _friendly_mic_label(name):
    for token, rate, label in KNOWN_MIC_LABELS:
        if token in name:
            return rate, label
    return 48000, name


def list_mic_candidates():
    """First entry is follow-system; then known devices, then other sources."""
    sources = discover_pipewire_sources()
    names = {s["name"] for s in sources}
    candidates = [(None, 48000, "跟随系统")]
    seen = set()
    for token, rate, label in KNOWN_MIC_LABELS:
        for name in names:
            if token in name and name not in seen:
                candidates.append((name, rate, label))
                seen.add(name)
                break
    for src in sources:
        name = src["name"]
        if name not in seen:
            candidates.append((name, 48000, name))
            seen.add(name)
    return candidates


def resolve_mic_choice(pinned_source=None, candidate_idx=0):
    candidates = list_mic_candidates()
    if pinned_source is not None:
        for source, rate, label in candidates:
            if source == pinned_source:
                return source, rate, label
        rate, label = _friendly_mic_label(pinned_source)
        return pinned_source, rate, f"{label}（未连接）"
    return candidates[candidate_idx % len(candidates)]


def pick_mic_source(candidate_idx=0, pinned_source=None):
    if pinned_source is None:
        pinned_source = load_mic_config()
    if pinned_source is not None and candidate_idx == 0:
        return resolve_mic_choice(pinned_source=pinned_source)
    return resolve_mic_choice(pinned_source=None, candidate_idx=candidate_idx)


def apply_mic_env(source, sample_rate, label):
    if source:
        os.environ["PULSE_SOURCE"] = source
        log(f"mic source={source} rate={sample_rate} label={label}")
    else:
        os.environ.pop("PULSE_SOURCE", None)
        log("mic source=default (follow system)")


def reset_pipewire_audio():
    """Restart user PipeWire stack — often clears ACP -32768 without full reboot."""
    try:
        subprocess.run(
            [
                "systemctl",
                "--user",
                "restart",
                "pipewire",
                "pipewire-pulse",
                "wireplumber",
            ],
            capture_output=True,
            timeout=20,
            check=False,
        )
        time.sleep(1.5)
        log("pipewire stack restarted")
        return True
    except Exception as exc:
        log(f"pipewire restart failed: {exc}")
        return False


def prepare_microphone(candidate_idx=None, pinned_source=None):
    for cmd in (
        ["amixer", "-c", "1", "set", "Capture", "cap"],
        ["amixer", "-c", "1", "set", "Mic Boost", "2"],
    ):
        try:
            subprocess.run(cmd, capture_output=True, timeout=3)
        except Exception:
            pass

    if candidate_idx is None:
        if pinned_source is None:
            pinned_source = load_mic_config()
        source, sample_rate, label = resolve_mic_choice(pinned_source=pinned_source)
    else:
        source, sample_rate, label = resolve_mic_choice(
            pinned_source=None, candidate_idx=candidate_idx
        )
    apply_mic_env(source, sample_rate, label)
    return sample_rate, label


def audio_peak(audio):
    if audio.size == 0:
        return 0.0
    if audio.ndim > 1:
        audio = audio[:, 0]
    peak = int(np.abs(audio.astype(np.int32)).max())
    return peak / 32768.0


def mic_capture_stuck_min(audio):
    """True when stream is stuck at PCM -32768 (PipeWire glitch)."""
    if audio is None or audio.size == 0:
        return False
    samples = audio.reshape(-1).astype(np.int32)
    if samples.size < 64:
        return False
    return float(np.mean(samples == -32768)) > 0.9


def mic_capture_broken(audio):
    if audio is None or audio.size == 0:
        return True
    flat = audio.reshape(-1)
    if flat.size < 64:
        return False
    samples = flat.astype(np.int32)
    stuck_min = float(np.mean(samples == -32768))
    stuck_zero = float(np.mean(samples == 0))
    if stuck_min > 0.9 or stuck_zero > 0.98:
        return True
    window = samples[: min(len(samples), 4096)]
    return len(np.unique(window)) <= 2 and stuck_min > 0.5


def meter_peak(audio):
    if mic_capture_broken(audio):
        return 0.0
    return audio_peak(audio)


def prepare_audio_for_stt(audio, src_rate):
    pcm = resample_to_16k(audio, src_rate)
    if pcm.ndim > 1:
        pcm = pcm[:, 0]
    peak = int(abs(pcm).max()) if pcm.size else 0
    if peak > 28000:
        pcm = (pcm.astype(np.float32) * (26000.0 / peak)).astype(np.int16)
    return pcm


def save_debug_wav(audio, src_rate, tag="debug"):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        path = os.path.join(
            LOG_DIR, f"{tag}_{datetime.now():%Y%m%d_%H%M%S}.wav"
        )
        pcm = resample_to_16k(audio, src_rate)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SONIOX_TARGET_RATE)
            wf.writeframes(pcm.tobytes())
        log(f"saved debug wav {path} peak={audio_peak(pcm):.4f}")
        return path
    except Exception as exc:
        log(f"save debug wav failed: {exc}")
        return None


def transcribe_async_rest(audio_16k):
    import requests

    key = get_soniox_key()
    if not key:
        return "", "未配置 Soniox Key"

    if audio_16k.ndim > 1:
        audio_16k = audio_16k[:, 0]

    tf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tf.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SONIOX_TARGET_RATE)
        wf.writeframes(audio_16k.astype(np.int16).tobytes())

    hdrs = {"Authorization": f"Bearer {key}"}
    fid = tid = None
    try:
        with open(tf.name, "rb") as f:
            r = requests.post(
                "https://api.soniox.com/v1/files",
                headers=hdrs,
                files={"file": f},
                timeout=30,
            )
        if r.status_code not in (200, 201):
            return "", f"上传失败 HTTP {r.status_code}"
        fid = r.json().get("id")
        if not fid:
            return "", "上传异常"

        r = requests.post(
            "https://api.soniox.com/v1/transcriptions",
            headers=hdrs,
            json={
                "model": "stt-async-v4",
                "file_id": fid,
                "language_hints": ["zh", "en"],
                "enable_language_identification": True,
            },
            timeout=30,
        )
        if r.status_code not in (200, 201):
            return "", f"创建转录失败 HTTP {r.status_code}"
        tid = r.json().get("id")
        if not tid:
            return "", "创建转录失败"

        for _ in range(80):
            time.sleep(0.3)
            r = requests.get(
                f"https://api.soniox.com/v1/transcriptions/{tid}",
                headers=hdrs,
                timeout=10,
            )
            st = r.json().get("status")
            if st == "completed":
                break
            if st == "failed":
                return "", "Soniox 识别失败"

        r = requests.get(
            f"https://api.soniox.com/v1/transcriptions/{tid}/transcript",
            headers=hdrs,
            timeout=10,
        )
        text = r.json().get("text", "").strip()
        log(f"async transcript len={len(text)}")
        return text, None
    except Exception as exc:
        log(f"async transcript error: {exc}")
        return "", str(exc)
    finally:
        try:
            os.unlink(tf.name)
        except Exception:
            pass
        for obj, oid in (("files", fid), ("transcriptions", tid)):
            if oid:
                try:
                    requests.delete(
                        f"https://api.soniox.com/v1/{obj}/{oid}",
                        headers=hdrs,
                        timeout=5,
                    )
                except Exception:
                    pass


class SonioxRealtimeSession:
    def __init__(self, api_key, on_text, on_error, on_finished, on_ready=None):
        self.api_key = api_key
        self.on_text = on_text
        self.on_error = on_error
        self.on_finished = on_finished
        self.on_ready = on_ready
        self.audio_q = queue.Queue()
        self.pending_chunks = []
        self.final_tokens = []
        self._ws = None
        self._running = False
        self._ready = threading.Event()
        self._send_thread = None
        self._recv_thread = None
        self._aborted = False

    def abort(self):
        if self._aborted:
            return
        self._aborted = True
        self._running = False
        try:
            self.audio_q.put_nowait(None)
        except queue.Full:
            pass
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass

    def start(self):
        from websockets.sync.client import connect

        config = {
            "api_key": self.api_key,
            "model": "stt-rt-v4",
            "language_hints": ["zh", "en"],
            "enable_language_identification": True,
            "enable_endpoint_detection": True,
            "audio_format": "pcm_s16le",
            "sample_rate": SONIOX_TARGET_RATE,
            "num_channels": 1,
        }

        self._running = True
        self.final_tokens = []
        self._ws = connect(
            SONIOX_WS_URL,
            ping_interval=20,
            ping_timeout=60,
            close_timeout=10,
            open_timeout=12,
        )
        self._ws.send(json.dumps(config))
        self._ready.set()
        self._send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._send_thread.start()
        self._recv_thread.start()
        self.flush_pending()
        if self.on_ready:
            self.on_ready()
        log("soniox websocket connected")

    def push_audio(self, chunk):
        if not self._running:
            return
        if self._ready.is_set():
            self.audio_q.put(chunk)
        else:
            self.pending_chunks.append(chunk)

    def flush_pending(self):
        for chunk in self.pending_chunks:
            self.audio_q.put(chunk)
        self.pending_chunks.clear()

    def stop(self):
        if not self._running:
            return
        self._running = False
        try:
            self.audio_q.put_nowait(None)
        except queue.Full:
            pass

    def _send_loop(self):
        try:
            while True:
                chunk = self.audio_q.get()
                if chunk is None:
                    break
                if self._aborted:
                    break
                self._ws.send(chunk.tobytes())
            if not self._aborted:
                try:
                    self._ws.send(json.dumps({"type": "finalize"}))
                except Exception:
                    pass
                self._ws.send("")
                log("soniox audio stream ended")
        except Exception as exc:
            if not self._aborted:
                log(f"soniox send error: {exc}")
                self.on_error(str(exc))

    def _recv_loop(self):
        try:
            while True:
                if self._aborted:
                    break
                msg = self._ws.recv()
                if self._aborted:
                    break
                res = json.loads(msg)
                if res.get("error_code"):
                    err = f"{res['error_code']}: {res.get('error_message', '')}"
                    log(f"soniox server error: {err}")
                    if not self._aborted:
                        self.on_error(err)
                    break

                msg_tokens = res.get("tokens", [])
                text = parse_soniox_tokens(self.final_tokens, msg_tokens)
                has_partial = any(
                    t.get("text") and not t.get("is_final") for t in msg_tokens
                )
                if not self._aborted:
                    self.on_text(text, has_partial, len(text))

                if res.get("finished"):
                    final_text = render_tokens(self.final_tokens, [])
                    log(f"soniox finished len={len(final_text)} finals={len(self.final_tokens)}")
                    if not self._aborted:
                        self.on_finished(final_text)
                    break
        except Exception as exc:
            if self._aborted:
                return
            final_text = render_tokens(self.final_tokens, [])
            log(f"soniox recv error: {exc}; partial len={len(final_text)}")
            if not self._aborted:
                if self._running:
                    self.on_error(str(exc))
                elif final_text.strip():
                    self.on_finished(final_text)
                else:
                    self.on_error(str(exc))
        finally:
            try:
                self._ws.close()
            except Exception:
                pass


class DictationApp:
    def __init__(self, root):
        self.root = root
        root.title(APP_NAME)
        root.geometry("480x680")
        root.configure(bg=BG)
        root.minsize(400, 560)
        try:
            root.tk.call("wm", "class", root._w, "pipesay-lab", APP_NAME)
        except tk.TclError:
            pass

        self.recording = False
        self.audio_stream = None
        self.capture_rate = 48000
        self.mic_label = "跟随系统"
        self._mic_pinned_source = load_mic_config()
        self.mode = tk.StringVar(value="soniox")
        self.whisper_model = None
        self.soniox_session = None
        self.record_started_at = 0.0
        self.local_chunks = []
        self.peak_level = 0.0
        self.last_raw_audio = None
        self.mic_ok = False
        self.auto_copy = tk.BooleanVar(value=True)
        self.always_on_top = False
        self._shutting_down = False
        self._rt_pending = []
        self._level_pending = None
        self._rt_token = 0
        self._active_rt_token = 0
        self._finalizing_rt_token = 0
        self._finalize_timeout_id = None
        self._session_live_text = ""
        self._committed_text = ""
        self._live_follow = True
        self._mic_candidate_idx = 0
        self._mic_broken = False
        self._mic_broken_streak = 0
        self._mic_rotate_at = 0.0
        self._mic_warmup_until = 0.0
        self._mic_stuck_streak = 0
        self._mic_stuck_active = False
        self._mic_recover_attempts = 0
        self._user_status_until = 0.0
        self._mic_restarting = False
        self._last_tick = time.time()
        self._suspended = False
        self._record_watchdog_id = None
        self._long_record_warned = False
        self._idle_stuck_streak = 0
        self._idle_stuck_recover_at = 0.0
        self._sleep_listener_started = False
        self._mic_hard_recover_at = 0.0
        self._connect_epoch = 0
        self._last_record_stop_at = 0.0
        self._rt_connecting = False

        self._setup_styles()
        self._build_ui()
        self._write_pid_file()
        self._register_raise_handler()
        self.root.bind("<space>", self._on_space_key)
        self.root.after(0, self._init_background)
        self._schedule_suspend_watch()
        self._start_sleep_listener()
        log("lab app started")

    def _write_pid_file(self):
        path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), PID_BASENAME)
        try:
            with open(path, "w") as f:
                f.write(str(os.getpid()))
        except OSError as exc:
            log(f"pid file write failed: {exc}")

    def _remove_pid_file(self):
        path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), PID_BASENAME)
        try:
            os.remove(path)
        except OSError:
            pass

    def _schedule_suspend_watch(self):
        if self._shutting_down:
            return
        self.root.after(5000, self._check_suspend)

    def _release_mic_stream(self):
        if self.audio_stream:
            try:
                self.audio_stream.stop()
                self.audio_stream.close()
            except Exception:
                pass
            self.audio_stream = None
        self.mic_ok = False

    def _reset_pipewire_audio(self):
        return reset_pipewire_audio()

    def _hard_recover_mic(self, reason="mic recover"):
        if self.recording or self._shutting_down:
            return
        now = time.time()
        if now - self._mic_hard_recover_at < 45:
            return
        self._mic_hard_recover_at = now
        log(f"hard mic recover: {reason}")
        self._release_mic_stream()
        self._reset_pipewire_audio()
        if self._mic_pinned_source is not None:
            prepare_microphone(pinned_source=self._mic_pinned_source)
        else:
            prepare_microphone()
        self._mic_warmup_until = time.time() + 3.0
        self._mic_candidate_idx = 0
        self._idle_stuck_streak = 0
        self._start_mic_monitor()

    def _start_sleep_listener(self):
        if self._sleep_listener_started:
            return
        self._sleep_listener_started = True

        def run():
            def on_sleep_signal():
                try:
                    self.root.after(0, self._on_prepare_for_sleep)
                except Exception:
                    pass

            for cmd in (
                [
                    "gdbus",
                    "monitor",
                    "--system",
                    "--dest",
                    "org.freedesktop.login1",
                    "--object-path",
                    "/org/freedesktop/login1",
                ],
                ["busctl", "monitor", "org.freedesktop.login1"],
            ):
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                    )
                    for line in proc.stdout:
                        low = line.lower()
                        if "prepareforsleep" in low.replace("_", "") and "true" in low:
                            on_sleep_signal()
                    return
                except FileNotFoundError:
                    continue
                except Exception as exc:
                    log(f"sleep listener ({cmd[0]}) failed: {exc}")
                    return
            log("sleep listener unavailable (no gdbus/busctl)")

        threading.Thread(target=run, daemon=True).start()

    def _on_prepare_for_sleep(self):
        log("PrepareForSleep — release mic before suspend")
        if self.recording:
            self._emergency_stop_recording("合盖休眠 — 已自动停录")
        else:
            self._release_mic_stream()

    def _cancel_record_watchdog(self):
        tid = self._record_watchdog_id
        if tid:
            try:
                self.root.after_cancel(tid)
            except Exception:
                pass
        self._record_watchdog_id = None

    def _schedule_record_watchdog(self):
        self._cancel_record_watchdog()
        self._record_watchdog_id = self.root.after(60000, self._check_recording_safety)

    def _check_recording_safety(self):
        self._record_watchdog_id = None
        if not self.recording or self._shutting_down:
            return
        elapsed = time.time() - self.record_started_at
        if elapsed >= 7200:
            self._emergency_stop_recording("录音超过 2 小时 — 已自动停录")
            return
        if elapsed >= 3600 and not self._long_record_warned:
            self._long_record_warned = True
            self._set_status("仍在录音 — 忘记停录？按空格即可停止", ORANGE, hold_sec=8)
        self._schedule_record_watchdog()

    def _emergency_stop_recording(self, reason, save_partial=True):
        if not self.recording:
            return
        log(f"emergency stop recording: {reason}")
        self._cancel_record_watchdog()
        self.recording = False
        self.record_btn.config(text="开始录音", bg=BTN_BG)
        partial = (self._session_live_text or "").strip() if save_partial else ""
        self._abort_session()
        self._hide_live_panel()
        self.local_chunks = []
        self.peak_level = 0.0
        self._release_mic_stream()
        if partial:
            self._commit_result_text(partial)
            if self.auto_copy.get():
                self._set_clipboard(partial)
                self._set_status(
                    f"{reason} — 已保存 {len(partial)} 字并复制", GREEN, hold_sec=5
                )
            else:
                self._set_status(f"{reason} — 已保存 {len(partial)} 字", GREEN, hold_sec=5)
        else:
            self._set_status(f"{reason}", ORANGE, hold_sec=4)
        self.root.after(800, lambda: self._hard_recover_mic(reason))

    def _check_suspend(self):
        if self._shutting_down:
            return
        now = time.time()
        gap = now - self._last_tick
        self._last_tick = now

        if gap > 30 and not self._suspended:
            self._suspended = True
            log(f"suspend detected: gap={gap:.0f}s")
            self._on_resume()

        if self._suspended and gap < 10:
            self._suspended = False

        self.root.after(5000, self._check_suspend)

    def _on_resume(self):
        was_recording = self.recording
        if self.recording:
            log("auto-stop recording on resume from suspend")
            self._emergency_stop_recording("休眠恢复 — 已自动停录")
        else:
            self._release_mic_stream()

        self._mic_candidate_idx = 0
        self._mic_broken = False
        self._mic_broken_streak = 0
        self._mic_stuck_streak = 0
        self._mic_stuck_active = False
        self._mic_recover_attempts = 0
        self._idle_stuck_streak = 0

        def reinit():
            self._hard_recover_mic("resume from suspend")
            if not was_recording:
                self._set_status("休眠已恢复 — 麦克风已重新初始化", MUTED, hold_sec=3)
            log("resume: mic reinitialized")

        self.root.after(2000, reinit)

    def _register_raise_handler(self):
        def raise_window(*_):
            if self._shutting_down:
                return
            try:
                self.root.after(0, self._bring_to_front)
            except Exception:
                pass

        try:
            signal.signal(RAISE_SIGNAL, raise_window)
        except Exception as exc:
            log(f"signal register failed: {exc}")

    def _bring_to_front(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(
                200, lambda: self.root.attributes("-topmost", self.always_on_top)
            )
            self.root.focus_force()
        except Exception as exc:
            log(f"bring to front failed: {exc}")

    def _ui(self, fn):
        if threading.current_thread() is threading.main_thread():
            fn()
        else:
            self.root.after(0, fn)

    def _cancel_live_ui(self):
        pass

    def _sync_committed_from_widget(self):
        body = self.text_area.get("1.0", "end-1c")
        if body.startswith("录音时这里会实时") or body.startswith("已定稿的结果"):
            self._committed_text = ""
        else:
            self._committed_text = body
            if self._committed_text and not self._committed_text.endswith("\n"):
                self._committed_text += "\n"

    def _show_live_panel(self):
        if not self.live_frame.winfo_ismapped():
            self.live_frame.pack(fill="x", pady=(0, 10), before=self.out_head)
        self._live_follow = True
        self._set_live_display("…", partial=False)

    def _hide_live_panel(self):
        self.live_frame.pack_forget()
        self._session_live_text = ""

    def _live_at_bottom(self):
        try:
            _, y1 = self.live_text.yview()
            return y1 >= 0.98
        except tk.TclError:
            return True

    def _sync_live_follow(self):
        self._live_follow = self._live_at_bottom()

    def _set_live_display(self, text, partial=False):
        display = text if text else "…"
        if partial and text:
            display += " …"
        at_bottom = self._live_at_bottom()
        self.live_text.configure(state="normal")
        self.live_text.delete("1.0", "end")
        self.live_text.insert("1.0", display)
        if at_bottom or self._live_follow:
            self.live_text.see("end")
            self._live_follow = True
        self.live_text.configure(state="disabled")

    def _apply_live_text(self, rt_token, text, partial, text_len=0):
        if rt_token not in (self._active_rt_token, self._finalizing_rt_token):
            return
        self._session_live_text = text or ""
        self._set_live_display(self._session_live_text, partial=partial)

    def _begin_live_region(self):
        self._sync_committed_from_widget()
        self._session_live_text = ""
        self._show_live_panel()

    def _set_status(self, text, fg=MUTED, hold_sec=0):
        self.status_label.config(text=text, fg=fg)
        if hold_sec > 0:
            self._user_status_until = time.time() + hold_sec

    def _toggle_pin(self):
        self.always_on_top = not self.always_on_top
        self.root.attributes("-topmost", self.always_on_top)
        if self.always_on_top:
            self.pin_btn.config(bg=ACCENT, fg=TEXT, text="已置顶", activebackground=ACCENT2)
            self._set_status("窗口已置顶", GREEN, hold_sec=2)
        else:
            self.pin_btn.config(bg=CARD2, fg=MUTED, text="置顶", activebackground=BORDER)
            self._set_status("已取消置顶", MUTED, hold_sec=2)
        log(f"always_on_top={self.always_on_top}")

    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Level.Horizontal.TProgressbar",
            troughcolor=BORDER,
            background=ACCENT,
            borderwidth=0,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            thickness=8,
        )
        style.configure(
            "Busy.Horizontal.TProgressbar",
            troughcolor=BORDER,
            background=ORANGE,
            borderwidth=0,
            thickness=4,
        )

    def _pill_btn(self, parent, text, command, bg, fg=TEXT, active_bg=None, **kw):
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=kw.pop("font", ("Segoe UI", 10)),
            bg=bg,
            fg=fg,
            activebackground=active_bg or bg,
            activeforeground=fg,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            highlightthickness=0,
            **kw,
        )

    def _on_space_key(self, event):
        if event.widget.__class__.__name__ in ("Text",):
            return
        self._toggle_record()

    def _init_background(self):
        if os.environ.get("PIPESAY_TEST_UI"):
            self.capture_rate = 48000
            self.mic_label = "测试模式"
            self.chunk_samples = self.capture_rate * CHUNK_MS // 1000
            self.mic_info_label.config(text="麦克风 · 测试模式 (无音频)")
            return
        other = find_other_pipesay_pid(PID_BASENAME)
        if other:
            log(f"other pipesay running pid={other}")
            self._set_status(
                f"检测到另一个 PipeSay 在运行 (PID {other}) — 请只开一个，否则麦/转写会异常",
                ORANGE,
                hold_sec=10,
            )
        prepare_microphone(pinned_source=self._mic_pinned_source)
        _, self.capture_rate, self.mic_label = resolve_mic_choice(
            pinned_source=self._mic_pinned_source
        )
        self.chunk_samples = self.capture_rate * CHUNK_MS // 1000
        self._update_mic_info_label()
        self._start_mic_monitor()
        self.root.after(0, self._set_idle_status)

    def _update_mic_info_label(self):
        if self._mic_pinned_source is None:
            prefix = "麦克风 · 跟随系统"
        else:
            prefix = f"麦克风 · {self.mic_label}"
        self.mic_info_label.config(text=f"{prefix} @ {self.capture_rate}Hz")

    def _mic_stream_active(self):
        stream = self.audio_stream
        if not stream or not self.mic_ok:
            return False
        try:
            return bool(stream.active)
        except Exception:
            return False

    def _ensure_mic_ready(self):
        if self._mic_stream_active():
            return True
        self._start_mic_monitor()
        return self.mic_ok

    def _try_next_mic_source(self):
        if self.recording or self._mic_pinned_source is not None:
            return
        now = time.time()
        if now - self._mic_rotate_at < 5.0:
            return
        self._mic_rotate_at = now
        self._mic_candidate_idx += 1
        candidates = list_mic_candidates()
        if self._mic_candidate_idx >= len(candidates):
            self._mic_candidate_idx = 0
        log(f"rotate mic candidate -> {self._mic_candidate_idx}")
        prepare_microphone(candidate_idx=self._mic_candidate_idx)
        self._start_mic_monitor()

    def _recover_mic_stream(self):
        if self._mic_restarting:
            return
        log("mic stuck -32768, restarting stream")
        if self._mic_pinned_source is not None:
            prepare_microphone(pinned_source=self._mic_pinned_source)
        else:
            prepare_microphone(candidate_idx=self._mic_candidate_idx)
        self._mic_warmup_until = time.time() + 1.5
        self._start_mic_monitor()
        if self.recording:
            self._set_status("麦克风卡死已重连 — 请继续说话", ORANGE, hold_sec=3)

    def _fail_mic_stuck(self):
        if not self.recording:
            return
        log("mic stuck -32768, abort recording")
        self.recording = False
        self.record_btn.config(text="开始录音", bg=BTN_BG)
        self._abort_session()
        self._hide_live_panel()
        self._mic_recover_attempts = 0
        self._mic_stuck_streak = 0
        self.status_label.config(
            text="麦克风卡死 — 正在尝试重启 PipeWire…",
            fg=ORANGE,
        )
        self.root.after(300, lambda: self._hard_recover_mic("recording stuck -32768"))

    def _start_mic_monitor(self):
        self._mic_restarting = True
        self._mic_broken = False
        self._mic_broken_streak = 0
        self._mic_warmup_until = time.time() + 3.0
        if self._mic_pinned_source is not None:
            source, self.capture_rate, self.mic_label = resolve_mic_choice(
                pinned_source=self._mic_pinned_source
            )
        else:
            source, self.capture_rate, self.mic_label = resolve_mic_choice(
                candidate_idx=self._mic_candidate_idx
            )
        apply_mic_env(source, self.capture_rate, self.mic_label)
        self.chunk_samples = self.capture_rate * CHUNK_MS // 1000
        self._update_mic_info_label()

        def callback(indata, frames, time_info, status):
            if self._shutting_down or self._mic_restarting:
                return
            peak = audio_peak(indata)
            broken = mic_capture_broken(indata)
            stuck_min = mic_capture_stuck_min(indata)
            self._mic_stuck_active = stuck_min
            if self.recording and broken and not stuck_min and peak >= 0.015:
                broken = False
            if stuck_min:
                meter = 0.0
                if self.recording:
                    self._mic_stuck_streak += 1
                    if self._mic_stuck_streak >= 4 and not self._mic_restarting:
                        self._mic_stuck_streak = 0
                        if (
                            time.time() - self.record_started_at < 4.0
                            or self._mic_recover_attempts >= 2
                        ):
                            try:
                                self.root.after(0, self._fail_mic_stuck)
                            except Exception:
                                pass
                        else:
                            self._mic_recover_attempts += 1
                            try:
                                self.root.after(0, self._recover_mic_stream)
                            except Exception:
                                pass
            else:
                self._mic_stuck_streak = 0
                meter = peak if self.recording else meter_peak(indata)
            warming_up = time.time() < self._mic_warmup_until
            if stuck_min and not self.recording and not warming_up:
                self._idle_stuck_streak += 1
                if (
                    self._idle_stuck_streak >= 40
                    and time.time() - self._idle_stuck_recover_at > 60
                ):
                    self._idle_stuck_recover_at = time.time()
                    self._idle_stuck_streak = 0
                    try:
                        self.root.after(
                            0, lambda: self._hard_recover_mic("idle stuck -32768")
                        )
                    except Exception:
                        pass
            elif not stuck_min:
                self._idle_stuck_streak = 0
            if broken and not warming_up and not self.recording:
                self._mic_broken = True
                self._mic_broken_streak += 1
                if self._mic_broken_streak >= 25 and not self.recording:
                    self._mic_broken_streak = 0
                    try:
                        self.root.after(0, self._try_next_mic_source)
                    except Exception:
                        pass
            elif not broken:
                self._mic_broken = False
                self._mic_broken_streak = 0
            elif warming_up or self.recording:
                if not stuck_min:
                    self._mic_broken = False
            if self.recording and not broken and not stuck_min:
                chunk = indata.copy()
                self.local_chunks.append(chunk)
                self.peak_level = max(self.peak_level, peak)
                if self.soniox_session:
                    pcm16 = resample_to_16k(chunk, self.capture_rate).reshape(-1, 1)
                    if self.soniox_session._ready.is_set():
                        self.soniox_session.push_audio(pcm16)
                    else:
                        self._rt_pending.append(pcm16)
            if self._level_pending is None and not self._shutting_down:
                self._level_pending = meter
                try:
                    self.root.after(0, self._flush_level)
                except Exception:
                    pass

        try:
            if self.audio_stream:
                try:
                    self.audio_stream.stop()
                    self.audio_stream.close()
                except Exception:
                    pass
            self.audio_stream = _sounddevice().InputStream(
                samplerate=self.capture_rate,
                channels=1,
                dtype="int16",
                blocksize=self.chunk_samples,
                callback=callback,
            )
            self.audio_stream.start()
            self.mic_ok = True
            log("mic monitor started")
        except Exception as exc:
            self.mic_ok = False
            self.status_label.config(text=f"麦克风不可用: {exc}", fg="#ff6b6b")
            log(f"mic monitor failed: {exc}")
        finally:
            self._mic_restarting = False

    def _flush_level(self):
        if self._shutting_down:
            return
        peak = self._level_pending or 0.0
        self._level_pending = None
        if self.recording and self._mic_stuck_active:
            self.level_bar["value"] = 0
            self.level_label.config(text="卡死", fg=ORANGE)
            return
        if self._mic_broken and not self.recording:
            self.level_bar["value"] = 0
            self.level_label.config(text="异常", fg=ORANGE)
            if not self.recording and time.time() > self._user_status_until:
                hint = "麦克风数据异常"
                if self._mic_pinned_source is not None:
                    hint += " — 固定设备异常，请换设备或改回「跟随系统」"
                elif self._mic_candidate_idx != 0:
                    hint += " — 已切到备用麦，建议重启应用恢复"
                else:
                    hint += " — 合盖/长时间录音后常见，请重启 PipeSay 或 PipeWire"
                self.status_label.config(text=hint, fg=ORANGE)
            return
        pct = min(100, int(peak * 100))
        self.level_bar["value"] = pct
        self.level_label.config(text=f"{pct}%", fg=MUTED)

    def _build_ui(self):
        shell = tk.Frame(self.root, bg=BG, padx=20, pady=16)
        shell.pack(fill="both", expand=True)

        header = tk.Frame(shell, bg=BG)
        header.pack(fill="x", pady=(0, 14))
        tk.Label(
            header,
            text=APP_NAME,
            font=("Segoe UI", 22, "bold"),
            bg=BG,
            fg=TEXT,
        ).pack(side="left")
        if not DND_AVAILABLE:
            tk.Label(
                header,
                text="Lab · 拖放不可用",
                font=("Segoe UI", 10),
                bg=BG,
                fg=ORANGE,
            ).pack(side="left", padx=(10, 0))
        self.pin_btn = self._pill_btn(
            header,
            "置顶",
            self._toggle_pin,
            CARD2,
            fg=MUTED,
            active_bg=BORDER,
            font=("Segoe UI", 10),
            padx=14,
            pady=6,
        )
        self.pin_btn.pack(side="right")

        hero = tk.Frame(shell, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        hero.pack(fill="x", pady=(0, 12))

        self.record_btn = tk.Button(
            hero,
            text="开始录音",
            font=("Segoe UI", 17, "bold"),
            bg=BTN_BG,
            fg=TEXT,
            activebackground=BTN_ON,
            activeforeground=TEXT,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            pady=16,
            command=self._toggle_record,
        )
        self.record_btn.pack(fill="x", padx=16, pady=(16, 8))

        self.status_label = tk.Label(
            hero,
            text="就绪 — 空格开始/停止，出现「实时转写中」再说话",
            font=("Segoe UI", 11),
            bg=PANEL,
            fg=MUTED,
            wraplength=420,
            justify="center",
        )
        self.status_label.pack(pady=(0, 10))

        meter = tk.Frame(hero, bg=PANEL)
        meter.pack(fill="x", padx=16, pady=(0, 14))
        tk.Label(meter, text="输入", font=("Segoe UI", 10), bg=PANEL, fg=MUTED, width=4).pack(
            side="left"
        )
        self.level_bar = ttk.Progressbar(
            meter, mode="determinate", maximum=100, style="Level.Horizontal.TProgressbar"
        )
        self.level_bar.pack(side="left", fill="x", expand=True, padx=(8, 8))
        self.level_label = tk.Label(
            meter, text="0%", font=("Segoe UI", 10), bg=PANEL, fg=MUTED, width=5
        )
        self.level_label.pack(side="right")

        opts = tk.Frame(shell, bg=BG)
        opts.pack(fill="x", pady=(0, 10))
        tk.Checkbutton(
            opts,
            text="识别完自动复制",
            variable=self.auto_copy,
            font=("Segoe UI", 11),
            bg=BG,
            fg=MUTED,
            activebackground=BG,
            activeforeground=MUTED,
            selectcolor=CARD,
            highlightthickness=0,
        ).pack(side="left")
        self.key_btn = self._pill_btn(
            opts,
            "API Key — 点此设置",
            self._open_soniox_key_dialog,
            ORANGE,
            font=("Segoe UI", 10, "bold"),
            padx=14,
            pady=5,
        )
        self.key_btn.pack(side="right")
        self.model_label = tk.Label(opts, text="", font=("Segoe UI", 10), bg=BG, fg=MUTED)
        self.model_label.pack(side="right", padx=(0, 10))

        mode_frame = tk.Frame(shell, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        mode_frame.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(mode_frame, bg=PANEL, padx=12, pady=10)
        inner.pack(fill="x")
        tk.Label(
            inner, text="引擎", font=("Segoe UI", 10, "bold"), bg=PANEL, fg=MUTED
        ).pack(side="left", padx=(0, 10))
        self.soniox_btn = self._pill_btn(
            inner,
            "Soniox 云端",
            lambda: self._switch_mode("soniox"),
            ACCENT,
            font=("Segoe UI", 10, "bold"),
            padx=14,
            pady=6,
        )
        self.soniox_btn.pack(side="left", padx=(0, 6))
        self.local_btn = self._pill_btn(
            inner,
            "本地 Whisper",
            lambda: self._switch_mode("local"),
            CARD2,
            fg=MUTED,
            active_bg=BORDER,
            padx=14,
            pady=6,
        )
        self.local_btn.pack(side="left")

        mic_row = tk.Frame(shell, bg=BG)
        mic_row.pack(anchor="w", fill="x", pady=(0, 8))
        self.mic_info_label = tk.Label(
            mic_row,
            text=f"麦克风 · {self.mic_label}",
            font=("Segoe UI", 10),
            bg=BG,
            fg="#52525b",
        )
        self.mic_info_label.pack(side="left")
        self._pill_btn(
            mic_row,
            "选择…",
            self._open_mic_picker_dialog,
            CARD2,
            fg=MUTED,
            active_bg=BORDER,
            font=("Segoe UI", 9),
            padx=10,
            pady=3,
        ).pack(side="left", padx=(8, 0))

        self.live_frame = tk.Frame(shell, bg=PANEL, highlightbackground=ACCENT, highlightthickness=1)
        live_head = tk.Frame(self.live_frame, bg=PANEL)
        live_head.pack(fill="x", padx=12, pady=(8, 4))
        tk.Label(
            live_head,
            text="实时转写",
            font=("Segoe UI", 11, "bold"),
            bg=PANEL,
            fg=ACCENT,
        ).pack(side="left")
        self._pill_btn(
            live_head,
            "复制实时",
            self._copy_live,
            CARD2,
            fg=TEXT,
            active_bg=BORDER,
            font=("Segoe UI", 10),
            padx=12,
            pady=4,
        ).pack(side="right")
        attach_drag_handle(
            live_head,
            get_text=lambda: self._session_live_text,
            on_status=self._drag_status,
            on_empty=self._drag_empty,
            on_clipboard=self._drag_clipboard,
            bg=PANEL,
            fg=TEXT,
            muted=MUTED,
            accent=ACCENT,
        )
        live_body = tk.Frame(self.live_frame, bg=PANEL)
        live_body.pack(fill="x", padx=1, pady=(0, 10))
        self.live_scroll = tk.Scrollbar(live_body, orient="vertical")
        self.live_text = tk.Text(
            live_body,
            height=5,
            font=("Segoe UI", 14),
            bg=CARD,
            fg=TEXT,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            wrap="word",
            padx=12,
            pady=8,
            yscrollcommand=self._live_yscroll,
        )
        self.live_scroll.config(command=self.live_text.yview)
        self.live_scroll.pack(side="right", fill="y")
        self.live_text.pack(side="left", fill="x", expand=True)
        self.live_text.insert("1.0", "…")
        self.live_text.configure(state="disabled")
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.live_text.bind(seq, lambda _e: self.root.after_idle(self._sync_live_follow))
        self.live_text.bind("<Control-c>", self._copy_live_key)
        self.live_text.bind("<Control-C>", self._copy_live_key)

        self.out_head = tk.Frame(shell, bg=BG)
        self.out_head.pack(fill="x", pady=(0, 6))
        tk.Label(
            self.out_head,
            text="识别结果",
            font=("Segoe UI", 13, "bold"),
            bg=BG,
            fg=TEXT,
        ).pack(side="left")
        self._pill_btn(
            self.out_head,
            "复制全部",
            self._copy_all,
            CARD2,
            fg=TEXT,
            active_bg=BORDER,
            font=("Segoe UI", 10),
            padx=12,
            pady=4,
        ).pack(side="right", padx=(6, 0))
        self._pill_btn(
            self.out_head,
            "清空",
            self._clear,
            CARD2,
            fg=MUTED,
            active_bg=BORDER,
            font=("Segoe UI", 10),
            padx=12,
            pady=4,
        ).pack(side="right")

        out = tk.Frame(shell, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        out.pack(fill="both", expand=True)
        self.text_area = scrolledtext.ScrolledText(
            out,
            font=("Segoe UI", 14),
            bg=CARD,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            wrap="word",
            padx=14,
            pady=12,
        )
        self.text_area.pack(fill="both", expand=True, padx=1, pady=1)
        self.text_area.insert("1.0", "已定稿的结果会保留在这里\n")

        bottom = tk.Frame(shell, bg=BG)
        bottom.pack(fill="x", pady=(10, 0))
        self._pill_btn(
            bottom,
            "保存到文件",
            self._save,
            CARD2,
            fg=MUTED,
            active_bg=BORDER,
            padx=14,
            pady=8,
        ).pack(side="right")

        self.progress = ttk.Progressbar(
            shell, mode="indeterminate", style="Busy.Horizontal.TProgressbar"
        )
        self._refresh_mode_ui()
        if not get_soniox_key():
            self.status_label.config(
                text="首次使用：点右上角「API Key」填入 Soniox Key（soniox.com 注册）",
                fg=ORANGE,
            )

    def _refresh_key_btn(self):
        key = get_soniox_key()
        if key:
            tail = key[-4:] if len(key) > 4 else "已配置"
            self.key_btn.config(
                text=f"API Key ·…{tail}",
                bg=CARD2,
                fg=TEXT,
                font=("Segoe UI", 10),
            )
        else:
            self.key_btn.config(
                text="API Key — 点此设置",
                bg=ORANGE,
                fg=TEXT,
                font=("Segoe UI", 10, "bold"),
            )

    def _refresh_mode_ui(self):
        mode = self.mode.get()
        self._refresh_key_btn()
        if mode == "soniox":
            self.soniox_btn.config(bg=ACCENT, fg=TEXT, font=("Segoe UI", 10, "bold"))
            self.local_btn.config(bg=CARD2, fg=MUTED, font=("Segoe UI", 10))
            self.model_label.config(text="")
        else:
            self.local_btn.config(bg=ACCENT, fg=TEXT, font=("Segoe UI", 10, "bold"))
            self.soniox_btn.config(bg=CARD2, fg=MUTED, font=("Segoe UI", 10))
            if self.whisper_model:
                self.model_label.config(text="small 模型已就绪")
            else:
                self.model_label.config(text="")

    def _open_soniox_key_dialog(self):
        if self.recording:
            self._set_status("录音中无法修改 API Key — 请先停止", ORANGE, hold_sec=2)
            return

        win = tk.Toplevel(self.root)
        win.title("Soniox API Key")
        win.configure(bg=PANEL)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        body = tk.Frame(win, bg=PANEL, padx=20, pady=16)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text="Soniox API Key",
            font=("Segoe UI", 13, "bold"),
            bg=PANEL,
            fg=TEXT,
        ).pack(anchor="w")
        tk.Label(
            body,
            text="在 soniox.com 注册后获取。保存到 ~/.soniox_key，仅本机可读。",
            font=("Segoe UI", 10),
            bg=PANEL,
            fg=MUTED,
            wraplength=360,
            justify="left",
        ).pack(anchor="w", pady=(6, 12))

        entry = tk.Entry(
            body,
            font=("Segoe UI", 11),
            bg=CARD,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            show="*",
            width=42,
        )
        entry.pack(fill="x", ipady=6)
        existing = get_soniox_key()
        if existing:
            entry.insert(0, existing)

        hint = tk.Label(body, text="", font=("Segoe UI", 10), bg=PANEL, fg="#ff6b6b")
        hint.pack(anchor="w", pady=(8, 0))

        btns = tk.Frame(body, bg=PANEL)
        btns.pack(fill="x", pady=(14, 0))

        def close():
            win.grab_release()
            win.destroy()

        def save():
            err = save_soniox_key(entry.get())
            if err:
                hint.config(text=err, fg="#ff6b6b")
                return
            self._refresh_mode_ui()
            self._set_status("API Key 已保存", GREEN, hold_sec=2)
            close()

        self._pill_btn(btns, "保存", save, ACCENT, padx=16, pady=6).pack(side="right")
        self._pill_btn(
            btns, "取消", close, CARD2, fg=MUTED, active_bg=BORDER, padx=16, pady=6
        ).pack(side="right", padx=(0, 8))

        win.bind("<Escape>", lambda _e: close())
        entry.bind("<Return>", lambda _e: save())
        entry.focus_set()
        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _open_mic_picker_dialog(self):
        if self.recording:
            self._set_status("录音中无法切换麦克风 — 请先停止", ORANGE, hold_sec=2)
            return

        candidates = list_mic_candidates()
        current = self._mic_pinned_source

        win = tk.Toplevel(self.root)
        win.title("选择麦克风")
        win.configure(bg=PANEL)
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        body = tk.Frame(win, bg=PANEL, padx=20, pady=16)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text="选择麦克风",
            font=("Segoe UI", 13, "bold"),
            bg=PANEL,
            fg=TEXT,
        ).pack(anchor="w")
        tk.Label(
            body,
            text="默认「跟随系统」使用 PipeWire 当前默认输入；也可固定某设备。设置保存在 ~/.config/pipesay/mic.json",
            font=("Segoe UI", 10),
            bg=PANEL,
            fg=MUTED,
            wraplength=380,
            justify="left",
        ).pack(anchor="w", pady=(6, 12))

        choice = tk.StringVar(value=current or "__system__")
        list_frame = tk.Frame(body, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        list_frame.pack(fill="both", expand=True)

        for source, _rate, label in candidates:
            value = source or "__system__"
            display = label if source else f"{label}（推荐）"
            tk.Radiobutton(
                list_frame,
                text=display,
                variable=choice,
                value=value,
                font=("Segoe UI", 10),
                bg=CARD,
                fg=TEXT,
                activebackground=CARD,
                activeforeground=TEXT,
                selectcolor=CARD2,
                highlightthickness=0,
                anchor="w",
                padx=12,
                pady=4,
            ).pack(fill="x")

        btns = tk.Frame(body, bg=PANEL)
        btns.pack(fill="x", pady=(14, 0))

        def close():
            win.grab_release()
            win.destroy()

        def apply():
            picked = choice.get()
            source = None if picked == "__system__" else picked
            save_mic_config(source)
            self._mic_pinned_source = source
            self._mic_candidate_idx = 0
            if self._mic_pinned_source is not None:
                prepare_microphone(pinned_source=self._mic_pinned_source)
            else:
                prepare_microphone()
            self._start_mic_monitor()
            mode = "跟随系统" if source is None else self.mic_label
            self._set_status(f"麦克风已设为：{mode}", GREEN, hold_sec=2)
            close()

        self._pill_btn(btns, "确定", apply, ACCENT, padx=16, pady=6).pack(side="right")
        self._pill_btn(
            btns, "取消", close, CARD2, fg=MUTED, active_bg=BORDER, padx=16, pady=6
        ).pack(side="right", padx=(0, 8))

        win.bind("<Escape>", lambda _e: close())
        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _switch_mode(self, mode):
        if self.recording:
            self._set_status("录音中无法切换引擎 — 请先停止", ORANGE, hold_sec=2)
            return
        self.mode.set(mode)
        self._refresh_mode_ui()
        if mode == "local" and not self.whisper_model:
            self._load_local_model()

    def _load_local_model(self):
        self.model_label.config(text="正在加载本地模型...")
        self.root.update()

        def load():
            try:
                from faster_whisper import WhisperModel

                self.whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
                self.root.after(
                    0,
                    lambda: (
                        self.model_label.config(text="small 模型已就绪"),
                        self._refresh_mode_ui(),
                    ),
                )
            except ImportError:
                venv_pip = os.path.join(os.path.dirname(__file__), ".venv", "bin", "pip")
                hint = (
                    "本地模式需安装 faster-whisper · "
                    f"{venv_pip} install -r requirements-local.txt"
                )
                self.root.after(
                    0,
                    lambda: (
                        self.model_label.config(text=hint),
                        self.status_label.config(
                            text="本地 Whisper 未安装，请用 Soniox 云端或执行上方命令",
                            fg=ORANGE,
                        ),
                    ),
                )
            except Exception as exc:
                self.root.after(0, lambda: self.model_label.config(text=f"加载失败: {exc}"))

        threading.Thread(target=load, daemon=True).start()

    def _update_level(self, peak):
        self.peak_level = max(self.peak_level, peak)
        pct = min(100, int(peak * 100))
        self.level_bar["value"] = pct
        self.level_label.config(text=f"{pct}%")

    def _set_idle_status(self):
        if self.recording or self._rt_connecting or self._finalizing_rt_token:
            return
        self.status_label.config(
            text="就绪 — 空格开始/停止，出现「实时转写中」再说话",
            fg=MUTED,
        )

    def _toggle_record(self):
        if self._finalizing_rt_token:
            self._set_status("正在定稿… 请稍等", ORANGE, hold_sec=2)
            return
        if self.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if self.mode.get() == "soniox" and not get_soniox_key():
            self.status_label.config(
                text="未配置 Soniox API Key — 点右上角「API Key」",
                fg="#ff6b6b",
            )
            return
        if self.mode.get() == "local" and not self.whisper_model:
            self.status_label.config(text="本地模型未就绪", fg="#ff6b6b")
            self._load_local_model()
            return
        if not self._ensure_mic_ready():
            self._set_status("麦克风未就绪", ORANGE, hold_sec=2)
            return

        self._mic_broken = False
        self._mic_broken_streak = 0
        self._mic_stuck_streak = 0
        self._mic_stuck_active = False
        self._mic_recover_attempts = 0
        if self._mic_candidate_idx != 0:
            self._mic_candidate_idx = 0
            prepare_microphone(
                pinned_source=self._mic_pinned_source
                if self._mic_pinned_source is not None
                else None
            )
            self._start_mic_monitor()

        self._abort_session()
        self._cancel_live_ui()
        self._rt_token += 1
        self._connect_epoch += 1
        self._active_rt_token = self._rt_token
        self._finalizing_rt_token = 0
        rt_token = self._active_rt_token

        self.recording = True
        self._rt_connecting = True
        self.record_started_at = time.time()
        self._long_record_warned = False
        self._schedule_record_watchdog()
        self._begin_live_region()
        self.local_chunks = []
        self.peak_level = 0.0
        self.last_raw_audio = None
        self._rt_pending = []
        self.level_bar["value"] = 0
        self.level_label.config(text="0%")

        self.record_btn.config(text="停止录音", bg=BTN_ON)
        self.status_label.config(text="正在连接 Soniox (1/5)…", fg=ORANGE)
        self._set_live_display("连接云端中… 连上后这里会实时出字", partial=False)
        log(f"record start mode={self.mode.get()} rate={self.capture_rate} token={rt_token}")

        if self.mode.get() == "soniox":
            self.soniox_session = SonioxRealtimeSession(
                get_soniox_key(),
                on_text=lambda t, p, n, tok=rt_token: self._on_live_text(tok, t, p, n),
                on_error=lambda m, tok=rt_token: self._on_soniox_error(tok, m),
                on_finished=lambda t, tok=rt_token: self._on_soniox_finished(tok, t),
                on_ready=self._on_rt_ready,
            )
            threading.Thread(
                target=self._connect_rt, args=(rt_token,), daemon=True
            ).start()

    def _set_recording_status_if_active(self, rt_token, text, fg="#ff6b6b"):
        if rt_token != self._active_rt_token or not self.recording:
            return False
        self.status_label.config(text=text, fg=fg)
        return True

    def _connect_rt(self, rt_token):
        delays = (0, 2, 4, 6, 8)
        last_exc = "连接失败"
        epoch = self._connect_epoch
        total = len(delays)

        def make_session():
            return SonioxRealtimeSession(
                get_soniox_key(),
                on_text=lambda t, p, n, tok=rt_token: self._on_live_text(tok, t, p, n),
                on_error=lambda m, tok=rt_token: self._on_soniox_error(tok, m),
                on_finished=lambda t, tok=rt_token: self._on_soniox_finished(tok, t),
                on_ready=self._on_rt_ready,
            )

        for attempt, delay in enumerate(delays):
            if delay:
                time.sleep(delay)
            if (
                epoch != self._connect_epoch
                or rt_token != self._active_rt_token
                or not self.recording
            ):
                return
            if attempt > 0:
                if self.soniox_session:
                    self.soniox_session.abort()
                self.soniox_session = make_session()
            session = self.soniox_session
            if not session:
                return
            try:
                self.root.after(
                    0,
                    lambda a=attempt + 1, tok=rt_token: self._set_recording_status_if_active(
                        tok, f"正在连接 Soniox ({a}/{total})…", ORANGE
                    ),
                )
            except Exception:
                pass
            try:
                session.start()
                if rt_token != self._active_rt_token or not self.recording:
                    session.abort()
                    return
                self.root.after(
                    0,
                    lambda tok=rt_token: self._set_recording_status_if_active(
                        tok, "正在录音… 实时转写中"
                    ),
                )
                return
            except Exception as exc:
                last_exc = str(exc)
                log(f"soniox connect failed try {attempt + 1}/{len(delays)}: {exc}")
                if self.soniox_session:
                    self.soniox_session.abort()

        self.root.after(
            0, lambda: self._on_rt_connect_failed(last_exc, rt_token)
        )

    def _on_rt_connect_failed(self, msg, rt_token):
        if rt_token != self._active_rt_token:
            return
        self._rt_connecting = False
        self.recording = False
        self.record_btn.config(text="开始录音", bg=BTN_BG)
        if self.soniox_session:
            self.soniox_session.abort()
        self.soniox_session = None
        raw = np.concatenate(self.local_chunks, axis=0) if self.local_chunks else None
        self.last_raw_audio = raw
        duration = time.time() - self.record_started_at if self.record_started_at else 0
        if (
            raw is not None
            and audio_peak(raw) >= 0.01
            and duration >= 12
            and not network_error_blocks_transcription(msg)
        ):
            log(f"connect failed, fallback async: {msg}")
            self._hide_live_panel()
            self.status_label.config(text="实时未连上 — 正在补识别…", fg=ORANGE)
            self._fallback_async("connect-failed", rt_token)
            return
        self.status_label.config(
            text=friendly_connect_error(msg), fg="#ff6b6b"
        )
        self.root.after(4000, self._set_idle_status)

    def _on_rt_ready(self):
        self._rt_connecting = False
        session = self.soniox_session
        if not session or session._aborted:
            return
        for chunk in self._rt_pending:
            session.push_audio(chunk)
        self._rt_pending.clear()
        session.flush_pending()
        log("rt audio flushed")

        def ui():
            if not self.recording:
                return
            if self._mic_stuck_active:
                self._set_recording_status_if_active(
                    self._active_rt_token, "麦克风卡死 — 无法转写", ORANGE
                )
            else:
                self._set_recording_status_if_active(
                    self._active_rt_token, "正在录音… 实时转写中"
                )

        self.root.after(0, ui)

    def _stop_recording(self):
        self._cancel_record_watchdog()
        self._rt_connecting = False
        self.recording = False
        self._last_record_stop_at = time.time()
        self.record_btn.config(text="开始录音", bg=BTN_BG)

        duration = time.time() - self.record_started_at
        raw = np.concatenate(self.local_chunks, axis=0) if self.local_chunks else None
        self.last_raw_audio = raw
        peak = max(self.peak_level, audio_peak(raw) if raw is not None else 0.0)
        log(f"record stop dur={duration:.1f}s peak={peak:.4f}")

        if duration < 0.4:
            self._abort_session()
            self.status_label.config(text="录音太短", fg="#ff6b6b")
            return

        if peak < 0.01 or mic_capture_broken(raw):
            self._abort_session()
            if mic_capture_broken(raw) and peak >= 0.01:
                msg = "麦克风数据异常(卡死)，已重连 — 请关闭占用麦克风的应用后再试"
            else:
                msg = f"没收到有效声音 (peak={peak:.3f})，请检查麦克风权限/静音"
            self.status_label.config(text=msg, fg="#ff6b6b")
            if raw is not None:
                save_debug_wav(raw, self.capture_rate, "silent")
            self.root.after(200, self._start_mic_monitor)
            return

        if self.mode.get() == "soniox":
            session = self.soniox_session
            live_text = (self._session_live_text or "").strip()
            rt_ready = bool(session and session._ready.is_set())
            if session and rt_ready:
                self._finalizing_rt_token = self._active_rt_token
                self.status_label.config(text="正在定稿…", fg=ORANGE)
                self.progress.pack(pady=(6, 0))
                self.progress.start()
                self.soniox_session.stop()
                self._schedule_finalize_timeout(self._finalizing_rt_token)
                return
            self._abort_session()
            self._hide_live_panel()
            if live_text:
                self._commit_result_text(live_text)
                if self.auto_copy.get():
                    self._set_clipboard(live_text)
                    self.status_label.config(
                        text=f"完成 — {len(live_text)} 字 · 已复制（云端未完全就绪）",
                        fg=GREEN,
                    )
                else:
                    self.status_label.config(
                        text=f"完成 — {len(live_text)} 字（云端未完全就绪）", fg=GREEN
                    )
                return
            if raw is not None and peak >= 0.01 and duration >= 12:
                log("rt not ready on stop, fallback async")
                self.status_label.config(text="实时未连上 — 正在补识别…", fg=ORANGE)
                self._fallback_async("rt-not-ready")
                return
            if raw is not None and peak >= 0.01:
                self.status_label.config(
                    text="云端还没连上（停太早）— 这段未转写，请等「实时转写中」再说话",
                    fg=ORANGE,
                )
                return
            self.status_label.config(
                text="云端未连接 — 请等状态栏显示「实时转写中」再说话", fg=ORANGE
            )
            return

        if raw is None:
            self.status_label.config(text="没录到声音", fg="#ff6b6b")
            return

        self.status_label.config(text="本地转录中...", fg=ORANGE)
        self.progress.pack(pady=(6, 0))
        self.progress.start()
        threading.Thread(
            target=self._transcribe_local,
            args=(raw, duration),
            daemon=True,
        ).start()

    def _schedule_finalize_timeout(self, rt_token, sec=12):
        self._cancel_finalize_timeout()
        self._finalize_timeout_id = self.root.after(
            int(sec * 1000), lambda t=rt_token: self._on_finalize_timeout(t)
        )

    def _cancel_finalize_timeout(self):
        tid = self._finalize_timeout_id
        if tid:
            try:
                self.root.after_cancel(tid)
            except Exception:
                pass
        self._finalize_timeout_id = None

    def _on_finalize_timeout(self, rt_token):
        self._finalize_timeout_id = None
        if rt_token != self._finalizing_rt_token:
            return
        log(f"finalize timeout token={rt_token}")
        self._abort_session()
        self.progress.stop()
        self.progress.pack_forget()
        final = (self._session_live_text or "").strip()
        self._finalizing_rt_token = 0
        self._hide_live_panel()
        if final:
            self._commit_result_text(final)
            if self.auto_copy.get():
                self._set_clipboard(final)
                self.status_label.config(
                    text=f"完成 — {len(final)} 字 · 已复制（连接超时，已用已识别文字）",
                    fg=GREEN,
                )
            else:
                self.status_label.config(
                    text=f"完成 — {len(final)} 字（连接超时，已用已识别文字）",
                    fg=GREEN,
                )
        else:
            self.status_label.config(
                text="定稿超时（休眠/网络断开后常见）— 请重新开始录音",
                fg=ORANGE,
            )

    def _abort_session(self):
        self._cancel_finalize_timeout()
        session = self.soniox_session
        if session:
            session.abort()
        self.soniox_session = None
        self._finalizing_rt_token = 0
        self._hide_live_panel()

    def _on_live_text(self, rt_token, text, partial, text_len=0):
        self._ui(
            lambda: self._apply_live_text(rt_token, text, partial, text_len)
        )

    def _on_soniox_error(self, rt_token, message):
        if rt_token not in (self._active_rt_token, self._finalizing_rt_token):
            log(f"ignore stale rt error token={rt_token}: {message}")
            return

        def update():
            if rt_token not in (self._active_rt_token, self._finalizing_rt_token):
                return
            if (
                rt_token == self._active_rt_token
                and self.recording
                and rt_token != self._finalizing_rt_token
            ):
                if soniox_error_is_disconnect(message):
                    self._emergency_stop_recording(
                        "云端连接断开（休眠/网络）", save_partial=True
                    )
                else:
                    self.status_label.config(
                        text=f"云端异常: {friendly_soniox_error(message)} — 可继续说话或停录",
                        fg=ORANGE,
                    )
                return
            self.progress.stop()
            self.progress.pack_forget()
            self.status_label.config(
                text=f"识别错误: {friendly_soniox_error(message)}", fg="#ff6b6b"
            )
            self._fallback_async("soniox-error", rt_token)

        self._ui(update)

    def _commit_result_text(self, text):
        if not text.strip():
            return
        if self._committed_text.startswith("已定稿的结果") or self._committed_text.startswith(
            "录音时这里会实时"
        ):
            self._committed_text = ""
        self._committed_text += text.strip() + "\n"
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", self._committed_text)
        self.text_area.see("end")

    def _on_soniox_finished(self, rt_token, text):
        if rt_token != self._finalizing_rt_token:
            log(f"ignore stale rt finished token={rt_token}")
            return

        def update():
            if rt_token != self._finalizing_rt_token:
                return
            self._cancel_finalize_timeout()
            self.progress.stop()
            self.progress.pack_forget()
            final = (text or self._session_live_text or "").strip()
            self._hide_live_panel()
            if final:
                self._commit_result_text(final)
                self.soniox_session = None
                self._finalizing_rt_token = 0
                if self.auto_copy.get():
                    self._set_clipboard(final)
                    self.status_label.config(
                        text=f"完成 — {len(final)} 字 · 已复制 · Cursor 用 Ctrl+V", fg=GREEN
                    )
                else:
                    self.status_label.config(text=f"完成 — {len(final)} 字", fg=GREEN)
                self.root.after(5000, self._set_idle_status)
            else:
                self.status_label.config(text="实时识别为空，正在重试...", fg=ORANGE)
                self._fallback_async("soniox-empty", rt_token)

        self._ui(update)

    def _fallback_async(self, reason, rt_token=None):
        if rt_token is not None and rt_token not in (
            self._active_rt_token,
            self._finalizing_rt_token,
        ):
            return
        if rt_token is not None and self._finalizing_rt_token == 0:
            self._finalizing_rt_token = rt_token
        if self.last_raw_audio is None:
            self.soniox_session = None
            self.status_label.config(text="没听清，请再试一次", fg=ORANGE)
            return

        audio16 = prepare_audio_for_stt(self.last_raw_audio, self.capture_rate)
        peak = audio_peak(audio16)
        log(f"fallback async reason={reason} peak={peak:.4f}")

        def run():
            text, err = transcribe_async_rest(audio16)
            self.root.after(0, lambda: self._finish_fallback(text, err, peak))

        self.progress.pack(pady=(6, 0))
        self.progress.start()
        threading.Thread(target=run, daemon=True).start()

    def _finish_fallback(self, text, err, peak):
        self.progress.stop()
        self.progress.pack_forget()
        self.soniox_session = None
        self._finalizing_rt_token = 0
        self._hide_live_panel()
        if text.strip():
            self._commit_result_text(text.strip())
            if self.auto_copy.get():
                self._set_clipboard(text.strip())
                self.status_label.config(
                    text=f"完成 — {len(text.strip())} 字（补识别）· 已复制", fg=GREEN
                )
            else:
                self.status_label.config(
                    text=f"完成 — {len(text.strip())} 字（补识别）", fg=GREEN
                )
            return

        path = save_debug_wav(self.last_raw_audio, self.capture_rate, "failed")
        if err:
            self.status_label.config(
                text=friendly_connect_error(str(err)), fg="#ff6b6b"
            )
        else:
            self.status_label.config(text="没听清，请再试一次", fg=ORANGE)
        self.root.after(5000, self._set_idle_status)
        log(f"fallback failed peak={peak:.3f} err={err} path={path}")

    def _transcribe_local(self, audio, duration):
        try:
            audio16 = prepare_audio_for_stt(audio, self.capture_rate)
            audio_f = audio16.astype(np.float32) / 32768.0
            segments, _ = self.whisper_model.transcribe(
                audio_f, language="zh", beam_size=5, vad_filter=True
            )
            text = " ".join(s.text.strip() for s in segments if s.text.strip())
            self.root.after(0, lambda: self._finish_local(text.strip(), duration))
        except Exception as exc:
            self.root.after(0, lambda: self._finish_local("", duration, str(exc)))

    def _finish_local(self, text, duration, error=None):
        self.progress.stop()
        self.progress.pack_forget()
        if error:
            self.status_label.config(text=f"本地识别失败: {error}", fg="#ff6b6b")
            return
        if text:
            self.text_area.insert("end", text + "\n")
            self.text_area.see("end")
            self.status_label.config(text=f"完成 — {len(text)} 字 ({duration:.1f}s)", fg=GREEN)
        else:
            save_debug_wav(self.last_raw_audio, self.capture_rate, "local-empty")
            self.status_label.config(text="没听清，请再试一次", fg=ORANGE)

    def shutdown(self):
        if self._shutting_down:
            return
        self._shutting_down = True
        self._cancel_finalize_timeout()
        self.recording = False
        self._abort_session()
        if self.audio_stream:
            try:
                self.audio_stream.stop()
                self.audio_stream.close()
            except Exception:
                pass
            self.audio_stream = None
        self._remove_pid_file()
        log("app shutting down")
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def _live_yscroll(self, first, last):
        self.live_scroll.set(first, last)
        self.root.after_idle(self._sync_live_follow)

    def _drag_status(self, message, kind="info"):
        colors = {
            "info": ACCENT,
            "ok": GREEN,
            "warn": ORANGE,
            "hint": MUTED,
        }
        self.status_label.config(text=message, fg=colors.get(kind, MUTED))

    def _drag_empty(self):
        self.status_label.config(text="还没有可拖动的文字", fg=ORANGE)

    def _set_clipboard(self, text):
        return set_clipboard(self.root, text)

    def _drag_clipboard(self, text):
        self._set_clipboard(text)

    def _copy_live(self):
        text = (self._session_live_text or "").strip()
        if not text:
            self.status_label.config(text="实时转写还没有内容", fg=ORANGE)
            return
        self._set_clipboard(text)
        self._set_status(f"已复制实时转写 — {len(text)} 字", GREEN, hold_sec=2)

    def _copy_live_key(self, _event=None):
        self._copy_live()
        return "break"

    def _copy_all(self):
        text = self.text_area.get("1.0", "end-1c")
        if text.strip():
            self._set_clipboard(text)
            self._set_status("已复制到剪贴板", GREEN, hold_sec=2)
        else:
            self._set_status("没有内容可复制", ORANGE, hold_sec=2)

    def _clear(self):
        self.text_area.delete("1.0", "end")
        self._committed_text = ""
        self._hide_live_panel()
        self._set_status("已清空", GRAY, hold_sec=2)

    def _save(self):
        text = self.text_area.get("1.0", "end-1c")
        if not text.strip():
            self.status_label.config(text="没有内容", fg=ORANGE)
            return
        out_dir = os.path.expanduser("~/dictations")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(
            out_dir, f"dictation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        with open(path, "w") as f:
            f.write(text)
        self._set_status(f"已保存: {path}", GREEN, hold_sec=3)


def cli_test_ui_e2e():
    os.environ["PIPESAY_TEST_UI"] = "1"
    root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
    root.withdraw()
    app = DictationApp(root)
    root.update_idletasks()
    fails = []

    def check(name, cond):
        if not cond:
            fails.append(name)

    app.text_area.delete("1.0", "end")
    app.text_area.insert("1.0", "E2E按钮测试")
    app._copy_all()
    root.update()
    try:
        check("copy_all", "E2E" in root.clipboard_get())
    except tk.TclError:
        check("copy_all", False)

    app._toggle_pin()
    root.update()
    check("pin_on", app.always_on_top)
    app._toggle_pin()
    check("pin_off", not app.always_on_top)

    app._switch_mode("local")
    check("switch_local", app.mode.get() == "local")
    app._switch_mode("soniox")
    check("switch_soniox", app.mode.get() == "soniox")

    app._clear()
    check("clear", not app.text_area.get("1.0", "end-1c").strip())

    app._session_live_text = "实时区测试"
    app._copy_live()
    root.update()
    try:
        check("copy_live", "实时区测试" in root.clipboard_get())
    except tk.TclError:
        check("copy_live", False)

    root.destroy()
    if fails:
        print("FAIL:", ", ".join(fails))
        return 1
    print("OK: pin, copy_all, copy_live, clear, mode switch")
    return 0


def cli_test_rt_e2e():
    """Stream example audio and verify live transcript grows across updates."""
    import requests
    from websockets.sync.client import connect

    key = get_soniox_key()
    if not key:
        print("ERROR: no Soniox key")
        return 1

    mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    r = requests.get("https://soniox.com/media/examples/coffee_shop.mp3", timeout=30)
    r.raise_for_status()
    mp3.write(r.content)
    mp3.close()

    updates = []
    finished = {"text": "", "err": None}

    def on_text(text, partial, text_len=0):
        updates.append((len(text), partial))
        print(f"  live #{len(updates):02d} len={len(text):3d} partial={partial} {text[:70]!r}")

    def on_error(msg):
        finished["err"] = msg

    def on_finished(text):
        finished["text"] = text

    config = {
        "api_key": key,
        "model": "stt-rt-v4",
        "language_hints": ["en"],
        "enable_endpoint_detection": True,
        "audio_format": "auto",
    }

    print("E2E RT stream test…")
    with connect(SONIOX_WS_URL, ping_interval=20, ping_timeout=60) as ws:
        ws.send(json.dumps(config))

        def stream():
            with open(mp3.name, "rb") as fh:
                while chunk := fh.read(3840):
                    ws.send(chunk)
                    time.sleep(0.05)
            ws.send(json.dumps({"type": "finalize"}))
            ws.send("")

        threading.Thread(target=stream, daemon=True).start()

        final_tokens = []
        while True:
            res = json.loads(ws.recv())
            if res.get("error_code"):
                print(f"ERROR: {res['error_code']} {res.get('error_message')}")
                os.unlink(mp3.name)
                return 1
            msg_tokens = res.get("tokens", [])
            text = parse_soniox_tokens(final_tokens, msg_tokens)
            has_partial = any(
                t.get("text") and not t.get("is_final") for t in msg_tokens
            )
            on_text(text, has_partial, len(text))
            if res.get("finished"):
                on_finished(render_tokens(final_tokens, []))
                break

    os.unlink(mp3.name)

    if finished["err"]:
        print("ERROR:", finished["err"])
        return 1
    if len(updates) < 5:
        print(f"FAIL: only {len(updates)} live updates (need >=5)")
        return 1
    if updates[-1][0] <= updates[0][0]:
        print(f"FAIL: text did not grow ({updates[0][0]} -> {updates[-1][0]})")
        return 1
    if len(finished["text"]) < 20:
        print(f"FAIL: final too short ({len(finished['text'])})")
        return 1

    print(
        f"OK: {len(updates)} live updates, "
        f"growth {updates[0][0]}->{updates[-1][0]}, final={len(finished['text'])} chars"
    )
    return 0


def cli_test_soniox():
    import requests
    from websockets.sync.client import connect

    key = get_soniox_key()
    if not key:
        print("ERROR: Soniox API key not found")
        return 1

    prepare_microphone()
    mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    r = requests.get("https://soniox.com/media/examples/coffee_shop.mp3", timeout=30)
    r.raise_for_status()
    mp3.write(r.content)
    mp3.close()

    config = {
        "api_key": key,
        "model": "stt-rt-v4",
        "language_hints": ["en"],
        "enable_endpoint_detection": True,
        "audio_format": "auto",
    }

    final_tokens = []
    print("Connecting to Soniox real-time API...")
    with connect(SONIOX_WS_URL, ping_interval=20, ping_timeout=60) as ws:
        ws.send(json.dumps(config))
        with open(mp3.name, "rb") as fh:
            while True:
                data = fh.read(3840)
                if not data:
                    break
                ws.send(data)
                time.sleep(0.05)
        ws.send("")
        while True:
            msg = ws.recv()
            res = json.loads(msg)
            if res.get("error_code"):
                print(f"ERROR: {res['error_code']} — {res.get('error_message')}")
                os.unlink(mp3.name)
                return 1
            for token in res.get("tokens", []):
                if token.get("is_final") and token.get("text"):
                    final_tokens.append(token)
            if res.get("finished"):
                break

    os.unlink(mp3.name)
    text = render_tokens(final_tokens, [])
    print("OK:", text[:200])
    return 0 if text.strip() else 1


def cli_test_mic(seconds=3):
    prepare_microphone()
    _source, rate, label = resolve_mic_choice(pinned_source=load_mic_config())
    print(f"Mic: {label} @ {rate}Hz, recording {seconds}s...")
    chunks = []

    def cb(indata, frames, ti, st):
        chunks.append(indata.copy())

    with _sounddevice().InputStream(samplerate=rate, channels=1, dtype="int16", callback=cb):
        time.sleep(seconds)

    raw = np.concatenate(chunks)
    peak = audio_peak(raw)
    print(f"peak={peak:.4f}")
    path = save_debug_wav(raw, rate, "cli-test")
    if path:
        print(f"saved {path}")

    audio16 = resample_to_16k(raw, rate)
    text, err = transcribe_async_rest(audio16)
    if err:
        print("async error:", err)
    print("text:", repr(text[:200]))
    return 0 if text.strip() else 1


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            raise SystemExit(cli_test_soniox())
        if sys.argv[1] == "--test-rt-e2e":
            raise SystemExit(cli_test_rt_e2e())
        if sys.argv[1] == "--test-mic":
            sec = float(sys.argv[2]) if len(sys.argv) > 2 else 3
            raise SystemExit(cli_test_mic(sec))
        if sys.argv[1] == "--test-ui":
            raise SystemExit(cli_test_ui_e2e())

    if TkinterDnD is not None:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = DictationApp(root)
    root.protocol("WM_DELETE_WINDOW", app.shutdown)
    try:
        signal.signal(signal.SIGINT, lambda *_: app.shutdown())
        signal.signal(signal.SIGTERM, lambda *_: app.shutdown())
    except Exception:
        pass
    root.mainloop()


if __name__ == "__main__":
    main()
