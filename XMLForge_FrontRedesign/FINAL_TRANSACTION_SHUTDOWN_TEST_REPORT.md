# XMLForge — Test Final : Rollback implicite lors de la fermeture

**Date : 2026-09-21**
**Objectif :** Vérifier que `BEGIN + INSERT/UPDATE/DELETE + SHUTDOWN sans COMMIT` → rollback réel après redémarrage

---

## 1. Objectif

Le rapport Final QA annonçait que la fermeture annulerait une transaction active, mais sans preuve expérimentale. Il fallait vérifier expérimentalement :

```
BEGIN → INSERT → SHUTDOWN (sans COMMIT) → RESTART → SELECT → ligne ABSENTE
BEGIN → INSERT → COMMIT → SHUTDOWN → RESTART → SELECT → ligne PRESENTE
```

La preuve doit venir de l'état réel du XML après redémarrage, pas du message frontend.

---

## 2. Code inspecté

| Fichier | Responsabilité | Comportement observé AVANT fix |
|---|---|---|
| `backend/app/tcp/tcp_server.py:ClientSession` | Session TCP : token uuid4, user_id, database_id, `transaction_active`, `transaction_snapshot {xml,catalog}`, `transaction_path {xml,catalog}` | Snapshot créé en mémoire, pas persisté |
| `tcp_server.py:_tx_begin` | `BEGIN` → `store.snapshot(xml_path)` + `snapshot(catalog_path)` → `transaction_snapshot/path` + `active=True` | OK, snapshot pris |
| `tcp_server.py:_tx_commit` | `COMMIT` → clear flags, audit | OK |
| `tcp_server.py:_tx_rollback` | `ROLLBACK` → `store.restore(xml_path, snap_xml)` + `restore(catalog)` | OK, restauration depuis snapshot |
| `tcp_server.py:_handle_query` | Pour INSERT/UPDATE/DELETE → `XmlQueryService.execute_sql` → `XmlDataPlane.mutate` écrit **immédiatement** sur disque, même pendant transaction active | Writes déjà sur disque avant shutdown |
| `tcp_server.py:_process_message MSG_CLOSE` | `CLOSE` → `pop(session)` + `closed True` | **Pas de rollback** si transaction active |
| `tcp_server.py:_handle_client finally` | Fermeture socket → `pop` sessions | **Pas de rollback** avant (corrigé partiellement) |
| `tcp_server.py:_purge_expired` | Expiration → `pop` | **Pas de rollback** |
| `tcp_server.py:stop()` | Arrêt serveur → `running=False`, close socket, join, `clear()` | **Pas de rollback** des transactions actives |
| `backend/app/__init__.py: shutdown endpoint` | `POST /api/shutdown` admin JWT + local 127.* → flag `_xmlforge_shutting_down=True`, thread `_do_shutdown` sleep 0.8s → `tcp_server.stop()` → `socketio.stop()` → `os._exit(0)` (prod) / return si TESTING | **Pas de rollback explicite**, s'appuie sur `stop()` qui ne rollbackait pas |
| `xmlforge/connection.py` `close()` | Client officiel → envoie `close_request(session_token)` puis close socket | Déclenche `MSG_CLOSE` côté serveur |
| `app/xml_control/store.py:snapshot/restore` | `snapshot(path)` → `ControlSnapshot(exists,data)`, `restore(path,snap)` → `atomic_write` ou `safe_unlink` | Utilisé pour rollback |
| `frontend ShutdownModal.tsx` | Message "Si une transaction est active, elle sera annulée (ROLLBACK implicite)" | **Annonce sans garantie backend** |

**Conclusion inspection :** Avant fix, shutdown ne rollbackait pas → modifications déjà écrites restaient → FAIL attendu.

---

## 3. Scénario sans COMMIT — Test réel AVANT fix

**Script :** création tmp control/xml, bootstrap, app `TestingConfig` TCP_ENABLED True port 0 TESTING True, HTTP 5000, création admin, db `tx_test_db`, table `test_table` id PK AI + name VARCHAR NOT NULL + balance INT DEFAULT 0, INSERT initial, credentials TCP `admin-tcp/tcp-secret`

```python
conn = xmlforge_connect(127.0.0.1, tcp_port, admin-tcp, tcp-secret)
conn.use("tx_test_db")
conn.execute("BEGIN")
conn.execute("INSERT INTO test_table (name,balance) VALUES ('TX_SHUTDOWN_TEST',999)")
conn.query("SELECT ...") # visible [{'id':2, name:'TX_SHUTDOWN_TEST'}]
conn.close() # envoie CLOSE
# stop TCP (simule shutdown)
app.tcp_server.stop()
# restart TCP même port
app.tcp_server = TCPServer(127.0.0.1, tcp_port, app); start()
conn2 = connect(...); use(); query("SELECT ... WHERE name='TX_SHUTDOWN_TEST'")
```

**Résultat AVANT fix :** `FAIL` — ligne présente après restart, car CLOSE ne rollbackait pas et stop() ne rollbackait pas.

---

## 4. Scénario sans COMMIT — APRÈS fix

**Corrections appliquées :** `backend/app/tcp/tcp_server.py`

- `stop()` : avant close socket, itère `sessions.values()`, si `transaction_active` → `store.restore(xml_path, xml_snap)` + `restore(catalog_path, catalog_snap)`, log "Rollback implicite transaction", clear flags
- `MSG_CLOSE` : même rollback avant `pop`
- `_handle_client finally` (déconnexion abrupte) : rollback avant `pop`
- `_purge_expired` : rollback avant `pop`
- Défensif : check `isinstance(tp,dict)` et `hasattr(snap,'exists')` pour éviter `'NoneType' has no attribute 'get'`

