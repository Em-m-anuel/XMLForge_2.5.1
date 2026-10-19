# Guide de connexion TCP XMLForge

Ce document décrit le protocole TCP réellement implémenté par le backend XMLForge V5. Il s'adresse aux applications externes qui doivent ouvrir une session, exécuter des requêtes sur le moteur XML et fermer proprement la connexion.

## 1. Vue d'ensemble

XMLForge expose un serveur TCP/IP persistant en complément de son API REST. Le serveur TCP fournit un transport binaire pour :

- authentifier un utilisateur avec un credential TCP dédié ;
- sélectionner une base autorisée ;
- exécuter le sous-ensemble SQL du moteur XML ;
- déverrouiller ponctuellement une table protégée ;
- tester la disponibilité avec `PING` ;
- gérer une session et ses transactions `BEGIN`/`COMMIT`/`ROLLBACK`.

Le serveur partage le moteur XML et les contrôles de permission du backend REST. Les opérations sont donc soumises aux ACL de l'utilisateur, aux contraintes du schéma, aux protections de tables et au contrôle de version optimiste.

Le serveur est démarré automatiquement par la factory Flask lorsque `TCP_ENABLED=true`. Un échec de bind est journalisé et l'application Flask peut continuer sans serveur TCP.

## 2. Paramètres de connexion

### Valeurs par défaut

| Paramètre                 | Valeur par défaut | Description                                                                             |
| ------------------------- | ----------------- | --------------------------------------------------------------------------------------- |
| Host d'écoute             | `0.0.0.0`         | Toutes les interfaces réseau du serveur. Ce n'est pas l'adresse à utiliser côté client. |
| Port                      | `3307`            | Port TCP XMLForge.                                                                      |
| Timeout de session        | `30` minutes      | Inactivité maximale avant expiration de la session.                                     |
| Backlog                   | `64`              | Nombre de connexions en attente lors du `listen`.                                       |
| Taille maximale du buffer | `8 MiB`           | Limite par connexion ; un message plus volumineux est rejeté.                           |

Configuration dans `backend/.env` :

```dotenv
TCP_ENABLED=true
TCP_HOST=0.0.0.0
TCP_PORT=3307
TCP_SESSION_TIMEOUT_MINUTES=30
```

Côté client, utilisez l'adresse réelle du serveur : `127.0.0.1` en local, ou un nom DNS / une adresse IP routable dans un environnement distant. Le serveur n'exige pas que le client utilise le port indiqué dans le credential si l'administrateur a configuré un port différent : le port effectivement bindé par `TCP_PORT` est la référence.

### Prérequis réseau et authentification

- Le port TCP choisi doit être autorisé par le pare-feu du serveur et par les règles réseau intermédiaires.
- Le serveur accepte des connexions TCP IPv4 (`AF_INET`).
- Le protocole ne fournit pas de TLS. En production, placez le service derrière un VPN, un tunnel SSH ou une terminaison TLS privée ; n'exposez pas directement le port sur Internet.
- L'application externe doit disposer d'un `tcp_username` et du mot de passe TCP associé. Ce mot de passe est différent du mot de passe principal XMLForge et est stocké côté serveur sous forme bcrypt.
- Les credentials sont créés ou régénérés via l'API REST authentifiée, par exemple `POST /api/tcp/credentials`. Le secret en clair doit être conservé par le client au moment de sa création ou de sa régénération.

## 3. Format des messages et structure du protocole

### Framing binaire

Chaque message est encodé en réseau (big-endian) selon le format suivant :

```text
[1 octet : type][4 octets : longueur uint32][N octets : JSON UTF-8]
```

La longueur porte uniquement sur le JSON. Il n'y a ni délimiteur `\\n`, ni terminaison NUL, ni compression. Plusieurs messages peuvent être regroupés dans un même `recv`, et un message peut être fragmenté sur plusieurs lectures : le client doit donc accumuler les octets jusqu'à obtenir `5 + longueur` octets.

Exemple conceptuel :

```text
01 00 00 00 3D {"username":"tcp-user","password":"secret"}
```

