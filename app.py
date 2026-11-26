
import os
import re
import json
import wave
import traceback
import time


from io import BytesIO
from google.genai import types

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file
)

from rapidfuzz import fuzz

from google import genai
from google.genai import types

from config import (
    SECRET_KEY,
    DEBUG,
    GEMINI_API_KEY
)

from database import get_all_medicines
from ocr import extract_text
from chatbot import ask_chatbot


# =====================================================
# FLASK CONFIGURATION
# =====================================================

app = Flask(__name__)

app.secret_key = SECRET_KEY or "medicine-identification-secret-key"

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


# Gemini models
GEMINI_MODEL = "gemini-3.8-flash"
TRANSCRIPTION_MODEL = "gemini-3.8-flash"
TTS_MODEL = "gemini-3.8-flash-tts"


# Gemini client
client = None

if GEMINI_API_KEY:
    client = (
    genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(
            api_version="v1beta"
        )
    )
    if GEMINI_API_KEY
    else None
)


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def normalize_text(text):
    """Normalize text for medicine matching."""

    if not text:
        return ""

    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def score_medicine(ocr_text, medicine):
    """
    Compare OCR text with medicine brand and generic names.
    Brand and generic names receive priority.
    """

    normalized_ocr = normalize_text(ocr_text)

    if not normalized_ocr:
        return 0, "No match"

    brand = normalize_text(medicine.get("brand_name", ""))
    generic = normalize_text(medicine.get("generic_name", ""))

    best_score = 0
    match_type = "Possible match"

    if brand:
        if brand in normalized_ocr:
            return 100, "Exact brand match"

        score = fuzz.partial_ratio(brand, normalized_ocr)

        if score > best_score:
            best_score = score
            match_type = "Brand name match"

    if generic:
        if generic in normalized_ocr:
            score = 98

            if score > best_score:
                best_score = score
                match_type = "Exact generic match"

        else:
            score = fuzz.partial_ratio(generic, normalized_ocr)

            if score > best_score:
                best_score = score
                match_type = "Generic name match"

    return best_score, match_type


def parse_medicine_context(value):
    """Convert frontend medicine context into usable data."""

    if isinstance(value, (dict, list)):
        return value

    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = json.loads(value)

        if isinstance(parsed, (dict, list)):
            return parsed

    except (json.JSONDecodeError, TypeError):
        pass

    medicines = []

    for line in value.splitlines():
        try:
            parsed = json.loads(line)

            if isinstance(parsed, dict):
                medicines.append(parsed)

        except (json.JSONDecodeError, TypeError):
            continue

    if medicines:
        return medicines

    return value



def clean_tts_text(text):
    """Remove Markdown formatting before generating speech."""

    if not text:
        return ""

    text = str(text)

    # Remove Markdown code blocks
    text = re.sub(r"```[\s\S]*?```", " ", text)

    # Remove inline code formatting
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Keep link text but remove URLs
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove Markdown formatting symbols
    text = re.sub(r"[*#_~]", "", text)

    # Remove excessive spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()



def pcm_to_wav(audio_data, sample_rate=24000, channels=1, sample_width=2):
    """Convert raw PCM audio into a WAV file."""

    output = BytesIO()

    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data)

    output.seek(0)

    return output


# =====================================================
# HOME PAGE
# =====================================================

@app.route("/")
def home():
    return render_template("index.html")


# =====================================================
# MEDICINE IDENTIFICATION
# =====================================================

@app.route("/identify", methods=["POST"])
def identify_medicine():

    try:
        if "medicine_image" not in request.files:
            return jsonify({
                "success": False,
                "error": "No medicine image was uploaded."
            }), 400

        image_file = request.files["medicine_image"]

        if image_file.filename == "":
            return jsonify({
                "success": False,
                "error": "Please select an image."
            }), 400

        if not allowed_file(image_file.filename):
            return jsonify({
                "success": False,
                "error": "Unsupported image format."
            }), 400

        # Extract text using OCR
        extracted_text = extract_text(image_file)

        if isinstance(extracted_text, dict):
            extracted_text = extracted_text.get("text", "")

        extracted_text = str(extracted_text or "").strip()

        if not extracted_text:
            return jsonify({
                "success": True,
                "message": "No readable text was detected.",
                "extracted_text": "",
                "matches": []
            })

        # Retrieve medicines from MySQL
        medicines = get_all_medicines()

        if not medicines:
            return jsonify({
                "success": True,
                "message": "No medicines are currently registered in the database.",
                "extracted_text": extracted_text,
                "matches": []
            })

        possible_matches = []

        # Compare OCR text with database records
        for medicine in medicines:

            score, match_type = score_medicine(
                extracted_text,
                medicine
            )

            if score >= 70:

                possible_matches.append({
                    "brand_name": medicine.get("brand_name", ""),
                    "generic_name": medicine.get("generic_name", ""),
                    "medicine_type": medicine.get("medicine_type", ""),
                    "common_uses": medicine.get("common_uses", ""),
                    "warnings": medicine.get("warnings", ""),
                    "description": medicine.get("description", ""),
                    "source": medicine.get("source", ""),
                    "match_type": match_type,
                    "match_score": score
                })

        # Highest matching scores first
        possible_matches.sort(
            key=lambda item: item["match_score"],
            reverse=True
        )

        # Return only the best five matches
        possible_matches = possible_matches[:5]

        if possible_matches:
            message = "Possible medicine matches found."
        else:
            message = "No matching medicine was found in the database."

        return jsonify({
            "success": True,
            "message": message,
            "extracted_text": extracted_text,
            "matches": possible_matches
        })

    except Exception as error:

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": "Medicine identification failed: " + str(error)
        }), 500


