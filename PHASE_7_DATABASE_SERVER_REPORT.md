# PHASE 7 — XMLForge Database Server

**Date** : 2026-09-11

---

## 1. État initial

`PHASE_6K_STABLE_COMPLETE` — 325 tests backend, architecture XML-only (Control
Plane + Data Plane + Query = XML), TCP :3307 partageant les services REST.

## 2. Audit

- **Composants réutilisés** : `XmlNativeEngine` (moteur SQL), `XmlQueryService`
  (exécuteur partagé REST/TCP), `XmlDataPlane` (mutations atomiques), `store.py`
  (verrous/atomicité/snapshot), `PermissionService` (ACL unique), Control Plane
  XML (auth + sessions + audit).
- **Problèmes identifiés** : pas de `USE`/transactions/`DROP DATABASE` au niveau
  SQL ; pas de LEFT JOIN ; erreurs TCP sans code métier ; pas de client Python
  officiel ; `resolve_table` en O(bases).

## 3. Protocole (final, rétrocompatible)

Trame inchangée `[type:1][len:4 BE][JSON]` ; messages AUTH/QUERY/RESPONSE/ERROR/
PING/SELECT_DATABASE/UNLOCK_TABLE/CLOSE conservés. **Ajout additif** : champ
`error_code` (code métier) dans `MSG_ERROR` — les clients existants restent
compatibles. Documenté dans `XMLFORGE_PROTOCOL.md`.

## 4. Sessions

`ClientSession` enrichi : état de transaction (`transaction_active`,
`transaction_snapshot`, `transaction_path`) ; plusieurs requêtes par connexion
sans ré-authentification ; `USE` (SQL) ou `MSG_SELECT_DATABASE` ; timeout
(`TCP_SESSION_TIMEOUT_MINUTES`) ; purge des sessions expirées ; isolation des
sessions (transactions par connexion).

## 5. Client Python officiel (`xmlforge/`)

Package standard library : `connect()`, `Connection` (authenticate/use/execute/
query/close + context manager), `Result` (columns/rows/row_count/affected_rows/
last_insert_id/metadata), `XmlforgeError` (code métier + code numérique),
`protocol`. **Testé contre le vrai serveur TCP** (voir §11).

## 6. SQL — fonctionnalités supportées / non supportées

Matrice complète dans `XMLFORGE_SQL.md`. **Ajouts Phase 7** : `USE`, `BEGIN`/
`COMMIT`/`ROLLBACK` (`START TRANSACTION`), `DROP DATABASE`, **LEFT JOIN**.
Refusés (inchangé) : RIGHT/FULL OUTER JOIN, sous-requêtes, UNION, COUNT(DISTINCT).

## 7. Transactions

`BEGIN` capture un **snapshot du document XML + du miroir `catalog.xml`** ;
mutations immédiates (écriture atomique) ; `COMMIT` libère ; `ROLLBACK`
**restaure** les snapshots (données + version/checksum cohérents). Erreurs
`TRANSACTION_ACTIVE` / `TRANSACTION_NOT_ACTIVE` / `TRANSACTION_ERROR`.
Sémantique d'isolation documentée honnêtement dans `XMLFORGE_TRANSACTIONS.md`
(pas de MVCC ; audit/history append-only non annulés).

## 8. Concurrence