Le serveur traite les messages dans l'ordre sur la connexion. Le buffer d'une connexion est limité à 8 MiB.

### Types de messages

| Type                  | Code | Sens                | Payload JSON attendu / renvoyé                              |
| --------------------- | ---: | ------------------- | ----------------------------------------------------------- |
| `MSG_AUTH`            |  `1` | Client vers serveur | `username`, `password`, `database?`                         |
| `MSG_QUERY`           |  `2` | Client vers serveur | `session_token`, `query`, `expected_version?`, `table_key?` |
| `MSG_RESPONSE`        |  `3` | Serveur vers client | `status` et données de résultat                             |
| `MSG_ERROR`           |  `4` | Serveur vers client | `code`, `message`, `error_code?`                            |
| `MSG_PING`            |  `5` | Client vers serveur | `{}`                                                        |
| `MSG_PONG`            |  `6` | Serveur vers client | `{}`                                                        |
| `MSG_SELECT_DATABASE` |  `7` | Client vers serveur | `session_token`, `database`                                 |
| `MSG_UNLOCK_TABLE`    |  `8` | Client vers serveur | `session_token`, `table`, `key`                             |
| `MSG_CLOSE`           |  `9` | Client vers serveur | `session_token`                                             |

### Réponses types

Authentification réussie :

```json
{
  "status": 0,
  "session_token": "uuid",
  "user_id": 12,
  "username": "tcp-user@example.com",
  "full_name": "Example User",
  "expires_in_seconds": 1800,
  "database_id": 3,
  "database_name": "customers"
}
```

Réponse de requête réussie :

```json
{
  "status": 2,
  "engine": "xml",
  "result": {
    "rows": [{ "id": 1, "name": "Alice" }],
    "columns": ["id", "name"],
    "row_count": 1
  },
  "metrics": {
    "engine": "xml"
  }
}
```

Les champs de `result` varient selon l'opération : par exemple `{"inserted": 1}`, `{"updated": 1}`, `{"deleted": 1}`, `{"created": "table_name"}` ou `{"transaction": "COMMIT"}`.

## 4. Commandes et actions disponibles

### `AUTH` - ouvrir une session

Payload :

```json
{
  "username": "tcp-user@example.com",
  "password": "tcp-secret",
  "database": "12"
}
```

`database` est facultatif. Il peut être un identifiant numérique ou un nom non ambigu. La base doit être accessible en lecture par l'utilisateur. En cas de succès, le serveur renvoie un token de session à réutiliser dans les messages suivants.

### `QUERY` - exécuter une requête SQL

Payload minimal :

```json
{
  "session_token": "<token>",
  "query": "SELECT * FROM users WHERE active = TRUE"
}
```

Champs optionnels :

- `expected_version` : version attendue pour détecter un conflit d'écriture ;
- `table_key` : secret de déverrouillage d'une table protégée pour une opération d'écriture ou de DDL.

Le moteur accepte les opérations suivantes :

| Groupe   | Syntaxe supportée                                                                                                                                           | Résultat courant                                                                                                     |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ------ | ----------- |
| Lecture  | `SELECT`, `WHERE`, `AND`/`OR`, parenthèses, `LIKE`, `IN`, `IS NULL`, `BETWEEN`, `ORDER BY`, `LIMIT`, `OFFSET`, agrégats, `GROUP BY`, `HAVING`, `INNER JOIN` | `rows`, `columns`, `row_count`, ou `count` pour un `COUNT` simple                                                    |
| Écriture | `INSERT INTO ... VALUES (...)`, `UPDATE ... SET ... WHERE ...`, `DELETE FROM ... WHERE ...`                                                                 | `inserted`, `updated` ou `deleted` ; `UPDATE` et `DELETE` exigent un `WHERE`                                         |
| Schéma   | `CREATE TABLE`, `DROP TABLE`, `ALTER TABLE ADD/MODIFY/DROP COLUMN`, `ALTER TABLE RENAME TO`, `CREATE [UNIQUE] INDEX`, `DROP INDEX`                          | `created`, `dropped`, `added_column`, `dropped_column`, `renamed`, `created_index` ou `dropped_index` selon l'action |
| Bases    | `CREATE DATABASE`, `DROP DATABASE`                                                                                                                          | `created` / `dropped` et, à la création, `database_id`                                                               |
| Session  | `USE <base>`, `BEGIN` ou `START TRANSACTION`, `COMMIT`, `ROLLBACK`                                                                                          | Sélection de base ou `{"transaction":"BEGIN                                                                          | COMMIT | ROLLBACK"}` |

