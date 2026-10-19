# XMLForge — Serveur de base de données (Phase 7)

XMLForge est un **serveur de base de données relationnelle** dont le stockage est
**100 % XML**. Une application externe s'y connecte via **TCP :3307** (ou REST)
sans jamais accéder aux fichiers XML.

## Architecture

```
Applications externes
    ↓ XMLForge Client (xmlforge/)
    ↓ TCP :3307
XMLForge Server
    ├── TCP Server → Sessions → Authentification/Permissions
    ├── SQL Parser → Query Executor → XmlQueryService
    └── XML Native Engine → XML Storage (locks / atomic write / version / checksum)

Control Plane XML : security.xml · catalog.xml · history.xml · audit/YYYY-MM.xml
Data Plane XML     : data/xml/<id>_<slug>.xml
```

REST et TCP utilisent **les mêmes services** (`XmlQueryService`,
`PermissionService`, `XmlDataPlane`) : il n'existe qu'un seul moteur SQL.

## Démarrage

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && cp .env.example .env

flask --app run.py xml-bootstrap   # crée security.xml (rôles admin/user), catalog.xml, history.xml
flask --app run.py create-admin    # premier administrateur
python run.py                      # REST :5000, TCP :3307
```

## Configuration (`.env`)

```env
CONTROL_BACKEND=xml
DATA_BACKEND=xml
QUERY_BACKEND=xml
SYNC_SQLITE_PROJECTION=false
CONTROL_STORAGE_FOLDER=     # défaut backend/data/control
XML_STORAGE_FOLDER=         # défaut backend/data/xml
AUDIT_RETENTION_MONTHS=24
AUDIT_COMPRESS_OLD_MONTHS=true
COMMON_PERMISSION_DEFAULT=VIEW
TCP_PORT=3307
TCP_SESSION_TIMEOUT_MINUTES=30
```

**Aucun SQLite, SQLAlchemy ou fichier `.db` n'est créé ni requis.**

## Client

```python
from xmlforge import connect

with connect(host="localhost", port=3307, user="demo-tcp", password="...") as db:
    db.execute("USE Bibliotheque")
    result = db.query("SELECT * FROM books ORDER BY id")
    for row in result.rows:
        print(row)
```

Voir `XMLFORGE_CLIENT.md` et `examples/python_client_demo.py`.
