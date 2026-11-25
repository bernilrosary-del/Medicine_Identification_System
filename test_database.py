
from database import get_connection

try:
    connection = get_connection()

    if connection and connection.is_connected():
        print("Connected to MySQL successfully!")

        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        result = cursor.fetchone()

        print("Connected database:", result[0])

        cursor.close()
        connection.close()

except Exception as error:
    print("Database test failed:", error)
