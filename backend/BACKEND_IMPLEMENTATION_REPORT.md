# Rapport d’implémentation backend XMLForge V5

**Base de travail :** branche `main`, commit initial `ccfd9c57f0345799bfe95167ac85bda82c7787f5`  
**Périmètre :** backend exclusivement. Aucun fichier `xmlforge-react`, HTML, CSS ou frontend n’a été modifié.

## 1. Résultat global

Le backend utilise maintenant un document XML persistant par base comme source de vérité. Chaque document est validé puis projeté dans un vrai fichier SQLite relationnel. REST et TCP partagent `QueryService`; SELECT, INSERT, UPDATE et DELETE ne sont plus simulés.

Le control plane SQLAlchemy est conservé pour users/rôles/ACL/audit et comme catalogue de compatibilité. Il n’est pas la vérité des structures et données métier : supprimer le catalogue row et la projection puis recharger le XML reconstruit les deux, cas couvert par test.

## 2. Fichiers créés

### Modèles et sécurité

- `app/models/role.py` : rôles extensibles.
- `app/models/database_permission.py` : ACL de base.
- `app/models/table_permission.py` : ACL de table.
- `app/models/revoked_token.py` : blocklist JWT.
- `app/services/permission_service.py` : autorisation commune REST/TCP/services.
- `app/errors.py` : erreurs métier codifiées.

### XML et SQLite

- `app/xml_engine/document.py` : parser, normalisation, XSD, validation, sérialisation canonique.
- `app/xml_engine/projection.py` : construction DDL/DML d’une vraie projection SQLite.
- `app/xml_engine/storage.py` : locks, snapshots, fsync, remplacements atomiques.
- `app/xml_engine/service.py` : orchestration XML → SQLite → catalogue et rollback.
- `app/xml_engine/__init__.py`.

### Requêtes

- `app/query/sql_parser.py` : tokenizer/parser récursif du sous-ensemble SQL.
- `app/query/service.py` : moteur partagé REST/TCP.
- `app/query/__init__.py`.
- `app/routes/query.py` : endpoint de requête.

### API permissions

- `app/routes/permissions.py` : CRUD des ACL de base/table.

### Migrations et tests

- `app/schema_migrations.py` : migration V5 versionnée, idempotente et non destructive.
- `migrations/README.md`.
- `pytest.ini`.
- `tests/conftest.py`.
- `tests/test_auth_permissions.py`.
- `tests/test_tables_rows.py`.
- `tests/test_xml_projection.py`.
- `tests/test_tcp.py`.
- `tests/__init__.py`.

## 3. Principaux fichiers modifiés et rôle

- `app/__init__.py` : migrations, bootstrap XML, projections au démarrage, erreurs métier, vérification JWT active/blocklist, TCP configurable, CLI `create-admin`.
- `app/config.py`, `.env.example` : paths XML/projections, TCP, secrets sûrs, tests sans TCP, validation production.
- `app/models/user.py`, `database.py`, `table.py`, `column.py`, `tcp_credential.py` : rôles, ownership/scope, version/checksum/sync, ACL, FK/index persistants et masquage secrets.
- `app/services/database_service.py`, `table_service.py`, `column_service.py`, `row_service.py` : CRUD réorienté vers le XML canonique, projection et ACL.
- `app/services/import_service.py`, `export_service.py`, `project_service.py`, `sync_service.py` : source XML réelle, imports complets et conflits de version.
- `app/services/auth_service.py`, `user_service.py`, `tcp_credential_service.py` : rôles, token version, révocation, credentials TCP cohérents.
- `app/routes/*.py` concernés : contrôles permissions, versions, filtres, détails, query, sync/rebuild et codes HTTP.
- `app/tcp/tcp_server.py`, `tcp_protocol.py`, `xmlforge_client.py` : sessions corrigées, sélection autorisée, CRUD réel, unlock, close, timeout, multi-clients.
- `app/converters/xml_to_sql.py`, `sql_to_xml.py` : NULL, rows, contraintes/indexes et XML conforme.
- `xmlforge.xsd`, `app/static/xmlforge.xsd` : schéma aligné sur le XML réel.
- `requirements.txt` : `lxml` obligatoire et dépendances de tests.
- `README.md`, `API_DOCUMENTATION.md`, `BACKEND_DOCUMENTATION.md`, `TCP_SERVER_README.md` : documentation réécrite selon le code réellement livré.
- `.gitignore` : exclusion des données runtime XML/projections ; aucun frontend modifié.
- `run.py`, `app/app.py` : debug/unsafe Werkzeug non forcés.

