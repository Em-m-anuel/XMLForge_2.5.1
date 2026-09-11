"""Application externe minimale — client XMLForge (Phase 7).

Communique uniquement avec le serveur TCP (localhost:3307). N'accède jamais
directement aux fichiers XML.

Usage :
    python examples/python_client_demo.py [host] [port] [user] [password]
"""

import os
import sys

# Permet d'importer le package `xmlforge` depuis la racine du dépôt.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xmlforge import connect


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 3307
    user = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("XMLFORGE_TCP_USER")
    password = sys.argv[4] if len(sys.argv) > 4 else os.environ.get("XMLFORGE_TCP_PASSWORD")
    if not user or not password:
        print("Fournissez les credentials TCP : XMLFORGE_TCP_USER / XMLFORGE_TCP_PASSWORD "
              "ou les arguments user/password.")
        return 1

    with connect(host=host, port=port, user=user, password=password) as db:
        print(f"Connecté en tant que {db.username} (session {db.session_token[:8]}…)")

        db.execute("USE Bibliotheque")
        print(f"Base sélectionnée : {db.database_name}")

        try:
            db.execute("DROP TABLE books")
        except Exception:
            pass  # première exécution : table absente
        db.execute("CREATE TABLE books (id INT PRIMARY KEY AUTO_INCREMENT NOT NULL, title VARCHAR(200) NOT NULL)")
        db.execute("INSERT INTO books (title) VALUES ('Dune'), ('Fondation')")
        result = db.query("SELECT * FROM books ORDER BY id")
        print("SELECT :", result.rows)

        db.execute("UPDATE books SET title = 'Dune (édition 2026)' WHERE id = 1")
        db.execute("DELETE FROM books WHERE id = 2")

        # Transaction avec ROLLBACK : les modifications sont annulées.
        db.execute("BEGIN")
        db.execute("INSERT INTO books (title) VALUES ('Temporaire')")
        db.execute("ROLLBACK")

        # Transaction avec COMMIT : les modifications persistent.
        db.execute("BEGIN")
        db.execute("INSERT INTO books (title) VALUES ('Permanente')")
        db.execute("COMMIT")

        print("Après transactions :", db.query("SELECT * FROM books ORDER BY id").rows)

    print("Connexion fermée proprement.")


if __name__ == "__main__":
    raise SystemExit(main())
