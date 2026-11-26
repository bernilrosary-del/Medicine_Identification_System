
import io
import re
import wave

from google import genai
from google.genai import types

from config import GEMINI_API_KEY

TTS_MODEL = "gemini-2.5-flash-preview-tts"
VOICE_NAME = "Kore"


def clean_speech_text(text):
    text = str(text or "")
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"[*_~`>|]", " ", text)
    text = re.sub(r"[🔊⏹💊✅⚠️⭐📌]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def generate_speech(text, language="English"):

    if not GEMINI_API_KEY:
        raise ValueError("Gemini API key is missing.")

    instructions = {
        "English": "Speak naturally and clearly in English.",
        "Filipino": (
            "Speak naturally in Filipino as spoken in the Philippines. "
            "Use clear and accurate Filipino pronunciation."
        ),
        "Cebuano": (
            "Speak naturally in Cebuano Bisaya as spoken in Cebu, "
            "Philippines. Use authentic Cebuano pronunciation, "
            "not Tagalog pronunciation."
        )
    }

    if language not in instructions:
        language = "English"

    clean_text = clean_speech_text(text)

    if not clean_text:
        raise ValueError("There is no readable text to speak.")

    prompt = (
        instructions[language]
        + "\nRead the following text exactly. "
          "Do not translate or add explanations:\n"
        + clean_text
    )

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model=TTS_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=VOICE_NAME
                    )
                )
            )
        )
    )

    for part in response.parts:
        if part.inline_data and part.inline_data.data:

            pcm_data = part.inline_data.data

            # Convert raw PCM audio into a playable WAV file.
            audio_buffer = io.BytesIO()

            with wave.open(audio_buffer, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(24000)
                wav_file.writeframes(pcm_data)

            return audio_buffer.getvalue()

    raise RuntimeError("Gemini did not return audio.")
