# XMLForge — Protocole TCP (port 3307)

Protocole binaire simple, **rétrocompatible** avec les clients existants.

## Trame

```
[type:1 octet][longueur:4 octets big-endian][JSON UTF-8]
```

## Types de message

| Constante | Valeur | Sens |
|---|---|---|
| `MSG_AUTH` | 1 | authentification (username/password[/database]) |
| `MSG_QUERY` | 2 | instruction SQL (SELECT/INSERT/UPDATE/DELETE/DDL/USE/BEGIN/COMMIT/ROLLBACK) |
| `MSG_RESPONSE` | 3 | réponse (payload `status` + résultat) |
| `MSG_ERROR` | 4 | erreur (`code`, `message`, `error_code?`) |
| `MSG_PING` / `MSG_PONG` | 5 / 6 | keepalive |
| `MSG_SELECT_DATABASE` | 7 | sélection de base (équivaut à `USE`) |
| `MSG_UNLOCK_TABLE` | 8 | déverrouillage d'une table protégée |
| `MSG_CLOSE` | 9 | fermeture de session |

## Codes de réponse

| Constante | Valeur |
|---|---|
| `AUTH_SUCCESS` | 0 |
| `AUTH_FAILED` | 1 |
| `QUERY_SUCCESS` | 2 |
| `QUERY_ERROR` | 3 |
| `SESSION_EXPIRED` | 4 |
| `INVALID_REQUEST` | 5 |

## Flux logique

```
Client → TCP CONNECT
       → AUTH {username, password[, database]}
       ← RESPONSE {status: 0, session_token, user_id, username, expires_in_seconds}
       → QUERY "USE Bibliotheque"
       ← RESPONSE {status: 2, result: {database_id, database_name}}
       → QUERY "SELECT * FROM books"
       ← RESPONSE {status: 2, result: {rows, total, pagination}, metrics}
       → QUERY "BEGIN" / mutations / "COMMIT" ou "ROLLBACK"
       → CLOSE
       ← RESPONSE {status: 2, closed: true}
```

## Erreurs

Message `MSG_ERROR` :

```json
{"code": 3, "message": "Table active introuvable", "error_code": "TABLE_NOT_FOUND"}
```

- `code` : code numérique du protocole (stable) ;
- `error_code` : code métier XMLForge (ajout Phase 7, additif) ;
- `message` : description lisible.

Voir `XMLFORGE_ERRORS.md` pour la liste des codes métier.
