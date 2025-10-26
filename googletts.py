from typing import Callable, Tuple # Import Callable
import sys

from google.cloud import texttospeech
import re

from WavPlayer import WavPlayer
from MP3Player import MP3Player


"""
https://console.cloud.google.com/speech/text-to-speech;input=Hi%20whats%20up.%20this%20shit%20is%20wack.%20How%20do%20I%20sound%20chat%3F%3F%20damn.;locale=en-US;voice=en-US-Chirp3-HD-Laomedeia;encoding=LINEAR16;speed=1;location=global?hl=en&inv=1&invt=AbxWcg&project=famous-crossing-459522-d3
en-US-Chirp3-HD-Achernar
en-US-Chirp3-HD-Achird
en-US-Chirp3-HD-Algenib
en-US-Chirp3-HD-Algieba
en-US-Chirp3-HD-Alnilam
en-US-Chirp3-HD-Aoede
en-US-Chirp3-HD-Autonoe
en-US-Chirp3-HD-Callirrhoe
en-US-Chirp3-HD-Charon
en-US-Chirp3-HD-Despina
en-US-Chirp3-HD-Enceladus
en-US-Chirp3-HD-Erinome
en-US-Chirp3-HD-Fenrir
en-US-Chirp3-HD-Gacrux
en-US-Chirp3-HD-Iapetus
en-US-Chirp3-HD-Kore
en-US-Chirp3-HD-Laomedeia
en-US-Chirp3-HD-Leda
en-US-Chirp3-HD-Orus
en-US-Chirp3-HD-Puck
en-US-Chirp3-HD-Pulcherrima
en-US-Chirp3-HD-Rasalgethi
en-US-Chirp3-HD-Sadachbia
en-US-Chirp3-HD-Sadaltager
en-US-Chirp3-HD-Schedar
en-US-Chirp3-HD-Sulafat
en-US-Chirp3-HD-Umbriel
en-US-Chirp3-HD-Vindemiatrix
en-US-Chirp3-HD-Zephyr
en-US-Chirp3-HD-Zubenelgenubi
"""

"""
I like these 

"en-US-Chirp3-HD-Umbriel"
"en-US-Chirp3-HD-Laomedeia"
"en-US-Chirp3-HD-Alnilam"
en-US-Chirp3-HD-Charon
"""

from dotenv import load_dotenv
import os
load_dotenv()
GOOGLE_JSON_KEY = os.getenv("GOOGLE_JSON_KEY_FIGUINE")

if GOOGLE_JSON_KEY is None:
    print(f"GOOGLE_JSON_KEY was not loaded from .env")
    raise Exception("GOOGLE_JSON_KEY was not loaded from .env")

print("googletts.py")

premium_male_voices = [
    "en-US-Chirp3-HD-Charon",
    "en-US-Chirp3-HD-puck",
    "en-US-Chirp3-HD-Fenrir",
    "en-US-Chirp3-HD-Orus",

    "en-US-Chirp3-HD-Achird",
    "en-US-Chirp3-HD-Algenib",
    "en-US-Chirp3-HD-Algieba",
    "en-US-Chirp3-HD-Alnilam",
    "en-US-Chirp3-HD-Enceladus",
    "en-US-Chirp3-HD-Iapetus",
    "en-US-Chirp3-HD-Rasalgethi",
    "en-US-Chirp3-HD-Sadachbia",
    "en-US-Chirp3-HD-Sadaltager",
    "en-US-Chirp3-HD-Schedar",
    "en-US-Chirp3-HD-Umbriel",
    "en-US-Chirp3-HD-Zubenelgenubi"
]

premium_female_voices = [
    "en-US-Chirp3-HD-Laomedeia",
    "en-US-Chirp3-HD-Aoede",
    "en-US-Chirp3-HD-Kore",
    "en-US-Chirp3-HD-Leda",

    "en-US-Chirp3-HD-Achernar",
    "en-US-Chirp3-HD-Autonoe",
    "en-US-Chirp3-HD-Callirrhoe",
    "en-US-Chirp3-HD-Despina",
    "en-US-Chirp3-HD-Erinome",
    "en-US-Chirp3-HD-Gacrux",
    "en-US-Chirp3-HD-Pulcherrima",
    "en-US-Chirp3-HD-Sulafat",
    "en-US-Chirp3-HD-Vindemiatrix",
    "en-US-Chirp3-HD-Zephyr"
]


