"""
BookAlchemy - a personal digital library built with Flask and SQLAlchemy.

Features:
- Add authors and books (with validation)
- Search and sort library entries
- Book & author detail pages
- Delete books (and remove orphan authors)
- Fetch book summaries from Open Library by ISBN
"""

import os
from datetime import datetime

from flask import Flask, request, render_template, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError

from data_models import db, Author, Book
from utils import parse_date, normalize_isbn
from open_library_service import fetch_summary_by_isbn


app = Flask(__name__)
app.secret_key = "dev-secret-key"           # For flash messages (dev only).

basedir = os.path.abspath(os.path.dirname(__file__))

# Ensure data directory exists so SQLite can create the DB file
os.makedirs(os.path.join(basedir, "data"), exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'data/library.sqlite')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

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
    search_query = request.args.get("q", "").strip()
    sort_key = request.args.get("sort", "title").strip()

    book_query = Book.query.join(Author)

    # Optional search filter.
    if search_query:
        search_pattern = f"%{search_query}%"
        book_query = book_query.filter(
            (Book.title.ilike(search_pattern)) | (Author.name.ilike(search_pattern))
        )

    # Sorting.
    if sort_key == "author":
        books = book_query.order_by(
            Author.name.asc(),
            Book.title.asc()
        ).all()
    else:
        sort_key = "title"
        books = book_query.order_by(Book.title.asc()).all()

    return render_template(
        "home.html",
        books=books,
        q=search_query,
        sort_key=sort_key
    )


@app.route("/add_author", methods=["GET", "POST"])
def add_author():
    """
    Add a new author to the database.
    """
    message = None

    if request.method == "POST":
        # --- Read and validate form ---
        author_name = request.form.get("name", "").strip()
        birth_date_input = request.form.get("birth_date", "").strip()
        date_of_death_input = request.form.get("date_of_death", "").strip()

        if not author_name or not birth_date_input:
            message = "Please fill in at least name and birth date."
            return render_template("add_author.html", message=message)

        # --- Parse dates ---
        try:
            birth_date = parse_date(birth_date_input)
            date_of_death = parse_date(date_of_death_input)
        except ValueError:
            message = "Please enter valid dates."
            return  render_template("add_author.html", message=message)

        today = datetime.now().date()

        if birth_date is None:
            message = "Birth date is required."
            return render_template("add_author.html", message=message)

        if birth_date > today:
            message = "Birth date cannot be in the future."
            return render_template("add_author.html", message=message)

        if date_of_death and date_of_death > today:
            message = "Date of death cannot be in the future."
            return render_template("add_author.html", message=message)

        if date_of_death and date_of_death < birth_date:
            message = "Date of death cannot be before birth date."
            return render_template("add_author.html", message=message)

        # --- Persist ---
        new_author = Author(
            name=author_name,
            birth_date=birth_date,
            date_of_death=date_of_death
        )

        db.session.add(new_author)

        try:
            db.session.commit()
            message = f"Author '{new_author.name}' was added successfully ✅"
        except Exception:
            db.session.rollback()
            message = "Something went wrong while adding the author."

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
        book_title = request.form.get("title", "").strip()
        raw_isbn = request.form.get("isbn", "").strip()
        normalized_isbn = normalize_isbn(raw_isbn)
        publication_year_input = request.form.get("publication_year", "").strip()
        author_id_input = request.form.get("author_id", "").strip()

        # --- Required fields ---
        if not book_title or not normalized_isbn or not publication_year_input or not author_id_input:
            message = "Please fill in title, ISBN, publication year, and choose an author."
            return render_template(
                "add_book.html",
                message=message,
                authors=authors,
                current_year=current_year
            )

        # --- Cast to int ---
        try:
            publication_year = int(publication_year_input)
            author_id = int(author_id_input)
        except ValueError:
            message = "Publication year and author must be valid numbers."
            return render_template(
                "add_book.html",
                message=message,
                authors=authors,
                current_year=current_year
            )

        # --- Validate year range ---
        if publication_year < 0 or publication_year > current_year:
            message = f"Publication year must be between 0 and {current_year}."
            return render_template(
                "add_book.html",
                message=message,
                authors=authors,
                current_year=current_year
            )

        # --- Validate digits of ISBN ---
        if len(normalized_isbn) not in (10, 13):
            message = "ISBN must be 10 or 13 digits."
            return render_template(
                "add_book.html",
                message=message,
                authors=authors,
                current_year=current_year
            )

        # --- Create and persist
        new_book = Book(
            title=book_title,
            isbn=normalized_isbn,
            publication_year=publication_year,
            author_id=author_id,
            summary=fetch_summary_by_isbn(normalized_isbn)
        )

        db.session.add(new_book)

        try:
            db.session.commit()
            message = f"Book '{new_book.title}' was added successfully ✅"
        except IntegrityError:
            db.session.rollback()
            message = "This ISBN already exists. Please use a unique ISBN."
        except Exception:
            db.session.rollback()
            message = "Something went wrong while adding the book."

    return render_template(
        "add_book.html",
        message=message,
        authors=authors,
        current_year=current_year
    )


@app.route("/sort/<sort_key>")
def sort_books(sort_key):
    """
    Redirect helper to keep sort and search parameters unified.
    """
    search_query = request.args.get("q", "").strip()
    return redirect(url_for("home", sort=sort_key, q=search_query))

@app.route("/book/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    """
    Delete a book. If the book's author has no remaining books,
    the author is removed as well.
    """
    book = Book.query.get_or_404(book_id)
    author = book.author
    deleted_book_title = book.title

    try:
        db.session.delete(book)
        db.session.flush()                      # Apply deletion before counting remaining books.

        remaining_books_count = Book.query.filter_by(author_id=author.id).count()
        if remaining_books_count == 0:
            db.session.delete(author)

        db.session.commit()
        flash(f"Book '{deleted_book_title}' was deleted successfully ♻️", "success")
    except Exception:
        db.session.rollback()
        flash("Something went wrong while deleting the book.", "error")

    return redirect(url_for("home"))

@app.route("/author/<int:author_id>/delete", methods=["POST"])
def delete_author(author_id):
    """
    Delete an author and all related books (cascade delete).
    """
    author = Author.query.get_or_404(author_id)
    author_name = author.name

    try:
        db.session.delete(author)
        db.session.commit()
        flash(f"Author '{author_name}' and all related books were deleted successfully ♻️", "success")
    except Exception:
        db.session.rollback()
        flash("Something went wrong while deleting the author.", "error")

    return redirect(
        url_for(
            "home",
            sort=request.args.get("sort", "title"),
            q=request.args.get("q", "")
        )
    )

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

    app.run(host="0.0.0.0", port=5050, debug=True)