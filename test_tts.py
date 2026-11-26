
import base64
from google import genai
from config import GEMINI_API_KEY

# Connect using your existing Gemini API key
client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options={"api_version": "v1beta"}
)

MODEL = "gemini-3.8-flash-tts"

# Cebuano test sentence
TEST_TEXT = (
    "Ang Paracetamol kasagarang gigamit aron "
    "maibsan ang kasakit ug mopaubos sa hilanat."
)

try:
    print("Connecting to Gemini TTS...")
    print("Generating Cebuano voice feedback...")

    interaction = client.interactions.create(
        model=MODEL,
        input=[
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": TEST_TEXT,
                        "annotations": [
                            {
                                "type": "speech_metadata",
                                "style": (
                                    "Speak naturally in Cebuano "
                                    "with clear pronunciation, "
                                    "a warm conversational tone, "
                                    "and a moderate speaking pace."
                                )
                            }
                        ]
                    }
                ]
            }
        ],
        response_format={"type": "audio"},
        generation_config={
            "speech_config": [
                {"voice": "Kore"}
            ]
        }
    )

    if not interaction.output_audio or not interaction.output_audio.data:
        raise Exception("Gemini did not return audio.")

    audio_data = base64.b64decode(
        interaction.output_audio.data
    )

    with open("test_voice.wav", "wb") as audio_file:
        audio_file.write(audio_data)

    print("\nSUCCESS!")
    print("Cebuano voice generated successfully.")
    print("Audio saved as test_voice.wav")

except Exception as error:
    print("\nTTS ERROR:", error)
