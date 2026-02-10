from flask import Flask, request, render_template, redirect, url_for, flash
import os
from sqlalchemy.exc import IntegrityError
from data_models import db, Author, Book
from datetime import datetime
import requests

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "BookAlchemy/1.0 (academic project)",
    "Accept": "application/json",
})

app = Flask(__name__)
app.secret_key = "dev-secret-key"

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'data/library.sqlite')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

def parse_date(date_str: str):
    """
    Expects 'YYYY-MM-DD' from HTML <input type="date">
    Returns datetime.date or None.
    """
    date_str = (date_str or "").strip()
    if not date_str:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d").date()

def fetch_summary_by_isbn(isbn: str) -> str | None:
    isbn = (isbn or "").replace("-", "").strip()
    if not isbn:
        return None

    def extract_description(obj) -> str | None:
        desc = obj.get("description")
        if isinstance(desc, str) and desc.strip():
            return desc.strip()
        if isinstance(desc, dict):
            val = (desc.get("value") or "").strip()
            return val if val else None
        return None

    ed_url = f"https://openlibrary.org/isbn/{isbn}.json"
    r = SESSION.get(ed_url, timeout=8)

    print("ED STATUS:", r.status_code, "URL:", ed_url)
    if r.status_code != 200:
        print("ED BODY:", r.text[:200])
        return None

    edition = r.json()
    print("ED KEYS:", list(edition.keys())[:15])

    desc = extract_description(edition)
    print("ED DESC:", (desc[:80] + "...") if desc else None)
    if desc:
        return desc

    works = edition.get("works") or []
    print("ED WORKS:", works)

    if works and isinstance(works, list) and "key" in works[0]:
        work_key = works[0]["key"]
        w_url = f"https://openlibrary.org{work_key}.json"
        wr = SESSION.get(w_url, timeout=8)

        print("WORK STATUS:", wr.status_code, "URL:", w_url)
        if wr.status_code != 200:
            print("WORK BODY:", wr.text[:200])
            return None

        work = wr.json()
        print("WORK KEYS:", list(work.keys())[:15])

        wdesc = extract_description(work)
        print("WORK DESC:", (wdesc[:80] + "...") if wdesc else None)
        return wdesc

    return None

def create_app():
    return app

@app.route("/")
def home():
    q = request.args.get("q", "").strip()
    sort_key = request.args.get("sort", "title").strip()

    base_query = Book.query.join(Author)

    if q:
        like = f"%{q}%"
        base_query = base_query.filter(
            (Book.title.ilike(like)) | (Author.name.ilike(like))
        )

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
    message = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        birth_date_str = request.form.get("birth_date", "").strip()
        date_of_death_str = request.form.get("date_of_death", "").strip()

        if not name or not birth_date_str:
            message = "Please fill in at least name and birth date."
            return render_template("add_author.html", message=message)

        birth_date = parse_date(birth_date_str)
        date_of_death = parse_date(date_of_death_str)

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
    message = None

    # Authors for loading dropdown.
    authors = Author.query.order_by(Author.name.asc()).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        isbn = request.form.get("isbn", "").strip()
        publication_year_str = request.form.get("publication_year", "").strip()
        author_id_str = request.form.get("author_id", "").strip()

        if not title or not isbn or not publication_year_str or not author_id_str:
            message = "Please fill in title, ISBN, publication year, and choose an author."
            return render_template("add_book.html", message=message, authors=authors)

        try:
            publication_year = int(publication_year_str)
            author_id = int(author_id_str)
        except ValueError:
            message = "Publication year and author must be valid numbers."
            return render_template("add_book.html", message=message, authors=authors, current_year=datetime.now().year)

        current_year = datetime.now().year
        if publication_year < 0 or publication_year > current_year:
            message = f"Publication year must be between 0 and {current_year}."
            return render_template("add_book.html", message=message, authors=authors, current_year=current_year)

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

    return render_template("add_book.html", message=message, authors=authors, current_year=datetime.now().year)


@app.route("/sort/<sort_key>")
def sort_books(sort_key):
    # At least title and author.
    q = request.args.get("q", "").strip()
    return redirect(url_for("home", sort=sort_key, q=q))

@app.route("/book/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    book = Book.query.get_or_404((book_id))
    author = book.author

    db.session.delete(book)
    db.session.commit()

    if Book.query.filter_by(author_id=author.id).count() == 0:
        db.session.delete(author)
        db.session.commit()

    flash(f"Book '{book.title}' was deleted successfully ♻️", "success")
    return redirect(url_for("home"))

@app.route("/book/<int:book_id>")
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template("book_detail.html", book=book)

def extract_summary(data: dict) -> str | None:
    desc = data.get("description")

    if isinstance(desc, str):
        return desc.strip()

    if isinstance(desc, dict):
        return desc.get("value", "").strip()

    return None


@app.route("/author/<int:author_id>")
def author_detail(author_id):
    author = Author.query.get_or_404(author_id)
    return render_template("author_detail.html", author=author)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)