# XMLForge TCP/IP V5

Le serveur TCP est un transport binaire vers le même `QueryService`, le même système de permissions et le même pipeline XML/SQLite que REST.

## Protocole

```text
[type: uint8][longueur JSON: uint32 big-endian][JSON UTF-8]
```

| Code | Message |
|---:|---|
| 1 | AUTH |
| 2 | QUERY |
| 3 | RESPONSE |
| 4 | ERROR |
| 5/6 | PING/PONG |
| 7 | SELECT_DATABASE |
| 8 | UNLOCK_TABLE |
| 9 | CLOSE |

## Authentification

Créer/régénérer un credential avec `/api/tcp/credentials`. AUTH reçoit `username`, `password`, et `database` optionnelle (nom non ambigu ou ID). Le serveur vérifie `TcpCredential` bcrypt, le compte actif et l’ACL de la base. Le mot de passe principal Flask n’est pas accepté comme mot de passe TCP.

Une session contient token, user ID, base ID, dates et timeout. Elle est supprimée à CLOSE, fermeture socket ou expiration. Les droits sont revérifiés à chaque requête.

## Client Python

```python
from app.tcp import XMLForgeClient

client = XMLForgeClient("127.0.0.1", 3307)
client.connect("tcp-user@example.com", "tcp-secret", database="12")

client.insert("customers", {"email": "nyx@example.com", "active": True})
rows = client.select("customers", where="active=TRUE")
client.update("customers", {"active": False}, where="email='nyx@example.com'")
client.delete("customers", where="email='nyx@example.com'")

client.select_database(15)
client.unlock_table("protected_table", "TABLE-SECRET")
client.disconnect()
```

SELECT, INSERT, UPDATE et DELETE sont réels. Ils écrivent le XML canonique, valident et reconstruisent la projection SQLite avant succès.

Sous-ensemble SQL exact : voir `BACKEND_DOCUMENTATION.md`. UPDATE/DELETE sans WHERE et les constructions non prises en charge sont refusés au lieu d’être simulés.

## Configuration

```env
TCP_ENABLED=true
TCP_HOST=0.0.0.0
TCP_PORT=3307
TCP_SESSION_TIMEOUT_MINUTES=30
```

Le bind est réalisé avant que le serveur soit annoncé comme running. Backlog 64, thread par client, buffer limité à 8 MiB.

## Sécurité réseau

Le framing n’inclut pas encore TLS. En production, ne pas exposer directement 3307 sur Internet : utiliser réseau privé, VPN, tunnel SSH ou terminaison TLS. Les ACL applicatives restent obligatoires même derrière un tunnel.