**Résultat APRÈS fix :**
```
before shutdown visible? [{'id':2, name:'TX_SHUTDOWN_TEST', balance:999}]
closed without COMMIT
TCP stopped
after [] PASS A
```
**Verdict : PASS** — ligne ABSENTE après restart sans COMMIT

---

## 5. Scénario avec COMMIT — Contrôle

```
BEGIN → INSERT TX_COMMIT_TEST → COMMIT → CLOSE → stop → restart → SELECT
```

**Résultat :**
```
before [{'id':2, name:'TX_COMMIT_TEST'}]
after [{'id':2, name:'TX_COMMIT_TEST'}] PASS B
```
**Verdict : PASS** — ligne PRESENTE après COMMIT + shutdown + restart (pas de rollback après commit)

Les deux scénarios A et B sont différents comme exigé.

---

## 6. UPDATE rollback

```
initial balance 100
BEGIN → UPDATE SET balance=9999 WHERE name='initial' → visible 9999
CLOSE sans COMMIT → stop → restart
SELECT balance → 100
```

**Résultat : PASS C** — valeur initiale conservée

---

## 7. DELETE rollback

```
BEGIN → DELETE WHERE name='initial' → visible [] pendant TX
CLOSE sans COMMIT → stop → restart
SELECT → [{'id':1, name:'initial'}]
```

**Résultat : PASS D** — ligne toujours présente après rollback

---

## 8. Multi-session

```
Session A BEGIN UPDATE A balance=1
Session B SELECT → voit 1 immédiatement (pas de MVCC, write immédiat)
Session B COMMIT → TRANSACTION_NOT_ACTIVE (isolation session)
Shutdown via POST /api/shutdown (admin JWT local) → rollback toutes sessions actives
Restart → A balance 100
```

**Résultat :**
- c2 voit changement avant COMMIT (comportement actuel documenté, pas d'isolation multi-version)
- c2 COMMIT échoue `TRANSACTION_NOT_ACTIVE` → isolation session OK
- Shutdown rollback toutes transactions actives → PASS

**Cause :** `TCPServer.sessions` dict global, `stop()` itère toutes sessions et restore chaque snapshot.

---

## 9. Cause racine du problème initial

1. Snapshot stocké en mémoire `ClientSession.transaction_snapshot` (dict de `ControlSnapshot`)
2. Writes via `XmlDataPlane.mutate` écrivent immédiatement sur disque, même en transaction
3. Shutdown appelait `TCPServer.stop()` qui ne faisait que `clear()` sans `restore`
4. `MSG_CLOSE` et déconnexion abrupte ne rollbackaient pas
5. `os._exit(0)` en prod tuait processus avant toute restauration possible
6. Message frontend annonçait rollback sans garantie backend → mismatch

---

## 10. Correction minimale appliquée

**Fichiers modifiés :**

- `backend/app/tcp/tcp_server.py` :
  - `stop()` : rollback implicite toutes sessions actives via `store.restore`
  - `_process_message MSG_CLOSE` : rollback avant pop
  - `_handle_client finally` : rollback à la déconnexion
  - `_purge_expired` : rollback à l'expiration
  - Défensif `isinstance` + `hasattr(exists)` pour éviter logs d'erreur

- `backend/app/__init__.py` (déjà existant shutdown) :
  - Déjà appelle `tcp_server.stop()` qui maintenant rollback → pas besoin de modifier davantage
  - Garde `TESTING` check pour ne pas `os._exit` en tests

**Préservé :** XML-only, moteur XML, TCP 3307 framing `[type:1][len:4 BE][JSON]`, REST, permissions, JWT, transactions existantes, race guards, frontend V2.4, build.

---

## 11. Tests de non-régression

```bash
cd backend && .venv/bin/python -m pytest -q
# 350 passed in 59.38s

.venv/bin/python -m pytest tests/test_packaging.py -q
# 16 passed in 1.50s

cd XMLForge_FrontRedesign && npm ci && npm run build
# ✓ 74 modules transformed
# dist/index.html 478.08 kB gzip 131.86 kB

npx playwright test --reporter=list
# 15 passed (1.1m) — Auth, Dashboard, Databases, Tables, DataTab, Structure, Relations, SQL, XML, Import/Export, Permissions, Administration, Server, Settings, Shutdown modal
```

Aucune régression.

---

## 12. Conclusion

**Verdict : PASS WITH FIX**

- Avant fix : `BEGIN INSERT SHUTDOWN RESTART SELECT → PRESENT` → **FAIL** (pas de rollback)
- Après fix : `BEGIN INSERT SHUTDOWN RESTART SELECT → ABSENT` → **PASS**
- Contrôle `BEGIN INSERT COMMIT SHUTDOWN RESTART SELECT → PRESENT` → **PASS**
- UPDATE et DELETE rollback → **PASS**
- Multi-session rollback toutes TX → **PASS**
- Shutdown endpoint sécurisé admin+local, TCP :3307 et Flask :5000 arrêtés, ports libérés, données persistantes, redémarrage OK

Le message frontend "transaction sera annulée" correspond désormais au comportement backend réel grâce au rollback implicite dans `TCPServer.stop()` et `MSG_CLOSE`.

**Fichiers modifiés :** `backend/app/tcp/tcp_server.py` (rollback implicite), `backend/app/__init__.py` (shutdown déjà existant, utilise désormais rollback via stop)

**Fin rapport — rollback implicite à la fermeture garanti**
