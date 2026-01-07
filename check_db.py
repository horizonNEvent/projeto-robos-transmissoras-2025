import sqlite3
import os

DB_PATH = os.path.join(os.getcwd(), 'sql_app.db')

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print("Checking specific codes:")
    cursor.execute("SELECT codigo_ons, sigla, nome, cnpj FROM transmissora WHERE codigo_ons IN ('1292', '1254', '1355')")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
        
    print("\nChecking by CNPJ 10261111000105:")
    cursor.execute("SELECT codigo_ons, sigla, nome, cnpj FROM transmissora WHERE replace(replace(replace(cnpj, '.', ''), '/', ''), '-', '') = '10261111000105'")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
        
    conn.close()
except Exception as e:
    print(e)