# =====================================================
# GEMINI MEDICINE CHATBOT
# =====================================================

@app.route("/chat", methods=["POST"])
def chat():

    try:
        data = request.get_json(silent=True) or {}

        question = str(data.get("question", "")).strip()
        language = data.get("language", "English")

        medicine_context = parse_medicine_context(
            data.get("medicine_context")
        )

        if not question:
            return jsonify({
                "success": False,
                "error": "Please enter a question."
            }), 400

        if not GEMINI_API_KEY:
            return jsonify({
                "success": False,
                "error": "Gemini API key is missing. Check your .env file."
            }), 500

        # Ask chatbot
        answer = ask_chatbot(
            question,
            language,
            medicine_context
        )

        if not answer:
            return jsonify({
                "success": False,
                "error": "The chatbot did not return an answer."
            }), 500

        return jsonify({
            "success": True,
            "answer": str(answer)
        })

    except Exception as error:

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": "Chatbot error: " + str(error)
        }), 500


# =====================================================
# GEMINI VOICE TRANSCRIPTION
# =====================================================

@app.route("/transcribe", methods=["POST"])
def transcribe():

    if not GEMINI_API_KEY or client is None:
        return jsonify({
            "success": False,
            "error": "Gemini API key is missing."
        }), 500

    if "audio" not in request.files:
        return jsonify({
            "success": False,
            "error": "No audio recording was received."
        }), 400

    audio_file = request.files["audio"]
    audio_data = audio_file.read()

    if not audio_data:
        return jsonify({
            "success": False,
            "error": "The audio recording is empty."
        }), 400

    language = request.form.get("language", "English")
    mime_type = audio_file.mimetype or "audio/webm"

    prompt = (
        "Transcribe the audio recording accurately. "
        "The preferred language is " + language + ". "
        "Return only the transcribed words. "
        "Do not answer the question or add explanations."
    )

    # Automatically retry temporary Gemini errors
    for attempt in range(3):

        try:
            response = client.models.generate_content(
                model=TRANSCRIPTION_MODEL,
                contents=[
                    prompt,
                    types.Part.from_bytes(
                        data=audio_data,
                        mime_type=mime_type
                    )
                ]
            )

            transcription = (response.text or "").strip()

            if not transcription:
                return jsonify({
                    "success": False,
                    "error": "No speech was detected. Please try again."
                }), 500

            return jsonify({
                "success": True,
                "transcription": transcription
            })

        except Exception as error:

            error_message = str(error)

            print(
                f"Transcription attempt {attempt + 1} failed: "
                f"{error_message}"
            )

            is_temporary_error = (
                "503" in error_message
                or "UNAVAILABLE" in error_message
                or "429" in error_message
                or "RESOURCE_EXHAUSTED" in error_message
            )

            if is_temporary_error and attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue

            traceback.print_exc()

            return jsonify({
                "success": False,
                "error": (
                    "Gemini voice transcription is temporarily unavailable. "
                    "Please wait a moment and try recording again."
                    if is_temporary_error
                    else "Voice transcription failed: " + error_message
                )
            }), 503

    return jsonify({
        "success": False,
        "error": "Transcription failed. Please try again."
    }), 503


# =====================================================
# GEMINI TEXT-TO-SPEECH
# =====================================================

@app.route("/speak", methods=["POST"])
def speak():

    try:
        if not GEMINI_API_KEY or client is None:
            return jsonify({
                "success": False,
                "error": "Gemini API key is missing."
            }), 500

        data = request.get_json(silent=True) or {}

        text = clean_tts_text(data.get("text", ""))
        language = data.get("language", "English")

        if not text:
            return jsonify({
                "success": False,
                "error": "There is no text to read."
            }), 400

        prompt = (
            "Read the following text aloud clearly and naturally "
            "in " + language + ". "
            "Do not add extra words. "
            "Text to read: " + text
        )

        response = client.models.generate_content(
            model=TTS_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Kore"
                        )
                    )
                )
            )
        )

        audio_data = None

        for candidate in (response.candidates or []):

            content = candidate.content

            if not content:
                continue

            for part in (content.parts or []):

                if part.inline_data and part.inline_data.data:
                    audio_data = part.inline_data.data
                    break

            if audio_data:
                break

        if not audio_data:
            return jsonify({
                "success": False,
                "error": "Gemini did not return audio."
            }), 500

        # Gemini TTS normally returns raw 24 kHz PCM audio.
        wav_audio = pcm_to_wav(audio_data)

        return send_file(
            wav_audio,
            mimetype="audio/wav",
            as_attachment=False,
            download_name="medicine_speech.wav"
        )

    except Exception as error:

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": "Text-to-speech failed: " + str(error)
        }), 500


# =====================================================
# FILE SIZE ERROR
# =====================================================

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({
        "success": False,
        "error": "Image is too large. Maximum upload size is 5 MB."
    }), 413


# =====================================================
# RUN FLASK APPLICATION
# =====================================================

if __name__ == "__main__":

    print("------------------------------------------")
    print("MEDICINE IDENTIFICATION SYSTEM")
    print("------------------------------------------")

    if GEMINI_API_KEY:
        print("Gemini API key: FOUND")
    else:
        print("Gemini API key: MISSING")

    print("Starting Flask application...")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=DEBUG
    )
