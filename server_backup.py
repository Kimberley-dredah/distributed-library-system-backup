
from flask import Flask, render_template, jsonify, request
from threading import Lock

app = Flask(__name__)

# Temporary sample data for Day 1.
# We will replace this with SQLite later.
books = [
    {
        "id": 1,
        "title": "Introduction to Networking",
        "author": "James Kurose",
        "total_copies": 3,
        "available_copies": 3
    },
    {
        "id": 2,
        "title": "Distributed Systems",
        "author": "Andrew Tanenbaum",
        "total_copies": 1,
        "available_copies": 1
    },
    {
        "id": 3,
        "title": "Python Programming",
        "author": "John Zelle",
        "total_copies": 2,
        "available_copies": 2
    }
]

# Protects book updates from simultaneous requests
book_lock = Lock()


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


# Route 3: Retrieve all books
@app.route("/api/books")
def get_books():
    with book_lock:
        return jsonify(books)


# Route 4: Borrow a book
@app.route("/api/borrow", methods=["POST"])
def borrow_book():
    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")

    if book_id is None:
        return jsonify({
            "success": False,
            "message": "Book ID is required."
        }), 400

    with book_lock:
        for book in books:
            if book["id"] == book_id:

                if book["available_copies"] > 0:
                    book["available_copies"] -= 1

                    return jsonify({
                        "success": True,
                        "message": f"You borrowed {book['title']} successfully."
                    })

                return jsonify({
                    "success": False,
                    "message": "Sorry, this book is currently unavailable."
                }), 409

    return jsonify({
        "success": False,
        "message": "Book not found."
    }), 404


# Start the server
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )
