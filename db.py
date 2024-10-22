import sqlite3

# Initialize SQLite database and create a table to store conversation state
def init_db():
    conn = sqlite3.connect('conversation_state.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS image_uploads (
            sender TEXT PRIMARY KEY,
            person_image TEXT,
            garment_image TEXT
        );
    ''')
    conn.commit()
    conn.close()

# Insert or update an image record
def update_image(sender, image_type, image_url):
    conn = sqlite3.connect('conversation_state.db')
    cursor = conn.cursor()

    try:
        if image_type == 'person':
            cursor.execute('''
                INSERT INTO image_uploads (sender, person_image, garment_image)
                VALUES (?, ?, NULL);
            ''', (sender, image_url))
        elif image_type == 'garment':
            cursor.execute('''
                INSERT INTO image_uploads (sender, person_image, garment_image)
                VALUES (?, NULL, ?);
            ''', (sender, image_url))
        
        conn.commit()  # Ensure commit is called after the transaction
        print(f"Database updated successfully for {sender} with {image_type} image.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")  # Log the error for troubleshooting
    finally:
        conn.close()  # Always close the connection to avoid leaks

# Retrieve stored image data for a sender
def get_images(sender):
    conn = sqlite3.connect('conversation_state.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT person_image, garment_image FROM image_uploads;
    ''')
    data = cursor.fetchone()
    conn.close()
    return data