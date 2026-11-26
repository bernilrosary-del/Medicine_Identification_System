
import re
import pytesseract

from PIL import (
    Image,
    ImageOps,
    ImageEnhance,
    ImageFilter
)

from pytesseract import Output
from config import TESSERACT_PATH


# ==========================================
# TESSERACT CONFIGURATION
# ==========================================

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# ==========================================
# IMAGE PREPROCESSING
# ==========================================

def preprocess_image(image):

    # Correct image orientation
    image = ImageOps.exif_transpose(image)

    # Convert to grayscale
    image = ImageOps.grayscale(image)

    # Increase image resolution
    width, height = image.size

    image = image.resize(
        (width * 2, height * 2),
        Image.Resampling.LANCZOS
    )

    # Improve contrast
    image = ImageOps.autocontrast(image)

    image = ImageEnhance.Contrast(image).enhance(2.0)

    # Sharpen text
    image = image.filter(ImageFilter.SHARPEN)

    return image


# ==========================================
# OCR TEXT CORRECTION
# ==========================================

def correct_ocr_text(text):

    if not text:
        return ""

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Correct S00, SOO and similar OCR mistakes
    # when followed by a medicine dosage unit
    text = re.sub(
        r"\b[Ss][Oo0]{2}(?=\s*(?:mg|mcg|g|ml|tablets?|capsules?))",
        "500",
        text,
        flags=re.IGNORECASE
    )

    # Correct common OCR confusion between O and 0
    # in dosage values followed by mg
    text = re.sub(
        r"\b([0-9]*)[Oo]([0-9]*)\s*(?=mg\b)",
        lambda m: m.group(1) + "0" + m.group(2) + " ",
        text,
        flags=re.IGNORECASE
    )

    return text.strip()


# ==========================================
# OCR TEXT EXTRACTION
# ==========================================

def extract_text(image_file):

    try:

        # Open uploaded medicine image
        image = Image.open(image_file)

        # Preprocess image
        processed_image = preprocess_image(image)

        # Multiple OCR configurations
        configurations = [
            "--oem 3 --psm 6",
            "--oem 3 --psm 11",
            "--oem 3 --psm 4"
        ]

        best_text = ""
        best_score = -1

        for config in configurations:

            # Extract OCR data
            data = pytesseract.image_to_data(
                processed_image,
                config=config,
                output_type=Output.DICT
            )

            words = []
            confidences = []

            for i, word in enumerate(data["text"]):

                word = word.strip()

                try:
                    confidence = float(data["conf"][i])
                except (ValueError, TypeError):
                    confidence = -1

                if word and confidence >= 0:

                    words.append(word)
                    confidences.append(confidence)

            extracted_text = " ".join(words)

            if not extracted_text:
                continue

            # Calculate average confidence
            average_confidence = (
                sum(confidences) / len(confidences)
                if confidences else 0
            )

            # Score OCR result
            score = average_confidence

            if len(extracted_text) > len(best_text):
                score += 2

            if score > best_score:

                best_score = score
                best_text = extracted_text

        # Correct extracted text
        best_text = correct_ocr_text(best_text)

        print("\n========== OCR RESULT ==========")
        print("Extracted Text:", best_text)
        print("OCR Confidence:", best_score)
        print("================================\n")

        return best_text

    except Exception as error:

        print("OCR Error:", error)

        return ""


# ==========================================
# MEDICINE KEYWORD EXTRACTION
# ==========================================

def extract_medicine_keywords(text):

    if not text:
        return []

    # Extract words, numbers and medicine-related terms
    words = re.findall(
        r"[A-Za-z0-9-]+",
        text
    )

    # Remove duplicate words
    return list(dict.fromkeys(words))
