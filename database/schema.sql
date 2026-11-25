
CREATE DATABASE IF NOT EXISTS medicine_system;

USE medicine_system;

CREATE TABLE IF NOT EXISTS medicines (
    medicine_id INT AUTO_INCREMENT PRIMARY KEY,

    brand_name VARCHAR(150) NOT NULL,

    generic_name VARCHAR(150) NOT NULL,

    medicine_type VARCHAR(100),

    common_uses TEXT,

    warnings TEXT,

    description TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_brand_name (brand_name),

    INDEX idx_generic_name (generic_name)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;
