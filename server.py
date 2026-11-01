
from flask import Flask, render_template, jsonify, request
from database import connect_db, initialize_database
from open_library import search_books
import sqlite3

app = Flask(__name__)

# Prepare the database when the server starts.
initialize_database()


# Route 1: Display the website
@app.route("/")
def home():
    return render_template("index.html")


# Route 2: Check whether the server is running
@app.route("/api/health")
def health():
    return jsonify({
        "status": "online",
        "server": "PC A - Primary"
    })


# Route 3: Retrieve all books from SQLite
@app.route("/api/books")
def get_books():
    connection = connect_db()

    books = connection.execute("""
        SELECT id, title, author, total_copies, available_copies
        FROM books
        ORDER BY id
    """).fetchall()

    connection.close()

    return jsonify([dict(book) for book in books])


# Route 4: Search Open Library
@app.route("/api/search")
def search_library():
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify({
            "success": False,
            "message": "Please enter a book title or author."
        }), 400

    results = search_books(query)

    return jsonify({
        "success": True,
        "results": results
    })


# Route 5: Add a selected Open Library book to SQLite
@app.route("/api/add-book", methods=["POST"])
def add_book():
    data = request.get_json(silent=True) or {}

    external_id = data.get("book_id")
    title = data.get("title")
    author = data.get("authors", "Unknown author")
    

    if not external_id or not title:
        return jsonify({
            "success": False,
            "message": "Book ID and title are required."
        }), 400

    connection = connect_db()

    try:
        connection.execute("""
            INSERT INTO books
                (external_id, title, author, available,
                    total_copies, available_copies)
            VALUES (?, ?, ?, 1, 1, 1)
        """, (external_id, title, author))

        connection.commit()

        return jsonify({
            "success": True,
            "message": f"{title} was added to your library."
        })

    except sqlite3.IntegrityError:
        return jsonify({
            "success": False,
            "message": "This book is already in your library."
        }), 409

    finally:
        connection.close()


# Route 6: Borrow a book safely
@app.route("/api/borrow", methods=["POST"])
def borrow_book():
    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")

    if book_id is None:
        return jsonify({
            "success": False,
            "message": "Book ID is required."
        }), 400

    connection = connect_db()

    try:
        # Only one request can successfully take the final copy.
        result = connection.execute("""
            UPDATE books
            SET available_copies = available_copies - 1
            WHERE id = ? AND available_copies > 0
        """, (book_id,))

        if result.rowcount == 1:
            book = connection.execute(
                "SELECT title FROM books WHERE id = ?",
                (book_id,)
            ).fetchone()

            connection.commit()

            return jsonify({
                "success": True,
                "message": f"You borrowed {book['title']} successfully."
            })

        connection.rollback()

        book = connection.execute(
            "SELECT id FROM books WHERE id = ?",
            (book_id,)
        ).fetchone()

        if book is None:
            return jsonify({
                "success": False,
                "message": "Book not found."
            }), 404

        return jsonify({
            "success": False,
            "message": "Sorry, this book is currently unavailable."
        }), 409

    finally:
        connection.close()


# Start the server
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )
