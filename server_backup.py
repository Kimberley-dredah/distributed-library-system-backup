
from flask import Flask, jsonify, request, render_template
from database import connect_db, initialize_database

import sqlite3
from open_library import search_books
from ha import HAController
import os
import hmac
import json
import urllib.request
import threading
import time

app = Flask(__name__)

ha = HAController("PC-B", startup_delay=20)
ha.start()

# Shared secret: PC A must use exactly the same value.
REPLICATION_TOKEN = os.environ.get("LIBRARY_REPLICATION_TOKEN")

if not REPLICATION_TOKEN:
    raise RuntimeError("LIBRARY_REPLICATION_TOKEN is missing.")

BACKUP_URL = "http://10.216.237.113:5000/internal/replicate"
BACKUP_PROMOTED = False

# Prepare PC B's own database.
initialize_database()

def replicate_books():
    connection = connect_db()

    try:
        rows = connection.execute("""
            SELECT id, external_id, title, author,
                   total_copies, available_copies
            FROM books
            ORDER BY id
        """).fetchall()

        books = [dict(row) for row in rows]
    finally:
        connection.close()

    payload = json.dumps({"books": books}).encode("utf-8")

    req = urllib.request.Request(
        BACKUP_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Replication-Token": REPLICATION_TOKEN
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))

        return result.get("success", False), result.get("message", "")

    except Exception as error:
        print("PC A REPLICATION FAILED:", error)
        return False, str(error)

def background_replication():
    while True:
        time.sleep(10)

        try:
            if ha.is_leader():
                success, message = replicate_books()

                if success:
                    print("BACKGROUND REPLICATION SUCCESS:", message)
                else:
                    print("BACKGROUND REPLICATION RETRY:", message)

        except Exception as error:
            print("BACKGROUND REPLICATION ERROR:", error)


