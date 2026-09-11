# XMLForge Backend V5 — API REST

Base recommandée : `/api`. Pour compatibilité, les routes non TCP existent aussi sans `/api`. Auth : `Authorization: Bearer <JWT>`.

Réponse succès : `{"success":true,"message":"...","data":...}`.

Réponse erreur : `{"success":false,"message":"...","errors":{"code":"..."}}`.

## Authentification

| Méthode | URL | Corps/paramètres | Autorisation |
|---|---|---|---|
| POST | `/api/register` | `full_name,email,password` | public |
| POST | `/api/login` | `email,password` | public |
| GET | `/api/me` | — | JWT actif |
| POST | `/api/logout` | — | JWT ; révoque le jti |

## Utilisateurs

Toutes les routes exigent le rôle admin :

- `GET/POST /api/users`
- `GET/PUT/DELETE /api/users/<user_id>`
- `POST /api/users/<user_id>/reset-password` : `new_password`
- `POST /api/users/<user_id>/toggle-active`

`PUT` accepte `full_name`, `email`, `is_active`, `role` (`admin`/`user`). Le dernier admin actif ne peut pas être retiré/désactivé/supprimé.

## Bases

- `GET /api/databases?include_archived=true` : uniquement les bases accessibles, avec `owner_id`, `scope`, `is_owner` et `access` (`VIEW`/`EDIT`/`MANAGE`).
- `POST /api/databases` : `name`, `description?`, `comment?`, `scope?` (`PERSONAL` par défaut ou `COMMON`).
- `GET /api/databases/<id>` : droit read.
- `PUT /api/databases/<id>` : droit write ; `name`, `description`, `comment`, `scope` (scope exige admin), `expected_version?`.
- `DELETE /api/databases/<id>` : owner/admin ACL.
- `POST /api/databases/<id>/archive|restore`
- `GET/PUT /api/databases/<id>/comment`

`If-Match: <document_version>` peut remplacer `expected_version`.

## Partage et permissions

- `GET /api/databases/<id>/permissions` : droit admin.
- `POST /api/databases/<id>/permissions` : `{user_id?,email?,can_read,can_write,can_ddl,can_admin}`.
- `DELETE /api/databases/<id>/permissions/<user_id>`.
- `GET/POST /api/tables/<id>/permissions` : liste ou applique une surcharge de table.
- `DELETE /api/tables/<id>/permissions/<user_id>`.

Les droits supérieurs impliquent `can_read`. Une clé de protection ne remplace jamais une ACL.

## Tables

- `GET /api/tables/<database_id>` : droit read ; secrets masqués.
- `GET /api/tables/<table_id>/detail` : détail d'une table.
- `POST /api/tables` : `{name,database_id,description?,comment?,protected?,file_identifier?,expected_version?}` ; droit DDL.
- `PUT /api/tables/<id>` : rename/métadonnées/protection/file ID/statut ; droit DDL + unlock si déjà protégée.
- `DELETE /api/tables/<id>` : droit DDL + unlock.
- commentaires et archive/restore : `/api/tables/<id>/comment|archive|restore`.

## Colonnes

- `GET /api/columns/<table_id>`.
- `GET /api/columns/<column_id>/detail`.
- `POST /api/columns` : `table_id,name,type,length?,nullable?,primary_key?,foreign_key?,references?,unique?,auto_increment?,index?,default?,on_delete?,on_update?,key_identifier?`.
- `PUT/DELETE /api/columns/<id>`.
- commentaires et archive/restore : `/api/columns/<id>/comment|archive|restore`.

Aliases camelCase historiques acceptés : `primaryKey`, `foreignKey`, `autoIncrement`.

## Rows

- `GET /api/tables/<table_id>/rows`
  - `limit` max 500, `offset`
  - `filters` : objet JSON URL-encodé d’égalités
  - `search` : recherche textuelle multi-colonnes
  - `sort`, `order=ASC|DESC`
- `POST /api/tables/<id>/rows` : `{data:{...}, key_identifier?, expected_version?}`.
- `PUT /api/tables/<id>/rows/<row_id>` : remplace les données.
- `DELETE /api/tables/<id>/rows/<row_id>`.

Types et contraintes sont appliqués par la projection SQLite avant commit.

## Requête SQL contrôlée

`POST /api/databases/<id>/query`

```json
{
  "sql": "SELECT id,email FROM customers WHERE active=TRUE ORDER BY id DESC LIMIT 20 OFFSET 0",
  "expected_version": 12,
  "key_identifier": "optionnel-pour-table-protegee"
}
```

Sous-ensemble : SELECT/INSERT/UPDATE/DELETE, WHERE AND/OR/parenthèses, comparaisons, LIKE, IN, IS NULL, ORDER BY, LIMIT/OFFSET. UPDATE/DELETE sans WHERE refusés. Pas de JOIN texte, DDL, sous-requête, GROUP BY ou agrégat.

## Protection

- `POST /api/unlock-table` : `{table_id,key_identifier}`.
- `GET /api/unlocks`.
- `DELETE /api/unlocks`.

Unlock individuel, expirant, effacé à logout et login suivant.

## XML, sync, import et export

- `POST /api/databases/<id>/sync-xml` : `{xml,expected_version?,key_identifier?}`. Si `expected_version` manque, la version du XML entrant est utilisée.
- `POST /api/tables/<id>/sync-xml` : `{xml,expected_version,key_identifier?}` ; version obligatoire.
- aliases `/sync`.
- `POST /api/databases/<id>/rebuild-projection` : supprime implicitement le drift et reconstruit SQLite depuis le XML autoritaire.
- `POST /api/import/xml` et `/import/project` : multipart `file` ou JSON `{xml,database_name?,scope?}`.
- `POST /api/import/sql` : multipart ou `{sql,database_name?}`.
- `GET /api/export/xml/<database_id>` et `/export/project/<database_id>` : droit admin, car le document complet contient la protection.
- `GET /api/export/sql/<database_id>` : droit read.
- table : `/export/table-xml/<id>`, `/export/table-sql/<id>` et aliases historiques.
- `download=true` renvoie le fichier ; sinon JSON.
- converters texte : `/api/convert/xml-to-sql`, `/api/convert/sql-to-xml`.
- compatibilité legacy : `POST /api/database/create` matérialise encore un export dans MySQL si `MYSQL_*` est configuré ; ce chemin n'est pas la projection V5 et n'est pas synchronisé en continu.

## Historique/audit

Rôle admin :

- `GET /api/history?limit=100&database_id=`
- `GET /api/audit-logs?limit=100`
- `GET /api/audit`

## TCP REST

Ces routes existent uniquement sous `/api/tcp` :

- `GET/POST/PUT/DELETE /api/tcp/credentials`
- `POST /api/tcp/credentials/regenerate`
- `POST /api/tcp/credentials/show-password` avec `current_password` ; régénère un secret affichable une fois
- `GET /api/tcp/sessions`
- `GET /api/tcp/status` (public)

Le serveur TCP utilise le credential TCP, pas le mot de passe principal.

## Codes usuels

- 400 validation/requête non supportée ;
- 401 JWT/credential invalide ou expiré ;
- 403 ACL/protection ;
- 404 ressource ;
- 409 contrainte ou conflit de version ;
- 500 stockage/projection inattendu.
