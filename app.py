"""
BookAlchemy - a personal digital library built with Flask and SQLAlchemy.

Features:
- Add authors and books (with validation)
- Search and sort library entries
- Book & author detail pages
- Delete books (and remove orphan authors)
- Fetch book summaries from Open Library by ISBN
"""


from flask import Flask, request, render_template, redirect, url_for, flash
import os
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import requests

from data_models import db, Author, Book


# Reuse one HTTP session for better performance and to set consistent headers.
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "BookAlchemy/1.0 (academic project)",
    "Accept": "application/json",
})


app = Flask(__name__)
app.secret_key = "dev-secret-key"           # For flash messages (dev only).

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'data/library.sqlite')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)


def parse_date(date_str: str):
    """
    Parse a HTML <input type="date"> ('YYYY-MM-DD') into a datetime.date.

    Returns:
         datetime.date or None.
    """
    date_str = (date_str or "").strip()
    if not date_str:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def normalize_isbn(isbn: str) -> str:
    """
    Normalize ISBN input by removing hyphens and spaces.
    """
    return (isbn or "").replace("-", "").replace(" ", "").strip()

def extract_summary(data: dict) -> str | None:
    """
    Extracts a book summary from an Open Library JSON object.
    The Open Library API may return the "description" field either as a plain
    string or as a dictionary containing a "value" key. This function handles
    both cases and returns a cleaned summary string if available.

    Args:
         data (dict): JSON data returned by the Open Library API.

    Returns:
        str or None: The extracted summary text, or None if no summary exists.
    """
    desc = data.get("description")

    if isinstance(desc, str):
        desc = desc.strip()
        return desc if desc else None

    if isinstance(desc, dict):
        val = (desc.get("value") or "").strip()
        return val if val else None

    return None

def fetch_summary_by_isbn(isbn: str) -> str | None:
    """
    Fetch a book summary from Open Library using ISBN.

    Strategy:
    1) Try edition endpoint: (/isbn/{isbn}.json)
    2) If missing, fallback to the linked Work: /works/{id}.json
    """
    isbn = normalize_isbn(isbn)
    if not isbn:
        return None

    # --- 1) Edition ---
    ed_url = f"https://openlibrary.org/isbn/{isbn}.json"
    try:
        r = SESSION.get(ed_url, timeout=8)
        if r.status_code != 200:
            return None

        edition = r.json()
    except (requests.RequestException, ValueError):
        return None

    summary = extract_summary(edition)
    if summary:
        return summary

    # --- 2) Work fallback ---
    works = edition.get("works") or []
    if works and isinstance(works, list) and isinstance(works[0], dict) and "key" in works[0]:
        work_key = works[0]["key"]
        w_url = f"https://openlibrary.org{work_key}.json"
        try:
            wr = SESSION.get(w_url, timeout=8)
            if wr.status_code != 200:
                return None
            work = wr.json()
        except (requests.RequestException, ValueError):
            return None

        return extract_summary(work)

    return None


def create_app():
    """
    Factory hook (for testing)
    """
    return app


@app.route("/")
def home():
    """
    Homepage: shows all books, support:
    - search by title or author via ?q=
    - sorting via ?sort=title|author
    """
    q = request.args.get("q", "").strip()
    sort_key = request.args.get("sort", "title").strip()

    base_query = Book.query.join(Author)

    # Optional search filter.
    if q:
        like = f"%{q}%"
        base_query = base_query.filter(
            (Book.title.ilike(like)) | (Author.name.ilike(like))
        )

    # Sorting.
    if sort_key == "author":
        books = base_query.order_by(
            Author.name.asc(),
            Book.title.asc()
        ).all()
    else:
        sort_key = "title"
        books = base_query.order_by(Book.title.asc()).all()

    return render_template("home.html", books=books, q=q, sort_key=sort_key)


