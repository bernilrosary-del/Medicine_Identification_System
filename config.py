
import os
from dotenv import load_dotenv

load_dotenv()

# Flask Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# MySQL Database Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# Gemini AI Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)

# Tesseract OCR Configuration
TESSERACT_PATH = os.getenv(
    "TESSERACT_PATH",
    r"C:\Users\rosaryjame.bernil\Downloads\Medicine_Identification_System-main\tesseract.exe"
)

