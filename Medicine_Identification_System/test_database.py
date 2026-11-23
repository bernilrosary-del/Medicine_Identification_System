
import mysql.connector

try:
    connection = mysql.connector.connect(
        host="localhost",
        port=3306,
        user="root",
        password="stem123",
        database="medicine_system"
    )

    print("Connected to MySQL successfully!")

    cursor = connection.cursor()
    cursor.execute("SELECT brand_name, generic_name FROM medicines")

    medicines = cursor.fetchall()

    for medicine in medicines:
        print("Brand name:", medicine[0])
        print("Generic name:", medicine[1])

    cursor.close()
    connection.close()

except mysql.connector.Error as error:
    print("Database connection failed:", error)
