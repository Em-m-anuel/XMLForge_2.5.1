# XMLForge — Transactions

## Syntaxe

```sql
BEGIN;
INSERT INTO accounts (name, balance) VALUES ('A', 100);
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;   -- ou ROLLBACK;
```

Alias : `START TRANSACTION` = `BEGIN`.

## Sémantique

- Une transaction appartient à une **session TCP** (jamais partagée entre
  connexions).
- `BEGIN` capture un **snapshot** du document XML de la base courante **et** du
  miroir `catalog.xml` (version/checksum).
- Les mutations sont appliquées immédiatement (écriture atomique) pendant la
  transaction.
- `COMMIT` libère le snapshot (les mutations persistent).
- `ROLLBACK` **restaure** les snapshots (les données et la version du document
  reviennent à l'état précédant `BEGIN`).
- Erreurs : `TRANSACTION_ACTIVE` (double `BEGIN`), `TRANSACTION_NOT_ACTIVE`
  (`COMMIT`/`ROLLBACK` sans transaction), `TRANSACTION_ERROR` (échec de
  restauration).

## Isolation (documenté honnêtement)

XMLForge est **mono-processus, multi-connexions**. Il n'y a **pas**
d'isolation multi-version (MVCC) :

- un lecteur peut voir les modifications non validées d'une autre connexion
  (write immediate) ;
- un `ROLLBACK` restaure l'état du document ; une écriture concurrente survenue
  entre `BEGIN` et `ROLLBACK` peut être écrasée (dernier écrivain gagnant).

Ces limites sont **assumées** et documentées ; elles ne remettent pas en cause
l'architecture XML-only. Pour les charges où ces garanties sont requises, une
sérialisation explicite (verrous applicatifs / `expected_version`) est la voie
recommandée.

## Notes

- REST est **sans état** : `BEGIN`/`COMMIT`/`ROLLBACK` y sont refusés
  (transactions réservées aux sessions TCP).
- L'audit et l'historique (append-only) **ne sont pas** annulés par un
  `ROLLBACK` : ils enregistrent ce qui a été tenté.