@app.route("/")
def home():
    if not ha.is_leader():
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Redirecting to Master Server</title>
            <meta http-equiv="refresh"
                  content="2;url=http://10.216.237.113:5000/">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background: #f1f5f9;
                    text-align: center;
                    padding: 100px 20px;
                    color: #12304a;
                }
                .box {
                    background: white;
                    padding: 35px;
                    border-radius: 12px;
                    max-width: 550px;
                    margin: auto;
                }
            </style>
        </head>
        <body>
            <div class="box">
                <h2>PC B - Backup Server</h2>
                <p>
                    PC B (backup server) is currently on standby.
                </p>
                <h3>Redirecting you to PC A (Master Server)...</h3>
                <p>Please wait.</p>
            </div>

            <script>
                setTimeout(function() {
                    window.location.replace(
                        "http://10.216.237.113:5000/"
                    );
                }, 2000);
            </script>
        </body>
        </html>
        """

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

        # Keep JSON available to your website's JavaScript.
        if request.args.get("format") == "json":
            return jsonify([dict(book) for book in books])

        rows = ""

        for book in books:
            availability = (
                "Available" if book["available_copies"] > 0
                else "Unavailable"
            )

            rows += f"""
            <tr>
                <td>{book['id']}</td>
                <td>{book['title']}</td>
                <td>{book['author']}</td>
                <td>{book['total_copies']}</td>
                <td>{book['available_copies']}</td>
                <td>{availability}</td>
            </tr>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Library Books Catalogue</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background: #f1f5f9;
                    padding: 30px;
                    color: #1e293b;
                }}
                h1 {{ color: #12304a; }}
                .container {{
                    background: white;
                    padding: 20px;
                    border-radius: 12px;
                    overflow-x: auto;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    min-width: 650px;
                }}
                th, td {{
                    padding: 14px;
                    border-bottom: 1px solid #ddd;
                    text-align: left;
                }}
                th {{
                    background: #12304a;
                    color: white;
                }}
                tr:hover {{ background: #f1f5f9; }}
                .count {{ margin-bottom: 18px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Community Library Catalogue</h1>
                <p class="count">Total books: {len(books)}</p>
                <table>
                    <thead>
                        <tr>
                            <th>Book ID</th>
                            <th>Title</th>
                            <th>Author</th>
                            <th>Total Copies</th>
                            <th>Available Copies</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows if rows else '<tr><td colspan="6">No books found.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """

    finally:
        connection.close()



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

@app.route("/api/add-book", methods=["POST"])
def add_book():
    if not ha.is_leader():
        return jsonify({
            "success": False,
            "message": "PC B is standby. Book changes are disabled."
        }), 503
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
            INSERT INTO books (
                external_id, title, author, available,
                total_copies, available_copies
            )
            VALUES (?, ?, ?, 1, 1, 1)
        """, (external_id, title, author))

        connection.commit()

        return jsonify({
            "success": True,
            "message": f"{title} was added to the library.",
            "backup_synced": backup_ok,
            "backup_message": backup_message
        })

    except sqlite3.IntegrityError:
        connection.rollback()
        return jsonify({
            "success": False,
            "message": "This book is already in the library."
        }), 409

    finally:
        connection.close()
        backup_ok, backup_message = replicate_books()

@app.route("/internal/replicate", methods=["POST"])
def receive_replication():
    token = request.headers.get("X-Replication-Token", "")

    if not hmac.compare_digest(token, REPLICATION_TOKEN):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    if ha.is_leader():
        return jsonify({
            "success": False,
            "message": "PC B is leader; replication from PC A is rejected."
        }), 409

    data = request.get_json(silent=True) or {}
    books = data.get("books")

    if not isinstance(books, list):
        return jsonify({"success": False, "message": "A books list is required."}), 400

    for book in books:
        if not isinstance(book, dict):
            return jsonify({"success": False, "message": "Invalid book record."}), 400

        if (
            type(book.get("id")) is not int
            or not isinstance(book.get("title"), str)
            or not isinstance(book.get("author"), str)
            or type(book.get("total_copies")) is not int
            or type(book.get("available_copies")) is not int
            or book["total_copies"] < 0
            or book["available_copies"] < 0
            or book["available_copies"] > book["total_copies"]
        ):
            return jsonify({"success": False, "message": "Invalid book record."}), 400

    connection = connect_db()

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM books")

        for book in books:
            connection.execute("""
                INSERT INTO books (
                    id, external_id, title, author, available,
                    total_copies, available_copies
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                book["id"],
                book.get("external_id"),
                book["title"],
                book["author"],
                1 if book["available_copies"] > 0 else 0,
                book["total_copies"],
                book["available_copies"]
            ))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "PC B catalogue updated from PC A.",
            "books_received": len(books)
        })

    except Exception as error:
        connection.rollback()
        return jsonify({"success": False, "message": str(error)}), 400

    finally:
        connection.close()
    token = request.headers.get("X-Replication-Token")

    if token != REPLICATION_TOKEN:
        return jsonify({
            "success": False,
            "message": "Unauthorized"
        }), 401

    if BACKUP_PROMOTED:
        return jsonify({
            "success": False,
            "message": "PC B has taken over. Replication from PC A is disabled."
        }), 409
    
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
    if not ha.is_leader():
        return jsonify({
            "success": False,
            "message": "PC B is standby. Borrowing is disabled."
        }), 503
    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")

    if book_id is None:
        return jsonify({
            "success": False,
            "message": "Book ID is required."
        }), 400

    connection = connect_db()
    try:
        result = connection.execute("""
            UPDATE books
            SET available_copies = available_copies - 1
            WHERE id = ? AND available_copies > 0
        """, (book_id,))

        if result.rowcount == 0:
            connection.rollback()
            return jsonify({
                "success": False,
                "message": "Book not found or unavailable."
            }), 409

        connection.commit()
        backup_ok, backup_message = replicate_books()

        return jsonify({
            "success": True,
            "message": "Book borrowed successfully on PC B.",
            "backup_synced": backup_ok,
            "backup_message": backup_message
        })
    finally:
        connection.close()


@app.route("/api/return", methods=["POST"])
def return_book():
    if not ha.is_leader():
        return jsonify({
            "success": False,
            "message": "PC B is not the active server"
        }), 503

    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")

    if book_id is None:
        return jsonify({
            "success": False,
            "message": "Book ID is required."
        }), 400

    connection = connect_db()

    try:
        result = connection.execute("""
            UPDATE books
            SET available_copies = available_copies + 1
            WHERE id = ?
            AND available_copies < total_copies
        """, (book_id,))

        if result.rowcount != 1:
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
                "message": "All copies of this book are already available."
            }), 409

        book = connection.execute(
            "SELECT title FROM books WHERE id = ?",
            (book_id,)
        ).fetchone()

        title = book["title"]
        connection.commit()

    finally:
        connection.close()

    backup_ok, backup_message = replicate_books()

    return jsonify({
        "success": True,
        "message": f"{title} was returned successfully.",
        "backup_synced": backup_ok,
        "backup_message": backup_message
    })


if __name__ == "__main__":

    threading.Thread(
        target=background_replication,
        daemon=True
    ).start()

    app.run(
        host="0.0.0.0",
        port=5001,
        debug=False,
        threaded=True
    )
