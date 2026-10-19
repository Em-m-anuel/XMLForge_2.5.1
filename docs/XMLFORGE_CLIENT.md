# XMLForge — Client Python

Package `xmlforge/` (racine du dépôt), standard library uniquement (socket, json,
struct). Le client ne parle **que** au serveur TCP :3307.

## Installation

```python
import sys
sys.path.insert(0, "/chemin/vers/XMLForge")   # ou PYTHONPATH=XMLForge
from xmlforge import connect
```

## API

```python
from xmlforge import connect, XmlforgeError

db = connect(host="localhost", port=3307, user="demo-tcp", password="...")

db.execute("USE Bibliotheque")          # sélectionne la base courante
result = db.query("SELECT * FROM books ORDER BY id")
result.columns                         # ['id', 'title', ...]
result.rows                            # [{'id': 1, 'title': ...}, ...]
result.row_count                       # total (indépendant de LIMIT)
result.affected_rows                   # INSERT/UPDATE/DELETE
result.last_insert_id                  # INSERT (AUTO_INCREMENT)
result.metadata                        # DDL / USE / transactions

db.execute("INSERT INTO books (title) VALUES ('Dune')")
db.execute("BEGIN") ... db.execute("COMMIT") / db.execute("ROLLBACK")
db.close()
```

Gestionnaire de contexte :

```python
with connect(...) as db:
    db.execute("USE Bibliotheque")
    print(db.query("SELECT COUNT(*) FROM books").rows)
```

## Résultats

| Champ | SELECT | INSERT | UPDATE/DELETE | DDL/USE/transaction |
|---|---|---|---|---|
| `columns` | ✅ | — | — | — |
| `rows` | ✅ | — | — | — |
| `row_count` | ✅ (total) | — | — | — |
| `affected_rows` | — | ✅ | ✅ | — |
| `last_insert_id` | — | ✅ | — | — |
| `metadata` | pagination… | — | — | ✅ |

## Erreurs

Toute erreur lève `xmlforge.errors.XmlforgeError` avec :

- `.message` : description ;
- `.code` : code métier (ex. `TABLE_NOT_FOUND`, `ACCESS_DENIED`, `AUTH_FAILED`) ;
- `.numeric_code` : code de protocole numérique.

Exemple complet : `examples/python_client_demo.py`.
