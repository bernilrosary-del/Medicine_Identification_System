
from ocr import extract_text

image_path = input("Enter the medicine image path: ")

text = extract_text(image_path)

print("\n========== OCR RESULT ==========")

if text:
    print(text)
else:
    print("No text detected. Try another image.")

print("================================")
