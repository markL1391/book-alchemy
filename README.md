# 📚 BookAlchemy

BookAlchemy is a personal digital library built with **Flask** and **SQLAlchemy**.  
It allows users to manage authors and books, explore details, and automatically fetch book summaries from the Open Library API using ISBNs.

---

## ✨ Features

- Add authors with birth and death dates
- Add books with ISBN, publication year, and author
- Automatic book summary fetching via **Open Library API**
- Search books by title or author
- Sort books by title or author
- Book detail pages with summaries
- Author detail pages with all related books
- Delete books (authors are removed automatically if orphaned)
- Clean, modern, card-based UI

---

## 🛠 Tech Stack

- **Python 3**
- **Flask**
- **Flask-SQLAlchemy**
- **SQLite**
- **Jinja2**
- **Open Library API**

---

## 📂 Project Structure
```bash
book-alchemy/
│
├── app.py
├── data_models.py
├── data/
│ └── library.sqlite
│
├── templates/
│ ├── base.html
│ ├── home.html
│ ├── add_book.html
│ ├── add_author.html
│ ├── book_detail.html
│ └── author_detail.html
│
├── README.md
└── requirements.txt
```

---

## 🚀 Setup & Run

### 1. Clone repository
```bash
git clone https://github.com/your-username/book-alchemy.git
```
```bash
cd book-alchemy
```

### 2. Create virtual environment
```bash
python -m venv .venv
```
```bash
source .venv/bin/activate   # macOS / Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run application
```bash
python app.py
```

Open browser at:

👉
```http://127.0.0.1:5000```

---

## 🌐 Open Library API

Book summaries are fetched automatically using the Open Library API:

- Edition endpoint: ```bash /isbn/{isbn}.json```
- Fallback to work endpoint if no summary is found

To comply with Open Library guidelines, requests include a custom User-Agent header.

---

## 🧠 Data Model

### Author

- id
- name
- birth_date
- date_of_death
- books (cascade delete)

### Book

- id
- title
- isbn (unique)
- publication_year
- summary
- author_id

---

## ♻️ Deletion Logic

- Deleting a book automatically removes its author if no other books exist
- Implemented via SQLAlchemy cascade delete and runtime checks

---

## 📌 Notes

- This project is intended as an academic / learning project
- UI focus: calm, minimal, readable
- Error handling and validation included for user input

---

## 🙌 Credits

- Data provided by Open Library
- Built with Flask & SQLAlchemy