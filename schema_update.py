import sqlite3

# Connect to the database
conn = sqlite3.connect('maindatabase.db')
c = conn.cursor()

# Check if state and lga columns already exist
c.execute("PRAGMA table_info(users)")
columns = c.fetchall()
column_names = [col[1] for col in columns]

# Add state column if it doesn't exist
if 'state' not in column_names:
    c.execute("ALTER TABLE users ADD COLUMN state TEXT")
    print("Added state column to users table")

# Add lga column if it doesn't exist
if 'lga' not in column_names:
    c.execute("ALTER TABLE users ADD COLUMN lga TEXT")
    print("Added lga column to users table")

# Commit changes and close connection
conn.commit()
conn.close()

print("Database schema updated successfully")