## 4. Fonctionnalités réellement opérationnelles

### Auth

- register/login bcrypt ;
- JWT expirant ;
- vérification compte actif ;
- logout avec révocation `jti` ;
- invalidation globale via `token_version` au reset/désactivation ;
- rôles admin/user persistants ;
- bootstrap admin explicite, aucun email magique pour les nouvelles inscriptions.

### Propriété et permissions

- owner ;
- bases PERSONAL/COMMON ;
- ACL read/write/DDL/admin au niveau base et table ;
- filtrage des listes ;
- permissions revalidées côté services et TCP ;
- secrets de protection masqués.

### XML/SQLite

- XML canonique persistant ;
- XSD correspondant aux exports réels ;
- parser durci ;
- projection SQLite reconstructible au démarrage ou par endpoint ;
- PK, FK, UNIQUE, NOT NULL, DEFAULT, AUTO_INCREMENT, INDEX réels ;
- rows XML réellement insérées et requêtables ;
- NULL explicite ;
- renommage/suppression de colonnes reflété dans rows et projection ;
- détection FK/PK/UNIQUE/types avant commit.

### CRUD et query

- bases, tables, colonnes et rows ;
- SELECT/INSERT/UPDATE/DELETE ;
- filtres d’égalité REST, search, tri, pagination ;
- WHERE récursif AND/OR ;
- comparaisons, LIKE, IN, IS NULL ;
- ORDER BY, LIMIT, OFFSET ;
- UPDATE/DELETE sans WHERE refusés.

### Protection

- protection depuis XML/create/update ;
- unlock individuel ;
- expiration ;
- effacement logout et reconnexion ;
- ACL exigée avant même la clé ;
- support REST et TCP.

### TCP

- credentials TCP bcrypt réellement utilisés ;
- session ↔ user ↔ base corrigée ;
- sélection par nom non ambigu ou ID avec ACL ;
- SELECT/INSERT/UPDATE/DELETE réels ;
- PING/PONG, SELECT_DATABASE, UNLOCK_TABLE, CLOSE ;
- timeout et purge ;
- fermeture propre ;
- threads multi-clients ;
- limite de buffer ;
- audit.

## 5. Fonctionnalités volontairement encore incomplètes

- JOIN SQL texte, GROUP BY, agrégats, sous-requêtes et DDL via QueryService ne sont pas supportés. Les FK sont cependant appliquées réellement. Le sous-ensemble refusé n’est jamais simulé.
- Le protocole TCP applicatif n’intègre pas TLS. Il doit être placé derrière réseau privé/VPN/tunnel/TLS avant exposition Internet.
- Le parser SQL → XML reste adapté aux dumps CREATE TABLE/INSERT courants, pas à tout MySQL (triggers, procédures, vues, ALTER complexes).
- La route legacy `/database/create` MySQL est conservée mais n’est pas la projection V5 et ne bénéficie pas de synchronisation continue.
- Les snapshots de rollback des artefacts sont chargés en mémoire ; pour des fichiers multi-gigaoctets, une stratégie de journal/backup par renommage sera préférable.
- Le session store TCP est en mémoire du processus. Un déploiement multi-instance nécessitera Redis ou un store partagé.
- Le verrou `flock` est adapté au déploiement local ; un stockage distribué demandera un verrou distribué.
- MFA, validation email et récupération de compte ne sont pas inclus.

## 6. Migrations

Migration V5 implémentée et exécutée dans les tests en mémoire et lors d’un test de redémarrage sur SQLite persistant temporaire :

- ajout `users.role_id`, `users.token_version` ;
- ajout owner/scope/xml path/projection path/version/checksum/sync status ;
- ajout FK references/index aux colonnes ;
- création roles, permissions et revoked tokens ;
- backfill owner=creator et scope=PERSONAL ;
- rôle user par défaut ;
- promotion de l’ancien compte nyx seulement s’il existait déjà avant migration ;
- aucune suppression de donnée.

Aucune base de production utilisateur n’était présente dans le dépôt, donc aucune migration destructive ou production n’a été exécutée.

## 7. Tests ajoutés et exécutés

Commande :

```bash
python -m pytest -q
```

Résultat initial V5 : **7 passed**. Après ajout de la suite E2E réelle :

- `backend/tests/e2e` : **3 passed** ;
- toute la suite `backend/tests` : **13 passed** (incluant retry WinError 5, fallback et libération SQLAlchemy engine/session/checkout).

