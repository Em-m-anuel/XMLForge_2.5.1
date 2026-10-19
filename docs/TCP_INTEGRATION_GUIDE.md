# XMLForge — Guide d'intégration TCP externe (port 3307)

**Version :** 5.0.0 — Protocole V5  
**Source de vérité :** `backend/app/tcp/tcp_protocol.py`, `tcp_server.py`, `xmlforge_client.py`, `xmlforge/connection.py`, `xmlforge/protocol.py`, `xmlforge/result.py`, `xmlforge/errors.py`, `TCP_PROTOCOL.md`, `TCP_SERVER_README.md`, `app/query/sql_parser.py`, `app/query/xml_query_service.py`, `tests/test_tcp.py`, `tests/test_phase7.py`, `tests/e2e/test_tcp_security_permissions_e2e.py`

> Ce document est basé UNIQUEMENT sur le code réel. Aucun champ inventé. Si une info n'est pas déterminable → `Non documenté / à vérifier dans l'implémentation`.

---

## 1. Introduction

### Qu'est-ce que le serveur TCP XMLForge ?

XMLForge est un SGBD relationnel **100% XML** (pas de SQLite). Il expose deux transports vers le **même moteur** :

- **API REST** (Flask, `:5000`, JWT) — utilisée par le frontend React
- **Serveur TCP** (`:3307`) — connexion directe binaire JSON pour applications externes

Les deux utilisent :
- `PermissionService` (PERSONAL/COMMON, VIEW/EDIT/MANAGE/ADMIN, owner)
- `XmlQueryService` → `XmlNativeEngine` (lecture/écriture directe sur document XML canonique)
- `UnlockService` (tables protégées, session 24h, clear on logout)
- `AuditService`

### Pourquoi TCP ?

- Latence plus faible que HTTP
- Session stateful (base courante, transaction)
- Pas de JWT, mais credentials TCP bcrypt dédiés
- Idéal pour ETL, scripts, IoT, intégration d'apps Python/Java/C#/Node

### Différences REST vs TCP

| Aspect | REST | TCP |
|---|---|---|
| Port | 5000 (HTTP) | 3307 (binaire) |
| Auth | JWT Bearer `access_token` | `tcp_username`/`tcp_password` bcrypt |
| Session | stateless (JWT) | stateful (`session_token` uuid4) |
| Base courante | param `database_id` par requête | `USE` ou `MSG_SELECT_DATABASE` stocké en session |
| Transactions | Non supporté REST (lève `ValidationFailed` pour BEGIN/COMMIT/ROLLBACK) | Supporté via session (`BEGIN`/`COMMIT`/`ROLLBACK`) |
| Framing | HTTP JSON | `[type:1][len:4 BE][JSON]` |

---

## 2. Architecture TCP

```
Application externe (Python / Node / Java / C# / ...)
        |
        | socket TCP 127.0.0.1:3307 (ou <IP>:3307)
        v
+-------------------------------+
| XMLForge TCPServer :3307      |
|  - bind 0.0.0.0:3307 synchrone|
|  - backlog 64                 |
|  - thread par client (daemon) |
|  - buffer max 8 MiB / conn    |
|  - accept timeout 1s          |
|  - client recv timeout 2s     |
+-------------------------------+
        |
        +--> Authentification
        |     - TcpCredentialService.authenticate(username,password)
        |     - bcrypt check, user.is_active, credential.is_active
        |     - credentials créés via REST POST /api/tcp/credentials
        |
        +--> Session (ClientSession)
        |     - token uuid4, user_id, username, database_id/name
        |     - created_at, last_activity, timeout 30 min (configurable)
        |     - transaction_active, snapshot {xml,catalog}
        |     - stockée dans dict self.sessions, lock RLock
        |
        +--> PermissionService
        |     - accessible_databases(user_id), can_database(user_id, db, "read"/"ddl"/"admin")
        |     - can_table(user_id, table_id, "read"/"write"/"ddl"/"delete")
        |     - PERSONAL : owner only + grants, COMMON : tous actifs + common_permission
        |
        +--> XmlQueryService.execute_sql(database_id, user_id, sql, provided_key, expected_version)
        |     - parse_sql_statement(sql) → {operation, ...}
        |     - _run_read / _run_write / _run_ddl
        |     - XmlNativeEngine(document) → select/insert/update/delete/ddl
        |     - mutate atomique via XmlDataPlane.mutate (version +1, ConflictError si expected_version stale)
        |
        +--> XML storage / XML engine
              - Control Plane : security.xml (users, roles, tcp_credentials), catalog.xml (databases), history.xml
              - Data Plane : data/xml/{database_id}.xml (document canonique)
              - storage.snapshot() / restore() pour transactions
```

---

## 3. Connexion

### Adresse / Port

- **Défaut :** `127.0.0.1:3307` ou `localhost:3307`
- **Config serveur :** `TCP_HOST` (défaut `0.0.0.0`), `TCP_PORT` (défaut `3307`), `TCP_ENABLED` (défaut `true`), `TCP_SESSION_TIMEOUT_MINUTES` (défaut 30)
- **Bind actuel :** `socket.bind((host,port))` synchrone avant `running=True`, `SO_REUSEADDR=1`, `listen(64)`, `settimeout(1)` sur socket d'écoute
- **Client timeout :** `client.settimeout(2)` côté serveur (recv), côté client officiel `XMLForgeClient` timeout 30s défaut, `xmlforge.Connection` timeout 10s défaut

### Réseau local

Si `TCP_HOST=0.0.0.0`, toute interface est bindée → `<IP_XMLFORGE>:3307` accessible depuis LAN si firewall autorise.  
Si `TCP_HOST=127.0.0.1`, seulement loopback.  
**Non documenté / à vérifier** : firewall Windows popup ports 5000/3307 en packaging, pas de TLS natif (doc recommande VPN/SSH/tunnel).

### Étapes avant requête

1. Ouvrir socket TCP
2. Envoyer `MSG_AUTH` (type 1)
3. Recevoir `MSG_RESPONSE` status `AUTH_SUCCESS` (0) avec `session_token`
4. Optionnel : `USE <db>` ou `MSG_SELECT_DATABASE` (si pas de database à l'auth)
5. Envoyer `MSG_QUERY` (type 2) avec `session_token` + `query`
6. Recevoir `MSG_RESPONSE` `QUERY_SUCCESS` ou `MSG_ERROR`

### Timeout / Fermeture / Reconnexion

- **Expiration session :** `ClientSession.is_expired()` → `utcnow - last_activity > timeout_minutes`. Purge dans `_run` loop `except socket.timeout: self._purge_expired()` et à chaque `_session()` lookup
- **Fermeture propre :** Envoyer `MSG_CLOSE` (type 9) avec `session_token`, attendre `MSG_RESPONSE {closed:True}`, puis `socket.close()`. Serveur supprime session dans `with self.lock: self.sessions.pop(token)`
- **Fermeture socket :** Si client coupe sans CLOSE, `client.recv` retourne vide → `break`, `finally: client.close()` + `self.sessions.pop(token)` pour tous `connection_tokens`
- **Reconnexion :** Nouvelle session = `UnlockService.clear_user_unlocks(user_id)` → protections remises à zéro. Il faut re-`USE` base et re-`unlock_table` si nécessaire.

---

## 4. Protocole de Framing — CRITIQUE

**Implémentation réelle :** `tcp_protocol.py:pack_message` et `xmlforge/protocol.py:pack_message`

```text
[type: 1 octet unsigned][length: 4 octets big-endian][JSON UTF-8]
```
- `length` = taille JSON seul, pas du header
- JSON encodé UTF-8, pas de compression
- Limite serveur : `if len(buffer) > 8*1024*1024: error INVALID_REQUEST "Message trop volumineux"`
- Découpage TCP : le client peut recevoir partiellement → boucler jusqu'à avoir 5 octets header, puis `length`, puis payload complet

**Pack :**
```python
json_data = json.dumps(data).encode('utf-8')
message = struct.pack('!I', len(json_data)) + json_data
return struct.pack('!B', msg_type) + message
```

**Unpack :**
```python
msg_type = unpack('!B', data[:1])[0]
length = unpack('!I', data[1:5])[0]
if len(data) < 5+length: raise ValueError("Message incomplet")
json_data = data[5:5+length].decode('utf-8')
data_dict = json.loads(json_data)
return msg_type, data_dict, 5+length
```

---

## 5. Types de messages

| Constante | Code | Direction | Payload principal (réel) |
|---|---|---:|---|
| `MSG_AUTH` | 1 | C→S | `username`, `password`, `database?` (str id ou name) |
| `MSG_QUERY` | 2 | C→S | `session_token`, `query`, `expected_version?`, `table_key?`, `engine?` |
| `MSG_RESPONSE` | 3 | S→C | `status`, données |
| `MSG_ERROR` | 4 | S→C | `code`, `message`, `error_code?` |
| `MSG_PING` | 5 | C→S | `{}` |
| `MSG_PONG` | 6 | S→C | `{}` |
| `MSG_SELECT_DATABASE` | 7 | C→S | `session_token`, `database` (id ou name) |
| `MSG_UNLOCK_TABLE` | 8 | C→S | `session_token`, `table` (id ou name), `key` |
| `MSG_CLOSE` | 9 | C→S | `session_token` |

**Codes status réponse (`MSG_RESPONSE.status`) :**
- `AUTH_SUCCESS` 0
- `AUTH_FAILED` 1
- `QUERY_SUCCESS` 2
- `QUERY_ERROR` 3
- `SESSION_EXPIRED` 4
- `INVALID_REQUEST` 5

---

## 6. Authentification

### Credentials TCP vs JWT

- REST utilise JWT (`/login` → `access_token`)
- TCP utilise **credentials dédiés** stockés dans `security.xml` → `tcp_credentials` : `user_id`, `tcp_username`, `tcp_password` (hash bcrypt), `tcp_host`, `tcp_port`, `is_active`
- **Création via REST :** `POST /api/tcp/credentials` JWT requis, payload `{tcp_username?, tcp_password?, tcp_host?, tcp_port?}`. Si `tcp_username` absent → email user, si `tcp_password` absent → `secrets.token_urlsafe(16)`. Retourne `{credential:{...}, plain_password}` une seule fois.
- **Vérification :** `TcpCredentialService.authenticate(tcp_username, plain_password)` → check `credential.is_active`, `user.is_active`, `bcrypt.check_password_hash`
- **Unicité :** `tcp_username` unique global, 1 credential par user

### Requête AUTH

Client → Serveur :
```json
{
  "username": "guest-tcp",
  "password": "guest-tcp-password",
  "database": "12" // optionnel : id ou name, peut être absent
}
```
Encodé : `pack_message(MSG_AUTH=1, data)`

### Réponse AUTH succès

Serveur → Client `MSG_RESPONSE` :
```json
{
  "status": 0,
  "session_token": "uuid4",
  "user_id": 2,
  "username": "guest@example.com",
  "full_name": "Guest",
  "expires_in_seconds": 1800,
  "database_id": 12,
  "database_name": "common_tcp"
}
```
Si `database` non fournie à l'auth, `database_id/name` absents → il faut `USE` après.

### Erreurs AUTH

`MSG_ERROR` :
```json
{"code": 1, "message": "Credentials TCP invalides", "error_code": "AUTH_FAILED"}
{"code": 1, "message": "Base introuvable ou non autorisée"}
{"code": 1, "message": "Nom de base ambigu; utilisez database_id"}
```
`code` = `AUTH_FAILED` (1). `error_code` métier optionnel.

**Sécurité :** Mot de passe Flask principal **non accepté** comme mot de passe TCP. ACL base vérifiée dès l'auth si database fournie : `PermissionService.accessible_databases` + `can_database(...,"read")`.

---

## 7. Session

### Structure `ClientSession`

```python
address, token uuid4, user_id, username, database_id, database_name,
created_at utcnow, last_activity utcnow, authenticated bool,
timeout_minutes 30,
transaction_active bool, transaction_snapshot {xml,catalog}, transaction_path {xml,catalog}
```

### Gestion

- `update_activity()` à chaque message valide (sauf PING ? code appelle pour tous sauf AUTH/PING)
- `is_expired()` → `utcnow - last_activity > timedelta(minutes=timeout)`
- Stockée dans `self.sessions[token]` avec `RLock`
- Supprimée sur `MSG_CLOSE`, fermeture socket, expiration, ou `clear_user_unlocks` à la prochaine auth (reconnexion = nouvelle session protection)

### Sélection base après auth

**Option A : SQL `USE`**

Client envoie `MSG_QUERY` avec `query="USE bank"` (ou `USE 12`). Serveur dans `_handle_query` :

```python
if operation == "use":
    error = _select_database_for_session(session, statement["database"])
    if error: return error QUERY_ERROR
    return RESPONSE QUERY_SUCCESS {engine:xml, result:{database_id, database_name}}
```

`_select_database_for_session` :
- Si selector int ou digit string → `_database(int(selector))` direct
- Sinon → filtre `accessible_databases(user_id)` où `d.name == selector`
- Garde seulement ceux où `can_database(user_id,d,"read")`
- Si 0 → "Base introuvable ou non autorisée"
- Si >1 → "Nom de base ambigu; utilisez database_id"
- Sinon set `session.database_id/name`

**Option B : Message `MSG_SELECT_DATABASE` (type 7)**

```json
{"session_token": "...", "database": "bank" }
```
Réponse :
```json
{"status":2, "database_id":12, "database_name":"bank"}
```
Erreur : `MSG_ERROR code 3` message.

Les deux sont équivalents, `USE` est plus simple depuis client Python officiel (`conn.use("bank")` fait `execute("USE bank")`).

---

## 8. Requêtes / Réponses

### Requête QUERY (type 2)

```json
{
  "session_token": "uuid4",
  "query": "SELECT * FROM accounts ORDER BY id",
  "expected_version": 5, // optionnel, pour optimistic concurrency
  "table_key": "TABLE-SECRET", // optionnel, clé pour table protégée
  "engine": "xml" // optionnel, serveur ignore et force xml
}
```

- `expected_version` = `database.document_version` (int). Si fourni, `XmlDataPlane.mutate` vérifie version disque sous verrou, lève `ConflictError` si stale → TCP retourne `error_code CONFLICT`
- `table_key` = `file_identifier` / clé protection. Transmis comme `provided_key` à `XmlQueryService`. Pour table protégée, sans clé → `PermissionDenied` → `ACCESS_DENIED`

### Réponse QUERY succès

`MSG_RESPONSE` status `QUERY_SUCCESS` (2) :

```json
{
  "status": 2,
  "engine": "xml",
  "result": { ... },
  "metrics": {"engine":"xml","total_ms":12.3,"parse_ms":0.5,"exec_ms":...,"read_ms":...,"write_ms":...,"rows":...}
}
```

`result` dépend de l'opération (voir § SQL supporté).

### Unlock Table (type 8)

Pour table avec `is_protected=True` :

```json
{"session_token":"...", "table":"protected_items", "key":"TCP-TABLE-SECRET"}
```
`table` peut être id ou name, résolu via `resolve_table(database_id, selector)`.

Réponse :
```json
{"status":2, "unlocked":true, "table_id":5}
```
Erreur si clé fausse → `MSG_ERROR code 3` message.

Après unlock, `UnlockService.unlock_table` crée session personnelle 24h (ou jusqu'à `clear_user_unlocks`). Lecture OK, écriture nécessite unlock.

### Close (type 9)

```json
{"session_token":"..."}
```
Réponse :
```json
{"status":2, "closed":true}
```
Puis serveur ferme thread (return) et supprime session. Client doit fermer socket après.

### Ping/Pong (type 5/6)

Client → `MSG_PING {}` → Serveur → `MSG_PONG {}`. Utilisé dans `XMLForgeClient.ping()`.

---

## 9. SQL supporté — Réel depuis `sql_parser.py` et `xml_query_service.py`

**Parser :** `parse_sql_statement(sql)` lève `ValidationFailed` si non supporté.

Opérations supportées :

- `SELECT` : `SELECT [DISTINCT] col, * , t.col AS alias, COUNT(*), SUM(col), AVG, MIN, MAX FROM table [AS alias] [INNER JOIN | LEFT JOIN | LEFT OUTER JOIN table ON cond] [WHERE cond] [GROUP BY cols] [HAVING cond] [ORDER BY col [ASC/DESC], ...] [LIMIT n] [OFFSET n]`
  - WHERE : `AND/OR`, parenthèses, `= != <> < <= > >=`, `LIKE`, `NOT LIKE`, `IN`, `NOT IN`, `IS NULL`, `IS NOT NULL`, `BETWEEN`, colonnes qualifiées `t.col`, littéraux
  - JOIN : `INNER JOIN`, `LEFT JOIN`, `LEFT OUTER JOIN` avec `ON` (égalité colonne). `RIGHT JOIN` **non supporté** → ValidationFailed
  - Agrégats : `COUNT(*)/COUNT(col)`, `SUM`, `AVG`, `MIN`, `MAX` avec `GROUP BY` / `HAVING`
  - `SELECT *` → toutes colonnes
  - `LIMIT` max 500 (clamp `max(1,min(limit,500))`), `OFFSET` >=0
  - `UPDATE`/`DELETE` sans WHERE **refusés** par moteur XML (`"UPDATE sans WHERE est refusé par sécurité"`)

- `INSERT` : `INSERT INTO table [(col,...)] VALUES (val,...), (val,...)` — une ou plusieurs lignes, colonnes implicites = ordre schéma si `columns` absent
  - Types coercés via `coerce_literal` : INT, REAL, BOOLEAN (`TRUE/FALSE`), TEXT, DATE (`YYYY-MM-DD`), DATETIME, TIME, NULL
  - `AUTO_INCREMENT` : si valeur NULL/absente → compteur persistant `next_auto_increment` dans XML
  - Contraintes : PK, UNIQUE, NOT NULL, FK existence, DEFAULT, `CURRENT_TIMESTAMP`

- `UPDATE` : `UPDATE table SET col=val,... WHERE cond` — WHERE obligatoire

- `DELETE` : `DELETE FROM table WHERE cond` — WHERE obligatoire, gère `ON DELETE CASCADE/SET NULL/RESTRICT`

- `DDL` :
  - `CREATE TABLE table (col def,...)` avec `INT/VARCHAR(...)/TEXT/BOOLEAN/DATE/DATETIME/FLOAT/DECIMAL`, `PRIMARY KEY`, `AUTO_INCREMENT`, `NOT NULL`, `UNIQUE`, `INDEX`, `DEFAULT`, `REFERENCES table.col [ON DELETE/UPDATE CASCADE|SET NULL|RESTRICT]`, `COMMENT`
  - `DROP TABLE table`
  - `ALTER TABLE table ADD COLUMN col_def`, `DROP COLUMN name`, `MODIFY COLUMN col_def`, `RENAME TO new_name`
  - `CREATE [UNIQUE] INDEX name ON table (col,...)`, `DROP INDEX name [ON table]`

- `Session` (TCP uniquement, REST lève ValidationFailed) :
  - `USE database` (name ou id) → sélection base courante
  - `CREATE DATABASE name` → crée PERSONAL via `DatabaseService.create`
  - `DROP DATABASE name` → nécessite `can_database admin`
  - `BEGIN` / `START TRANSACTION`, `COMMIT`, `ROLLBACK` → transactions (voir §10)

**Non supporté :** `RIGHT JOIN`, `FULL JOIN`, sous-requêtes, `UNION`, `CREATE VIEW`, etc → `ValidationFailed` → `SYNTAX_ERROR` / `INVALID_QUERY`.

### Exemples de résultats

**SELECT :**
```json
{
  "rows": [{"id":1,"name":"A","balance":100}, ...],
  "total": 3,
  "limit": 100,
  "offset": 0,
  "pagination": {"page":1,"page_size":100,"total":3,"total_pages":1,"current_page":1}
}
```
Client officiel `xmlforge` mappe vers `Result.rows`, `Result.columns = list(rows[0].keys())`, `Result.row_count = total`.

**INSERT :**
```json
{"inserted":1, "row": {"uuid":"...","data":{"id":1,"name":"C"}, "internal_id":...}}
{"inserted":3} // multi-lignes
```
`Result.affected_rows = inserted`, `last_insert_id = row.data.id`.

**UPDATE :** `{"updated":1}` → `affected_rows`

**DELETE :** `{"deleted":1}`

**CREATE/DROP TABLE :** `{"created":"table"}`, `{"dropped":"table"}`, `{"added":"col","table":"t"}`

**USE :** `{"database_id":12,"database_name":"bank"}`

**Transactions :** `{"transaction":"BEGIN"}` etc.

---

## 10. Transactions

### Implémentation réelle

`TCPServer._tx_begin/_commit/_rollback` — **uniquement TCP**, pas REST.

- **BEGIN :**
  - Vérifie `database_id` sélectionné, sinon `QUERY_ERROR "Aucune base sélectionnée"`
  - Si `transaction_active` déjà → `error_code TRANSACTION_ACTIVE`
  - Snapshot : `store.snapshot(xml_path)` + `store.snapshot(catalog_path)` (document XML base + catalog version/checksum)
  - `transaction_path = {xml: path, catalog: path}`, `transaction_active=True`
  - Retourne `RESULT {transaction:BEGIN}`

- **COMMIT :**
  - Si pas active → `TRANSACTION_NOT_ACTIVE`
  - Clear snapshot/path, `transaction_active=False`
  - Audit `TRANSACTION_COMMIT`
  - Retourne `COMMIT`

- **ROLLBACK :**
  - Si pas active → `TRANSACTION_NOT_ACTIVE`
  - `store.restore(xml_path, snapshot_xml)` + `restore(catalog_path, snapshot_catalog)` → restaure fichiers depuis snapshot
  - Si restore échoue → `TRANSACTION_ERROR`
  - Clear flags, audit `TRANSACTION_ROLLBACK`
  - Retourne `ROLLBACK`

### Isolation

- Pas de MVCC : les writes sont immédiats sur fichier XML via `mutate` (verrou fichier `database_lock`), même pendant transaction ouverte
- **Isolation de session :** `transaction_active` est par session, pas global. `c1 BEGIN; UPDATE` → `c2` voit le changement (write immédiat), mais `c2 COMMIT` → `TRANSACTION_NOT_ACTIVE` (isolation de session, test `test_tcp_sessions_are_isolated`)
- ROLLBACK restaure snapshot pris au BEGIN, annule toutes modifs de la session depuis BEGIN (y compris celles vues par autres sessions — comportement documenté, pas d'isolation multi-version)
- Concurrence : `database_lock` + `expected_version` optimistic → `ConflictError` si version stale

### Usage client officiel

```python
from xmlforge import connect
conn = connect(host="127.0.0.1", port=3307, user="owner-tcp", password="tcp-secret")
conn.use("bank")
conn.execute("BEGIN")
conn.execute("INSERT INTO accounts (name,balance) VALUES ('D',999)")
conn.execute("UPDATE accounts SET balance=0 WHERE name='A'")
conn.execute("ROLLBACK") # ou COMMIT
```

---

## 11. Permissions — Réutilisation PermissionService

TCP réutilise **exactement** REST :

- `accessible_databases(user_id, include_archived=False)` + `can_database(user_id, db, "read"/"ddl"/"admin")` pour USE/SELECT_DATABASE et CREATE/DROP DATABASE
- `can_table(user_id, table_id, "read"/"write"/"ddl"/"delete")` pour SELECT/INSERT/UPDATE/DELETE/DDL
- `UnlockService.check_protection(user_id, table, provided_key)` pour tables protégées (`is_protected`, `file_identifier` = clé)
- `UnlockService.clear_user_unlocks(user_id)` à chaque AUTH → nouvelle session protection vierge
- Scope PERSONAL/COMMON : COMMON visible par tous actifs selon `common_permission` VIEW/EDIT/MANAGE, PERSONAL owner + grants via `/databases/{id}/permissions`

Si permission manquante → `PermissionDenied` → TCP `MSG_ERROR code QUERY_ERROR` + `error_code ACCESS_DENIED`.

---

## 12. Gestion des erreurs

### Format erreur TCP

`MSG_ERROR` (type 4) :

```json
{
  "code": 3,
  "message": "Permission write refusée sur la table ...",
  "error_code": "ACCESS_DENIED"
}
```
- `code` : numérique protocole (0-5) stable rétrocompatible
- `error_code` : métier XMLForge (ajouté sans casser clients)
- `message` : texte humain

### Mapping `_business_error_code`

Dans `tcp_server.py:_business_error_code(exc)` :

- `PermissionDenied` → `ACCESS_DENIED`
- `ConflictError` → `CONFLICT`
- `ConstraintViolation` → `CONSTRAINT_VIOLATION`
- `DataValidationError` → `DATA_INVALID`
- `NotFoundError` : si "Colonne" → `COLUMN_NOT_FOUND`, si "Table" → `TABLE_NOT_FOUND`, sinon `DATABASE_NOT_FOUND`
- `XmlValidationError` → `INVALID_QUERY`
- `ValidationFailed` → `SYNTAX_ERROR`
- `StorageError` → `INTERNAL_ERROR`
- Défaut → `INTERNAL_ERROR`

Autres codes métier exposés :
- `DATABASE_NOT_SELECTED` (pas de base sélectionnée)
- `TRANSACTION_ACTIVE` / `TRANSACTION_NOT_ACTIVE` / `TRANSACTION_ERROR`
- `AUTH_FAILED`, `SESSION_EXPIRED`, `AUTH_REQUIRED`, `CONNECTION_ERROR` (client officiel `xmlforge/errors.py`)

### Client officiel lève `XmlforgeError`

```python
from xmlforge.errors import XmlforgeError
try:
    conn.execute("SELECT * FROM ghost")
except XmlforgeError as e:
    print(e.code) # TABLE_NOT_FOUND
    print(e.numeric_code) # 3
    print(e.message)
```

Ancien client `backend/app/tcp/xmlforge_client.py` lève `ConnectionError` ou `RuntimeError` avec message, pas `XmlforgeError`.

---

## 13. Fermeture propre

**Client doit :**
1. Envoyer `MSG_CLOSE` avec `session_token`
2. Attendre `MSG_RESPONSE {closed:True}`
3. `socket.close()`

Serveur :
- `_process_message` si `MSG_CLOSE` → `pop(session.token)` + réponse + `close=True` → thread `_handle_client` return → `finally: client.close()` + cleanup `connection_tokens`
- Si socket fermée sans CLOSE → `recv` vide → break → cleanup

**Exemple ancien client :**
```python
def disconnect(self):
    if self.socket:
        try:
            if self.session_token:
                self.socket.sendall(TCPProtocol.create_close(self.session_token))
        except: pass
        self.socket.close()
```

**Nouveau client :**
```python
def close(self):
    if self._sock:
        try:
            if self.session_token:
                self._send(protocol.close_request(self.session_token))
        except OSError: pass
        self._sock.close()
    self._sock=None; self.session_token=None
```

---

## 14. Client Python officiel

Deux implémentations dans le repo (même protocole) :

### A. `xmlforge` package (recommandé, Phase 7)

`xmlforge/__init__.py`, `client.py`, `connection.py`, `protocol.py`, `result.py`, `errors.py`

```python
from xmlforge import connect
from xmlforge.errors import XmlforgeError

# Connexion
conn = connect(host="127.0.0.1", port=3307, user="owner-tcp", password="tcp-secret", database="bank", timeout=10)
# ou
# conn = connect(...); conn.use("bank")

# SELECT
r = conn.query("SELECT * FROM accounts ORDER BY id")
print(r.columns) # ["id","name","balance"]
print(r.row_count) # total sans LIMIT
print(r.rows) # [{"id":1,...}]
print(r.raw) # dict brut

# INSERT/UPDATE/DELETE
ins = conn.execute("INSERT INTO accounts (name,balance) VALUES ('C',0)")
print(ins.affected_rows, ins.last_insert_id)

# DDL
conn.execute("CREATE TABLE t (id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL)")

# Transactions
conn.execute("BEGIN")
conn.execute("UPDATE accounts SET balance=777 WHERE name='B'")
conn.execute("COMMIT") # ou ROLLBACK

# Context manager
with connect(...) as db:
    db.use("bank")
    db.query("SELECT COUNT(*) FROM accounts")

conn.close()
```

`Result` champs : `raw`, `operation`, `columns`, `rows`, `row_count`, `affected_rows`, `last_insert_id`, `metadata` (database_id, created, dropped, transaction, etc).

### B. `backend/app/tcp/xmlforge_client.py` (ancien, helpers CRUD)

```python
from app.tcp import XMLForgeClient, connect

client = XMLForgeClient(host='localhost', port=3307, timeout=30)
client.connect(username='user@example.com', password='tcp-pass', database='12')
client.insert('users', {'name':'John','email':'john@example.com'})
rows = client.select('users', columns='*', where="status='active'")
client.update('users', {'status':'active'}, where="email='john@example.com'")
client.delete('users', where="email='john@example.com'")
client.select_database(15)
client.unlock_table('protected_table', 'TABLE-SECRET')
client.ping()
client.disconnect()
```

Retourne `int` (affected) ou `list[dict]`. Lève `ConnectionError`/`RuntimeError`.

---

## 15. Implémenter un client dans un autre langage

### Principe général (indépendant du langage)

1. Ouvrir socket TCP vers `host:3307`
2. Implémenter `pack_message(type, dict)` : `[B type][I BE len][json utf8]`
3. Implémenter `unpack_message` avec boucle recv jusqu'à 5 octets, puis payload
4. Envoyer AUTH (1) avec `username`, `password`, `database?`
5. Boucler recv jusqu'à message complet, vérifier `MSG_RESPONSE status 0` + `session_token`
6. Envoyer QUERY (2) avec `session_token` + `query` + optionnels
7. Recevoir `MSG_RESPONSE` ou `MSG_ERROR`, parser `error_code`
8. Envoyer CLOSE (9) puis fermer socket

**Limites :** buffer 8 MiB, recv timeout serveur 2s (client doit gérer retry), session 30 min.

### Exemple Node.js (pseudo-code réel)

```js
const net = require('net');
function pack(type, obj) {
  const json = Buffer.from(JSON.stringify(obj), 'utf8');
  const buf = Buffer.alloc(1+4+json.length);
  buf.writeUInt8(type,0);
  buf.writeUInt32BE(json.length,1);
  json.copy(buf,5);
  return buf;
}
function unpack(data) {
  if (data.length<5) throw new Error('short');
  const type = data.readUInt8(0);
  const len = data.readUInt32BE(1);
  if (data.length<5+len) throw new Error('incomplete');
  const obj = JSON.parse(data.slice(5,5+len).toString('utf8'));
  return [type,obj,5+len];
}
const sock = net.createConnection(3307,'127.0.0.1');
let buffer=Buffer.alloc(0);
sock.on('data', chunk=>{
  buffer=Buffer.concat([buffer,chunk]);
  while(buffer.length>=5){
    const len=buffer.readUInt32BE(1);
    if(buffer.length<5+len) break;
    const [type,obj,consumed]=unpack(buffer);
    buffer=buffer.slice(consumed);
    console.log(type,obj);
  }
});
sock.write(pack(1,{username:'guest-tcp',password:'guest-tcp-password',database:'12'}));
// après AUTH_SUCCESS, sock.write(pack(2,{session_token:token,query:'SELECT * FROM items'}));
```

### Exemple Java (extrait)

```java
Socket s = new Socket("127.0.0.1",3307);
DataOutputStream out = new DataOutputStream(s.getOutputStream());
DataInputStream in = new DataInputStream(s.getInputStream());
byte[] json = "{\"username\":\"guest-tcp\",\"password\":\"...\"}".getBytes("UTF-8");
out.writeByte(1);
out.writeInt(json.length);
out.write(json);
// lire 1+4 puis json
int type = in.readUnsignedByte();
int len = in.readInt();
byte[] payload = new byte[len];
in.readFully(payload);
JSONObject obj = new JSONObject(new String(payload,"UTF-8"));
```

### Exemple C# (.NET)

```csharp
var client = new TcpClient("127.0.0.1",3307);
var stream = client.GetStream();
byte[] Pack(byte type, string json) {
  var j = Encoding.UTF8.GetBytes(json);
  var buf = new byte[1+4+j.Length];
  buf[0]=type;
  BitConverter.GetBytes(IPAddress.HostToNetworkOrder(j.Length)).CopyTo(buf,1);
  j.CopyTo(buf,5);
  return buf;
}
// envoyer AUTH, puis lire header 5 octets en boucle
```

**Non documenté / à vérifier :** TLS non implémenté, pas de compression, pas de batch multi-requêtes dans une trame (une trame = une requête, mais buffer peut contenir plusieurs trames → boucle `while len(buffer)>=5` côté serveur).

---

## 16. Configuration

```env
TCP_ENABLED=true
TCP_HOST=0.0.0.0
TCP_PORT=3307
TCP_SESSION_TIMEOUT_MINUTES=30
```

- `TCP_HOST` `0.0.0.0` → bind toutes interfaces, `127.0.0.1` → loopback only
- `TCP_PORT` peut être 0 en tests → port aléatoire `getsockname()[1]`
- `TCP_SESSION_TIMEOUT_MINUTES` → `ClientSession.timeout_minutes`
- Backlog `listen(64)`, thread daemon `xmlforge-tcp`, thread par client daemon
- `XMLFORGE_DATA_DIR`, `CONTROL_STORAGE_FOLDER`, etc. gèrent chemins XML, pas TCP

---

## 17. Logs et erreurs

- Serveur log `logger.exception("Erreur accept TCP")` et `Erreur client TCP %s`
- Audit : `AuditService.log(action="TCP_QUERY", element_type="base", element_name=database_name, meta={operation, engine:xml})` et `TRANSACTION_COMMIT/ROLLBACK`
- Erreurs métier toujours `MSG_ERROR`, jamais succès simulé (principe `fail-closed`)
- Tests vérifient `error_code` : `test_tcp_errors_have_business_codes`, `test_tcp_security_permissions_e2e`

---

## 18. Intégration dans une app externe — Checklist

1. Créer credentials TCP via REST : `POST /api/tcp/credentials` avec JWT user → récupérer `tcp_username` + `plain_password` (une seule fois)
2. Ouvrir socket TCP, implémenter framing `[1][4 BE][JSON]`
3. AUTH avec `username= tcp_username`, `password= plain_password`, `database= id ou name`
4. Gérer `AUTH_FAILED` / `DATABASE_NOT_FOUND` / ambigu
5. Si table protégée → `MSG_UNLOCK_TABLE` avec `key`
6. Exécuter `SELECT/INSERT/UPDATE/DELETE/CREATE TABLE/DROP TABLE/ALTER TABLE/BEGIN/COMMIT/ROLLBACK/USE/CREATE DATABASE/DROP DATABASE` via `MSG_QUERY`
7. Gérer `expected_version` pour éviter `CONFLICT` (récupérer `document_version` via REST `GET /databases/{id}` ou via `Result.metadata`)
8. Parser `Result` : `rows`, `total`, `inserted/updated/deleted`, `transaction`
9. Gérer erreurs `ACCESS_DENIED`, `CONSTRAINT_VIOLATION`, `TABLE_NOT_FOUND`, `DATABASE_NOT_SELECTED`, etc.
10. Fermer proprement avec `CLOSE`
11. En prod : ne pas exposer 3307 sur Internet sans VPN/TLS

---

## 19. Limitations et non documenté

- **TLS :** Non implémenté, `Non documenté / à vérifier dans l'implémentation` si besoin TLS → utiliser stunnel/VPN
- **Batch :** Une requête par trame, pas de pipeline multi-requêtes atomique hors transaction
- **Isolation transaction :** Pas de MVCC, writes visibles immédiatement par autres sessions avant COMMIT (voir §10)
- **Engine param :** Accepté dans `create_query_request` mais serveur force `engine=xml` (doc dit `sqlite` défaut dans ancien client, mais code réel force xml)
- **Permissions fines :** `can_table` vérifié à chaque requête, mais pas de `row-level` security
- **Timeout client recv :** Serveur 2s, mais si requête longue (gros SELECT) → `Non documenté / à vérifier` si timeout augmente
- **Max payload :** 8 MiB buffer par connexion, au-delà → `INVALID_REQUEST "Message trop volumineux"` + fermeture
- **PING/PONG :** Existe mais pas utilisé par nouveau client `xmlforge`

---

## 20. Références code

- `backend/app/tcp/tcp_protocol.py` : framing, types, codes, `create_*`
- `backend/app/tcp/tcp_server.py` : `TCPServer`, `ClientSession`, `_handle_client`, `_process_message`, `_handle_auth`, `_select_database_for_session`, `_handle_query`, `_tx_begin/commit/rollback`, `_handle_unlock`, `_purge_expired`, `get_sessions_info`
- `backend/app/tcp/xmlforge_client.py` : ancien client avec helpers `select/insert/update/delete/select_database/unlock_table/ping`
- `xmlforge/connection.py` : nouveau client officiel `Connection`, `connect`, `Result`, `XmlforgeError`
- `xmlforge/protocol.py` : `pack_message`, `auth_request`, `query_request`, `close_request`
- `app/query/sql_parser.py` : `parse_sql_statement` → operations supportées
- `app/query/xml_query_service.py` : `execute_sql` → `_run_read/_write/_ddl`
- `TCP_PROTOCOL.md` + `TCP_SERVER_README.md` : doc existante framing
- Tests : `test_tcp.py`, `test_phase7.py`, `e2e/test_tcp_security_permissions_e2e.py`

---

**Fin guide — Protocole TCP XMLForge V5, port 3307, framing `[type:1][len:4 BE][JSON]`, session uuid4, permissions identiques REST, moteur XML natif.**
