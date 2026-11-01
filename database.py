
import sqlite3

DATABASE = "library.db"


def connect_db():
    connection = sqlite3.connect(DATABASE, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = connect_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            total_copies INTEGER NOT NULL DEFAULT 1,
            available_copies INTEGER NOT NULL DEFAULT 1
        )
    """)

    # Upgrade an older version of the database if necessary.
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(books)")
    }

    if "external_id" not in columns:
        connection.execute("ALTER TABLE books ADD COLUMN external_id TEXT")

    if "total_copies" not in columns:
        connection.execute(
            "ALTER TABLE books ADD COLUMN total_copies INTEGER NOT NULL DEFAULT 1"
        )

    if "available_copies" not in columns:
        connection.execute(
            "ALTER TABLE books ADD COLUMN available_copies INTEGER NOT NULL DEFAULT 1"
        )

        # Preserve the available-copy values from the older database.
        if "available" in columns:
            connection.execute("""
                UPDATE books
                SET available_copies = available,
                    total_copies = available
            """)

    connection.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_books_external_id
        ON books(external_id)
    """)

    count = connection.execute(
        "SELECT COUNT(*) FROM books"
    ).fetchone()[0]

    if count == 0:
        sample_books = [
            ("Introduction to Networking", "James Kurose", 3, 3),
            ("Distributed Systems", "Andrew Tanenbaum", 1, 1),
            ("Python Programming", "John Zelle", 2, 2)
        ]

        connection.executemany("""
            INSERT INTO books (title, author, total_copies, available_copies)
            VALUES (?, ?, ?, ?)
        """, sample_books)

    connection.commit()
    connection.close()


if __name__ == "__main__":
    initialize_database()
    print("Library database is ready!")
