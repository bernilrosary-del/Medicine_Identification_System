
import os
import re
import base64
import traceback

from io import BytesIO

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from rapidfuzz import fuzz
from google import genai

from config import SECRET_KEY, DEBUG, GEMINI_API_KEY
from database import get_all_medicines
from ocr import extract_text
from chatbot import ask_chatbot


# ==========================================
# FLASK CONFIGURATION
# ==========================================

app = Flask(__name__)

app.secret_key = SECRET_KEY or "development-secret-key"

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

UPLOAD_FOLDER = "uploads"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ==========================================
# GEMINI TTS CONFIGURATION
# ==========================================

TTS_MODEL = "gemini-3.8-flash-tts"
TTS_VOICE = "Kore"


# ==========================================
# CLEAN TEXT FOR VOICE FEEDBACK
# ==========================================

def clean_tts_text(text):

    text = str(text or "")

    text = re.sub(r"```[\s\S]*?```", " ", text)

    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)

    text = re.sub(r"\*\*|__|\*|~~|`", "", text)

    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    text = re.sub(r"(?m)^\s*[-•]\s*", "", text)

    text = re.sub(
        r"\b[Ss][Oo0]{2}(?=\s*(?:mg|mcg|g|ml|tablets?|capsules?))",
        "500",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ==========================================
# GEMINI SPEECH GENERATION
# ==========================================

def generate_tts_audio(text, language):

    if not GEMINI_API_KEY:
        raise Exception("Gemini API key is missing.")

    language_styles = {

        "English": (
            "Speak naturally in clear English. "
            "Use a warm, friendly and professional voice. "
            "Use moderate speaking speed. "
            "Pronounce medicine names clearly."
        ),

        "Filipino": (
            "Speak naturally in Filipino (Tagalog). "
            "Use native Filipino pronunciation and natural intonation. "
            "Use a warm, friendly voice. "
            "Speak at a moderate pace. "
            "Do not pronounce the text using English pronunciation."
        ),

        "Cebuano": (
            "Speak naturally in Cebuano (Bisaya), "
            "as spoken by a native Cebuano speaker in the Philippines. "
            "Use natural Cebuano pronunciation, rhythm and intonation. "
            "Do not translate Cebuano into Tagalog. "
            "Use a warm, clear voice and moderate speaking pace."
        )

    }

    style = language_styles.get(
        language,
        language_styles["English"]
    )

    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={"api_version": "v1beta"}
    )

    interaction = client.interactions.create(

        model=TTS_MODEL,

        input=[
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": text,
                        "annotations": [
                            {
                                "type": "speech_metadata",
                                "style": style
                            }
                        ]
                    }
                ]
            }
        ],

        response_format={
            "type": "audio"
        },

        generation_config={
            "speech_config": [
                {
                    "voice": TTS_VOICE
                }
            ]
        }

    )

    if not interaction.output_audio:
        raise Exception("Gemini returned no audio output.")

    audio_data = interaction.output_audio.data

    if not audio_data:
        raise Exception("Gemini generated empty audio.")

    audio_bytes = base64.b64decode(audio_data)

    if not audio_bytes:
        raise Exception("Audio decoding failed.")

    return audio_bytes


# ==========================================
# FILE VALIDATION
# ==========================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ==========================================
# TEXT NORMALIZATION
# ==========================================

def normalize_text(text):

    if not text:
        return ""

    text = str(text).lower()

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text
    )

    return re.sub(r"\s+", " ", text).strip()


# ==========================================
# GENERATE OCR WORD COMBINATIONS
# ==========================================

def generate_text_candidates(text):

    words = normalize_text(text).split()

    candidates = set()

    for word in words:
        candidates.add(word)

    for size in (2, 3, 4):

        for i in range(len(words) - size + 1):

            phrase = " ".join(words[i:i + size])

            candidates.add(phrase)

    if words:
        candidates.add(" ".join(words))

    return list(candidates)


# ==========================================
# MEDICINE MATCH SCORING
# ==========================================