8 connexions TCP simultanées (5 INSERT chacune) : **aucune perte** (40 lignes +
état initial), aucune corruption, sessions isolées (testé : `COMMIT` sans
transaction échoue chez l'autre session ; `ROLLBACK` restaure). Limites
documentées dans `XMLFORGE_CONCURRENCY.md`.

## 9. Performance (mesures réelles)

**resolve_table (O(bases))** :

| bases | médiane | p95 |
|---|---|---|
| 10 | 3,60 ms | 3,73 ms |
| 50 | 17,64 ms | 18,00 ms |
| 100 | 47,30 ms | 50,45 ms |
| 500 | 189,52 ms | 194,54 ms |

**TCP round-trip (200 lignes, 30 itérations, min/max/moy/médiane/p95 ms)** :

| op | min | max | avg | médiane | p95 |
|---|---|---|---|---|---|
| SELECT * LIMIT 10 | 18,59 | 22,27 | 19,79 | 19,62 | 20,43 |
| SELECT WHERE | 19,36 | 21,84 | 20,31 | 20,30 | 20,88 |
| COUNT(*) | 20,17 | 23,04 | 21,09 | 21,05 | 21,71 |
| INSERT | 25,82 | 31,96 | 27,90 | 27,78 | 30,47 |
| UPDATE | 28,55 | 30,55 | 29,72 | 29,78 | 30,24 |
| DELETE | 29,97 | 38,41 | 31,24 | 30,99 | 31,82 |

Le surcoût TCP (~20–30 ms) est dominé par l'aller-retour réseau/sérialisation ;
le coût du moteur (parse+serialize lxml, mesuré en 6K) reste linéaire. Aucune
optimisation introduite (pas de cache lourd) — limitations documentées.

## 10. Sécurité

- bcrypt + JWT + `token_version` (auth REST) et credentials TCP (bcrypt) ;
- une seule logique de permission (PERSONAL/COMMON, VIEW/EDIT/MANAGE) pour REST
  et TCP ;
- aucun accès direct aux XML depuis un client TCP (aucune commande de lecture de
  fichier ; chemins jamais acceptés du client) ;
- fichiers Control Plane 0700/0600, validation XSD, verrous, atomicité ;
- erreurs sans fuite de secret/traceback (codes métier structurés).

## 11. Tests

- **Tests ajoutés** : `tests/test_phase7.py` (9) — parser (USE/BEGIN/COMMIT/
  ROLLBACK/DROP DATABASE/LEFT JOIN), LEFT JOIN moteur (NULL), session TCP
  complète + transactions (rollback/commit), codes d'erreur métier, isolation de
  sessions, DROP DATABASE via TCP, concurrence 8 clients, client Python
  (contexte + champs Result). Test e2e adapté (code métier `ACCESS_DENIED`).
- **Tests existants** : tous conservés.
- **Résultat** : **334/334 tests backend passés** (325 → 334) ; **11 tests
  frontend** (10 unitaires + 1 live) verts ; `npm run build` OK.

## 12. REST/TCP/Frontend E2E

Scénario réel exécuté : démarrage Flask :5000 + TCP :3307 → bootstrap →
`create-admin` → credentials TCP via REST → **client Python officiel** sur
localhost:3307 → `USE Bibliotheque` → `CREATE TABLE` → `INSERT` → `SELECT` →
`UPDATE` → `DELETE` → `BEGIN`/`ROLLBACK` → `BEGIN`/`COMMIT` → `CLOSE` →
**redémarrage du serveur** → reconnexion → `SELECT` (données intactes). Aucun
fichier `.db`/`.sqlite` créé (vérifié). REST inchangé ; frontend build+lint+tests
verts.

## 13. Installation propre

Installation vierge démontrée (bootstrap → admin → serveur → client TCP →
redémarrage) sans SQLite/SQLAlchemy.

## 14. Limitations

1. `resolve_table` en O(bases) (~0,4 ms/base) : à optimiser (index mémoire
   invalidé au catalogue) si le nombre de bases devient grand.
2. Write amplification XML (réécriture du document) : documentée en 6K, non
   optimisée (pas de cache).
3. Transactions sans MVCC (documenté) ; audit/history non annulés au ROLLBACK.
4. REST sans état : transactions réservées aux sessions TCP.

## 15. Fichiers créés / modifiés / supprimés

**Créés** : `xmlforge/` (client Python : `__init__.py`, `client.py`,
`connection.py`, `protocol.py`, `errors.py`, `result.py`),
`examples/python_client_demo.py`, `backend/tests/test_phase7.py`,
`XMLFORGE_SERVER.md`, `XMLFORGE_PROTOCOL.md`, `XMLFORGE_SQL.md`,
`XMLFORGE_CLIENT.md`, `XMLFORGE_TRANSACTIONS.md`, `XMLFORGE_ERRORS.md`,
`XMLFORGE_CONCURRENCY.md`.

**Modifiés** : `backend/app/query/sql_parser.py` (USE/BEGIN/COMMIT/ROLLBACK/
DROP DATABASE/LEFT JOIN), `backend/app/xml_engine/xml_native.py` (LEFT JOIN),
`backend/app/query/xml_query_service.py` (drop_database + refus explicite des
énoncés de session en REST), `backend/app/tcp/tcp_protocol.py` (error_code),
`backend/app/tcp/tcp_server.py` (sessions/transactions/erreurs métier),
`backend/tests/test_xml_engine_sql_advanced.py` (LEFT JOIN désormais supporté),
`backend/tests/e2e/test_tcp_security_permissions_e2e.py` (code métier).

**Supprimés** : aucun.

## 16. Conclusion

XMLForge est désormais utilisable comme **serveur de base de données** par une
application externe : client Python officiel, protocole documenté et
rétrocompatible, sessions, `USE`, transactions (BEGIN/COMMIT/ROLLBACK),
LEFT JOIN, erreurs métier structurées — le tout en **XML-only**, sans SQLite ni
SQLAlchemy, avec REST et le frontend intacts. Le scénario minimal obligatoire
(AUTH → USE → CREATE TABLE → INSERT → SELECT → UPDATE → DELETE → BEGIN → ROLLBACK
→ BEGIN → COMMIT → CLOSE → RESTART → RECONNECT → SELECT) est démontré de bout en
bout sur le port 3307.

PHASE_7_DATABASE_SERVER_COMPLETE
