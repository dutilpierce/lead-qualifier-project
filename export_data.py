import sqlite3
import csv
from datetime import datetime

DATABASE = 'lead_qualifier.db'
EXPORT_FILE = f'leads_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

try:
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM leads')
    
    # Get column names
    headers = [i[0] for i in cursor.description]
    
    with open(EXPORT_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(cursor.fetchall())

    print(f"Successfully exported {cursor.rowcount} records to {EXPORT_FILE}")

except sqlite3.OperationalError as e:
    print(f"ERROR: Could not read database. Make sure app.py is not running. Details: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    if conn:
        conn.close()