@app.route("/add_author", methods=["GET", "POST"])
def add_author():
    """
    Add a new author to the database.
    """
    message = None

    if request.method == "POST":
        # --- Read and validate form ---
        name = request.form.get("name", "").strip()
        birth_date_str = request.form.get("birth_date", "").strip()
        date_of_death_str = request.form.get("date_of_death", "").strip()

        if not name or not birth_date_str:
            message = "Please fill in at least name and birth date."
            return render_template("add_author.html", message=message)

        # --- Parse dates ---
        birth_date = parse_date(birth_date_str)
        date_of_death = parse_date(date_of_death_str)

        # --- Persist ---
        new_author = Author(
            name=name,
            birth_date=birth_date,
            date_of_death=date_of_death if date_of_death else None
        )

        db.session.add(new_author)
        db.session.commit()

        message = f"Author '{new_author.name}' was added successfully ✅"

    return render_template("add_author.html", message=message)


@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    """
    Add a new book. Validates:
    - required fields
    - publication year
    - unique ISBN (handled by DB constraint)
    Also tries to fetch a summary via Open Library.
    """
    message = None

    # Authors for loading dropdown.
    authors = Author.query.order_by(Author.name.asc()).all()
    current_year = datetime.now().year

    if request.method == "POST":
        # --- Read and normalize from data ---
        title = request.form.get("title", "").strip()
        isbn = request.form.get("isbn", "").strip()
        publication_year_str = request.form.get("publication_year", "").strip()
        author_id_str = request.form.get("author_id", "").strip()

        # --- Required fields ---
        if not title or not isbn or not publication_year_str or not author_id_str:
            message = "Please fill in title, ISBN, publication year, and choose an author."
            return render_template("add_book.html", message=message, authors=authors, current_year=current_year)

        # --- Cast to int ---
        try:
            publication_year = int(publication_year_str)
            author_id = int(author_id_str)
        except ValueError:
            message = "Publication year and author must be valid numbers."
            return render_template("add_book.html", message=message, authors=authors, current_year=current_year)

        # --- Validate year range ---
        if publication_year < 0 or publication_year > current_year:
            message = f"Publication year must be between 0 and {current_year}."
            return render_template("add_book.html", message=message, authors=authors, current_year=current_year)

        # --- Create and persist
        new_book = Book(
            title=title,
            isbn=isbn,
            publication_year=publication_year,
            author_id=author_id,
            summary=fetch_summary_by_isbn(isbn)
        )

        db.session.add(new_book)

        try:
            db.session.commit()
            message = f"Book '{new_book.title}' was added successfully ✅"
        except IntegrityError:
            db.session.rollback()
            message = "This ISBN already exists. Please use a unique ISBN."

    return render_template("add_book.html", message=message, authors=authors, current_year=current_year)


@app.route("/sort/<sort_key>")
def sort_books(sort_key):
    """
    Redirect helper to keep sort and search parameters unified.
    """
    q = request.args.get("q", "").strip()
    return redirect(url_for("home", sort=sort_key, q=q))

@app.route("/book/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    """
    Delete a book. If the book's author has no remaining books,
    the author is removed as well.
    """
    book = Book.query.get_or_404(book_id)
    author = book.author

    db.session.delete(book)
    db.session.flush()                      # Apply deletion before counting remaining books.

    if Book.query.filter_by(author_id=author.id).count() == 0:
        db.session.delete(author)

    db.session.commit()

    flash(f"Book '{book.title}' was deleted successfully ♻️", "success")
    return redirect(url_for("home"))

@app.route("/author/<int:author_id>/delete", methods=["POST"])
def delete_author(author_id):
    """
    Delete an author and all related books (cascade delete).
    """
    author = Author.query.get_or_404(author_id)
    name = author.name

    db.session.delete(author)
    db.session.commit()

    flash(f"Author '{name}' and all related books were deleted successfully ♻️", "success")
    return redirect(url_for("home", sort=request.args.get("sort", "title"), q=request.args.get("q", "")))

@app.route("/book/<int:book_id>")
def book_detail(book_id):
    """
    Displays a detail page for a single book, including its summary.
    """
    book = Book.query.get_or_404(book_id)
    return render_template("book_detail.html", book=book)


@app.route("/author/<int:author_id>")
def author_detail(author_id):
    """
    Show an author detail page (including their books).
    """
    author = Author.query.get_or_404(author_id)
    return render_template("author_detail.html", author=author)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)