def clean_text_for_tts(sample: str, remove_non_ascii: bool = True) -> str:
    # 1. keep printable ASCII only
    if remove_non_ascii:
        sample = ''.join(c for c in sample if 32 <= ord(c) <= 126 or c in '\n\r\t ')

    # 2. normalise white-space
    sample = re.sub(r'\s+', ' ', sample.strip())

    # 3. expand common symbols
    sample = re.sub(r'\s*&\s*', ' and ', sample)  # &  →  " and "
    sample = re.sub(r'\s*%\s*', ' percent ', sample)  # %  →  " percent "
    sample = re.sub(r'\s*@\s*', ' at ', sample)  # @  →  " at "

    # 4. drop symbols that upset Gemini (keep # and $)
    sample = re.sub(r'[\[\]\{\}\*\^\\<>|~`]', '', sample)

    # 5. **comma-number rule** – add a space after a comma that is _not_ followed by exactly 3 digits
    #    e.g. "1,2,3" → "1, 2, 3" while "123,456" stays the same
    sample = re.sub(r',(?=\d(?!\d{2}(?!\d)))', ', ', sample)

    # 6. usual punctuation spacing
    sample = re.sub(r'([?!])(?=\w)', r'\1 ', sample)        # ?! before a word
    sample = re.sub(r'([,!?])(?=[A-Za-z])', r'\1 ', sample) # ,!? before a letter

    # 7. word replacements
    sample = re.sub(r'\beh(?=\b)', 'AY', sample, flags=re.IGNORECASE)

    return sample.strip()


def chunk_text(text, min_chunk_size=10, max_chunk_size=100):
    delimiters = r"""
        (?<=[\.\?\!\,\:\;\)])\s+     |  # punctuation followed by space
        (\(\s*)                    |  # <<< capture the open paren and any space
        \n+                        |  # newlines
        \s"(?=\w)                  |  # space + " followed by word
        "(?=\s)                    |  # " followed by space
        \s'(?=\w)                  |  # space + ' followed by word
        '(?=\s)                    |  # ' followed by space
        \s–\s                          # space + em dash + space
        \s-\s                          # space + - + space
    """

    parts = re.split(delimiters, text, flags=re.VERBOSE)

    chunks = []
    current = ""

    def is_clean_cut(sample: str) -> bool:
        if len(sample) == 0:
            return False
        char = sample[-1]
        return char == '.' or char == '!' or char == '?' or char == ';'

    for part in parts:
        if part is None:
            continue
        if len(current) < min_chunk_size or (not is_clean_cut(current) and len(current) + len(part) <= max_chunk_size * (1 if is_clean_cut(part) else 0.75) ):
            # combine
            if current:
                current += ' ' + part
            else:
                current = part
        else:
            if current:
                chunks.append(current.strip())
            current = part
    if current:
        chunks.append(current.strip())

    return chunks


def text_to_speech_premium(
        text: str,
        voice_model: str = "en-US-Chirp3-HD-Umbriel",
        wav: bool = False,
        language_code: str = "en-US",
        clean_text: bool = True,
        remove_non_ascii: bool = True,
        cleaner_function: Callable[[str, bool], str] = clean_text_for_tts
):
    # Set the path to your service account key file
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_JSON_KEY
    # Initialize the client

    client = texttospeech.TextToSpeechClient()

    text = cleaner_function(text, remove_non_ascii) if clean_text else text

    # Set the text input
    synthesis_input = texttospeech.SynthesisInput(text=text)

    # Configure voice parameters - using a premium voice (Wavenet)
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_model
    )

    # Set audio configuration
    audio_config = texttospeech.AudioConfig(
        audio_encoding=(texttospeech.AudioEncoding.MP3 if not wav else texttospeech.AudioEncoding.LINEAR16),
    )

    # Generate speech
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    return response.audio_content


