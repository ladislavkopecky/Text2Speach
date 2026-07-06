import os
import asyncio
import tempfile
import subprocess
import sys
import re
import unicodedata


# Voice tuning parameters.
# Rychlost řeči
# Vyssi cislo = rychlejsi rec, nizsi cislo = pomalejsi rec.
LOCAL_TTS_RATE = 120

# Hlasitost hlasu
# 1.0 = plna hlasitost, 0.0 = ticho.
LOCAL_TTS_VOLUME = 0.9

# Jméno českého hlasu
# V tomto projektu je dostupny hlavne Antonin, tedy muzsky hlas.
EDGE_TTS_VOICE = 'cs-CZ-AntoninNeural'

# Výška hlasu
# Zaporne hodnoty zneji hloub, kladne vys.
EDGE_TTS_PITCH = '-15Hz'

# Tempo řeči
# Zaporne procento zpomaluje, maximalni hodnota je -1
EDGE_TTS_RATE = '-18%'

# Hlasitost
# '+0%' je neutralni, zaporne hodnoty tlumi vystup.
EDGE_TTS_VOLUME = '-8%'

# Ceske znacky pro intonaci v textu.
# Priklad:
# [hluboky]Jsem temny hlas.[/hluboky]
# [otazka]Kdo se diva do zrcadla?[/otazka]
# [krik]Ty se opovaz![/krik]
# [septani]Tohle je tajemstvi...[/septani]
# [povzdych]Ach jo...[/povzdych]
STYLE_PRESETS = {
    'normalni': {'pitch': EDGE_TTS_PITCH, 'rate': EDGE_TTS_RATE, 'volume': EDGE_TTS_VOLUME},
    'hluboky': {'pitch': '-28Hz', 'rate': '-22%', 'volume': '-6%'},
    'otazka': {'pitch': '-4Hz', 'rate': '-10%', 'volume': '-7%'},
    'krik': {'pitch': '+6Hz', 'rate': '+8%', 'volume': '+8%'},
    'septani': {'pitch': '-10Hz', 'rate': '-22%', 'volume': '-35%'},
    'povzdych': {'pitch': '-12Hz', 'rate': '-30%', 'volume': '-16%'},
}

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


def normalize_tag(tag: str) -> str:
    normalized = unicodedata.normalize('NFKD', tag.strip().lower())
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch))


def resolve_style_name(raw_tag: str) -> str:
    tag = normalize_tag(raw_tag)
    aliases = {
        'normalni': 'normalni',
        'hluboky': 'hluboky',
        'otazka': 'otazka',
        'krik': 'krik',
        'septani': 'septani',
        'povzdych': 'povzdych',
    }
    return aliases.get(tag, 'normalni')


def split_text_by_style_tags(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(
        r'\[(?P<tag>[^\]]+)\](?P<content>.*?)\[/\s*(?P=tag)\s*\]',
        re.IGNORECASE | re.DOTALL,
    )

    parts: list[tuple[str, str]] = []
    last_end = 0

    for match in pattern.finditer(text):
        if match.start() > last_end:
            plain = text[last_end:match.start()].strip()
            if plain:
                parts.append(('normalni', plain))

        style_name = resolve_style_name(match.group('tag'))
        content = match.group('content').strip()
        if content:
            parts.append((style_name, content))

        last_end = match.end()

    if last_end < len(text):
        plain = text[last_end:].strip()
        if plain:
            parts.append(('normalni', plain))

    if not parts:
        cleaned = text.strip()
        if cleaned:
            parts.append(('normalni', cleaned))

    return parts


async def save_edge_tts_audio(
    text: str,
    output_path: str,
    pitch: str,
    rate: str,
    volume: str,
) -> None:
    import edge_tts

    # Vygeneruje ceske mp3 primo pres edge-tts.
    # Parametry voice/rate/pitch/volume urcuji zakladni barvu hlasu.
    communicate = edge_tts.Communicate(
        text=text,
        voice=EDGE_TTS_VOICE,
        pitch=pitch,
        rate=rate,
        volume=volume,
    )
    await communicate.save(output_path)


async def save_tagged_edge_tts_audio(text: str, output_path: str, work_dir: str) -> None:
    import imageio_ffmpeg

    parts = split_text_by_style_tags(text)
    if not parts:
        raise ValueError('Input text is empty.')

    if len(parts) == 1 and parts[0][0] == 'normalni':
        preset = STYLE_PRESETS['normalni']
        await save_edge_tts_audio(
            text=parts[0][1],
            output_path=output_path,
            pitch=preset['pitch'],
            rate=preset['rate'],
            volume=preset['volume'],
        )
        return

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    segment_files: list[str] = []

    def write_concat_list(file_path: str, files: list[str]) -> None:
        with open(file_path, 'w', encoding='utf-8') as fp:
            for segment in files:
                safe_segment = segment.replace('\\', '/').replace("'", "'\\''")
                fp.write(f"file '{safe_segment}'\n")

    for index, (style_name, chunk) in enumerate(parts):
        preset = STYLE_PRESETS.get(style_name, STYLE_PRESETS['normalni'])
        segment_file = os.path.join(work_dir, f'segment_{index:04d}.mp3')
        await save_edge_tts_audio(
            text=chunk,
            output_path=segment_file,
            pitch=preset['pitch'],
            rate=preset['rate'],
            volume=preset['volume'],
        )
        segment_files.append(segment_file)

    concat_file = os.path.join(work_dir, 'segments.txt')
    await asyncio.to_thread(write_concat_list, concat_file, segment_files)

    ffmpeg_cmd = [
        ffmpeg_exe,
        '-y',
        '-f',
        'concat',
        '-safe',
        '0',
        '-i',
        concat_file,
        '-c:a',
        'libmp3lame',
        '-b:a',
        '128k',
        output_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr_data = await proc.communicate()
    if proc.returncode != 0:
        stderr_text = stderr_data.decode('utf-8', errors='replace') if stderr_data else ''
        raise subprocess.CalledProcessError(proc.returncode, ffmpeg_cmd, stderr=stderr_text)


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
        tag_help = (
            'Pouzij znacky [normalni], [hluboky], [otazka], [krik], [septani], [povzdych] '
            'pro rizeni intonace v textu.'
        )
        print(tag_help)
        asyncio.run(save_tagged_edge_tts_audio(text, temp_mp3, tempfile.gettempdir()))

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
