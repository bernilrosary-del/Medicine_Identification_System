
import os
import io
import re
from difflib import SequenceMatcher

from flask import Flask, request, render_template, jsonify
from PIL import Image, ImageOps, ImageEnhance
import pytesseract
import mysql.connector
from dotenv import load_dotenv
from google import genai

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

# Tesseract OCR location on Windows
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# Gemini configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

GEMINI_MODEL = "gemini-3-flash-preview"


# MySQL database connection
def get_connection():
    password = os.getenv("MYSQL_PASSWORD")

    if not password:
        raise ValueError("MYSQL_PASSWORD is missing from your .env file.")

    return mysql.connector.connect(
        host="localhost",
        port=3306,
        user="root",
        password=password,
        database="medicine_system"
    )


# Normalize text for better comparison
def normalize_text(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


# Compare two words and measure their similarity
def word_similarity(word1, word2):
    return SequenceMatcher(
        None,
        word1,
        word2
    ).ratio()


# Search for possible medicine matches
def search_medicines(text):

    ocr_text = normalize_text(text)

    if not ocr_text:
        return []

    ocr_words = set(
        word for word in ocr_text.split()
        if len(word) >= 4
    )

    if not ocr_words:
        return []

    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT brand_name,
                   generic_name,
                   medicine_type,
                   common_uses,
                   warnings,
                   source
            FROM medicines
        """)

        records = cursor.fetchall()

        possible_matches = []

        for medicine in records:

            brand = normalize_text(medicine.get("brand_name"))
            generic = normalize_text(medicine.get("generic_name"))

            # Only use brand and generic names for identification.
            # Do not identify medicines using dosage or classification alone.
            name_text = f"{brand} {generic}"
            name_words = set(
                word for word in name_text.split()
                if len(word) >= 4
            )

            if not name_words:
                continue

            # Exact full-name match
            if (
                (brand and brand in ocr_text)
                or (generic and generic in ocr_text)
            ):
                medicine["_match_score"] = 1.0
                possible_matches.append(medicine)
                continue

            # Check for OCR spelling errors
            best_scores = []

            for name_word in name_words:

                best_score = max(
                    (
                        word_similarity(name_word, ocr_word)
                        for ocr_word in ocr_words
                    ),
                    default=0
                )

                best_scores.append(best_score)

            # Keep only strong name-word matches.
            # Short words are excluded to reduce false matches.
            strong_matches = [
                score for score in best_scores
                if score >= 0.88
            ]

            if strong_matches:

                score = sum(strong_matches) / len(name_words)

                if score >= 0.88:
                    medicine["_match_score"] = score
                    possible_matches.append(medicine)

        # Highest matching scores appear first
        possible_matches.sort(
            key=lambda item: item["_match_score"],
            reverse=True
        )

        return possible_matches[:10]

    finally:
        connection.close()


# Main page
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


# Medicine image identification using OCR
@app.route("/identify", methods=["POST"])
def identify():

    uploaded = request.files.get("medicine_image")

    if not uploaded or not uploaded.filename:
        return render_template(
            "index.html",
            error_message="Please choose a medicine image first."
        )

    try:
        image_data = uploaded.read()

        if not image_data:
            return render_template(
                "index.html",
                error_message="The uploaded image is empty."
            )

        image = Image.open(io.BytesIO(image_data))

        image = ImageOps.exif_transpose(image)
        image = image.convert("L")
        image = ImageEnhance.Contrast(image).enhance(2)

        # Improve OCR recognition
        extracted_text = pytesseract.image_to_string(
            image,
            config="--oem 3 --psm 6"
        )

        if not extracted_text.strip():
            return render_template(
                "index.html",
                error_message=(
                    "No readable text was detected. "
                    "Try a clearer, well-lit image of the medicine label."
                )
            )

        # Search medicine database
        matches = search_medicines(extracted_text)

        message = None

        if not matches:
            message = (
                "Text was successfully detected, but the medicine "
                "brand name or generic name could not be matched "
                "in the current database. Please upload a clearer "
                "image showing the medicine name."
            )

        return render_template(
            "index.html",
            extracted_text=extracted_text,
            matches=matches,
            error_message=message
        )

    except Exception:
        app.logger.exception("Medicine image processing failed")

        return render_template(
            "index.html",
            error_message=(
                "The image could not be processed, or the database "
                "could not be reached. Check the VS Code terminal "
                "for details."
            )
        )


# Medicine information chatbot
@app.route("/chat", methods=["POST"])
def chat():

    if client is None:
        return jsonify({
            "error": "Gemini API key is missing. Check your .env file."
        }), 500

    data = request.get_json(silent=True) or {}

    question = str(data.get("question", "")).strip()
    language = str(data.get("language", "English")).strip()

    allowed_languages = {"English", "Filipino", "Cebuano"}

    if language not in allowed_languages:
        language = "English"

    if not question:
        return jsonify({
            "error": "Please enter a question."
        }), 400

    if len(question) > 1000:
        return jsonify({
            "error": "Your question is too long. Please use 1000 characters or fewer."
        }), 400

    # Retrieve possible medicine information from MySQL
    try:
        medicines = search_medicines(question)

        if medicines:
            medicine_context = "\n".join(
                (
                    f"Brand: {m.get('brand_name')}; "
                    f"Generic: {m.get('generic_name')}; "
                    f"Type: {m.get('medicine_type')}; "
                    f"Common uses: {m.get('common_uses')}; "
                    f"Warnings: {m.get('warnings')}; "
                    f"Source: {m.get('source')}"
                )
                for m in medicines
            )

        else:
            medicine_context = (
                "No matching medicine record was found "
                "in the local database."
            )

    except Exception:
        app.logger.exception("Medicine database search failed")

        medicine_context = (
            "The medicine database could not be searched. "
            "Do not claim that database information was verified."
        )

    # Gemini language and safety instructions
    prompt = f"""
You are an informational assistant for a student medicine-information
prototype used in community stores.

MANDATORY LANGUAGE INSTRUCTIONS:

The user's selected language is: {language}.

Write your entire answer in the selected language:

English: Use English.
Filipino: Use natural, understandable Filipino.
Cebuano: Use natural Cebuano (Bisaya).

Do not answer in another language just because the user
asked the question in that language.

Keep medicine names and technical terms accurate.
Explain technical terms in the selected language.

USER QUESTION:
{question}

LOCAL DATABASE INFORMATION:
{medicine_context}

SAFETY REQUIREMENTS:

- Provide general educational information only.
- Do not diagnose medical conditions or prescribe medicine.
- Do not recommend a personal dosage or tell someone to start
  or stop medicine.
- Do not claim that OCR has definitively identified a medicine.
- Clearly explain when information is unavailable or uncertain.
- Do not invent medicine facts or sources.
- Recommend consulting a licensed pharmacist or healthcare
  professional for medicine selection, dosage, interactions,
  pregnancy, children, allergies, and other personal concerns.
- For a possible overdose, severe allergic reaction, or other
  emergency, advise seeking urgent professional medical help.
- Use simple, clear sentences.
- Avoid unnecessary Markdown symbols and decorative formatting.
"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        answer = response.text

        if not answer:
            answer = (
                "The AI did not return an answer. Please try again."
            )

        return jsonify({"answer": answer})

    except Exception:
        app.logger.exception("Gemini chatbot request failed")

        return jsonify({
            "error": (
                "The AI chatbot could not answer right now. "
                "Check the VS Code terminal for details."
            )
        }), 502


if __name__ == "__main__":
    app.run(debug=True)
