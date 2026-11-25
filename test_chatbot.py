
from chatbot import ask_chatbot

print("MEDICINE AI CHATBOT LANGUAGE TEST")
print("----------------------------------")

question = "What is Paracetamol used for?"

languages = ["English", "Filipino", "Cebuano"]

for language in languages:

    print(f"\nTESTING LANGUAGE: {language}")
    print("----------------------------------")

    response = ask_chatbot(
        question,
        language=language
    )

    print(response)
    print("----------------------------------")
