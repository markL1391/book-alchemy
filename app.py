from flask import Flask, request, render_template, redirect, url_for
import os
from sqlalchemy.exc import IntegrityError
from data_models import db, Author, Book
from datetime import datetime


app = Flask(__name__)

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
            return render_template("add_book.html", message=message, authors=authors)

        new_book = Book(
            title=title,
            isbn=isbn,
            publication_year=publication_year,
            author_id=author_id
        )

        db.session.add(new_book)

        try:
            db.session.commit()
            message = f"Book '{new_book.title}' was added successfully ✅"
        except IntegrityError:
            db.session.rollback()
            message = "This ISBN already exists. Please use a unique ISBN."
    return render_template("add_book.html", message=message, authors=authors)

@app.route("/sort/<sort_key>")
def sort_books(sort_key):
    # At least title and author.
    q = request.args.get("q", "").strip()
    return redirect(url_for("home", sort=sort_key, q=q))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(debug=True)