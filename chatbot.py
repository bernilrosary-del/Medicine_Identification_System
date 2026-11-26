
import time
import re

from google import genai
from config import GEMINI_API_KEY


# ==========================================
# GEMINI CONFIGURATION
# ==========================================

GEMINI_MODEL = "gemini-3.5-flash-lite"
MAX_ATTEMPTS = 3


# ==========================================
# CLEAN AI RESPONSE
# ==========================================

def clean_response(text):
    """Remove Markdown formatting from AI responses."""

    if not text:
        return ""

    text = str(text)

    # Remove Markdown code blocks
    text = re.sub(r"```[\s\S]*?```", " ", text)

    # Remove Markdown headings
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)

    # Remove bold formatting
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)

    # Remove italic formatting
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"\1", text)

    # Remove inline code formatting
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Keep link text and remove URLs
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove bullet symbols
    text = re.sub(r"(?m)^\s*[-•]\s+", "", text)

    # Remove excessive spaces
    text = re.sub(r"[ \t]+", " ", text)

    # Normalize excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ==========================================
# MEDICINE CONTEXT PROCESSING
# ==========================================

def prepare_medicine_context(medicine_context):

    if not medicine_context:
        return "No specific medicine has been identified."

    if isinstance(medicine_context, dict):

        fields = [
            ("Brand Name", "brand_name"),
            ("Generic Name", "generic_name"),
            ("Medicine Type", "medicine_type"),
            ("Common Uses", "common_uses"),
            ("Warnings", "warnings"),
            ("Description", "description"),
            ("Source", "source")
        ]

        context_lines = []

        for label, key in fields:

            value = medicine_context.get(key)

            if value:
                context_lines.append(f"{label}: {value}")

        return "\n".join(context_lines)

    if isinstance(medicine_context, str):
        return medicine_context.strip()

    return "No valid medicine information was provided."


# ==========================================
# LANGUAGE INSTRUCTIONS
# ==========================================

LANGUAGE_INSTRUCTIONS = {

    "English": """
Use clear, natural, conversational English.
Avoid complicated medical terminology.
Use simple explanations.
""",

    "Filipino": """
Gumamit ng natural at madaling maintindihang Filipino.
Iwasan ang sobrang pormal o malalim na mga salita.
Gumamit lamang ng English medical terms kapag kinakailangan.
""",

    "Cebuano": """
Gamita ang natural ug hapsay nga Cebuano (Bisaya).
Ayaw gamita ang Tagalog isip kapuli sa Cebuano.
Likayi ang sobra ka pormal o lisod sabton nga mga pulong.
Gamita ang English medical terms kung gikinahanglan.
Siguroha nga natural paminawon ang mga sentence sa Cebuano.
"""
}


# ==========================================
# GEMINI CHATBOT
# ==========================================

def ask_chatbot(
    question,
    language="English",
    medicine_context=None
):

    if not GEMINI_API_KEY:
        return (
            "Gemini API key is missing. "
            "Please check your .env file."
        )

    if not isinstance(question, str) or not question.strip():
        return "Please enter a question."

    allowed_languages = [
        "English",
        "Filipino",
        "Cebuano"
    ]

    if language not in allowed_languages:
        language = "English"

    # Prepare medicine information
    context = prepare_medicine_context(medicine_context)

    # Initialize Gemini
    try:
        client = genai.Client(
            api_key=GEMINI_API_KEY
        )

    except Exception as error:
        print("Gemini Initialization Error:", error)

        return (
            "Unable to initialize the AI chatbot. "
            "Please check your API configuration."
        )

    # ======================================
    # AI PROMPT
    # ======================================

    prompt = f"""
You are a Medicine Information AI Chatbot.

YOUR PURPOSE:

Provide general educational information about common medicines.

You help users understand medicine names, generic names,
medicine classifications, common uses, and product warnings.

MEDICINE DATABASE INFORMATION:

{context}

IMPORTANT DATABASE RULES:

1. Use the provided medicine information as the primary
source for the identified medicine.

2. Never invent missing generic names or active ingredients.

3. If the generic name says "Check product packaging",
explain that the exact ingredients must be verified
using the actual product packaging.

4. Do not assume different medicine variants have
identical ingredients.

5. If no specific medicine is identified, provide
general educational information only.

6. Clearly distinguish database information from
general educational explanations.

7. If the database does not contain the requested
information, say that it is unavailable.

MEDICAL SAFETY RULES:

1. Do not diagnose medical conditions.

2. Do not prescribe medicines.

3. Do not recommend changing medication doses.

4. Never claim that a medicine is safe for everyone.

5. Do not recommend combining medicines without
professional guidance.

6. Encourage users to consult a pharmacist or
healthcare professional.

7. For emergencies, advise users to seek immediate
medical attention.

8. Do not treat database information as proof that
a medicine is appropriate for a particular person.

RESPONSE LANGUAGE:

Respond entirely in {language}.

LANGUAGE STYLE:

{LANGUAGE_INSTRUCTIONS[language]}

RESPONSE FORMATTING:

1. Use plain text.
2. Do not use Markdown formatting.
3. Do not use asterisks or hashtags.
4. Use short and clear paragraphs.
5. Make sentences easy to understand when read aloud.
6. Avoid unnecessary abbreviations.

USER QUESTION:

{question}

Provide a helpful, accurate, and understandable answer.
"""

    # ======================================
    # GEMINI REQUEST AND RETRY MECHANISM
    # ======================================

    for attempt in range(MAX_ATTEMPTS):

        try:

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )

            if response and response.text:
                return clean_response(response.text)

            return (
                "Sorry, I could not generate a response. "
                "Please try again."
            )

        except Exception as error:

            error_message = str(error).upper()

            print("\nGemini Chatbot Error:", error)

            # API quota or rate limit
            if (
                "429" in error_message
                or "RESOURCE_EXHAUSTED" in error_message
            ):

                return (
                    "The Gemini API usage limit may have been "
                    "reached. Please check your API quota "
                    "and try again later."
                )

            # Temporary server errors
            temporary_error = any(
                code in error_message
                for code in [
                    "503",
                    "UNAVAILABLE",
                    "500",
                    "502",
                    "504",
                    "INTERNAL",
                    "TIMEOUT"
                ]
            )

            if temporary_error:

                if attempt < MAX_ATTEMPTS - 1:

                    wait_time = 2 ** (attempt + 1)

                    print(
                        f"Gemini temporarily unavailable. "
                        f"Retrying in {wait_time} seconds..."
                    )

                    time.sleep(wait_time)
                    continue

                return (
                    "The AI chatbot is temporarily experiencing "
                    "high demand or a server problem. "
                    "Please try again later."
                )

            # Other errors
            return (
                "The AI chatbot encountered an unexpected error. "
                "Please check the server terminal."
            )

    return "The AI chatbot is temporarily unavailable."
