import os
import asyncio
import tempfile
import threading
import subprocess
import sys
from dataclasses import dataclass

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout

import imageio_ffmpeg


KV = """
<RootUI>:
    orientation: "vertical"
    padding: 12
    spacing: 8

    Label:
        text: "Ladění charakteru hlasu"
        size_hint_y: None
        height: 34
        font_size: "20sp"

    TextInput:
        id: preview_text
        text: root.preview_text
        multiline: True
        size_hint_y: None
        height: 120
        on_text: root.preview_text = self.text

    BoxLayout:
        size_hint_y: None
        height: 28
        Label:
            text: "Výška hlasu (Hz): " + str(int(root.pitch_hz))
        Label:
            text: "Tempo řeči (%): " + str(int(root.rate_pct))
        Label:
            text: "Hlasitost (%): " + str(int(root.volume_pct))

    BoxLayout:
        size_hint_y: None
        height: 36
        Slider:
            min: -40
            max: 20
            step: 1
            value: root.pitch_hz
            on_value: root.set_pitch(self.value)
        Slider:
            min: -50
            max: 30
            step: 1
            value: root.rate_pct
            on_value: root.set_rate(self.value)
        Slider:
            min: -60
            max: 20
            step: 1
            value: root.volume_pct
            on_value: root.set_volume(self.value)

    BoxLayout:
        size_hint_y: None
        height: 28
        Label:
            text: "Koeficient výšky (temný styl): " + ("%.2f" % root.dark_pitch_factor)
        Label:
            text: "Zpoždění echa (ms): " + str(int(root.echo_ms))
        Label:
            text: "Zesílení výstupu (dB): " + str(int(root.output_gain_db))

    BoxLayout:
        size_hint_y: None
        height: 36
        Slider:
            min: 0.70
            max: 1.05
            step: 0.01
            value: root.dark_pitch_factor
            on_value: root.set_dark_pitch(self.value)
        Slider:
            min: 0
            max: 300
            step: 5
            value: root.echo_ms
            on_value: root.set_echo_ms(self.value)
        Slider:
            min: -12
            max: 6
            step: 1
            value: root.output_gain_db
            on_value: root.set_output_gain(self.value)

    BoxLayout:
        size_hint_y: None
        height: 42
        Button:
            text: "Přehrát náhled"
            on_release: root.request_preview()
        ToggleButton:
            id: live_toggle
            text: "Živý náhled: VYP" if self.state == "normal" else "Živý náhled: ZAP"
            on_state: root.set_live(self.state == "down")
        Button:
            text: "Zastavit zvuk"
            on_release: root.stop_playback()

    Label:
        text: root.status
        size_hint_y: None
        height: 24
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
    preview_text = StringProperty("Zrcadlo, zrcadlo, kdo je v zemi zdejší nejkrásnější?")
    status = StringProperty("Připraveno")
    pitch_hz = NumericProperty(-15)
    rate_pct = NumericProperty(-18)
    volume_pct = NumericProperty(-8)
    dark_pitch_factor = NumericProperty(0.90)
    echo_ms = NumericProperty(100)
    output_gain_db = NumericProperty(-2)
    live_mode = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.params = Params()
        self._debounce_ev = None
        self._worker_lock = threading.Lock()
        self._running = False
        self._play_proc = None

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

    def request_preview(self):
        if self._running:
            return
        text = self.preview_text.strip()
        if not text:
            self.status = "Text je prázdný"
            return
        threading.Thread(target=self._render_and_play, args=(text,), daemon=True).start()

    def _render_and_play(self, text):
        with self._worker_lock:
            self._running = True
            try:
                Clock.schedule_once(lambda dt: self._set_status("Generuji..."), 0)
                raw_mp3 = os.path.join(tempfile.gettempdir(), "kivy_voice_raw.mp3")
                dark_mp3 = os.path.join(tempfile.gettempdir(), "kivy_voice_dark.mp3")

                asyncio.run(self._edge_tts(text, raw_mp3))
                self._stylize(raw_mp3, dark_mp3)

                self.stop_playback()
                ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
                ffplay_exe = os.path.join(ffmpeg_dir, "ffplay.exe")
                if os.path.exists(ffplay_exe):
                    self._play_proc = subprocess.Popen(
                        [ffplay_exe, "-nodisp", "-autoexit", "-loglevel", "quiet", dark_mp3],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    os.startfile(dark_mp3)

                Clock.schedule_once(lambda dt: self._set_status("Přehrávám náhled"), 0)
            except Exception as e:
                Clock.schedule_once(lambda dt: self._set_status("Chyba: " + str(e)), 0)
            finally:
                self._running = False

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

    def stop_playback(self):
        if self._play_proc and self._play_proc.poll() is None:
            self._play_proc.terminate()
        self._play_proc = None
        self.status = "Zastaveno"

    def _set_status(self, msg):
        self.status = msg


def load_initial_text_from_args() -> tuple[str | None, str | None]:
    # Načti textový soubor včetně českých znaků.
    # Priorita:
    # 1) 1. argument CLI
    # 2) výchozí soubor pohadka-test.txt vedle skriptu
    # Kódování: UTF-8/UTF-8 BOM, pak fallback na cp1250 a latin-1.
    if len(sys.argv) >= 2:
        input_path = sys.argv[1]
    else:
        input_path = os.path.join(os.path.dirname(__file__), "pohadka-test.txt")
        if not os.path.exists(input_path):
            return None, None

    if not os.path.exists(input_path):
        return None, f"Soubor nebyl nalezen: {input_path}"

    for encoding in ("utf-8", "utf-8-sig", "cp1250", "latin-1"):
        try:
            with open(input_path, "r", encoding=encoding) as f:
                return f.read(), f"Načteno ze souboru: {input_path} ({encoding})"
        except UnicodeDecodeError:
            continue

    return None, f"Soubor nelze načíst v podporovaném kódování: {input_path}"


class TunerApp(App):
    def build(self):
        Builder.load_string(KV)
        root = RootUI()
        loaded_text, message = load_initial_text_from_args()
        if loaded_text:
            root.preview_text = loaded_text
        if message:
            root.status = message
        root.ids.live_toggle.state = "down"
        return root


if __name__ == "__main__":
    TunerApp().run()