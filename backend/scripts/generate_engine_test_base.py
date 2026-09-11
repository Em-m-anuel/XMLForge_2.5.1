"""Génère la base XML de test du moteur : backend/bibliotheque_engine_test.xml.

Base déterministe (graine fixe) et réaliste pour tester sérieusement le moteur
XML natif : plusieurs centaines de lignes, PK, FK, UNIQUE, NULL, DEFAULT,
AUTO_INCREMENT, nombres, chaînes, dates et booléens. Aucune donnée personnelle
réelle : noms, titres et e-mails sont fictifs.

Usage :
    cd backend
    python scripts/generate_engine_test_base.py
"""

import os
import random
import sys
import uuid as uuid_lib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.xml_engine.document import serialize_document  # noqa: E402

rng = random.Random(20260828)

FIRST_NAMES = ["Ali", "Marie", "Paul", "Nina", "Omar", "Lina", "Hugo", "Emma", "Yann", "Sara",
               "Théo", "Aya", "Luc", "Ines", "Marc", "Chloé", "Rida", "Zoé", "Ivan", "Rose"]
LAST_NAMES = ["Dubois", "Martin", "Bernard", "Petit", "Durand", "Leroy", "Moreau", "Simon",
              "Laurent", "Lefebvre", "Roux", "Fournier", "Girard", "Bonnet", "Dupont", "Lambert"]

CATEGORIES = ["Roman", "Science-fiction", "Histoire", "Technique", "Poésie", "Biographie",
              "Jeunesse", "Policier", "Essai", "Fantasy"]
LANGUAGES = ["fr", "en", "es", "de"]
CITIES = ["Breda", "Paris", "Lyon", "Bruxelles", "Genève", "Montréal", "Tunis", "Dakar", None]


def _col(name, ctype, nullable=True, primary_key=False, foreign_key=False, references=None,
         unique=False, auto_increment=False, default=None, on_delete="NO ACTION"):
    return {
        "uuid": str(uuid_lib.uuid4()), "name": name, "type": ctype, "length": "-",
        "nullable": nullable, "primary_key": primary_key, "foreign_key": foreign_key or bool(references),
        "references": references, "on_delete": on_delete, "on_update": "NO ACTION",
        "unique": unique, "auto_increment": auto_increment, "index": False,
        "default": default, "comment": "", "status": "ACTIVE",
    }


def _row(data):
    return {"uuid": str(uuid_lib.uuid4()), "data": {k: (str(v) if v is not None else None) for k, v in data.items()}}


def _table(name, columns, rows):
    return {
        "uuid": str(uuid_lib.uuid4()), "name": name, "description": "", "comment": "",
        "protected": False, "file_identifier": None, "status": "ACTIVE",
        "constraints": [], "indexes": [], "columns": columns, "rows": rows,
    }


