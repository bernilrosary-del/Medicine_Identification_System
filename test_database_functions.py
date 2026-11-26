
from database import (
    get_all_medicines,
    get_medicine_by_name,
    search_medicine,
    add_medicine
)

print("\n===== TEST 1: GET ALL MEDICINES =====")

medicines = get_all_medicines()

for medicine in medicines:
    print(medicine["id"], medicine["brand_name"])


print("\n===== TEST 2: SEARCH MEDICINE =====")

results = search_medicine("Biogesic")

for medicine in results:
    print(medicine["brand_name"], medicine["generic_name"])


print("\n===== TEST 3: GET MEDICINE BY NAME =====")

medicine = get_medicine_by_name("Zyrtec")

print(medicine)


print("\n===== TEST 4: DUPLICATE PROTECTION =====")

result = add_medicine(
    brand_name="Biogesic",
    generic_name="Paracetamol",
    medicine_type="Tablet",
    common_uses="Test record",
    warnings="Test warning"
)

print("Insertion result:", result)