La mesure de couverture initiale était **57 % globale** avant l'ajout E2E, avec notamment QueryService 87 %, XmlEngineService 85 %, projection SQLite 81 %, TCPServer 78 %. Le guide E2E est `tests/E2E_TESTING_GUIDE.md`.

Contrôles supplémentaires :

- compilation de tous les fichiers Python : succès ;
- Ruff `F,E722,E741` : succès ;
- XSD sur `test.xml` et `BaseDonnees_INPTIC.xml` : valide ;
- round-trip SQL → XML canonique avec FK et rows : succès ;
- redémarrage avec suppression de projection puis reconstruction depuis XML : succès ;
- route map vérifiée, aliases TCP accidentels supprimés ;
- frontend non modifié.

## 8. Endpoints REST disponibles

Tous les endpoints ci-dessous existent sous `/api`; les routes historiques non TCP existent également sans ce préfixe.

### Auth/users

- `POST /register`, `POST /login`, `POST /logout`, `GET /me`
- `GET/POST /users`
- `GET/PUT/DELETE /users/<id>`
- `POST /users/<id>/reset-password`, `/toggle-active`

### Bases/permissions

- `GET/POST /databases`
- `GET/PUT/DELETE /databases/<id>`
- comment/archive/restore
- `GET/POST /databases/<id>/permissions`
- `DELETE /databases/<id>/permissions/<user_id>`
- `POST /databases/<id>/query`
- `POST /databases/<id>/sync[-xml]`
- `POST /databases/<id>/rebuild-projection`

### Tables/colonnes/rows

- `GET /tables/<database_id>`, `GET /tables/<id>/detail`
- `POST /tables`, `PUT/DELETE /tables/<id>`
- comment/archive/restore
- `GET/POST /tables/<id>/permissions`
- `DELETE /tables/<id>/permissions/<user_id>`
- `GET /columns/<table_id>`, `GET /columns/<id>/detail`
- `POST /columns`, `PUT/DELETE /columns/<id>`
- comment/archive/restore
- `GET/POST /tables/<id>/rows`
- `PUT/DELETE /tables/<id>/rows/<row_id>`
- `POST /tables/<id>/sync[-xml]`
- `POST /unlock-table`, `GET/DELETE /unlocks`

### Import/export/audit

- import XML/SQL/project ;
- export XML/SQL base/table/project ;
- converters XML↔SQL ;
- history/audit admin ;
- route legacy MySQL conservée.

### Gestion TCP via REST

- `/api/tcp/credentials` GET/POST/PUT/DELETE ;
- regenerate/show-password ;
- sessions/status.

Le détail des corps et permissions se trouve dans `API_DOCUMENTATION.md`.

## 9. Opérations TCP disponibles

- AUTH avec credentials TCP ;
- SELECT_DATABASE ;
- SELECT ;
- INSERT ;
- UPDATE ;
- DELETE ;
- UNLOCK_TABLE ;
- PING/PONG ;
- CLOSE.

Toutes les opérations data passent par QueryService et le pipeline XML/SQLite. Les erreurs ACL, contraintes, types, table/base absente, version et session sont renvoyées comme messages ERROR.

## 10. Flux exact XML → SQLite → requête → XML

### Chargement

```text
fichier XML
  -> parser sécurisé
  -> validation XSD + métier
  -> création SQLite temporaire
  -> DDL contraintes/indexes
  -> insertion rows
  -> foreign_key_check + quick_check
  -> remplacement atomique projection
  -> catalogue SQLAlchemy réaligné
```

### Lecture

```text
REST/TCP
  -> JWT ou session TCP
  -> ACL base/table
  -> QueryService
  -> SELECT paramétré dans la projection SQLite
  -> résultat paginé
```

### Écriture

```text
REST/TCP INSERT|UPDATE|DELETE ou DDL service
  -> auth + rôle + owner/ACL + protection
  -> lock base
  -> contrôle version
  -> mutation copie logique XML
  -> validation
  -> construction projection SQLite temporaire complète
  -> contraintes réelles
  -> préparation catalogue
  -> écriture atomique XML (vérité)
  -> remplacement projection SQLite
  -> commit control plane
  -> historique/audit
```

Toute erreur avant succès supprime la projection temporaire et conserve/restaure les artefacts précédents. Un crash après commit XML mais avant remplacement SQLite est réparé au démarrage en reprojetant depuis XML.