def build_document():
    # ------------------------------------------------------------- authors (30)
    authors = []
    author_names = []
    for i in range(1, 31):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        name = f"{first} {last}"
        while name in author_names:
            name = f"{first} {last} {rng.randint(2, 99)}"
        author_names.append(name)
        authors.append(_row({
            "id": i, "name": name,
            "birth_year": rng.choice([rng.randint(1900, 1990), None]),
            "country": rng.choice(["FR", "BE", "CA", "TN", "SN", "CH", None]),
            "deceased": rng.choice([True, False, False, False]),
        }))

    # ----------------------------------------------------------- categories (10)
    categories = [_row({"id": i, "name": CATEGORIES[i - 1]}) for i in range(1, 11)]

    # -------------------------------------------------------------- users (120)
    users = []
    emails = set()
    for i in range(1, 121):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        email = f"user{i:03d}@example.test"
        emails.add(email)
        users.append(_row({
            "id": i, "fullname": f"{first} {last}", "email": email,
            "city": rng.choice(CITIES),
            "birth_date": rng.choice([f"{rng.randint(1950, 2005)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}", None]),
            "active": rng.choice([True, True, True, False]),
        }))

    # -------------------------------------------------------------- books (400)
    books = []
    isbns = set()
    for i in range(1, 401):
        isbn = f"978-2-{rng.randint(100000, 999999):06d}-{rng.randint(10, 99):02d}"
        while isbn in isbns:
            isbn = f"978-2-{rng.randint(100000, 999999):06d}-{rng.randint(10, 99):02d}"
        isbns.add(isbn)
        books.append(_row({
            "id": i,
            "title": f"Titre {i:03d} — {rng.choice(CATEGORIES)}",
            "author_id": rng.randint(1, 30),
            "category_id": rng.choice([rng.randint(1, 10), None]),
            "isbn": rng.choice([isbn, None]),
            "price": round(rng.uniform(5.0, 60.0), 2),
            "stock": rng.randint(0, 25),
            "published_date": f"{rng.randint(1950, 2025)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "language": rng.choice(LANGUAGES),
            "available": rng.choice([True, True, False]),
        }))

    # -------------------------------------------------------------- loans (300)
    loans = []
    for i in range(1, 301):
        loan_year = rng.randint(2020, 2025)
        loan_month = rng.randint(1, 12)
        loan_day = rng.randint(1, 28)
        returned = rng.choice([True, False])
        return_date = None
        if returned:
            return_date = f"{loan_year + (1 if loan_month == 12 else 0)}-{(loan_month % 12) + 1:02d}-{rng.randint(1, 28):02d}"
        loans.append(_row({
            "id": i,
            "book_id": rng.randint(1, 400),
            "user_id": rng.randint(1, 120),
            "loan_date": f"{loan_year}-{loan_month:02d}-{loan_day:02d}",
            "return_date": return_date,
            "status": "returned" if returned else "active",
        }))

    return {
        "uuid": str(uuid_lib.uuid4()), "name": "bibliotheque_engine_test", "description": "Base de test du moteur XML natif",
        "comment": "Données fictives générées (aucune donnée personnelle réelle)", "status": "ACTIVE",
        "scope": "PERSONAL", "version": 1, "generator": "XMLForge", "created_at": "2026-08-28T00:00:00",
        "author": "scripts/generate_engine_test_base.py",
        "tables": [
            _table("authors", [
                _col("id", "INT", nullable=False, primary_key=True, auto_increment=True),
                _col("name", "VARCHAR", nullable=False, unique=True),
                _col("birth_year", "INT", nullable=True),
                _col("country", "VARCHAR", nullable=True),
                _col("deceased", "BOOLEAN", nullable=True, default="false"),
            ], authors),
            _table("categories", [
                _col("id", "INT", nullable=False, primary_key=True, auto_increment=True),
                _col("name", "VARCHAR", nullable=False, unique=True),
            ], categories),
            _table("users", [
                _col("id", "INT", nullable=False, primary_key=True, auto_increment=True),
                _col("fullname", "VARCHAR", nullable=False),
                _col("email", "VARCHAR", nullable=False, unique=True),
                _col("city", "VARCHAR", nullable=True),
                _col("birth_date", "DATE", nullable=True),
                _col("active", "BOOLEAN", nullable=True, default="true"),
            ], users),
            _table("books", [
                _col("id", "INT", nullable=False, primary_key=True, auto_increment=True),
                _col("title", "VARCHAR", nullable=False),
                _col("author_id", "INT", nullable=False, foreign_key=True, references="authors.id", on_delete="RESTRICT"),
                _col("category_id", "INT", nullable=True, foreign_key=True, references="categories.id", on_delete="SET NULL"),
                _col("isbn", "VARCHAR", nullable=True, unique=True),
                _col("price", "REAL", nullable=True),
                _col("stock", "INT", nullable=True, default="0"),
                _col("published_date", "DATE", nullable=True),
                _col("language", "VARCHAR", nullable=True, default="fr"),
                _col("available", "BOOLEAN", nullable=True, default="true"),
            ], books),
            _table("loans", [
                _col("id", "INT", nullable=False, primary_key=True, auto_increment=True),
                _col("book_id", "INT", nullable=False, foreign_key=True, references="books.id", on_delete="RESTRICT"),
                _col("user_id", "INT", nullable=False, foreign_key=True, references="users.id", on_delete="RESTRICT"),
                _col("loan_date", "DATE", nullable=False),
                _col("return_date", "DATE", nullable=True),
                _col("status", "VARCHAR", nullable=True, default="active"),
            ], loans),
        ],
    }


def main():
    target = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bibliotheque_engine_test.xml")
    document = build_document()
    xml_content = serialize_document(document)
    with open(target, "w", encoding="utf-8") as stream:
        stream.write(xml_content)
    total_rows = sum(len(t["rows"]) for t in document["tables"])
    print(f"OK -> {target}")
    print(f"     tables: {[t['name'] for t in document['tables']]}")
    print(f"     lignes totales: {total_rows}")


if __name__ == "__main__":
    main()
