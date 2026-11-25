from google import genai
from config import GEMINI_API_KEY

client = genai.Client(api_key=GEMINI_API_KEY)

try:
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents="Say: Medicine chatbot connection successful!"
    )

    print("SUCCESS!")
    print(response.text)

except Exception as e:
    print("Gemini Error:", e)