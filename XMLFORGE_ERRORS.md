# XMLForge — Erreurs

## Structure TCP (MSG_ERROR)

```json
{"code": 3, "message": "Table active introuvable", "error_code": "TABLE_NOT_FOUND"}
```

- `code` : code de protocole numérique (`QUERY_ERROR=3`, `AUTH_FAILED=1`,
  `SESSION_EXPIRED=4`, `INVALID_REQUEST=5`) — rétrocompatible ;
- `error_code` : code métier XMLForge (Phase 7) ;
- `message` : description lisible.

## Codes métier (`error_code`)

| Code | Origine |
|---|---|
| `AUTH_FAILED` | credentials TCP invalides |
| `ACCESS_DENIED` | permission refusée (PERSONAL/COMMON, owner, grants) |
| `DATABASE_NOT_FOUND` | base introuvable |
| `TABLE_NOT_FOUND` | table introuvable |
| `COLUMN_NOT_FOUND` | colonne introuvable |
| `DATABASE_NOT_SELECTED` | requête sans `USE` préalable |
| `SYNTAX_ERROR` | SQL invalide (parseur) |
| `INVALID_QUERY` | XML/SQL sémantiquement invalide |
| `DATA_INVALID` | valeur de type invalide |
| `CONSTRAINT_VIOLATION` | PK/FK/UNIQUE/NOT NULL/CHECK |
| `CONFLICT` | conflit de version optimiste (`expected_version`) |
| `TRANSACTION_ACTIVE` | `BEGIN` alors qu'une transaction est active |
| `TRANSACTION_NOT_ACTIVE` | `COMMIT`/`ROLLBACK` sans transaction |
| `TRANSACTION_ERROR` | échec de restauration au rollback |
| `INTERNAL_ERROR` | erreur interne |

## REST

REST conserve son format existant (`{success, message, errors:{code, details}}`)
avec les codes HTTP usuels (400, 401, 403, 404, 409, 500) et les codes métier
`XMLForgeError` (ex. `FORBIDDEN`, `NOT_FOUND`, `SYNC_CONFLICT`,
`CONSTRAINT_VIOLATION`). Les deux surfaces partagent les **mêmes exceptions**
métier : un seul système d'erreurs.