def large_tts(
        text: str,
        voice_model: str = "en-US-Chirp3-HD-Umbriel",
        wav: bool = False,
        language_code: str = "en-US",
        clean_text: bool = True,
        remove_non_ascii: bool = True,
        cleaner_function: Callable[[str, bool], str] = clean_text_for_tts,
        min_chunk_size=5,
        max_chunk_size=200,
        debug: bool = False,
        show_progress: bool = False
):
    min_chunk_size = min(min_chunk_size, 5000)
    max_chunk_size = min(max_chunk_size, 5000)

    if wav and 'WavPlayer' not in sys.modules:
        raise Exception("audio type is Wav but WavPlayer not imported from WavPlayer.py for large_tts")
    if not wav and 'MP3Player' not in sys.modules:
        raise Exception("audio type is mp3 but MP3Player not imported from MP3Player.py for large_tts")

    merge_audio: Callable[[list[bytes]], bytes] = WavPlayer.merge_wav_bytes if wav else MP3Player().merge_mp3
    if merge_audio is None:
        raise Exception("merge_audio is None in large_tts")

    chunks = chunk_text(text, min_chunk_size, max_chunk_size)
    audio_list = []
    for chunk in chunks:
        if debug:
            print(f"chunk({len(chunk)}): [{chunk}]")
        try:
            audio = text_to_speech_premium(chunk, voice_model, wav, language_code, clean_text, remove_non_ascii, cleaner_function)
            audio_list.append(audio)
        except Exception as e:
            print(f"error: {e}")
            print(f"Rechunking")
            rechunks = chunk_text(chunk, min_chunk_size=5, max_chunk_size=50)
            print(f"split into {len(rechunks)} chunks")
            for rechunk in rechunks:
                if debug:
                    print(f"chunk({len(chunk)}): [{chunk}]")
                try:
                    audio = text_to_speech_premium(chunk, voice_model, wav, language_code, clean_text, remove_non_ascii, cleaner_function)
                    audio_list.append(audio)
                except Exception as ee:
                    print(f"rechunk Error: {ee}")
        if show_progress:
            print(f"{len(audio_list)}/{len(chunks)} audios generated")

    combined_audio_bytes = merge_audio(audio_list)
    return combined_audio_bytes


def large_llm_tts_clean(
        text: str,
        min_chunk_size=5000,
        max_chunk_size=25000,
        debug: bool = False,
        show_progress: bool = False):
    import google_generativeai_api as llm

    direction = """
    Clean up this section of my report so that it can be read by TTS without hiccups. 
    Remove and weird number and convert anything that would be weird if said a loud into something that would be natural in human speech.
    Remove or reword parts that would be un-natural to read aloud. 
    Stay true to the original text.
    Do not respond with anything except for the text you have prepared for TTS.
    """.strip()
    writer = llm.FlashChat(direction)

    chunks = chunk_text(text, min_chunk_size, max_chunk_size)
    clean_text = ""

    count = 0
    for chunk in chunks:
        clean_chunk = writer.prompt(chunk)
        clean_text = f"{clean_text}{clean_chunk}"
        count += 1
        if debug:
            print("---")
            print(clean_chunk)
        if show_progress:
            print(f"{count}/{len(chunks)} chunks cleaned")

    return clean_text


