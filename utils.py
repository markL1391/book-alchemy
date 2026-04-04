from datetime import datetime

def parse_date(date_str: str):
    """
    Parse a HTML <input type="date"> ('YYYY-MM-DD') into a datetime.date object.

    Returns:
         datetime.date or None.
    """
    cleaned_date_string = (date_str or "").strip()
    if not cleaned_date_string:
        return None

    return datetime.strptime(cleaned_date_string, "%Y-%m-%d").date()


def normalize_isbn(isbn: str) -> str:
    """
    Normalize ISBN input by removing hyphens and spaces.
    """
    return (isbn or "").replace("-", "").replace(" ", "").strip()