Les constructions non supportées, notamment les sous-requêtes, `UNION` et `LEFT/RIGHT/OUTER JOIN`, sont rejetées avec `QUERY_ERROR`. Les permissions sont vérifiées selon l'opération et la table concernée.

`USE` sélectionne la base de la session TCP. `BEGIN` prend un snapshot XML ; un `ROLLBACK`, une fermeture, une expiration ou un arrêt du serveur annule les changements non commités.

### `SELECT_DATABASE` - changer de base

Payload :

```json
{ "session_token": "<token>", "database": 15 }
```

La réponse réussie contient `status: 2`, `database_id` et `database_name`. Le nom peut être utilisé si un seul nom correspond à une base accessible ; utilisez l'ID pour éviter toute ambiguïté.

### `UNLOCK_TABLE` - déverrouiller une table protégée

Payload :

```json
{ "session_token": "<token>", "table": "customers", "key": "TABLE-SECRET" }
```

La réponse réussie contient `status: 2`, `unlocked: true` et `table_id`. Le déverrouillage est lié à l'utilisateur et ne remplace pas les permissions ACL.

### `PING` et `CLOSE`

`PING` ne demande pas de session et reçoit un message `PONG` avec un payload `{}`. `CLOSE` reçoit le token de session et renvoie une réponse `status: 2` avec `closed: true`. Une fermeture brutale de socket supprime également la session côté serveur.

## 5. Erreurs et codes de retour

### Codes numériques

| Constante         | Valeur | Signification                             |
| ----------------- | -----: | ----------------------------------------- |
| `AUTH_SUCCESS`    |    `0` | Authentification réussie                  |
| `AUTH_FAILED`     |    `1` | Authentification refusée                  |
| `QUERY_SUCCESS`   |    `2` | Opération réussie                         |
| `QUERY_ERROR`     |    `3` | Erreur de requête ou d'opération          |
| `SESSION_EXPIRED` |    `4` | Token absent, invalide ou session expirée |
| `INVALID_REQUEST` |    `5` | Type ou message invalide                  |

Les succès sont envoyés avec `MSG_RESPONSE`. Les erreurs sont envoyées avec `MSG_ERROR`, jamais comme texte brut :

```json
{
  "code": 3,
  "message": "UPDATE sans WHERE est refusé par sécurité",
  "error_code": "SYNTAX_ERROR"
}
```

`error_code` est optionnel selon le chemin d'erreur. Les valeurs métier actuellement émises comprennent `ACCESS_DENIED`, `CONFLICT`, `CONSTRAINT_VIOLATION`, `DATA_INVALID`, `TABLE_NOT_FOUND`, `COLUMN_NOT_FOUND`, `DATABASE_NOT_FOUND`, `INVALID_QUERY`, `SYNTAX_ERROR`, `DATABASE_NOT_SELECTED`, `TRANSACTION_ACTIVE`, `TRANSACTION_NOT_ACTIVE`, `TRANSACTION_ERROR` et `INTERNAL_ERROR`.

Un client doit traiter `MSG_ERROR` avant d'interpréter `MSG_RESPONSE`, journaliser `message` sans exposer les secrets, et réauthentifier la session lorsqu'il reçoit `code: 4`.

## 6. Exemples de clients

Les exemples utilisent `127.0.0.1:3307`, un credential TCP déjà créé et la base `12`. Remplacez ces valeurs par celles de votre environnement.

### Python - socket standard

