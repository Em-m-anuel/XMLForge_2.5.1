> ⚠️ **DOCUMENT HISTORIQUE** — ne décrit pas l'architecture runtime actuelle (XML-only depuis la Phase 6J-B). Conservé comme archive.

# XMLForge — Mode backend XML (QUERY_BACKEND=xml)

Documentation du **mode XML-first** validé en Phase 4. SQLite est conservé
comme moteur de référence, de comparaison et de fallback explicite ; il n'est
**plus nécessaire** au fonctionnement des données métier lorsque le mode XML
est actif.

---

## 1. Architecture XML-first

```text
FRONTEND (React/Vite)
   |
   | REST /api (façade CRUD + /query)
   v
Services / Query
   |
   +--> XmlNativeEngine (moteur principal) --> fichier XML (source de vérité)
   |
   +--> SQLite (projection)   [optionnel : SYNC_SQLITE_PROJECTION=true]
   |                           [legacy / comparaison / fallback explicite]

TCP CLIENT
   |
   | protocole binaire JSON (:3307), champ "engine"
   v
TCPServer --> XmlQueryService / QueryService --> XmlNativeEngine --> XML
```

## 2. Configuration

| Variable | Valeurs | Défaut | Rôle |
|---|---|---|---|
| `QUERY_BACKEND` | `sqlite` · `xml` · `compare` | `sqlite` | moteur principal quand le champ `engine` d'une requête est absent |
| `XML_ENGINE_ENABLED` | `true` · `false` | `false` | garde-fou d'exploitation (autorise le moteur XML) |
| `SYNC_SQLITE_PROJECTION` | `true` · `false` | `true` | reconstruit la projection SQLite après chaque mutation XML |

**Trois modes explicites (aucun fallback silencieux) :**

```bash
# MODE SQLITE (défaut, historique) — projection SQLite active
QUERY_BACKEND=sqlite SYNC_SQLITE_PROJECTION=true

# MODE XML (moteur XML principal) — projection SQLite non nécessaire
QUERY_BACKEND=xml SYNC_SQLITE_PROJECTION=false

# MODE COMPARE — exécute les deux moteurs (nécessite la projection)
QUERY_BACKEND=compare SYNC_SQLITE_PROJECTION=true
```

> **Aucun fallback silencieux.** Si `QUERY_BACKEND=xml` et que le moteur XML
> échoue, l'erreur est retournée telle quelle. Symétriquement, en mode XML pur
> (`SYNC_SQLITE_PROJECTION=false`), le chemin SQLite (`engine=sqlite`) échoue
> explicitement (`SQLITE_PROJECTION_ERROR`), il n'est jamais rejoué sur XML.

## 3. REST

`POST /api/databases/<id>/query` :

```json
{"sql": "SELECT * FROM books", "engine": "sqlite|xml|compare", "expected_version": 3}
```

- `engine` absent → `QUERY_BACKEND`.
- `engine=xml` → `{"result": …, "metrics": {engine, total_ms, parse_ms, exec_ms, read_ms, write_ms, rows}}`.
- `engine=compare` → `{"comparison": {equivalent, sqlite, xml, diff}}`.

`GET /api/databases/<id>/schema` → introspection **basée sur le XML** (tables,
colonnes, PK/FK/unique/default/auto_increment, index, foreign_keys, row_count).

La façade CRUD (tables, colonnes, lignes) reste fonctionnelle : les métadonnées
proviennent du catalogue (control plane) et les lignes sont lues **depuis le
XML** quand la projection est absente.

## 4. TCP

`engine` est un champ optionnel du message `QUERY` : `sqlite` (défaut), `xml`,
`compare`. En mode XML, les mutations TCP écrivent le XML
(`TCP → XmlQueryService → XmlNativeEngine → fichier XML`), jamais
`TCP → SQLite → XML`.

## 5. Frontend

Le frontend consomme la façade CRUD REST ; il fonctionne en mode XML car :
- création de bases/tables/colonnes → `XmlEngineService.mutate` (XML) ;
- lecture des lignes → repli XML de `RowService.get_by_table` ;
- exports/imports/sync → XML ;
- authentification/permissions → control plane (inchangé).

Vérifié par le test navigateur Playwright (mode défaut) et par les tests
`test_xml_backend_mode.py` (façade lignes en mode XML).

## 6. Permissions

`PermissionService` (rôles `admin`/`user`, ACL `can_read/can_write/can_ddl/
can_admin`, niveaux `VIEW/EDIT/MANAGE`, `OWNER`) est appliqué **avant** toute
exécution, quel que soit le moteur. Aucune opération XML ne contourne les
permissions (testé : VIEW lit, ne peut pas écrire, ni en REST ni en TCP).

## 7. CRUD / DDL / index / pagination / contraintes / FK

Toutes ces opérations passent par le moteur XML (étapes 1-13) :
`SELECT` (WHERE complet, agrégats, GROUP BY/HAVING, INNER JOIN, DISTINCT,
BETWEEN/NOT IN/NOT LIKE), `INSERT` (simple/multi/implicite), `UPDATE`,
`DELETE`, `CREATE/DROP/ALTER TABLE`, `CREATE/DROP INDEX`, `CREATE DATABASE`,
PK/UNIQUE/NOT NULL/FK (RESTRICT/CASCADE/SET NULL)/DEFAULT/AUTO_INCREMENT,
pagination (`pagination` metadata), introspection.

## 8. Comparaison SQLite/XML

`engine=compare` exécute la requête sur la projection SQLite **et** sur le
moteur XML et retourne `equivalent`, les lignes, les métriques réelles et le
`diff`. Le sens de référence est **XML → SQLite** (jamais l'inverse) : la
projection est reconstruite depuis le XML quand la synchronisation est active.

## 9. Observabilité

Chaque requête est journalisée (sans données sensibles) :

```text
[QUERY] engine=xml operation=SELECT database=1 table=books
[QUERY] engine=sqlite operation=INSERT database=1 table=books
```

## 10. Limitations

- Le **control plane** (auth, rôles, permissions, catalogue, audit, historique,
  unlocks, credentials TCP) reste sur SQLAlchemy — voir
  [SQLITE_DEPENDENCIES.md](SQLITE_DEPENDENCIES.md).
- Lecture XML en mémoire (scan + parse) ; index XML en mémoire.
- Pas de `LEFT/RIGHT/OUTER JOIN`, sous-requêtes, `UNION`, `COUNT(DISTINCT …)`.
- `SET DEFAULT` référentiel non supporté.
- En mode XML pur, `engine=sqlite` et `engine=compare` échouent (projection
  absente) — comportement attendu et explicite.

Voir aussi : [XML_ENGINE.md](backend/XML_ENGINE.md) (moteur),
[XML_ENGINE_TESTING.md](backend/XML_ENGINE_TESTING.md) (tests).
