import requests

# Reuse one HTTP session for better performance and to set consistent headers.
http_session = requests.Session()
http_session.headers.update({
    "User-Agent": "BookAlchemy/1.0 (academic project)",
    "Accept": "application/json",
})


def extract_summary(book_data: dict) -> str | None:
    """
    Extracts a book summary from an Open Library JSON object.
    The Open Library API may return the "description" field either as a plain
    string or as a dictionary containing a "value" key. This function handles
    both cases and returns a cleaned summary string if available.

    Args:
         book_data (dict): JSON data returned by the Open Library API.

    Returns:
        str or None: The extracted summary text, or None if no summary exists.
    """
    description = book_data.get("description")

    if isinstance(description, str):
        cleaned_description = description.strip()
        return cleaned_description if cleaned_description else None

    if isinstance(description, dict):
        description_value = (description.get("value") or "").strip()
        return description_value if description_value else None

    return None

def fetch_summary_by_isbn(isbn: str) -> str | None:
    """
    Fetch a book summary from Open Library using ISBN.

    Strategy:
    1) Try edition endpoint: (/isbn/{isbn}.json)
    2) If missing, fallback to the linked Work: /works/{id}.json
    """
    if not isbn:
        return None

    # --- 1) Edition ---
    edition_url = f"https://openlibrary.org/isbn/{isbn}.json"
    try:
        edition_response = http_session.get(edition_url, timeout=8)
        if edition_response.status_code != 200:
            return None
        edition_data = edition_response.json()
    except (requests.RequestException, ValueError):
        return None

    edition_summary = extract_summary(edition_data)
    if edition_summary:
        return edition_summary

    # --- 2) Work fallback ---
    works = edition_data.get("works") or []
    if not (isinstance(works, list)) and works and isinstance(works[0], dict) and "key" in works[0]:
        return None

    work_key = works[0]["key"]
    work_url = f"https://openlibrary.org{work_key}.json"

    try:
        work_response = http_session.get(work_url, timeout=8)
        if work_response.status_code != 200:
            return None
        work_data = work_response.json()
    except (requests.RequestException, ValueError):
        return None

    return extract_summary(work_data)