
import json
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError, HTTPError


def search_books(search_term):
    url = "https://www.googleapis.com/books/v1/volumes"

    parameters = {
        "q": search_term,
        "maxResults": 10,
        "printType": "books"
    }

    request_url = url + "?" + urlencode(parameters)

    try:
        with urlopen(request_url, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        books = []

        for item in data.get("items", []):
            info = item.get("volumeInfo", {})

            books.append({
                "google_id": item.get("id"),
                "title": info.get("title", "Unknown title"),
                "authors": ", ".join(info.get("authors", ["Unknown author"])),
                "publisher": info.get("publisher", "Unknown publisher"),
                "description": info.get("description", ""),
                "cover": info.get("imageLinks", {}).get("thumbnail", "")
            })

        return books

    except (URLError, HTTPError, TimeoutError, ValueError) as error:
        print("Google Books API error:", error)
        return []


if __name__ == "__main__":
    results = search_books("computer science")

    print(f"\nFound {len(results)} books:\n")

    for book in results:
        print("Title:", book["title"])
        print("Author:", book["authors"])
        print("Publisher:", book["publisher"])
        print("-" * 40)
