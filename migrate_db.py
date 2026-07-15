import sqlite3

conn = sqlite3.connect('instance/database.db')
cur = conn.cursor()

# Add foto_toko column
try:
    cur.execute('ALTER TABLE pengaturan_toko ADD COLUMN foto_toko VARCHAR(200) NOT NULL DEFAULT ""')
    print('Column foto_toko added successfully')
except Exception as e:
    print(f'Column may already exist: {e}')

# Update WA number
cur.execute('UPDATE pengaturan_toko SET no_wa = "6287715811122" WHERE id = 1')
conn.commit()
rows = cur.execute('SELECT id, no_wa, foto_toko FROM pengaturan_toko').fetchall()
print('Current data:', rows)
conn.close()
print('Done!')
