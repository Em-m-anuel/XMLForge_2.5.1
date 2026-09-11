# Guide d’exécution des tests End-to-End XMLForge

## 1. Vue d’ensemble

La suite `backend/tests/e2e/` valide XMLForge dans des conditions locales réelles, sans mock des composants métier :

- vrai serveur HTTP Werkzeug threadé sur un port local éphémère ;
- vraies requêtes HTTP JSON vers les routes Flask `/api/*` ;
- vrai serveur TCP XMLForge sur un port local éphémère ;
- vrais sockets et framing documenté dans `backend/TCP_PROTOCOL.md` ;
- vrai control plane SQLAlchemy dans un fichier SQLite ;
- vrais documents XML canoniques écrits sur disque ;
- vraies projections SQLite séparées ;
- vrais locks, threads, transactions, contraintes et erreurs réseau.

Objectif : vérifier le circuit complet, et non une fonction isolée :

```text
HTTP REST ou socket TCP
    -> authentification
    -> AccessService/permissions/protection
    -> service métier / QueryService
    -> mutation XML canonique sous verrou/version
    -> validation XSD et métier
    -> projection SQLite temporaire
    -> contraintes PK/FK/UNIQUE/NOT NULL
    -> commit atomique
    -> lecture réseau et vérification directe des fichiers
```

Les tests unitaires/intégration rapides historiques restent sous `backend/tests/`. Les tests E2E les complètent ; ils ne les remplacent pas.

---

## 2. Prérequis

### Logiciels

- Python 3.10 ou supérieur ;
- SQLite fourni avec Python ;
- environnement autorisant l’ouverture de ports TCP locaux sur `127.0.0.1` ;
- aucun serveur MySQL n’est nécessaire.

### Installation

Depuis la racine du dépôt :

```bash
python -m venv backend/.venv
source backend/.venv/bin/activate          # Linux/macOS
# backend\.venv\Scripts\activate          # Windows PowerShell
pip install -r backend/requirements.txt
```

Vérification :

```bash
python -c "import flask, sqlalchemy, lxml, pytest; print('dependencies OK')"
```

### Variables d’environnement

Aucune variable sensible ni `.env` de développement n’est requis. La fixture E2E remplace explicitement :

- `DATABASE_URL` par un fichier control plane temporaire ;
- `XML_STORAGE_FOLDER` par un dossier temporaire ;
- `SQLITE_PROJECTION_FOLDER` par un dossier temporaire ;
- `TCP_ENABLED=False` pour éviter le démarrage automatique, puis démarre elle-même un vrai serveur TCP sur port éphémère ;
- `SQLITE_BUSY_TIMEOUT_MS=50` ;
- `SQLITE_LOCK_RETRIES=20` ;
- `SQLITE_RETRY_BASE_DELAY_MS=10`.

Cela évite toute collision avec les données de développement et permet d’exercer rapidement les retries SQLite.

Ne pointez jamais ces tests vers un dossier XML ou une base de production.

---

## 3. Isolation et nettoyage

La fixture `e2e_environment` est **function-scoped** : chaque fonction de test reçoit une installation neuve dans le `tmp_path` pytest :

```text
<tmp_path>/
├── control.sqlite
├── xml/
│   └── <database_id>_<slug>.xml
└── projections/
    └── <database_id>_<slug>.sqlite
```

Pour chaque test, la fixture :

1. crée le dossier isolé ;
2. initialise l’application et applique les migrations ;
3. démarre le serveur REST réel ;
4. démarre le serveur TCP réel ;
5. exécute le scénario ;
6. arrête le serveur TCP ;
7. arrête et ferme le serveur HTTP ;
8. ferme les sessions/engines SQLite ;
9. laisse pytest supprimer le dossier temporaire.

Aucun port fixe n’est utilisé : le système d’exploitation choisit les ports libres.

### Nettoyage après interruption brutale

Normalement, aucun nettoyage manuel n’est nécessaire. Après un `kill -9` ou une panne de l’interpréteur, vérifier :

```bash
ps aux | grep -E 'pytest|xmlforge-e2e' | grep -v grep
```

Puis supprimer uniquement les dossiers temporaires pytest identifiés :

```bash
rm -rf /tmp/pytest-of-$USER/pytest-*
```

