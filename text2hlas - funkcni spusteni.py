import os
import asyncio
import tempfile
import subprocess
import sys


# Voice tuning parameters.
# LOCAL_TTS_RATE: rychlost pro lokalni Windows hlas v pyttsx3.
# Vyssi cislo = rychlejsi rec, nizsi cislo = pomalejsi rec.
LOCAL_TTS_RATE = 125

# LOCAL_TTS_VOLUME: hlasitost lokalniho hlasu v rozsahu 0.0 az 1.0.
# 1.0 = plna hlasitost, 0.0 = ticho.
LOCAL_TTS_VOLUME = 0.9

# EDGE_TTS_VOICE: jmeno online ceskeho hlasu z edge-tts.
# V tomto projektu je dostupny hlavne Antonin, tedy muzsky hlas.
EDGE_TTS_VOICE = 'cs-CZ-AntoninNeural'

# EDGE_TTS_PITCH: vyska hlasu pro edge-tts.
# Zaporne hodnoty zneji hloub, kladne vys.
EDGE_TTS_PITCH = '-15Hz'

# EDGE_TTS_RATE: tempo reci pro edge-tts.
# Zaporne procento zpomaluje, kladne zrychluje.
EDGE_TTS_RATE = '-18%'

# EDGE_TTS_VOLUME: hlasitost pro edge-tts.
# '+0%' je neutralni, zaporne hodnoty tlumi vystup.
EDGE_TTS_VOLUME = '-8%'

# USE_LOCAL_STYLIZATION: kdyz je True, po vygenerovani mp3 se pouzije lokalni
# post-process efekt pro tmavsi, hlubsi a trochu "zvukove" stylizovany hlas.
USE_LOCAL_STYLIZATION = True

# STYLE_PITCH_FACTOR: koeficient pro zmenu vysky hlasu v lokalnim ffmpeg filtru.
# Mensi cislo = hlubsi hlas, vetsi cislo = vyssi hlas.
STYLE_PITCH_FACTOR = 0.90

# STYLE_ECHO_MS: zpozdeni echa v milisekundach.
# Mensi cislo = mensi prostor, vetsi cislo = vetsi prostor.
STYLE_ECHO_MS = 100

# STYLE_ECHO_GAIN_DB: sila echa v decibelech.
# Kladne cislo echo zesili, zaporne cislo echo ztlumi.
STYLE_ECHO_GAIN_DB = 12

# STYLE_OUTPUT_GAIN_DB: celkove zesileni nebo utlumení finalniho souboru.
# Zaporne cislo výstup ztiší, kladne zesili.
STYLE_OUTPUT_GAIN_DB = -2

# STYLE_BASE_SAMPLE_RATE: zakladni vzorkovaci frekvence pro lokalni ffmpeg filtr.
# Tato hodnota musi odpovidat zdrojovemu MP3, ktere generuje edge-tts.
STYLE_BASE_SAMPLE_RATE = 24000


async def save_edge_tts_audio(text: str, output_path: str) -> None:
    import edge_tts

    # Vygeneruje ceske mp3 primo pres edge-tts.
    # Parametry voice/rate/pitch/volume urcuji zakladni barvu hlasu.
    communicate = edge_tts.Communicate(
        text=text,
        voice=EDGE_TTS_VOICE,
        pitch=EDGE_TTS_PITCH,
        rate=EDGE_TTS_RATE,
        volume=EDGE_TTS_VOLUME,
    )
    await communicate.save(output_path)


def stylize_dark_voice(input_mp3: str, output_mp3: str) -> None:
    import imageio_ffmpeg

    # Pouzije zabalenou binarku ffmpeg z imageio-ffmpeg, takze neni potreba
    # instalovat systemovy ffmpeg.
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    # Mensi echo_gain znamena silnejsi echo; prevedeme to na decay koeficient.
    echo_decay = max(0.05, min(0.95, 1 - (STYLE_ECHO_GAIN_DB / 20.0)))

    # Local filter chain pro temnejsi vypravecsky hlas:
    # 1. asetrate/aresample snizi nebo zvedne vysku hlasu,
    # 2. aecho pridava jemny prostor,
    # 3. lowpass odrizne vysoke frekvence,
    # 4. volume upravi celkovou hlasitost.
    filters = (
        f"asetrate={STYLE_BASE_SAMPLE_RATE}*{STYLE_PITCH_FACTOR},"
        f"aresample={STYLE_BASE_SAMPLE_RATE},"
        f"aecho=0.8:0.5:{STYLE_ECHO_MS}:{echo_decay},"
        "lowpass=f=2200,"
        f"volume={STYLE_OUTPUT_GAIN_DB}dB"
    )

    # Spusti ffmpeg a vytvori stylizovanou verzi mp3.
    subprocess.run(
        [
            ffmpeg_exe,
            '-y',
            '-i',
            input_mp3,
            '-af',
            filters,
            output_mp3,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

# Načti vstupní text ze souboru z příkazové řádky.
# Když žádný argument nedostaneš, použije se výchozí soubor pohadka.txt vedle skriptu.
if len(sys.argv) > 1:
    file_path = sys.argv[1]
else:
    file_path = os.path.join(os.path.dirname(__file__), 'pohadka.txt')


def build_output_path(input_path: str) -> str:
    # MP3 se uklada vedle skriptu a bere jmeno podle zdrojoveho textu.
    source_name = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(os.path.dirname(__file__), f'{source_name}.mp3')

if os.path.exists(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()

    output_mp3 = build_output_path(file_path)
    temp_mp3 = os.path.join(tempfile.gettempdir(), f'{os.path.splitext(os.path.basename(file_path))[0]}_raw.mp3')
    styled_mp3 = os.path.join(tempfile.gettempdir(), f'{os.path.splitext(os.path.basename(file_path))[0]}_dark.mp3')

    # Hlavni tok:
    # 1. z textoveho souboru vygeneruj MP3 pres edge-tts,
    # 2. podle USE_LOCAL_STYLIZATION aplikuj lokalni "temny" efekt,
    # 3. vysledek uloz vedle skriptu pod nazvem odvozenym ze vstupu,
    # 4. otevri vystup v systemovem prehravaci.
    print("Converting text to speech...")

    try:
        asyncio.run(save_edge_tts_audio(text, temp_mp3))

        final_output = temp_mp3
        if USE_LOCAL_STYLIZATION:
            try:
                stylize_dark_voice(temp_mp3, styled_mp3)
                final_output = styled_mp3
            except Exception as style_exc:
                print(f"Stylization failed, using base MP3: {style_exc}")

        if os.path.exists(output_mp3):
            os.remove(output_mp3)

        os.replace(final_output, output_mp3)
        os.startfile(output_mp3)
        print(f"Created Czech audio file: {output_mp3}")
        print("Playing audio in the system default player.")
    except ImportError:
        print("Required package is missing.")
        print("Install with: python -m pip install edge-tts imageio-ffmpeg")
    except Exception as exc:
        print(f"Fallback speech failed: {exc}")
else:
    print(f"File not found: {file_path}")
