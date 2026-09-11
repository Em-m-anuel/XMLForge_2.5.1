# XMLForge Backend — XML-only (V5)

Backend Flask de gestion de données avec **XML comme unique source de vérité** :
Control Plane et Data Plane sont stockés exclusivement en fichiers XML.

> SQLite, SQLAlchemy, Flask-SQLAlchemy, la projection SQLite et les modèles ORM
> ont été **retirés du runtime** (Phase 6J-B). Aucun fichier `.db`/`.sqlite`
> n'est créé ni requis.

## Architecture

```
Frontend (React)
    │ REST
Services XMLForge
    ├── Control Plane (XML) : security.xml, catalog.xml, history.xml, audit/YYYY-MM.xml
    └── Data Plane   (XML) : data/xml/<id>_<slug>.xml (tables/colonnes/lignes)
    │
XML Native Engine (SELECT/INSERT/UPDATE/DELETE/DDL/index/agrégats/JOIN)
    │
XML Storage (verrous, écriture atomique, version, checksum, snapshot/rollback)
```

TCP (port **3307**) et REST utilisent les mêmes services et les mêmes règles de
permission.

## Fonctionnalités

- Auth JWT + bcrypt, rôles `admin`/`user`, `token_version`, logout ;
- bases `PERSONAL`/`COMMON` (accès collectif `VIEW`/`EDIT`/`MANAGE`), owner, ACL base/table ;
- tables/colonnes/lignes, protection et unlock individuel (mémoire) ;
- contraintes PK/FK/UNIQUE/NOT NULL/DEFAULT/AUTO_INCREMENT/INDEX, NULL ;
- SELECT (WHERE/AND/OR/LIKE/IN/BETWEEN, ORDER BY, LIMIT/OFFSET, agrégats, GROUP BY/HAVING, JOIN) ;
- DDL : CREATE TABLE, ALTER (ADD/MODIFY/DROP COLUMN, RENAME), CREATE/DROP INDEX, DROP TABLE ;
- import/export XML/SQL (convertisseurs sans SQLite) ;
- audit mensuel rotatif (`audit/YYYY-MM.xml`, compression gzip, rétention `AUDIT_RETENTION_MONTHS`) ;
- historique avec before/after ;
- verrous, versions et conflits optimistes (`expected_version` → 409), checksum SHA-256.

## Installation vierge (aucun SQLite)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

flask --app run.py xml-bootstrap   # crée security.xml (rôles admin/user), catalog.xml, history.xml
flask --app run.py create-admin    # premier compte administrateur (prompt email/nom/mot de passe)
python run.py                       # REST sur :5000, TCP sur :3307
```

## Configuration (`.env`)

```env
CONTROL_BACKEND=xml
DATA_BACKEND=xml
QUERY_BACKEND=xml
SYNC_SQLITE_PROJECTION=false   # compat historique — toujours false (projection retirée)
CONTROL_STORAGE_FOLDER=        # défaut backend/data/control
XML_STORAGE_FOLDER=            # défaut backend/data/xml
AUDIT_RETENTION_MONTHS=24
AUDIT_COMPRESS_OLD_MONTHS=true
COMMON_PERMISSION_DEFAULT=VIEW
TCP_PORT=3307
```

## Tests

```bash
pytest -q          # suite backend (325 tests)
```

Frontend : `cd xmlforge-react && npm ci && npm test` (tests unitaires) ; le test
d'intégration réel est lancé avec `VITE_API_URL=http://localhost:5000/api
XMLFORGE_LIVE_E2E=1 npx vitest run src/test/liveBackend.test.js`.

## Documentation

- protocole TCP : `TCP_PROTOCOL.md`, `TCP_SERVER_README.md`
- moteur XML : `XML_ENGINE.md`
- API REST : `API_DOCUMENTATION.md`
- rapports de migration : `PHASE_6J_FINAL_XML_ARCHITECTURE_REPORT.md` (racine du dépôt)
