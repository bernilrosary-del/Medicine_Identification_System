import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GEMINI_API_KEY was not found in your .env file.")
else:
    try:
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents="Reply with this exact sentence: Medicine chatbot connection successful!"
        )

        print("AI connection successful!")
        print(response.text)

    except Exception as e:
        print("AI connection failed.")
        print("Error:", e)