Ne supprimez pas `backend/data/xml` ou `backend/data/projections` si ceux-ci contiennent des données de développement à conserver.

---

## 4. Architecture de la suite

```text
backend/tests/e2e/
├── __init__.py
├── conftest.py
├── helpers.py
├── test_rest_xml_sqlite_e2e.py
├── test_tcp_security_permissions_e2e.py
└── test_concurrency_robustness_e2e.py
```

### `conftest.py`

- classe `ApiClient` utilisant `urllib` pour de vraies requêtes HTTP ;
- serveur Werkzeug `threaded=True` ;
- serveur `TCPServer` réel ;
- control plane SQLite fichier ;
- XML/projections fichier ;
- teardown complet.

### `helpers.py`

Helpers de scénario pour register/login, création de base/table/colonne et partage. Ils vérifient systématiquement les codes HTTP et ne remplacent aucune logique applicative.

### `test_rest_xml_sqlite_e2e.py`

Scénario complet REST :

- base COMMON ;
- tables parent/enfant ;
- colonnes PK, FK, UNIQUE, NOT NULL, DEFAULT, INDEX, AUTO_INCREMENT ;
- INSERT via query REST ;
- inspection directe du XML par XPath ;
- inspection directe SQLite par `sqlite_master` et PRAGMA ;
- violations PK, UNIQUE et FK ;
- garantie XML/version inchangés après échec ;
- erreur 409 sur version obsolète ;
- UPDATE/DELETE row ;
- rename/delete table ;
- suppression de la base et de ses artefacts.

### `test_tcp_security_permissions_e2e.py`

Scénario TCP réel :

- credentials TCP bcrypt ;
- PERSONAL non partagé refusé ;
- COMMON sans ACL non implicite ;
- ACL read/write explicite ;
- assertions directes sur `AccessService` ;
- table protégée et unlock individuel ;
- erreurs `MSG_ERROR` structurées selon `TCP_PROTOCOL.md` ;
- SELECT/INSERT/UPDATE/DELETE réels ;
- révocation ACL prise en compte dans une session déjà ouverte ;
- CLOSE et suppression de session.

### `test_concurrency_robustness_e2e.py`

Scénario concurrence/robustesse :

- cinq writers REST et cinq writers TCP libérés par la même barrière ;
- serveur Werkzeug explicitement `threaded=True` avec threads daemon ;
- timeout réseau de 90 s et timeout des futures de 120 s pour absorber la sérialisation I/O Windows sans réduire la charge ;
- contrôle des dix réponses ;
- IDs auto-increment sans doublon ;
- contrôle des dix rows dans REST, XML et SQLite ;
- deux updates REST/TCP sur la même version : exactement un succès et un conflit 409 ;
- version incrémentée une seule fois ;
- mode WAL vérifié ;
- lecture REST pendant une transaction writer SQLite ;
- contention réelle entre deux writers SQLite ;
- `busy_timeout` et reprise exponentielle réels ;
- assertion qu’au moins un `SQLITE_BUSY/locked` a eu lieu avant succès ;
- handle runtime volontairement laissé ouvert, puis fermeture automatique avant remplacement ;
- assertion que le handle résiduel est réellement fermé après la mutation.

---

## 5. Commandes d’exécution

Toutes les commandes ci-dessous sont lancées depuis la **racine du dépôt**.

### Suite E2E complète (depuis la racine du dépôt)

```bash
PYTHONPATH=backend pytest backend/tests/e2e
```

### Commande Windows demandée (depuis `backend/`)

```powershell
cd backend
python -m pytest -v tests/e2e
```

Cette commande exécute exactement les trois modules E2E. Aucun `PYTHONPATH` supplémentaire n'est nécessaire lorsque le répertoire courant est `backend`.

Le workflow `.github/workflows/backend-e2e-windows.yml` exécute cette même commande sur `windows-latest`, puis les régressions ciblées `tests/test_windows_storage.py` à chaque modification backend et à la demande (`workflow_dispatch`).

Version concise :

```bash
PYTHONPATH=backend pytest -q backend/tests/e2e
```

### Toute la suite backend, E2E incluse

```bash
PYTHONPATH=backend pytest -q backend/tests
```

### REST ↔ XML ↔ SQLite uniquement

```bash
PYTHONPATH=backend pytest -v backend/tests/e2e/test_rest_xml_sqlite_e2e.py
```

