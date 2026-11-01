
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def search_books(search_term):
    url = "https://openlibrary.org/search.json"

    parameters = {
        "q": search_term,
        "fields": "key,title,author_name,first_publish_year,cover_i",
        "limit": 10
    }

    request_url = url + "?" + urlencode(parameters)

    request = Request(
        request_url,
        headers={
            "User-Agent": "DistributedLibraryStudentProject/1.0 (student project)"
        }
    )

    try:
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))

        books = []

        for item in data.get("docs", []):
            cover_id = item.get("cover_i")

            books.append({
                "book_id": item.get("key"),
                "title": item.get("title", "Unknown title"),
                "authors": ", ".join(
                    item.get("author_name", ["Unknown author"])
                ),
                "year": item.get("first_publish_year", "Unknown"),
                "cover": (
                    f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
                    if cover_id else ""
                )
            })

        return books

    except (URLError, HTTPError, TimeoutError, ValueError) as error:
        print("Open Library API error:", error)
        return []


if __name__ == "__main__":
    results = search_books("computer science")

    print(f"\nFound {len(results)} books:\n")

    for book in results:
        print("Title:", book["title"])
        print("Author:", book["authors"])
        print("Year:", book["year"])
        print("Cover:", book["cover"])
        print("-" * 40)
