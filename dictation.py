#!/usr/bin/env python3
"""
Coco Dictation — 语音转文字桌面应用
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
import sounddevice as sd
import tkinter as tk
from tkinter import scrolledtext, ttk

SONIOX_TARGET_RATE = 16000
CHUNK_MS = 120
SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
LOG_DIR = os.path.expanduser("~/.local/share/coco-dictation")
LOG_FILE = os.path.join(LOG_DIR, "dictation.log")
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
        os.path.expanduser("~/.soniox_key"),
        os.path.join(os.path.dirname(__file__), ".soniox_key"),
    ):
        if os.path.exists(path):
            with open(path) as f:
                return f.read().strip()
    return None


def render_tokens(final_tokens, non_final_tokens):
    parts = []
    for token in final_tokens + non_final_tokens:
        text = token.get("text") or ""
        if text in ("<end>", "<fin>"):
            continue
        parts.append(text)
    return "".join(parts)


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


def pick_mic_source():
    sources = discover_pipewire_sources()
    for src in sources:
        name = src["name"]
        if "acp63" in name or "dmic" in name.lower():
            return name, 48000, "内置数字麦克风 (acp63)"
    for src in sources:
        name = src["name"]
        if "Generic_1__source" in name or "ALC257" in name:
            return name, 44100, "模拟麦克风 (ALC257)"
    for src in sources:
        if src.get("class") == "Audio/Source":
            return src["name"], 48000, src["name"]
    return None, 48000, "系统默认"


def prepare_microphone():
    for cmd in (
        ["amixer", "-c", "1", "set", "Capture", "cap"],
        ["amixer", "-c", "1", "set", "Mic Boost", "3"],
    ):
        try:
            subprocess.run(cmd, capture_output=True, timeout=3)
        except Exception:
            pass

    source, sample_rate, label = pick_mic_source()
    if source:
        os.environ["PULSE_SOURCE"] = source
        log(f"mic source={source} rate={sample_rate} label={label}")
    else:
        log("mic source=default")
    return sample_rate, label


def audio_peak(audio):
    if audio.size == 0:
        return 0.0
    if audio.ndim > 1:
        audio = audio[:, 0]
    return float(abs(audio).max()) / 32768.0


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
            open_timeout=8,
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
        self.audio_q.put(None)

    def _send_loop(self):
        try:
            while True:
                chunk = self.audio_q.get()
                if chunk is None:
                    break
                self._ws.send(chunk.tobytes())
            self._ws.send("")
            log("soniox audio stream ended")
        except Exception as exc:
            log(f"soniox send error: {exc}")
            self.on_error(str(exc))

    def _recv_loop(self):
        try:
            while True:
                msg = self._ws.recv()
                res = json.loads(msg)
                if res.get("error_code"):
                    err = f"{res['error_code']}: {res.get('error_message', '')}"
                    log(f"soniox server error: {err}")
                    self.on_error(err)
                    break

                non_final = []
                for token in res.get("tokens", []):
                    if not token.get("text"):
                        continue
                    if token.get("is_final"):
                        self.final_tokens.append(token)
                    else:
                        non_final.append(token)

                text = render_tokens(self.final_tokens, non_final)
                self.on_text(text, bool(non_final))

                if res.get("finished"):
                    final_text = render_tokens(self.final_tokens, [])
                    log(f"soniox finished len={len(final_text)}")
                    self.on_finished(final_text)
                    break
        except Exception as exc:
            final_text = render_tokens(self.final_tokens, [])
            log(f"soniox recv error: {exc}; partial len={len(final_text)}")
            if final_text.strip():
                self.on_finished(final_text)
            elif self._running:
                self.on_error(str(exc))
        finally:
            try:
                self._ws.close()
            except Exception:
                pass


class DictationApp:
    def __init__(self, root):
        self.root = root
        root.title("Coco Dictation")
        root.geometry("480x680")
        root.configure(bg=BG)
        root.minsize(400, 560)

        self.recording = False
        self.audio_stream = None
        self.capture_rate = 48000
        self.mic_label = "系统默认"
        self.mode = tk.StringVar(value="soniox")
        self.whisper_model = None
        self.soniox_session = None
        self.live_start_index = "1.0"
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

        self._setup_styles()
        self._build_ui()
        self._write_pid_file()
        self._register_raise_handler()
        self.root.bind("<space>", self._on_space_key)
        self.root.after(0, self._init_background)
        log("app started")

    def _write_pid_file(self):
        path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "coco-dictation.pid")
        try:
            with open(path, "w") as f:
                f.write(str(os.getpid()))
        except OSError as exc:
            log(f"pid file write failed: {exc}")

    def _remove_pid_file(self):
        path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "coco-dictation.pid")
        try:
            os.remove(path)
        except OSError:
            pass

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

    def _toggle_pin(self):
        self.always_on_top = not self.always_on_top
        self.root.attributes("-topmost", self.always_on_top)
        if self.always_on_top:
            self.pin_btn.config(bg=ACCENT, fg=TEXT, text="已置顶", activebackground=ACCENT2)
        else:
            self.pin_btn.config(bg=CARD2, fg=MUTED, text="置顶", activebackground=BORDER)
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
        prepare_microphone()
        self.capture_rate, self.mic_label = pick_mic_source()[1:]
        if not self.mic_label:
            self.capture_rate, self.mic_label = 48000, "系统默认"
        self.chunk_samples = self.capture_rate * CHUNK_MS // 1000
        self.mic_info_label.config(text=f"麦克风 · {self.mic_label} @ {self.capture_rate}Hz")
        self._start_mic_monitor()

    def _start_mic_monitor(self):
        prepare_microphone()
        self.capture_rate, self.mic_label = pick_mic_source()[1:]
        self.chunk_samples = self.capture_rate * CHUNK_MS // 1000
        self.mic_info_label.config(text=f"麦克风 · {self.mic_label} @ {self.capture_rate}Hz")

        def callback(indata, frames, time_info, status):
            if self._shutting_down:
                raise sd.CallbackAbort
            peak = audio_peak(indata)
            if self.recording:
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
                self._level_pending = peak
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
            self.audio_stream = sd.InputStream(
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

    def _flush_level(self):
        if self._shutting_down:
            return
        peak = self._level_pending or 0.0
        self._level_pending = None
        pct = min(100, int(peak * 100))
        self.level_bar["value"] = pct
        self.level_label.config(text=f"{pct}%")

    def _build_ui(self):
        shell = tk.Frame(self.root, bg=BG, padx=20, pady=16)
        shell.pack(fill="both", expand=True)

        header = tk.Frame(shell, bg=BG)
        header.pack(fill="x", pady=(0, 14))
        tk.Label(
            header,
            text="Coco Dictation",
            font=("Segoe UI", 22, "bold"),
            bg=BG,
            fg=TEXT,
        ).pack(side="left")
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
            text="就绪 — 空格键可开始/停止",
            font=("Segoe UI", 11),
            bg=PANEL,
            fg=MUTED,
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
        self.model_label = tk.Label(opts, text="", font=("Segoe UI", 10), bg=BG, fg=MUTED)
        self.model_label.pack(side="right")

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

        self.mic_info_label = tk.Label(
            shell,
            text=f"麦克风 · {self.mic_label}",
            font=("Segoe UI", 10),
            bg=BG,
            fg="#52525b",
        )
        self.mic_info_label.pack(anchor="w", pady=(0, 8))

        out_head = tk.Frame(shell, bg=BG)
        out_head.pack(fill="x", pady=(0, 6))
        tk.Label(
            out_head,
            text="识别结果",
            font=("Segoe UI", 13, "bold"),
            bg=BG,
            fg=TEXT,
        ).pack(side="left")
        self._pill_btn(
            out_head,
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
            out_head,
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
        self.text_area.insert("1.0", "录音时这里会实时出字，停止后定稿保留\n")

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

    def _refresh_mode_ui(self):
        mode = self.mode.get()
        if mode == "soniox":
            self.soniox_btn.config(bg=ACCENT, fg=TEXT, font=("Segoe UI", 10, "bold"))
            self.local_btn.config(bg=CARD2, fg=MUTED, font=("Segoe UI", 10))
            self.model_label.config(text="")
        else:
            self.local_btn.config(bg=ACCENT, fg=TEXT, font=("Segoe UI", 10, "bold"))
            self.soniox_btn.config(bg=CARD2, fg=MUTED, font=("Segoe UI", 10))
            if self.whisper_model:
                self.model_label.config(text="small 模型已就绪")

    def _switch_mode(self, mode):
        if self.recording:
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
                self.root.after(
                    0,
                    lambda: self.model_label.config(
                        text="缺少 faster-whisper: pip install faster-whisper"
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

    def _toggle_record(self):
        if self.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if self.mode.get() == "soniox" and not get_soniox_key():
            self.status_label.config(text="未配置 Soniox API Key", fg="#ff6b6b")
            return
        if self.mode.get() == "local" and not self.whisper_model:
            self.status_label.config(text="本地模型未就绪", fg="#ff6b6b")
            self._load_local_model()
            return
        if not self.mic_ok:
            self._start_mic_monitor()
            if not self.mic_ok:
                return

        self.recording = True
        self.record_started_at = time.time()
        hint = self.text_area.get("1.0", "end-1c")
        if hint.startswith("录音时这里会实时"):
            self.text_area.delete("1.0", "end")
        self.live_start_index = self.text_area.index("end-1c")
        self.local_chunks = []
        self.peak_level = 0.0
        self.last_raw_audio = None
        self._rt_pending = []
        self.level_bar["value"] = 0
        self.level_label.config(text="0%")

        self.record_btn.config(text="停止录音", bg=BTN_ON)
        self.status_label.config(text="正在连接… 请对着麦克风说话", fg="#ff6b6b")
        log(f"record start mode={self.mode.get()} rate={self.capture_rate}")

        if self.mode.get() == "soniox":
            self.soniox_session = SonioxRealtimeSession(
                get_soniox_key(),
                on_text=self._on_live_text,
                on_error=self._on_soniox_error,
                on_finished=self._on_soniox_finished,
                on_ready=self._on_rt_ready,
            )
            threading.Thread(target=self._connect_rt, daemon=True).start()

    def _connect_rt(self):
        try:
            self.soniox_session.start()
            self.root.after(
                0,
                lambda: self.status_label.config(
                    text="正在录音… 实时转写中", fg="#ff6b6b"
                ),
            )
        except Exception as exc:
            log(f"soniox connect failed: {exc}")
            self.root.after(0, lambda: self._on_rt_connect_failed(str(exc)))

    def _on_rt_connect_failed(self, msg):
        self.recording = False
        self.record_btn.config(text="开始录音", bg=BTN_BG)
        self.status_label.config(text=f"连接失败: {msg}", fg="#ff6b6b")
        self.soniox_session = None

    def _on_rt_ready(self):
        session = self.soniox_session
        if not session:
            return
        for chunk in self._rt_pending:
            session.push_audio(chunk)
        self._rt_pending.clear()
        session.flush_pending()
        log("rt audio flushed")

    def _stop_recording(self):
        self.recording = False
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

        if peak < 0.01:
            self._abort_session()
            self.status_label.config(
                text=f"没收到有效声音 (peak={peak:.3f})，请检查麦克风权限/静音",
                fg="#ff6b6b",
            )
            save_debug_wav(raw, self.capture_rate, "silent")
            return

        if self.mode.get() == "soniox":
            if self.soniox_session:
                self.status_label.config(text="正在识别...", fg=ORANGE)
                self.progress.pack(pady=(6, 0))
                self.progress.start()
                self.soniox_session.stop()
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

    def _abort_session(self):
        if self.soniox_session:
            self.soniox_session.stop()
            self.soniox_session = None

    def _on_live_text(self, text, partial):
        def update():
            self.text_area.delete(self.live_start_index, "end")
            if text:
                suffix = " …" if partial else ""
                self.text_area.insert("end", text + suffix)
            self.text_area.see("end")

        self.root.after(0, update)

    def _on_soniox_error(self, message):
        def update():
            self.progress.stop()
            self.progress.pack_forget()
            self.status_label.config(text=f"识别错误: {message}", fg="#ff6b6b")
            self._fallback_async("soniox-error")

        self.root.after(0, update)

    def _on_soniox_finished(self, text):
        def update():
            self.progress.stop()
            self.progress.pack_forget()
            self.text_area.delete(self.live_start_index, "end")
            if text.strip():
                self.text_area.insert("end", text.strip() + "\n")
                self.text_area.see("end")
                self.soniox_session = None
                if self.auto_copy.get():
                    self.root.clipboard_clear()
                    self.root.clipboard_append(text.strip())
                    self.status_label.config(
                        text=f"完成 — {len(text.strip())} 字 · 已复制", fg=GREEN
                    )
                else:
                    self.status_label.config(
                        text=f"完成 — {len(text.strip())} 字", fg=GREEN
                    )
            else:
                self.status_label.config(text="实时识别为空，正在重试...", fg=ORANGE)
                self._fallback_async("soniox-empty")

        self.root.after(0, update)

    def _fallback_async(self, reason):
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
        self.text_area.delete(self.live_start_index, "end")
        if text.strip():
            self.text_area.insert("end", text.strip() + "\n")
            self.text_area.see("end")
            if self.auto_copy.get():
                self.root.clipboard_clear()
                self.root.clipboard_append(text.strip())
                self.status_label.config(
                    text=f"完成 — {len(text.strip())} 字 (备用识别) · 已复制", fg=GREEN
                )
            else:
                self.status_label.config(
                    text=f"完成 — {len(text.strip())} 字 (备用识别)", fg=GREEN
                )
            return

        path = save_debug_wav(self.last_raw_audio, self.capture_rate, "failed")
        hint = f"peak={peak:.3f}"
        if path:
            hint += f"，录音已保存到 {path}"
        if err:
            hint = f"{err}; {hint}"
        self.status_label.config(text=f"没听清 ({hint})", fg="#ff6b6b")
        log(f"fallback failed {hint}")

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

    def _copy_all(self):
        text = self.text_area.get("1.0", "end-1c")
        if text.strip():
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.status_label.config(text="已复制到剪贴板", fg=GREEN)
        else:
            self.status_label.config(text="没有内容", fg=ORANGE)

    def _clear(self):
        self.text_area.delete("1.0", "end")
        self.status_label.config(text="已清空", fg=GRAY)

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
        self.status_label.config(text=f"已保存: {path}", fg=GREEN)


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
    rate, label = pick_mic_source()[1:]
    print(f"Mic: {label} @ {rate}Hz, recording {seconds}s...")
    chunks = []

    def cb(indata, frames, ti, st):
        chunks.append(indata.copy())

    with sd.InputStream(samplerate=rate, channels=1, dtype="int16", callback=cb):
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
        if sys.argv[1] == "--test-mic":
            sec = float(sys.argv[2]) if len(sys.argv) > 2 else 3
            raise SystemExit(cli_test_mic(sec))

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