### TCP, sécurité et permissions uniquement

```bash
PYTHONPATH=backend pytest -v backend/tests/e2e/test_tcp_security_permissions_e2e.py
```

### Concurrence, WAL et robustesse uniquement

```bash
PYTHONPATH=backend pytest -v backend/tests/e2e/test_concurrency_robustness_e2e.py
```

### Un test précis

```bash
PYTHONPATH=backend pytest -v \
  backend/tests/e2e/test_concurrency_robustness_e2e.py::test_parallel_rest_tcp_writes_no_lost_rows_and_optimistic_conflict
```

### Afficher les sorties réseau/client

```bash
PYTHONPATH=backend pytest -v -s backend/tests/e2e
```

`-s` désactive la capture pytest ; utile pour observer les connexions du client TCP.

### Arrêt au premier échec

```bash
PYTHONPATH=backend pytest -x -vv backend/tests/e2e
```

### Réexécuter seulement les derniers échecs

```bash
PYTHONPATH=backend pytest --lf -vv backend/tests/e2e
```

### Dossier temporaire contrôlé pour inspection

```bash
rm -rf /tmp/xmlforge-e2e-debug
PYTHONPATH=backend pytest -vv -s \
  --basetemp=/tmp/xmlforge-e2e-debug \
  backend/tests/e2e/test_rest_xml_sqlite_e2e.py
```

Pytest nettoie normalement `--basetemp`. Pour conserver les artefacts lors d’un diagnostic, placer temporairement un breakpoint avant le teardown plutôt que de désactiver définitivement le nettoyage.

### Couverture

```bash
PYTHONPATH=backend pytest \
  --cov=app --cov-report=term-missing \
  backend/tests/e2e
```

---

## 6. Matrice de couverture fonctionnelle

| Exigence | Fichier / scénario | Vérification réelle |
|---|---|---|
| Serveur REST réel | `conftest.py` | Socket HTTP local, Werkzeug threadé, `urllib` |
| Serveur TCP réel | `conftest.py` | `TCPServer.start()` sur port OS éphémère |
| Création REST | `test_rest_xml_sqlite_e2e.py` | Base, tables, colonnes, rows |
| Modification REST | même fichier | UPDATE row et rename table |
| Suppression REST | même fichier | row, table, base et artefacts |
| Persistance XML canonique | même fichier | lecture fichier + XPath |
| Projection SQLite exacte | même fichier | SELECT direct, sqlite_master, PRAGMA |
| PRIMARY KEY | même fichier | doublon réel → 409, XML inchangé |
| FOREIGN KEY | même fichier | `foreign_key_list` + violation → 409 |
| UNIQUE | même fichier | index SQLite + doublon → 409 |
| NOT NULL/DEFAULT | même fichier | `table_info` + valeur projetée |
| AUTO_INCREMENT | REST + concurrence | IDs continus et uniques |
| INDEX | REST + concurrence | `index_list` et index nommé |
| Version/If-Match | REST + concurrence | mismatch → `SYNC_CONFLICT`/409 |
| Pas de mutation partielle | REST | comparaison byte-à-byte XML après erreurs |
| PERSONAL interdit | `test_tcp_security_permissions_e2e.py` | AUTH TCP refusé |
| COMMON + ACL | même fichier | accès seulement après grant |
| AccessService | même fichier | appels directs sur vraies entités persistées |
| Credentials TCP | même fichier | AUTH bcrypt réel |
| Table protégée | même fichier | write refusé, mauvais unlock refusé, bon unlock accepté |
| Erreur TCP structurée | même fichier | type 4, clés `code/message`, codes protocole |
| SELECT TCP | même fichier | résultat data réel |
| INSERT TCP | même fichier | row XML/SQLite réelle |
| UPDATE TCP | même fichier | compteur réel |
| DELETE TCP | même fichier | compteur réel |
| Révocation en session | même fichier | ACL supprimée → requête ouverte refusée |
| Fermeture session | même fichier | CLOSE puis session absente |
| Multi-clients REST/TCP | `test_concurrency_robustness_e2e.py` | 10 writers en parallèle |
| Pas de lost rows | même fichier | 10 réponses + 10 rows REST/XML/SQLite |
| Lost update détecté | même fichier | même version → 1 succès + 1 conflit |
| Verrou par base | même fichier | mutations concurrentes sérialisées |
| WAL | même fichier | `PRAGMA journal_mode = wal` |
| Reader pendant writer | même fichier | SELECT REST réussi sous `BEGIN IMMEDIATE` |
| busy_timeout | même fichier | connexion runtime configurée à 50 ms |
| Retries SQLite | même fichier | lock réel, nombre d’essais ≥ 2, commit final |
| Handles Windows | même fichier | connexion runtime ouverte, mutation, handle fermé avant replace |
| Retry WinError 5 | `tests/test_windows_storage.py` | 2 refus simulés puis succès, et fallback après 5 refus |
| SQLAlchemy projection | `tests/test_windows_storage.py` | Session + checkout DBAPI fermés, engine disposé, nouveau pool sur fichier promu |
| Nettoyage | `conftest.py` | stop TCP/HTTP, dispose engine, tmp_path |

