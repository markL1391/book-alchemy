from flask import Flask, request, render_template
from flask_sqlalchemy import SQLAlchemy
import os
from data_models import db, Author, Book

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'data/library.sqlite')}"
db.init_app(app)


with app.app_context():
  db.create_all()

@app.route("/")
def home():
    books = Book.query.order_by(Book.title).all()
    return render_template("home.html", books=books)

@app.route("/add_author", methods=["GET", "POST"])
def add_author():
    success_message = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        birth_date = request.form.get("birth_date", "").strip()
        date_of_death = request.form.get("date_of_death", "").strip()

        if not name or not birth_date:
            success_message = "Please fill in at least name and birth date."
            return render_template("add_author.html", message=success_message)

        new_author = Author(
            name=name,
            birth_date=birth_date,
            date_of_death=date_of_death if date_of_death else None
        )

        db.session.add(new_author)
        db.session.commit()

        success_message = f"Author '{new_author.name}' was added successfully ✅"

    return render_template("add_author.html", message=success_message)

@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    success_message = None

    # Authors for loading dropdown.
    authors = Author.query.order_by(Author.name).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        isbn = request.form.get("isbn", "").strip()
        publication_year = request.form.get("publication_year", "").strip()
        author_id = request.form.get("author_id", "").strip()

        if not title or not isbn or not author_id:
            success_message = "Please fill in title, ISBN, and choose an author."
            return render_template("add_book.html", message=success_message, authors=authors)

        new_book = Book(
            title=title,
            isbn=isbn,
            publication_year=publication_year,
            author_id = int(author_id)
        )

        db.session.add(new_book)
        db.session.commit()

        success_message = f"Book '{new_book.title}' was added successfully ✅"

    return render_template("add_book.html", message=success_message, authors=authors)



if __name__ == "__main__":
    app.run(debug=True)