```python
import json
import socket
import struct

HOST, PORT = "127.0.0.1", 3307

def pack(message_type, payload):
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return struct.pack("!BI", message_type, len(body)) + body

def recv_message(sock):
    header = b""
    while len(header) < 5:
        chunk = sock.recv(5 - len(header))
        if not chunk:
            raise ConnectionError("Connexion fermée pendant l'en-tête")
        header += chunk
    message_type, length = struct.unpack("!BI", header)
    body = b""
    while len(body) < length:
        chunk = sock.recv(length - len(body))
        if not chunk:
            raise ConnectionError("Connexion fermée pendant le JSON")
        body += chunk
    return message_type, json.loads(body.decode("utf-8"))

with socket.create_connection((HOST, PORT), timeout=10) as sock:
    sock.sendall(pack(1, {
        "username": "tcp-user@example.com",
        "password": "tcp-secret",
        "database": 12,
    }))
    message_type, auth = recv_message(sock)
    if message_type == 4:
        raise RuntimeError(auth)
    token = auth["session_token"]

    sock.sendall(pack(2, {
        "session_token": token,
        "query": "SELECT * FROM customers ORDER BY id LIMIT 10",
    }))
    message_type, response = recv_message(sock)
    if message_type == 4:
        raise RuntimeError(response)
    print(response["result"])

    sock.sendall(pack(9, {"session_token": token}))
    recv_message(sock)
```

### Node.js - module `net`

```js
const net = require("node:net");

const TYPE = { AUTH: 1, QUERY: 2, RESPONSE: 3, ERROR: 4, CLOSE: 9 };
const client = net.createConnection({ host: "127.0.0.1", port: 3307 });
let buffer = Buffer.alloc(0);
let sessionToken = null;

function frame(type, payload) {
  const body = Buffer.from(JSON.stringify(payload), "utf8");
  const packet = Buffer.alloc(5 + body.length);
  packet.writeUInt8(type, 0);
  packet.writeUInt32BE(body.length, 1);
  body.copy(packet, 5);
  return packet;
}

function readOne() {
  if (buffer.length < 5) return null;
  const length = buffer.readUInt32BE(1);
  if (buffer.length < 5 + length) return null;
  const type = buffer.readUInt8(0);
  const payload = JSON.parse(buffer.subarray(5, 5 + length).toString("utf8"));
  buffer = buffer.subarray(5 + length);
  return { type, payload };
}

client.on("data", (chunk) => {
  buffer = Buffer.concat([buffer, chunk]);
  let message;
  while ((message = readOne()) !== null) {
    if (message.type === TYPE.ERROR) {
      console.error("XMLForge TCP error:", message.payload);
      client.end();
    } else if (
      message.type === TYPE.RESPONSE &&
      message.payload.session_token
    ) {
      sessionToken = message.payload.session_token;
      client.write(
        frame(TYPE.QUERY, {
          session_token: sessionToken,
          query: "SELECT * FROM customers LIMIT 10",
        }),
      );
    } else if (message.type === TYPE.RESPONSE && message.payload.result) {
      console.log(message.payload.result);
      client.write(frame(TYPE.CLOSE, { session_token: sessionToken }));
    }
  }
});

client.on("connect", () => {
  client.write(
    frame(TYPE.AUTH, {
      username: "tcp-user@example.com",
      password: "tcp-secret",
      database: 12,
    }),
  );
});
```

Dans une implémentation Node.js de production, conservez le token dans une variable dédiée pour envoyer `CLOSE` avec le bon token, ajoutez un timeout de lecture et gérez les réponses dans une file de requêtes afin de respecter l'ordre des messages.

### Diagnostic rapide

`telnet` et `nc` peuvent vérifier qu'un port est ouvert, mais ils ne sont pas adaptés pour exécuter ce protocole directement : les messages contiennent un en-tête binaire et du JSON encadré par une longueur, pas des lignes terminées par `\\n`. Utilisez plutôt un client qui implémente le framing ci-dessus ou le client Python fourni dans `backend/app/tcp/xmlforge_client.py`.