def calculate_match_score(medicine_name, extracted_text):

    medicine_name = normalize_text(medicine_name)

    if not medicine_name or not extracted_text:
        return 0

    candidates = generate_text_candidates(extracted_text)

    best_score = 0

    for candidate in candidates:

        score = fuzz.ratio(
            medicine_name,
            candidate
        )

        best_score = max(
            best_score,
            score
        )

    normalized_text = normalize_text(extracted_text)

    if f" {medicine_name} " in f" {normalized_text} ":
        return 100

    return best_score


# ==========================================
# MEDICINE MATCHING
# ==========================================

def find_medicine(text, medicines):

    if not text or not medicines:
        return []

    matches = []

    for medicine in medicines:

        brand = medicine.get("brand_name") or ""

        generic = medicine.get("generic_name") or ""

        normalized_brand = normalize_text(brand)

        normalized_generic = normalize_text(generic)

        brand_score = calculate_match_score(
            brand,
            text
        )

        generic_score = 0

        if (
            generic
            and normalized_generic != "check product packaging"
        ):

            generic_score = calculate_match_score(
                generic,
                text
            )

        weighted_brand = brand_score

        weighted_generic = generic_score * 0.94

        final_score = max(
            weighted_brand,
            weighted_generic
        )

        if len(normalized_brand) <= 4:
            threshold = 92
        elif len(normalized_brand) <= 6:
            threshold = 85
        else:
            threshold = 82

        if final_score < threshold:
            continue

        result = medicine.copy()

        result["match_score"] = round(final_score, 2)

        result["brand_score"] = round(brand_score, 2)

        result["generic_score"] = round(generic_score, 2)

        if brand_score >= 95:

            result["match_type"] = "Brand Name Match"

        elif generic_score >= 95:

            result["match_type"] = "Generic Name Match"

        else:

            result["match_type"] = "Possible Fuzzy Match"

        matches.append(result)

    matches.sort(
        key=lambda item: (
            item["match_score"],
            item["brand_score"],
            item["generic_score"]
        ),
        reverse=True
    )

    unique_matches = []

    seen = set()

    for medicine in matches:

        key = (
            normalize_text(medicine.get("brand_name", "")),
            normalize_text(medicine.get("generic_name", ""))
        )

        if key not in seen:

            seen.add(key)

            unique_matches.append(medicine)

    return unique_matches[:5]


# ==========================================
# HOME PAGE
# ==========================================

@app.route("/")
def home():

    return render_template("index.html")


# ==========================================
# MEDICINE IDENTIFICATION
# ==========================================

@app.route("/identify", methods=["POST"])
def identify():

    if "medicine_image" not in request.files:

        return jsonify({
            "error": "Please upload a medicine image."
        }), 400

    image = request.files["medicine_image"]

    if image.filename == "":

        return jsonify({
            "error": "No image selected."
        }), 400

    if not allowed_file(image.filename):

        return jsonify({
            "error": "Unsupported image format."
        }), 400

    filename = secure_filename(image.filename)

    if not filename:

        return jsonify({
            "error": "Invalid image filename."
        }), 400

    filepath = None

    try:

        # Create a unique temporary filename
        import uuid

        filename = f"{uuid.uuid4().hex}_{filename}"

        filepath = os.path.join(
            UPLOAD_FOLDER,
            filename
        )

        # Save uploaded image
        image.save(filepath)

        # Extract text using Tesseract OCR
        extracted_text = extract_text(filepath)

        if not extracted_text:

            return jsonify({

                "success": False,

                "extracted_text": "",

                "matches": [],

                "message": (
                    "No readable text detected. "
                    "Try a clearer medicine image."
                )

            })

        # Retrieve medicine records from MySQL
        medicines = get_all_medicines()

        if not medicines:

            return jsonify({

                "success": False,

                "extracted_text": extracted_text,

                "matches": [],

                "message": (
                    "No medicine records are currently available."
                )

            })

        # Find possible medicine matches
        matches = find_medicine(
            extracted_text,
            medicines
        )

        print("\n========== MEDICINE IDENTIFICATION ==========")

        print("OCR TEXT:", extracted_text)

        for medicine in matches:

            print(
                "MATCH:",
                medicine.get("brand_name"),
                "| SCORE:",
                medicine.get("match_score"),
                "| TYPE:",
                medicine.get("match_type")
            )

        print("============================================\n")

        return jsonify({

            "success": True,

            "extracted_text": extracted_text,

            "matches": matches,

            "message": (
                "Possible medicine matches found."
                if matches
                else "No matching medicine found in the database."
            )

        })

    except Exception as error:

        print("IDENTIFICATION ERROR:")

        traceback.print_exc()

        return jsonify({

            "error": (
                "The image could not be processed "
                "or the database could not be reached."
            )

        }), 500

    finally:

        if filepath and os.path.exists(filepath):

            try:
                os.remove(filepath)
            except OSError as error:
                print("Temporary image cleanup failed:", error)


