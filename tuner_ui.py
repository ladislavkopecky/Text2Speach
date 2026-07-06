import os
import asyncio
import tempfile
import threading
import subprocess
import time
import json
import tkinter as tk
from tkinter import filedialog
from dataclasses import dataclass

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout

import imageio_ffmpeg


KV = """
#:import C kivy.utils.get_color_from_hex

<MoonButton@Button>:
    background_color: C("#2d1b4e")
    background_normal: ""
    color: C("#c8b8e8")
    bold: True
    canvas.before:
        Color:
            rgba: C("#1a0838") if self.state == "down" else C("#150d2e")
        RoundedRectangle:
            pos: self.pos[0] + (2 if self.state == "down" else 0), self.pos[1] - (2 if self.state == "down" else 0)
            size: self.size
            radius: [6]
        Color:
            rgba: C("#5a3090") if self.state == "down" else C("#3d2060")
        RoundedRectangle:
            pos: self.pos[0] + (1 if self.state == "down" else -1), self.pos[1] - (1 if self.state == "down" else 1)
            size: self.size
            radius: [6]

<MoonToggle@ToggleButton>:
    background_normal: ""
    background_down: ""
    background_color: 0, 0, 0, 0
    color: C("#c8b8e8")
    bold: True
    on_state: self.canvas.ask_update()
    canvas.before:
        Color:
            rgba: C("#8b44cc") if self.state == "down" else C("#3d2060")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [6]

<RootUI>:
    orientation: "vertical"
    padding: 12
    spacing: 8
    canvas.before:
        Color:
            rgba: C("#0d0820")
        Rectangle:
            pos: self.pos
            size: self.size

    Label:
        text: "Ladění charakteru hlasu"
        size_hint_y: None
        height: 34
        font_size: "20sp"
        color: C("#b39ddb")
        bold: True

    TextInput:
        id: preview_text
        text: root.preview_text
        multiline: True
        size_hint_y: 1
        on_text: root.preview_text = self.text
        background_color: C("#150d2e")
        foreground_color: C("#d4c8f0")
        cursor_color: C("#9b6dca")
        hint_text_color: C("#5a4575")

    BoxLayout:
        size_hint_y: None
        height: 28
        Label:
            text: "Výška hlasu (Hz): " + str(int(root.pitch_hz))
            color: C("#a78fc0")
        Label:
            text: "Tempo řeči (%): " + str(int(root.rate_pct))
            color: C("#a78fc0")
        Label:
            text: "Hlasitost (%): " + str(int(root.volume_pct))
            color: C("#a78fc0")

    BoxLayout:
        size_hint_y: None
        height: 36
        Slider:
            min: -100
            max: 20
            step: 1
            value: root.pitch_hz
            on_value: root.set_pitch(self.value)
            cursor_image: ""
            value_track: True
            value_track_color: C("#7c4daa")
            value_track_width: 3
        Slider:
            min: -50
            max: 30
            step: 1
            value: root.rate_pct
            on_value: root.set_rate(self.value)
            cursor_image: ""
            value_track: True
            value_track_color: C("#7c4daa")
            value_track_width: 3
        Slider:
            min: -60
            max: 20
            step: 1
            value: root.volume_pct
            on_value: root.set_volume(self.value)
            cursor_image: ""
            value_track: True
            value_track_color: C("#7c4daa")
            value_track_width: 3

    BoxLayout:
        size_hint_y: None
        height: 28
        Label:
            text: "Koeficient výšky (temný styl): " + ("%.2f" % root.dark_pitch_factor)
            color: C("#a78fc0")
        Label:
            text: "Zpoždění echa (ms): " + str(int(root.echo_ms))
            color: C("#a78fc0")
        Label:
            text: "Zesílení výstupu (dB): " + str(int(root.output_gain_db))
            color: C("#a78fc0")

    BoxLayout:
        size_hint_y: None
        height: 36
        Slider:
            min: 0.70
            max: 1.05
            step: 0.01
            value: root.dark_pitch_factor
            on_value: root.set_dark_pitch(self.value)
            cursor_image: ""
            value_track: True
            value_track_color: C("#7c4daa")
            value_track_width: 3
        Slider:
            min: 0
            max: 300
            step: 5
            value: root.echo_ms
            on_value: root.set_echo_ms(self.value)
            cursor_image: ""
            value_track: True
            value_track_color: C("#7c4daa")
            value_track_width: 3
        Slider:
            min: -12
            max: 6
            step: 1
            value: root.output_gain_db
            on_value: root.set_output_gain(self.value)
            cursor_image: ""
            value_track: True
            value_track_color: C("#7c4daa")
            value_track_width: 3

    BoxLayout:
        size_hint_y: None
        height: 42
        spacing: 4
        MoonButton:
            text: "Načíst text ze souboru"
            on_release: root.request_load_text()
        MoonButton:
            text: root.preview_button_text
            on_release: root.toggle_preview_or_stop()
        MoonButton:
            text: "Uložit MP3 jako..."
            on_release: root.request_save_mp3()
        MoonToggle:
            id: live_toggle
            text: "Živý náhled: VYP" if self.state == "normal" else "Živý náhled: ZAP"
            on_state: root.set_live(self.state == "down")

    BoxLayout:
        size_hint_y: None
        height: 36
        spacing: 4
        MoonButton:
            text: "Uložit nastavení"
            on_release: root.save_params()
        MoonButton:
            text: "Načíst nastavení"
            on_release: root.load_params()

    BoxLayout:
        size_hint_y: None
        height: 22
        spacing: 8
        canvas.before:
            Color:
                rgba: C("#1a0e33")
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [4]
        ProgressBar:
            max: root.playback_max
            value: root.playback_progress
        Label:
            size_hint_x: None
            width: 130
            text: root.playback_time
            color: C("#9b8ab8")

    Label:
        text: root.status
        size_hint_y: None
        height: 24
        color: C("#7c6899")
        italic: True
"""

