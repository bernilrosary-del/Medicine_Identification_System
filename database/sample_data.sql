
USE medicine_system;

INSERT INTO medicines
(brand_name, generic_name, medicine_type, common_uses, warnings, description)
VALUES
(
    'Biogesic',
    'Paracetamol',
    'Tablet',
    'Commonly used for fever and mild to moderate pain.',
    'Follow the product label. Taking too much paracetamol can cause serious liver damage.',
    'A medicine containing paracetamol as its active ingredient.'
),
(
    'Calpol',
    'Paracetamol',
    'Oral Suspension',
    'Commonly used for fever and pain.',
    'Check the age-appropriate product instructions and dosage on the label.',
    'A paracetamol-based oral suspension.'
),
(
    'Neozep',
    'Phenylephrine and other ingredients',
    'Tablet',
    'Used for temporary relief of certain cold and nasal symptoms.',
    'Check all active ingredients, contraindications, and product instructions.',
    'A combination cold medicine. Formulations may vary.'
),
(
    'Alaxan FR',
    'Ibuprofen and Paracetamol',
    'Capsule',
    'Used for temporary relief of certain types of pain.',
    'Check the label. Ibuprofen may cause stomach irritation and may not be suitable for everyone.',
    'A combination pain-relief medicine.'
),
(
    'Kremil-S',
    'Aluminum Hydroxide, Magnesium Hydroxide and Simethicone',
    'Tablet',
    'Used for relief of heartburn, acidity, and gas.',
    'Check the product label and consult a healthcare professional if symptoms persist.',
    'An antacid and antiflatulent combination.'
);
