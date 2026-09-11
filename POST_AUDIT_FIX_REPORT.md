# POST_AUDIT_FIX_REPORT.md

**Titre :** Post-Phase 7 audit corrections
**Date :** 2026-09-11
**Statut :** corrections P0/P1/P2 réalisées, validées, commitées.

---

## 1. Résumé

Corrections ciblées des problèmes **P0/P1/P2** identifiés dans
`PHASE_7_POST_AUDIT_REPORT.md`. **Aucune modification d'architecture** : XML-only
conservé, moteur XML natif intact, TCP 3307 intact, REST intact, client Python
intact, permissions PERSONAL/COMMON intactes, transactions intactes, aucune
technologie réintroduite.

Toutes les validations passent (voir §5) et l'état du dépôt a été **sécurisé
dans Git** (3 commits + 1 commit pour ce rapport).

---

## 2. Problèmes corrigés

| ID | Problème | Priorité | Action | Statut |
|---|---|---|---|---|
| P0-1 | Git/versionnement | P0 | 3 commits de stabilisation logiques (backend+client, frontend, docs/CI) ; `.gitignore` renforcé ; aucun secret commité ; remote absent signalé | ✅ |
| P0-2 | Identifiants en clair dans la doc | P0 | Emails/mots de passe réels remplacés par des placeholders dans 14 fichiers de doc/exemple | ✅ |
| P1-1 | CI Windows (test supprimé référencé) | P1 | Retrait de l'étape `test_windows_storage.py` ; renommage de l'étape restante | ✅ |
| P1-2 | UI « Projection SQLite » obsolète | P1 | Section/bouton/messages retirés du Workspace ; `rebuildProjection` retiré de `databaseService` ; remplacé par un indicateur « Stockage XML » | ✅ |
| P1-3 | Documentation SQL ↔ code | P1 | `XMLFORGE_SQL.md` aligné sur le parser/moteur réel (PK simple, FK inline, LIMIT=100, RIGHT/FULL non supportés) | ✅ |
| P2-1 | Fichiers legacy | P2 | Artefacts runtime SQLite obsolètes supprimés ; docs historiques conservées avec bandeau « DOCUMENT HISTORIQUE » | ✅ |
| P2-2 | Code mort | P2 | Retrait de `uses_sqlite()`, `record_divergence/divergences/clear_divergences`, `ProjectionError`, branche RIGHT/FULL inatteignable du parser | ✅ |
| P2-3 | Docstrings périmées | P2 | Docstrings SQLite/SQLAlchemy corrigées (permission_service, views, xml_engine/__init__, auth_service, xml_control/service, volatile, xml_services, routes audit/history/users) | ✅ |
| P2-4 | eventlet inutilisé | P2 | Retiré de `requirements.txt` ; serveur et tests validés sans eventlet | ✅ |
| P2-5 | README racine | P2 | `README.md` créé (porte d'entrée vers les documents détaillés) | ✅ |

---

## 3. Fichiers modifiés

### Backend — code

| Fichier | Raison | Nature |
|---|---|---|
| `backend/app/data_plane/__init__.py` | code mort | suppression de `uses_sqlite()` et de son export `__all__` |
| `backend/app/auth/decorators.py` | code mort | suppression de l'import inutilisé `uses_sqlite` |
| `backend/app/services/permission_service.py` | code mort + docstring | import `uses_sqlite` retiré ; docstring « reste en SQLite » corrigée |
| `backend/app/control_plane/base.py` | code mort | suppression de `record_divergence/divergences/clear_divergences` + imports `logging`/`threading` devenus inutiles |
| `backend/app/control_plane/__init__.py` | code mort | exports des fonctions de divergence retirés |
| `backend/app/errors.py` | code mort | suppression de `ProjectionError` (jamais levée) |
| `backend/app/query/sql_parser.py` | code mort | suppression de la branche RIGHT/FULL inatteignable |
| `backend/app/control_plane/views.py` | docstring | retrait des références aux modèles SQLAlchemy/backend SQLite |
| `backend/app/xml_engine/__init__.py` | docstring | retrait de « projection SQLite »/SQLAlchemy |
| `backend/app/services/auth_service.py` | docstring | retrait de « backend sqlite \| xml \| compare » |
| `backend/app/xml_control/service.py` | docstring | « ce service n'est pas encore utilisé » corrigé ; `next_object_id=0` → `1` ; note sur `version` de l'audit |
| `backend/app/control_plane/volatile.py` | docstring | retrait de la référence SQLAlchemy |
| `backend/app/data_plane/xml_services.py` | docstring | retrait de « services SQLite » |
| `backend/app/routes/audit.py`, `history.py`, `users.py` | docstring + identifiant | « admin only (<email historique retiré>) » → « admin uniquement » |
| `backend/requirements.txt` | dépendance inutilisée | suppression de `eventlet==0.36.1` |

### Backend — docs / exemples (identifiants)

| Fichier | Raison | Nature |
|---|---|---|
| `backend/app/tcp/SETUP.md` | identifiant | `password='pass'` → `password='<VOTRE_MOT_DE_PASSE>'` |
| `backend/app/tcp/examples.py` | identifiant | `<mot de passe retiré>` → `<VOTRE_MOT_DE_PASSE>` (8 occurrences) |
| `backend/postman_collection.json` | identifiant | `<email historique retiré>`/`<mot de passe retiré>`/`<nom d'exemple retiré>` → `admin@example.com`/`<VOTRE_MOT_DE_PASSE>`/`Admin Dev` |
| `backend/test_tcp_server.py` | identifiant | `<mot de passe retiré>` → `<VOTRE_MOT_DE_PASSE>` |
| `backend/test.xml` | identifiant | cellule `<email historique retiré>` → `admin@example.com` |
| `backend/migrations/README.md` | identifiant | `<email historique retiré>` → `admin@example.com` |
| `backend/BACKEND_DOCUMENTATION.md` | identifiant | `<email historique retiré>` → `admin@example.com` (2 occurrences) |

### Frontend

| Fichier | Raison | Nature |
|---|---|---|
| `xmlforge-react/src/pages/Workspace/Workspace.jsx` | UI obsolète | suppression de l'état `rebuilding`, du handler `handleRebuildProjection` et de la section « Projection SQLite » ; remplacement par un indicateur « Stockage XML » ; message « XML et SQLite » → « stockage XML » |
| `xmlforge-react/src/services/databaseService.js` | UI obsolète | suppression de `rebuildProjection` |
| `xmlforge-react/e2e/xmlforge.spec.js` | doc | titre « XML/SQLite » → « XML » |
| `xmlforge-react/src/pages/Login/Login.jsx` | identifiant | placeholder `ex. <domaine d'exemple retiré>` → `ex. user@example.com` |
| `xmlforge-react/src/pages/Register/Register.jsx` | identifiant | idem |
| `xmlforge-react/FRONTEND_DOCUMENTATION.md` | identifiant | « privilège basé sur <email historique retiré> » → « email magique » |
| `xmlforge-react/FRONTEND_BACKEND_INTEGRATION_REPORT.md` | identifiant | « privilège <email historique retiré> » → « email magique » |
| `xmlforge-react/TEMPLATE_ADAPTATION_REPORT.md` | identifiant | « <email historique retiré> admin » → « email admin » |

### Documentation racine / CI / config

| Fichier | Raison | Nature |
|---|---|---|
| `XMLFORGE_SQL.md` | P1-3 | matrice alignée sur le code ; section « Limites de CREATE TABLE » |
| `.github/workflows/backend-e2e-windows.yml` | P1-1 | étape `test_windows_storage.py` supprimée ; étape E2E renommée |
| `README.md` | P2-5 | créé (porte d'entrée) |
| `.gitignore` | P0-1 | ajout `backend/data/control/`, `backend/uploads/*`, `backend/exports/*`, `xmlforge-react/test-results/` |
| `XML_BACKEND_MODE.md`, `SQLITE_DEPENDENCIES.md`, `MANUEL_TEST_VALIDATION_XMLFORGE.md`, `QUICKSTART.md`, `README_TCP_COMPLETE.md` | P2-1 | bandeau « DOCUMENT HISTORIQUE » ajouté |
| `TP_JAVABD_SQL_GUIDE.md` | P0-2 | `<identifiant TCP retiré>`/`<mot de passe retiré>`/`<mot de passe retiré>` → placeholders |
| `EVOLUTIONS_V4.md` | P0-2 | `<email historique retiré>` → `admin@example.com` (5 occurrences) |
| `IMPLEMENTATION_SUMMARY.md` | P0-2 | `<email support retiré>` → `support@example.com` |
| `PHASE_7_POST_AUDIT_REPORT.md` | P0-2 | valeurs d'identifiants citées en preuve remplacées par des marqueurs de retrait |

---

## 4. Fichiers supprimés

| Fichier | Raison | Preuve d'inutilité |
|---|---|---|
| `backend/xmlforge.db` | artefact runtime SQLite (gitignoré) | ancien Control Plane SQLAlchemy ; plus aucune référence dans le code (`grep` vide) ; `file` = « SQLite 3.x database » |
| `backend/data/projections/1_schema-db.sqlite` | artefact de projection (gitignoré) | la projection SQLite a été retirée en 6J-B ; aucune référence |
| `backend/data/xml/1_schema-db.xml` + 2 fichiers `.lock` + `1_browser-…xml.lock` | résidus dev orphelins (gitignorés) | aucun `catalog.xml` ne les référence ; le Data Plane ne les lit jamais |

> Ces fichiers étaient **gitignorés** (non versionnés) : leur suppression ne crée
> aucune entrée Git, elle nettoie uniquement l'espace de travail.

### Conservés volontairement (non supprimés)

- **Fixtures de test** `secret123` (`backend/tests/*`, `tests/e2e/*`, frontend
  `e2e/xmlforge.spec.js`, `liveBackend.test.js`) — protégées par consigne
  (« ne change pas les comptes réellement utilisés par les tests »).
- **`xmlforge-react/src/context/AuthContext.test.jsx`** : mock `<email historique retiré>`
  conservé car c'est un test de non-régression du retrait de l'« email magique ».
- **Rapports Phase 4/5/6** : mentionnent des *noms de scripts* supprimés
  (`create_essoya_tcp.py`…) sans reproduire de credentials — archives conservées.
- **`javascript_cours.html`** : fichier de cours hors périmètre XMLForge, non modifié.

---

## 5. Tests (résultats réels)

| Suite | Commande | Résultat |
|---|---|---|
| Backend | `cd backend && .venv/bin/python -m pytest -q` | **334 passed in 57.67s** (0 failed) |
| E2E backend | `cd backend && .venv/bin/python -m pytest tests/e2e -q` | **1 passed** |
| Frontend | `cd xmlforge-react && npm test` | **10 passed | 1 skipped** |
| Lint | `cd xmlforge-react && npm run lint` | **0 erreur, 3 warnings** (fast-refresh, préexistants) |
| Build | `cd xmlforge-react && npm run build` | **OK** (vite 8.1.5) |
| TCP | scénario client officiel sur serveur réel | **9/9 OK** — AUTH, USE, CREATE TABLE, INSERT, SELECT, UPDATE, DELETE, BEGIN+ROLLBACK, BEGIN+COMMIT, CLOSE |
| SQLite check | `find` sur installation vierge | **0 fichier** `.db`/`.sqlite`/`.sqlite3` |
| pip check | `.venv/bin/python -m pip check` | **No broken requirements found** |
| eventlet | import + démarrage serveur | **absent, serveur fonctionnel** |

---

## 6. Git

- **Commits créés :**
  - `0f8a9d6` `chore: stabilize XML-only architecture after Phase 7` — backend XML-only, client `xmlforge/`, tests (334), suppression physique des modèles SQLAlchemy, config + `.gitignore`.
  - `11e1077` `chore(frontend): remove obsolete SQLite projection UI` — retrait de l'UI/messages SQLite, indicateur « Stockage XML ».
  - `83b9d9e` `docs: post-audit alignment — SQL doc, credentials, legacy banners, CI, root README`.
  - (+ ce rapport dans un commit dédié)
- **Branche :** `main`.
- **Remote :** `git remote -v` → **aucun remote configuré** (des refs de suivi `origin/main` orphelines subsistent dans `.git/refs/remotes/origin/`, héritées de l'ancien dépôt).
  > **Remote Git absent — configuration manuelle requise.** Aucun dépôt distant n'a
  > été créé, aucune URL inventée, aucun push effectué.
- **Working tree :** propre après les commits.
- **Identité git locale** utilisée pour les commits (config du dépôt uniquement,
  pas de `--global`) : `XMLForge Maintenance <maintenance@xmlforge.local>`.
- **Vérification pré-commit :** scan du contenu stagé (emails/mots de passe/tokens) →
  aucune valeur sensible ; aucun fichier `.db`/`.sqlite`/`.env`/`.venv`/`node_modules`
  stagé.

---

## 7. Observations hors périmètre (non corrigées)

- `USE`/`SELECT_DATABASE` vers une base inexistante renvoie `INTERNAL_ERROR`
  (générique) au lieu d'un code métier précis — classé **P3** dans l'audit,
  **non traité** conformément à la consigne.
- Duplication des URL (blueprints enregistrés à la racine **et** sous `/api`) —
  comportement de compat existant, non modifié.
- `LIMIT` implicite = 100 désormais documenté dans `XMLFORGE_SQL.md` (comportement inchangé).
- `CREATE DATABASE` SQL crée toujours une base `PERSONAL` — désormais documenté.
- Route backend `POST /databases/<id>/rebuild-projection` **conservée** (compat) :
  elle répond `{projection: "XML_ONLY"}` sans effet ; seul le frontend a été nettoyé.
- Vulnérabilités `npm audit` (2 modérées, dev-only vitest) — hors périmètre (mise
  à jour majeure requise), non traitées.

---

## 8. Critère final de réussite

```text
Architecture inchangée        ✅
XML-only conservé             ✅
TCP 3307 conservé             ✅
REST conservé                 ✅
Client Python conservé        ✅
Permissions conservées        ✅
Transactions conservées       ✅
Tests verts (334 + e2e + front) ✅
CI cohérente                  ✅
Documentation cohérente       ✅
Ancienne UI SQLite retirée    ✅
Legacy nettoyé prudemment     ✅
Git sécurisé                  ✅
```

XMLForge reste **Phase 7 + corrections post-audit**, fonctionnel exactement comme
avant les corrections.