@dataclass
class Params:
    voice: str = "cs-CZ-AntoninNeural"
    pitch_hz: int = -15
    rate_pct: int = -18
    volume_pct: int = -8
    dark_pitch_factor: float = 0.90
    echo_ms: int = 100
    output_gain_db: int = -2
    base_sr: int = 24000


class RootUI(BoxLayout):
    preview_text = StringProperty("Testování pohádkových zvuků. Sem napiš text, nebo načti soubor s pohádkou. Pak klikni na tlačítko Přehrát náhled, nebo Uložit MP3 jako...")
    status = StringProperty("Připraveno")
    pitch_hz = NumericProperty(-15)
    rate_pct = NumericProperty(-18)
    volume_pct = NumericProperty(-8)
    dark_pitch_factor = NumericProperty(0.90)
    echo_ms = NumericProperty(100)
    output_gain_db = NumericProperty(-2)
    live_mode = BooleanProperty(False)
    playback_progress = NumericProperty(0.0)
    playback_max = NumericProperty(1.0)
    playback_time = StringProperty("00:00 / 00:00")
    preview_button_text = StringProperty("Náhled [>-------]")
    is_playing = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.params = Params()
        self._debounce_ev = None
        self._worker_lock = threading.Lock()
        self._running = False
        self._play_proc = None
        self._sound = None
        self._playback_ev = None
        self._playback_duration = 0.0
        self._playback_started_at = 0.0
        self._preview_btn_ev = None
        self._preview_btn_pos = 0
        self._processing_ev = None
        self._processing_started_at = 0.0
        self._processing_base_text = ""

    def set_pitch(self, v):
        self.pitch_hz = int(v)
        self.params.pitch_hz = int(v)
        self._schedule_live()

    def set_rate(self, v):
        self.rate_pct = int(v)
        self.params.rate_pct = int(v)
        self._schedule_live()

    def set_volume(self, v):
        self.volume_pct = int(v)
        self.params.volume_pct = int(v)
        self._schedule_live()

    def set_dark_pitch(self, v):
        self.dark_pitch_factor = float(v)
        self.params.dark_pitch_factor = float(v)
        self._schedule_live()

    def set_echo_ms(self, v):
        self.echo_ms = int(v)
        self.params.echo_ms = int(v)
        self._schedule_live()

    def set_output_gain(self, v):
        self.output_gain_db = int(v)
        self.params.output_gain_db = int(v)
        self._schedule_live()

    def set_live(self, on):
        self.live_mode = on
        if on:
            self.request_preview()

    def _schedule_live(self):
        if not self.live_mode:
            return
        if self._debounce_ev:
            self._debounce_ev.cancel()
        self._debounce_ev = Clock.schedule_once(lambda dt: self.request_preview(), 0.35)

    def toggle_preview_or_stop(self):
        if self.is_playing:
            self.stop_playback()
        else:
            self.request_preview()

    def request_preview(self):
        if self._running:
            return
        text = self.preview_text.strip()
        if not text:
            self.status = "Text je prázdný"
            return
        threading.Thread(target=self._render_and_play, args=(text,), daemon=True).start()

    def request_load_text(self):
        file_path = self._choose_input_text_file()
        if not file_path:
            self.status = "Načítání zrušeno"
            return

        text = self._read_text_file(file_path)
        if text is None:
            return

        self.preview_text = text
        self.status = f"Načteno: {file_path}"

    def request_save_mp3(self):
        if self._running:
            self.status = "Počkejte na dokončení aktuální úlohy"
            return
        text = self.preview_text.strip()
        if not text:
            self.status = "Text je prázdný"
            return

        output_path = self._choose_output_path()
        if not output_path:
            self.status = "Uložení zrušeno"
            return

        threading.Thread(target=self._render_and_save, args=(text, output_path), daemon=True).start()

    def _render_and_play(self, text):
        with self._worker_lock:
            self._running = True
            started_at = time.perf_counter()
            try:
                Clock.schedule_once(lambda dt: self._start_processing_indicator("Generuji náhled"), 0)
                raw_mp3 = os.path.join(tempfile.gettempdir(), "kivy_voice_raw.mp3")
                dark_wav = os.path.join(tempfile.gettempdir(), "kivy_voice_dark.wav")

                asyncio.run(self._edge_tts(text, raw_mp3))
                self._stylize(raw_mp3, dark_wav)

                elapsed = time.perf_counter() - started_at
                Clock.schedule_once(
                    lambda dt: self._play_preview_in_app(dark_wav, elapsed),
                    0,
                )
            except Exception as e:
                Clock.schedule_once(lambda dt: self._set_status("Chyba: " + str(e)), 0)
            finally:
                Clock.schedule_once(lambda dt: self._stop_processing_indicator(), 0)
                self._running = False

    def _play_preview_in_app(self, audio_path, elapsed):
        self.stop_playback(update_status=False)
        self._sound = SoundLoader.load(audio_path)
        if not self._sound:
            self._set_status("Chyba: Přímé přehrání v aplikaci se nepodařilo")
            return
        self._sound.play()
        self._playback_duration = float(getattr(self._sound, "length", 0.0) or 0.0)
        self._playback_started_at = time.perf_counter()
        self.playback_max = self._playback_duration if self._playback_duration > 0 else 1.0
        self.playback_progress = 0.0
        self.playback_time = "00:00 / " + (self._format_time(self._playback_duration) if self._playback_duration > 0 else "--:--")
        self.is_playing = True
        self._start_playback_indicator()
        self._start_preview_button_indicator()
        self._set_status(f"Přehrávám náhled (zpracováno za {elapsed:.2f} s)")

    def _render_and_save(self, text, output_path):
        with self._worker_lock:
            self._running = True
            try:
                Clock.schedule_once(lambda dt: self._start_processing_indicator("Generuji a ukládám MP3"), 0)
                raw_mp3 = os.path.join(tempfile.gettempdir(), "kivy_voice_raw.mp3")

                asyncio.run(self._edge_tts(text, raw_mp3))
                self._stylize(raw_mp3, output_path)

                Clock.schedule_once(lambda dt: self._set_status(f"Uloženo: {output_path}"), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self._set_status("Chyba: " + str(e)), 0)
            finally:
                Clock.schedule_once(lambda dt: self._stop_processing_indicator(), 0)
                self._running = False

    def _choose_output_path(self):
        default_name = "vystup.mp3"
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            selected = filedialog.asksaveasfilename(
                title="Uložit zvuk jako MP3",
                defaultextension=".mp3",
                initialfile=default_name,
                filetypes=[("MP3 soubor", "*.mp3"), ("Všechny soubory", "*.*")],
            )
            return selected or None
        finally:
            root.destroy()

    def _choose_input_text_file(self):
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            selected = filedialog.askopenfilename(
                title="Načíst textový soubor",
                filetypes=[("Textové soubory", "*.txt"), ("Všechny soubory", "*.*")],
            )
            return selected or None
        finally:
            root.destroy()

    def _read_text_file(self, file_path):
        for encoding in ("utf-8", "utf-8-sig", "cp1250", "latin-1"):
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except OSError as e:
                self.status = f"Chyba čtení: {e}"
                return None

        self.status = "Soubor nelze načíst v podporovaném kódování"
        return None

    async def _edge_tts(self, text, out_mp3):
        import edge_tts
        p = self.params
        communicate = edge_tts.Communicate(
            text=text,
            voice=p.voice,
            pitch=f"{p.pitch_hz:+d}Hz",
            rate=f"{p.rate_pct:+d}%",
            volume=f"{p.volume_pct:+d}%",
        )
        await communicate.save(out_mp3)

    def _stylize(self, input_mp3, output_mp3):
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        p = self.params
        echo_decay = 0.40
        filters = (
            f"asetrate={p.base_sr}*{p.dark_pitch_factor},"
            f"aresample={p.base_sr},"
            f"aecho=0.8:0.5:{p.echo_ms}:{echo_decay},"
            "lowpass=f=2200,"
            f"volume={p.output_gain_db}dB"
        )
        subprocess.run(
            [ffmpeg_exe, "-y", "-i", input_mp3, "-af", filters, output_mp3],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

    def stop_playback(self, update_status=True):
        self.is_playing = False
        self._stop_playback_indicator(reset=True)
        self._stop_preview_button_indicator(reset=True)
        if self._sound:
            self._sound.stop()
            self._sound = None
        if self._play_proc and self._play_proc.poll() is None:
            self._play_proc.terminate()
        self._play_proc = None
        if update_status:
            self.status = "Zastaveno"

    def _start_playback_indicator(self):
        self._stop_playback_indicator(reset=False)
        self._playback_ev = Clock.schedule_interval(self._update_playback_indicator, 0.1)
        self._update_playback_indicator(0)

    def _stop_playback_indicator(self, reset):
        if self._playback_ev:
            self._playback_ev.cancel()
            self._playback_ev = None
        if reset:
            self.playback_progress = 0.0
            self.playback_max = 1.0
            self.playback_time = "00:00 / 00:00"

    def _update_playback_indicator(self, dt):
        if not self._sound:
            self._stop_playback_indicator(reset=False)
            return False

        state = str(getattr(self._sound, "state", "")).lower()
        if state in ("stop", "stopped"):
            self.is_playing = False
            self._stop_playback_indicator(reset=False)
            self._stop_preview_button_indicator(reset=True)
            if self._playback_duration > 0:
                self.playback_progress = self._playback_duration
                self.playback_time = f"{self._format_time(self._playback_duration)} / {self._format_time(self._playback_duration)}"
            return False

        current = float(self._sound.get_pos() or 0.0)
        if current <= 0:
            current = time.perf_counter() - self._playback_started_at
        if current < 0:
            current = 0.0

        if self._playback_duration > 0:
            current = min(current, self._playback_duration)
            self.playback_progress = current
            self.playback_time = f"{self._format_time(current)} / {self._format_time(self._playback_duration)}"
        else:
            self.playback_progress = (self.playback_progress + 0.05) % self.playback_max
            self.playback_time = f"{self._format_time(current)} / --:--"

        return True

    def _format_time(self, seconds):
        total = max(0, int(seconds))
        minutes = total // 60
        secs = total % 60
        return f"{minutes:02d}:{secs:02d}"

    def _start_preview_button_indicator(self):
        self._stop_preview_button_indicator(reset=False)
        self._preview_btn_pos = 0
        self._preview_btn_ev = Clock.schedule_interval(self._update_preview_button_indicator, 0.12)
        self._update_preview_button_indicator(0)

    def _stop_preview_button_indicator(self, reset):
        if self._preview_btn_ev:
            self._preview_btn_ev.cancel()
            self._preview_btn_ev = None
        if reset:
            self.preview_button_text = "Náhled [>-------]"
            self.is_playing = False

    def _update_preview_button_indicator(self, dt):
        track_len = 8
        cells = ["-"] * track_len
        idx = self._preview_btn_pos % track_len
        cells[idx] = ">"
        self.preview_button_text = "Náhled [" + "".join(cells) + "]"
        self._preview_btn_pos += 1

    def _start_processing_indicator(self, base_text):
        self._stop_processing_indicator()
        self._processing_base_text = base_text
        self._processing_started_at = time.perf_counter()
        self._processing_ev = Clock.schedule_interval(self._update_processing_indicator, 0.2)
        self._update_processing_indicator(0)

    def _stop_processing_indicator(self):
        if self._processing_ev:
            self._processing_ev.cancel()
            self._processing_ev = None

    def _update_processing_indicator(self, dt):
        elapsed = time.perf_counter() - self._processing_started_at
        dots = "." * (int(elapsed * 5) % 4)
        self.status = f"{self._processing_base_text}{dots} ({elapsed:.1f} s)"

    def save_params(self):
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            path = filedialog.asksaveasfilename(
                title="Uložit nastavení hlasu",
                defaultextension=".json",
                initialfile="nastaveni_hlasu.json",
                filetypes=[("JSON soubor", "*.json"), ("Všechny soubory", "*.*")],
            )
        finally:
            root.destroy()
        if not path:
            self.status = "Uložení nastavení zrušeno"
            return
        p = self.params
        data = {
            "pitch_hz": p.pitch_hz,
            "rate_pct": p.rate_pct,
            "volume_pct": p.volume_pct,
            "dark_pitch_factor": p.dark_pitch_factor,
            "echo_ms": p.echo_ms,
            "output_gain_db": p.output_gain_db,
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.status = f"Nastavení uloženo: {path}"
        except OSError as e:
            self.status = f"Chyba uložení: {e}"

    def load_params(self):
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            path = filedialog.askopenfilename(
                title="Načíst nastavení hlasu",
                filetypes=[("JSON soubor", "*.json"), ("Všechny soubory", "*.*")],
            )
        finally:
            root.destroy()
        if not path:
            self.status = "Načítání nastavení zrušeno"
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            self.status = f"Chyba načítání: {e}"
            return
        mapping = {
            "pitch_hz": "set_pitch",
            "rate_pct": "set_rate",
            "volume_pct": "set_volume",
            "dark_pitch_factor": "set_dark_pitch",
            "echo_ms": "set_echo_ms",
            "output_gain_db": "set_output_gain",
        }
        for key, method in mapping.items():
            if key in data:
                getattr(self, method)(data[key])
        self.status = f"Nastavení načteno: {path}"

    def _set_status(self, msg):
        self.status = msg


class TunerApp(App):
    def build(self):
        Builder.load_string(KV)
        root = RootUI()
        root.ids.live_toggle.state = "normal"
        return root


if __name__ == "__main__":
    TunerApp().run()