---

## 7. Résultat de référence

Exécution validée au moment de la création de cette suite :

```text
PYTHONPATH=backend pytest -q backend/tests/e2e
3 passed

PYTHONPATH=backend pytest -q backend/tests
13 passed
```

Le temps dépend fortement du système de fichiers, de Windows Defender, du coût bcrypt et des scénarios de contention. Sur le dernier environnement POSIX de validation : environ 31 secondes pour E2E et 65 secondes pour toute la suite backend.

---

## 8. Diagnostic des échecs

### `Address already in use`

Les tests utilisent des ports éphémères. Cette erreur signale généralement un processus de test ancien ou une restriction système. Vérifier les processus et relancer.

### `[WinError 5] Accès refusé` pendant `os.replace`

Le backend ferme désormais toutes les connexions runtime suivies, dispose les engines de projection enregistrés, force un checkpoint WAL, supprime les sidecars `-wal/-shm`, déclenche le GC puis effectue jusqu'à cinq tentatives espacées de 50 ms. Un fallback sûr copie, fsync, supprime l'ancienne destination puis promeut la copie.

Si l'erreur persiste :

1. vérifier qu'un outil externe n'ouvre pas la projection (`DB Browser for SQLite`, antivirus, indexeur, IDE) ;
2. vérifier que tout `sqlite3.connect()` de nouveau test est utilisé avec `contextlib.closing()` ou `close()` dans un `finally` ;
3. enregistrer tout futur engine SQLAlchemy de projection avec `register_projection_engine()` ;
4. exécuter `python -m pytest -v tests/e2e/test_concurrency_robustness_e2e.py -s` depuis `backend/`.

Un handle externe inconnu ne peut pas être fermé de force sans risque ; le backend conserve alors l'ancien fichier et renvoie une erreur de stockage au lieu d'écraser une base ouverte.

### `database is locked`

Le scénario de robustesse provoque volontairement des locks, mais ils doivent être absorbés par `busy_timeout` et les retries. Un échec final peut indiquer :

- filesystem ne supportant pas correctement WAL/locks ;
- charge machine extrême ;
- paramètres de retry modifiés ;
- connexion non fermée par un nouveau code.

Lancer avec `-vv -s` et isoler le module concurrence.

### Erreur XSD/XML

Utiliser le chemin temporaire affiché par `-vv --basetemp=...`, puis :

```bash
xmllint --noout <document.xml>
```

La validation applicative complète se trouve dans `app/xml_engine/document.py`.

### Échec TCP structuré

Comparer type/code/payload avec `backend/TCP_PROTOCOL.md`. Un endpoint REST `/api/tcp/status` peut aider lors d’un lancement manuel, mais les tests interrogent directement leur fixture TCP.

---

## 9. Règles pour ajouter un scénario E2E

1. Utiliser `e2e_environment`, jamais les données locales du développeur.
2. Utiliser de vraies requêtes HTTP/TCP ; ne pas appeler directement la route testée.
3. Vérifier au moins deux niveaux : réponse réseau **et** état XML/SQLite/control plane.
4. Pour une erreur, vérifier que les artefacts précédents sont inchangés.
5. Fermer explicitement clients/sockets/connexions, même dans les branches d’erreur.
6. Ne jamais utiliser `sleep` sans borne ; préférer barrière, événement ou deadline.
7. Garder les valeurs uniques par test.
8. Documenter le nouveau scénario dans la matrice ci-dessus.
