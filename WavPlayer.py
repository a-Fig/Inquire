import sounddevice as sd
from scipy.io import wavfile
import io


import wave
import numpy as np


class WavPlayer:
    @staticmethod
    def save_wav(audio_bytes, file_path):
        with open(file_path, "wb") as f:
            f.write(audio_bytes)

    @staticmethod
    def merge_wav_bytes(audio_bytes_list):
        sample_rate = None
        data_list = []

        for b in audio_bytes_list:
            with wave.open(io.BytesIO(b), 'rb') as w:
                if sample_rate is None:
                    sample_rate = w.getframerate()
                frames = w.readframes(w.getnframes())
                audio_data = np.frombuffer(frames, dtype=np.int16)
                data_list.append(audio_data)

        merged_data = np.concatenate(data_list)

        out_buffer = io.BytesIO()
        with wave.open(out_buffer, 'wb') as w:
            w.setnchannels(1)  # or use w.getnchannels() from the first file
            w.setsampwidth(2)  # 2 bytes = 16-bit PCM
            w.setframerate(sample_rate)
            w.writeframes(merged_data.tobytes())

        return out_buffer.getvalue()

    @staticmethod
    def play_wav(audio_bytes):
        sample_rate, data = wavfile.read(io.BytesIO(audio_bytes))
        sd.play(data, sample_rate)
        sd.wait()