# ==========================================
# GEMINI AI CHATBOT
# ==========================================

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json(silent=True) or {}

    question = data.get("question", "")

    language = data.get("language", "English")

    medicine_context = data.get(
        "medicine_context",
        ""
    )

    if not isinstance(question, str):

        return jsonify({
            "answer": "Invalid question."
        }), 400

    question = question.strip()

    allowed_languages = [
        "English",
        "Filipino",
        "Cebuano"
    ]

    if language not in allowed_languages:

        language = "English"

    if not question:

        return jsonify({
            "answer": "Please enter a question."
        }), 400

    try:

        answer = ask_chatbot(
            question,
            language,
            medicine_context
        )

        return jsonify({
            "answer": answer
        })

    except Exception as error:

        print("CHATBOT ERROR:")

        traceback.print_exc()

        return jsonify({

            "answer": (
                "Sorry, the chatbot is temporarily unavailable. "
                "Please try again."
            )

        }), 500


# ==========================================
# GEMINI TEXT-TO-SPEECH
# ==========================================

@app.route("/speak", methods=["POST"])
def speak():

    data = request.get_json(silent=True) or {}

    text = data.get("text", "")

    language = data.get("language", "English")

    allowed_languages = [
        "English",
        "Filipino",
        "Cebuano"
    ]

    if language not in allowed_languages:

        language = "English"

    if not isinstance(text, str) or not text.strip():

        return jsonify({
            "error": "No text was provided."
        }), 400

    if len(text) > 4000:

        return jsonify({
            "error": "Text is too long. Please use a shorter response."
        }), 400

    clean_text = clean_tts_text(text)

    if not clean_text:

        return jsonify({
            "error": "No readable text is available."
        }), 400

    if not GEMINI_API_KEY:

        return jsonify({
            "error": "Gemini API key is missing. Check your .env file."
        }), 500

    try:

        print("\n===================================")

        print("GEMINI TEXT-TO-SPEECH")

        print("Language:", language)

        print("Text:", clean_text[:150])

        print("===================================\n")

        audio_bytes = generate_tts_audio(
            clean_text,
            language
        )

        print("TTS AUDIO GENERATED SUCCESSFULLY.")

        # Detect WAV output
        if audio_bytes.startswith(b"RIFF"):

            mimetype = "audio/wav"
            extension = "wav"

        # Detect MP3 output
        elif audio_bytes.startswith(b"ID3"):

            mimetype = "audio/mpeg"
            extension = "mp3"

        else:

            raise Exception(
                "Gemini returned an unrecognized audio format."
            )

        return send_file(

            BytesIO(audio_bytes),

            mimetype=mimetype,

            as_attachment=False,

            download_name=f"medicine_voice.{extension}"

        )

    except Exception as error:

        print("\n========== GEMINI TTS ERROR ==========")

        traceback.print_exc()

        print("======================================\n")

        return jsonify({
            "error": str(error)
        }), 503


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":

    app.run(
        debug=DEBUG
    )
