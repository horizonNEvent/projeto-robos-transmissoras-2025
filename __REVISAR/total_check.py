import sqlite3

conn = sqlite3.connect('d:/Workspace/Tust-AETE/sql_app.db')
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM robot_configs")
count = cursor.fetchone()[0]
print(f"Total de registros em robot_configs: {count}")

cursor.execute("SELECT id, robot_type, label FROM robot_configs LIMIT 10")
rows = cursor.fetchall()
for row in rows:
    print(row)

conn.close()
