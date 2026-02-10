from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Author(db.Model):
    """
    Author model storing basic life dates and related books.
    """
    __tablename__ = 'authors'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    date_of_death = db.Column(db.Date, nullable=True)

    books = db.relationship(
        "Book",
        backref="author",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"Author(id = {self.id}, name = {self.name})"

    def __str__(self):
        return f"{self.name}"

class Book(db.Model):
    """
    Book model storing ISBN, title, year, optional summary, and author link.
    """
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    isbn = db.Column(db.String(20), nullable=False, unique=True)
    title = db.Column(db.String(100), nullable=False)
    publication_year = db.Column(db.Integer, nullable=False)

    summary = db.Column(db.Text, nullable=True)

    author_id = db.Column(db.Integer, db.ForeignKey("authors.id"), nullable=False)

    def __repr__(self):
        return f"<Book id={self.id} title='{self.title}'>"

    def __str__(self):
        return f"{self.title} ({self.publication_year})" if self.publication_year else self.title
