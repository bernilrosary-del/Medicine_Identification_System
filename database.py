
import mysql.connector
from mysql.connector import IntegrityError

from config import (
    DB_HOST,
    DB_USER,
    DB_PASSWORD,
    DB_NAME,
    DB_PORT
)


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_connection():
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT
        )
        return connection

    except mysql.connector.Error as error:
        print("Database connection failed:", error)
        return None


# ==========================================
# GET ALL MEDICINES
# ==========================================

def get_all_medicines():
    connection = get_connection()

    if connection is None:
        return []

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM medicines
            ORDER BY brand_name ASC
        """)

        return cursor.fetchall()

    except mysql.connector.Error as error:
        print("Medicine retrieval failed:", error)
        return []

    finally:
        if cursor:
            cursor.close()
        connection.close()


# ==========================================
# GET MEDICINE BY ID
# ==========================================

def get_medicine_by_id(medicine_id):
    connection = get_connection()

    if connection is None:
        return None

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM medicines
            WHERE id = %s
            LIMIT 1
        """, (medicine_id,))

        return cursor.fetchone()

    except mysql.connector.Error as error:
        print("Medicine ID search failed:", error)
        return None

    finally:
        if cursor:
            cursor.close()
        connection.close()


# ==========================================
# SEARCH MEDICINE
# ==========================================

def search_medicine(keyword):
    if not keyword or not keyword.strip():
        return []

    connection = get_connection()

    if connection is None:
        return []

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        search_term = f"%{keyword.strip()}%"

        cursor.execute("""
            SELECT *
            FROM medicines
            WHERE brand_name LIKE %s
               OR generic_name LIKE %s
            ORDER BY brand_name ASC
        """, (search_term, search_term))

        return cursor.fetchall()

    except mysql.connector.Error as error:
        print("Medicine search failed:", error)
        return []

    finally:
        if cursor:
            cursor.close()
        connection.close()


# ==========================================
# GET MEDICINE BY NAME
# ==========================================

def get_medicine_by_name(medicine_name):
    if not medicine_name or not medicine_name.strip():
        return None

    connection = get_connection()

    if connection is None:
        return None

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM medicines
            WHERE LOWER(brand_name) = LOWER(%s)
               OR LOWER(generic_name) = LOWER(%s)
            ORDER BY
                CASE
                    WHEN LOWER(brand_name) = LOWER(%s)
                    THEN 0
                    ELSE 1
                END
            LIMIT 1
        """, (
            medicine_name.strip(),
            medicine_name.strip(),
            medicine_name.strip()
        ))

        return cursor.fetchone()

    except mysql.connector.Error as error:
        print("Medicine name search failed:", error)
        return None

    finally:
        if cursor:
            cursor.close()
        connection.close()


# ==========================================
# ADD MEDICINE
# ==========================================

def add_medicine(
    brand_name,
    generic_name,
    medicine_type=None,
    common_uses=None,
    warnings=None,
    source=None,
    description=None
):

    if not brand_name or not brand_name.strip():
        print("Brand name is required.")
        return False

    if not generic_name or not generic_name.strip():
        print("Generic name is required.")
        return False

    connection = get_connection()

    if connection is None:
        return False

    cursor = None

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO medicines (
                brand_name,
                generic_name,
                medicine_type,
                common_uses,
                warnings,
                source,
                description
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            brand_name.strip(),
            generic_name.strip(),
            medicine_type,
            common_uses,
            warnings,
            source,
            description
        ))

        connection.commit()

        print("Medicine added successfully!")
        return True

    except IntegrityError:
        connection.rollback()
        print("Duplicate medicine detected. Record was not added.")
        return False

    except mysql.connector.Error as error:
        connection.rollback()
        print("Medicine insertion failed:", error)
        return False

    finally:
        if cursor:
            cursor.close()
        connection.close()
