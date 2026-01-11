import sqlite3

conn = sqlite3.connect('d:/Workspace/Tust-AETE/sql_app.db')
cursor = conn.cursor()

cursor.execute("SELECT robot_type, label, base FROM robot_configs")
rows = cursor.fetchall()
for row in rows:
    print(row)

conn.close()
