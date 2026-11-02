
const bookList = document.getElementById("bookList");
const searchInput = document.getElementById("searchInput");
const messageBox = document.getElementById("message");

let allBooks = [];

// Remember books borrowed through this browser
let borrowedBookIds = new Set(
    JSON.parse(localStorage.getItem("borrowedBookIds") || "[]")
        .map(String)
);

function saveBorrowedBooks() {
    localStorage.setItem(
        "borrowedBookIds",
        JSON.stringify([...borrowedBookIds])
    );
}

// Check whether the Python server is running
async function checkServer() {
    try {
        const response = await fetch("/api/health");
        const data = await response.json();

        document.getElementById("serverStatus").textContent =
            data.status === "online" ? "Server Online" : "Server Offline";

    } catch (error) {
        document.getElementById("serverStatus").textContent =
            "Server Offline";
    }
}


// Load books from SQLite
async function loadBooks() {
    try {
        const response = await fetch("/api/books?format=json");

        if (!response.ok) {
            throw new Error("Could not retrieve books.");
        }

        allBooks = await response.json();

        updateStatistics();
        displayBooks(allBooks);

    } catch (error) {
        bookList.textContent = "Unable to connect to the library server.";
    }
}



function displayBooks(books) {
    bookList.innerHTML = "";

    if (books.length === 0) {
        bookList.textContent = "No matching books found.";
        return;
    }

    books.forEach(book => {
        const card = document.createElement("div");
        card.className = "book-card";

        const icon = document.createElement("div");
        icon.className = "book-icon";
        icon.textContent = "📖";

        const title = document.createElement("h3");
        title.textContent = book.title;

        const author = document.createElement("p");
        author.className = "author";
        author.textContent = "By " + book.author;

        const copies = document.createElement("p");
        copies.className = "copies";
        copies.textContent =
            "Available copies: " + book.available_copies;

        const button = document.createElement("button");
        button.className = "borrow-btn";

        const alreadyBorrowed =
            borrowedBookIds.has(String(book.id));

        if (alreadyBorrowed) {
            button.textContent = "Return Book";
            button.addEventListener("click", () => {
                returnBook(book.id);
            });

        } else if (book.available_copies > 0) {
            button.textContent = "Borrow Book";
            button.addEventListener("click", () => {
                borrowBook(book.id);
            });

        } else {
            button.textContent = "Unavailable";
            button.disabled = true;
        }

        card.append(icon, title, author, copies, button);
        bookList.appendChild(card);
    });
}


// Update the statistics
function updateStatistics() {
    const total = allBooks.reduce(
        (sum, book) => sum + book.total_copies, 0
    );

    const available = allBooks.reduce(
        (sum, book) => sum + book.available_copies, 0
    );

    document.getElementById("totalBooks").textContent = total;
    document.getElementById("availableBooks").textContent = available;
}



// Borrow a book
async function borrowBook(bookId) {
    try {
        const response = await fetch("/api/borrow", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                book_id: bookId
            })
        });

        const result = await response.json();

        if (result.success) {
            borrowedBookIds.add(String(bookId));
            saveBorrowedBooks();
        }

        showMessage(
            result.message,
            result.success ? "success" : "error"
        );

        await loadBooks();

    } catch (error) {
        showMessage("Could not contact the server.", "error");
    }
}


// Return a borrowed book
async function returnBook(bookId) {
    try {
        const response = await fetch("/api/return", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                book_id: bookId
            })
        });

        const result = await response.json();

        if (result.success) {
            borrowedBookIds.delete(String(bookId));
            saveBorrowedBooks();
        }

        showMessage(
            result.message,
            result.success ? "success" : "error"
        );

        await loadBooks();

    } catch (error) {
        showMessage("Could not contact the server.", "error");
    }
}


// Search Open Library
async function searchExternalBooks() {
    const input = document.getElementById("apiSearchInput");
    const resultsBox = document.getElementById("apiSearchResults");
    const button = document.getElementById("apiSearchButton");

    const query = input.value.trim();

    if (!query) {
        showMessage("Please enter a book title or author.", "error");
        return;
    }

    resultsBox.textContent = "Searching for books...";
    button.disabled = true;

    try {
        const response = await fetch(
            "/api/search?q=" + encodeURIComponent(query)
        );

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.message || "Book search failed.");
        }

        displayExternalBooks(data.results);

    } catch (error) {
        resultsBox.textContent =
            "Unable to search for books. Please try again.";

        showMessage(error.message, "error");

    } finally {
        button.disabled = false;
    }
}


// Display external search results
function displayExternalBooks(books) {
    const resultsBox = document.getElementById("apiSearchResults");

    resultsBox.innerHTML = "";

    if (!books || books.length === 0) {
        resultsBox.textContent = "No books found.";
        return;
    }

    books.forEach(book => {
        const card = document.createElement("div");
        card.className = "external-book";

        if (book.cover) {
            const image = document.createElement("img");
            image.src = book.cover;
            image.alt = "Book cover";
            image.loading = "lazy";
            card.appendChild(image);
        }

        const title = document.createElement("h3");
        title.textContent = book.title;

        const author = document.createElement("p");
        author.textContent = "Author: " + book.authors;

        const year = document.createElement("p");
        year.textContent = "First published: " + book.year;

        const button = document.createElement("button");
        button.className = "add-book-btn";
        button.textContent = "Add to My Library";

        button.addEventListener("click", () => {
            addBookToLibrary(book);
        });

        card.append(title, author, year, button);
        resultsBox.appendChild(card);
    });
}


// Add a selected book to SQLite
async function addBookToLibrary(book) {
    try {
        const response = await fetch("/api/add-book", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                book_id: book.book_id,
                title: book.title,
                authors: book.authors
            })
        });

        const result = await response.json();

        showMessage(
            result.message,
            result.success ? "success" : "error"
        );

        if (result.success) {
            await loadBooks();
        }

    } catch (error) {
        showMessage("Could not add the book.", "error");
    }
}


// Show messages
function showMessage(message, type) {
    messageBox.textContent = message;
    messageBox.className = "message " + type;

    setTimeout(() => {
        messageBox.className = "message";
    }, 4000);
}


// Search the existing local collection
searchInput.addEventListener("input", () => {
    const query = searchInput.value.toLowerCase();

    const filteredBooks = allBooks.filter(book =>
        book.title.toLowerCase().includes(query) ||
        book.author.toLowerCase().includes(query)
    );

    displayBooks(filteredBooks);
});


// Start the webpage
checkServer();
loadBooks();
