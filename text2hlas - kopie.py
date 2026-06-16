import pyttsx3
import os
import asyncio
import tempfile


# Voice tuning parameters
LOCAL_TTS_RATE = 125
LOCAL_TTS_VOLUME = 0.9

EDGE_TTS_VOICE = 'cs-CZ-AntoninNeural'
EDGE_TTS_PITCH = '-32Hz'
EDGE_TTS_RATE = '-18%'
EDGE_TTS_VOLUME = '-8%'


async def save_edge_tts_audio(text: str, output_path: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(
        text=text,
        voice=EDGE_TTS_VOICE,
        pitch=EDGE_TTS_PITCH,
        rate=EDGE_TTS_RATE,
        volume=EDGE_TTS_VOLUME,
    )
    await communicate.save(output_path)

# Initialize text-to-speech engine
engine = pyttsx3.init()

# Pick a Czech voice if available (Windows SAPI voice metadata varies by system).
voices = engine.getProperty('voices')
selected_czech_voice = None

for voice in voices:
    voice_name = (getattr(voice, 'name', '') or '').lower()
    voice_id = (getattr(voice, 'id', '') or '').lower()
    language_data = getattr(voice, 'languages', []) or []
    language_text = ' '.join(str(item).lower() for item in language_data)

    if (
        'czech' in voice_name
        or 'češt' in voice_name
        or 'cs-cz' in voice_id
        or 'cs_' in voice_id
        or 'czech' in voice_id
        or 'cs-cz' in language_text
        or 'czech' in language_text
    ):
        selected_czech_voice = voice.id
        break

if selected_czech_voice:
    engine.setProperty('voice', selected_czech_voice)
    print(f"Using Czech voice: {selected_czech_voice}")
else:
    print("Czech voice not found. Using default system voice.")

# Slow down speech rate for better clarity
engine.setProperty('rate', LOCAL_TTS_RATE)

# Set volume
engine.setProperty('volume', LOCAL_TTS_VOLUME)

# Read the Pirat.txt file
file_path = os.path.join(os.path.dirname(__file__), 'Pirat.txt')

if os.path.exists(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()
    
    # Convert text to speech
    print("Converting text to speech...")

    if selected_czech_voice:
        engine.say(text)
        engine.runAndWait()
        print("Text to speech conversion completed with local Czech voice!")
    else:
        try:
            output_mp3 = os.path.join(tempfile.gettempdir(), 'text2hlas_cs.mp3')
            asyncio.run(save_edge_tts_audio(text, output_mp3))
            os.startfile(output_mp3)
            print(f"Created Czech audio file: {output_mp3}")
            print("Playing audio in the system default player.")
        except ImportError:
            print("Package 'edge-tts' is not installed.")
            print("Install it with: python -m pip install edge-tts")
        except Exception as exc:
            print(f"Fallback speech failed: {exc}")
else:
    print(f"File not found: {file_path}")