def llm_large_tts_threaded(
    text: str,
    voice_model: str = "en-US-Chirp3-HD-Charon",
    wav: bool = False,
    language_code: str = "en-US",
    llm_min_chunk: int = 5_000,
    llm_max_chunk: int = 25_000,
    tts_min_chunk: int = 5,
    tts_max_chunk: int = 500,
    debug: bool = False,
    show_progress: bool = False,
    instant_response_audio_chunks: list[bytes] = None,
    audio_lock = None
):
    import google_generativeai_api as llm
    import threading

    cleaned_text_chunks: list[str] = []
    text_lock = threading.Lock()

    audio_chunks: list[bytes] = []

    _all_text_cleaned: list[bool] = [False]

    def cleaner_worker(all_text_cleaned=_all_text_cleaned):
        prompt = """
            Clean up this section of my report so that it can be read by TTS without hiccups. 
            Remove and weird number and convert anything that would be weird if said a loud into something more natural in human speech.
            You should make as few changes as possible aiming to keep the bulk of the report intact, only change what you must
            and do not add anything that was not already in the report.
            Do not respond with anything except for the text you have prepared for TTS.
        """.strip()
        writer = llm.FlashChat(prompt)

        chunks = chunk_text(text, llm_min_chunk, llm_max_chunk)
        for idx, chunk in enumerate(chunks):
            clean_chunk = writer.prompt(chunk)
            with text_lock:
                cleaned_text_chunks.append(clean_chunk)

            if show_progress:
                print(f"[clean] {idx+1}/{len(chunks)} cleaned", flush=True)
        all_text_cleaned[0] = True
        print("All text has been cleaned with LLM") if show_progress else None

    def tts_worker(all_text_cleaned=_all_text_cleaned):
        while not all_text_cleaned[0] or len(cleaned_text_chunks):
            if len(cleaned_text_chunks) == 0:
                time.sleep(0.2)
                continue
            print(f"{len(cleaned_text_chunks)} text chunks left for audio conversion") if show_progress else None
            cleaned_chunk = None
            with text_lock:
                cleaned_chunk = cleaned_text_chunks.pop(0)

            audio_chunk = large_tts(cleaned_chunk, voice_model, wav, language_code, min_chunk_size=tts_min_chunk, max_chunk_size=tts_max_chunk)
            audio_chunks.append(audio_chunk)

            if instant_response_audio_chunks is not None and audio_lock is not None:
                with audio_lock:
                    instant_response_audio_chunks.append(audio_chunk)
        print(f"all text converted to audio") if show_progress else None

    t1 = threading.Thread(target=cleaner_worker, daemon=True)
    t2 = threading.Thread(target=tts_worker,     daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    merge_audio: Callable[[list[bytes]], bytes] = WavPlayer.merge_wav_bytes if wav else MP3Player().merge_mp3
    with audio_lock:
        merged_audio_bytes = merge_audio(audio_chunks)
    return merged_audio_bytes


if __name__ == '__main__':
    import time
    from docx import Document

    start_time = time.time()
    file_name = "Investment Analysis of Petrobras (PBR) – Outlook, Valuation & Peer Comparison"
    doc = Document(f"C:/Users/smash/Downloads/{file_name}.docx")
    paper = "\n".join(p.text for p in doc.paragraphs)

    print("generating audio")
    import threading
    import MP3Player as mp3
    mp3_audio_bytes=[]
    audio_lock = threading.Lock()
    _thread_active = [False]

    def create_audio():
        audio = llm_large_tts_threaded(paper,
                                       show_progress=True,
                                       instant_response_audio_chunks=mp3_audio_bytes,
                                       audio_lock=audio_lock,
                                       llm_min_chunk=1_000,
                                       llm_max_chunk=5_000)
        print("saving audio")
        mp3.MP3Player().save_mp3(audio_bytes=audio, file_path=f"audio_files/async_{file_name}.mp3")

    def early_play(thread_active=_thread_active):
        while thread_active[0] or len(mp3_audio_bytes):
            if len(mp3_audio_bytes) == 0:
                print("waiting for audio")
                time.sleep(1)
                continue
            print("playing audio early")
            with audio_lock:
                bytes = mp3_audio_bytes.pop(0)
            mp3.MP3Player().play_mp3(bytes)

    t1 = threading.Thread(target=create_audio, daemon=True)
    t2 = threading.Thread(target=early_play,     daemon=True)
    t1.start()
    _thread_active[0] = True
    t2.start()
    t1.join()
    _thread_active[0] = False
    t2.join()

    print("finished")
    print(f"(async) Elapsed time: {time.time()-start_time:.2f}s")

