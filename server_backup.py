
from flask import Flask, jsonify, request, render_template
from database import connect_db, initialize_database

app = Flask(__name__)

# Shared secret: PC A must use exactly the same value.
REPLICATION_TOKEN = "library-replication-2026-change-this"

# Prepare PC B's own database.
initialize_database()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "online",
        "server": "PC B - Backup"
    })


@app.route("/api/books")
def get_books():
    connection = connect_db()

    try:
        books = connection.execute("""
            SELECT id, title, author, total_copies, available_copies
            FROM books
            ORDER BY id
        """).fetchall()

        return jsonify([dict(book) for book in books])
    finally:
        connection.close()


# PC A sends the complete book catalogue to this endpoint.
@app.route("/internal/replicate", methods=["POST"])
def receive_replication():
    token = request.headers.get("X-Replication-Token")

    if token != REPLICATION_TOKEN:
        return jsonify({
            "success": False,
            "message": "Unauthorized"
        }), 401

    data = request.get_json(silent=True) or {}
    books = data.get("books")

    if not isinstance(books, list):
        return jsonify({
            "success": False,
            "message": "A books list is required."
        }), 400

    connection = connect_db()

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM books")

        for book in books:
            book_id = book.get("id")
            title = book.get("title")
            author = book.get("author")
            total = book.get("total_copies")
            available = book.get("available_copies")
            external_id = book.get("external_id")

            if (
                not isinstance(book_id, int)
                or not isinstance(title, str)
                or not isinstance(author, str)
                or not isinstance(total, int)
                or not isinstance(available, int)
                or total < 0
                or available < 0
                or available > total
            ):
                raise ValueError("Invalid book record.")

            connection.execute("""
                INSERT INTO books (
                    id, external_id, title, author, available,
                    total_copies, available_copies
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                book_id,
                external_id,
                title,
                author,
                1 if available > 0 else 0,
                total,
                available
            ))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Backup catalogue updated.",
            "books_received": len(books)
        })

    except Exception as error:
        connection.rollback()

        return jsonify({
            "success": False,
            "message": str(error)
        }), 400

    finally:
        connection.close()


# PC B is read-only until we deliberately promote it.
@app.route("/api/borrow", methods=["POST"])
def backup_borrow():
    return jsonify({
        "success": False,
        "message": "This is the backup server. Borrowing is disabled."
    }), 503


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=False,
        threaded=True
    )
