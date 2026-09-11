# XMLForge TCP Protocol V5

## Framing

Chaque message est encodé ainsi :

```text
[type: unsigned byte][JSON length: unsigned uint32 big-endian][JSON UTF-8]
```

La longueur ne contient que le JSON. Le serveur limite le buffer d'une connexion à 8 MiB.

## Types de message

| Constante | Code | Direction | Payload principal |
|---|---:|---|---|
| `MSG_AUTH` | 1 | client → serveur | `username`, `password`, `database?` |
| `MSG_QUERY` | 2 | client → serveur | `session_token`, `query`, `expected_version?`, `table_key?` |
| `MSG_RESPONSE` | 3 | serveur → client | `status`, données |
| `MSG_ERROR` | 4 | serveur → client | `code`, `message` |
| `MSG_PING` | 5 | client → serveur | `{}` |
| `MSG_PONG` | 6 | serveur → client | `{}` |
| `MSG_SELECT_DATABASE` | 7 | client → serveur | `session_token`, `database` |
| `MSG_UNLOCK_TABLE` | 8 | client → serveur | `session_token`, `table`, `key` |
| `MSG_CLOSE` | 9 | client → serveur | `session_token` |

## Status de réponse

| Constante | Code |
|---|---:|
| `AUTH_SUCCESS` | 0 |
| `AUTH_FAILED` | 1 |
| `QUERY_SUCCESS` | 2 |
| `QUERY_ERROR` | 3 |
| `SESSION_EXPIRED` | 4 |
| `INVALID_REQUEST` | 5 |

Une erreur est toujours un `MSG_ERROR` avec au minimum :

```json
{"code": 3, "message": "Permission write refusée sur la table ..."}
```

Les credentials AUTH sont les credentials TCP bcrypt, pas le mot de passe JWT. La base est sélectionnée uniquement après validation ACL. Chaque QUERY revalide l'utilisateur et ses permissions.

## Sous-ensemble SQL QUERY

SELECT, INSERT, UPDATE, DELETE. WHERE prend en charge AND/OR, parenthèses, comparaisons, LIKE, IN, IS NULL. SELECT prend en charge ORDER BY, LIMIT et OFFSET. UPDATE et DELETE sans WHERE sont refusés.

Les constructions non supportées produisent `MSG_ERROR/QUERY_ERROR`; le serveur ne retourne jamais un succès simulé.
