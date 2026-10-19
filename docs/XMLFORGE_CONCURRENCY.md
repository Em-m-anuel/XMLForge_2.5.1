# XMLForge — Concurrence

## Modèle

XMLForge est **mono-processus** avec plusieurs connexions TCP simultanées
(threads). Les protections reposent sur :

- **verrou de fichier** par document (`fcntl.flock` + `threading.RLock`) ;
- **écriture atomique** (tempfile + `fsync` + `os.replace`) ;
- **version optimiste** (`expected_version` → `CONFLICT`) ;
- **checksum** SHA-256 ;
- **snapshot/restore** (transactions et rollback).

## Garanties

- Aucun fichier XML partiellement écrit (écriture atomique) ;
- aucune perte de mutation concurrente sur un même document (mutations
  sérialisées par le verrou du fichier) ;
- `catalog.next_object_id` et `AUTO_INCREMENT` alloués **sous verrou** : aucun
  identifiant réutilisé, même en concurrence ;
- transactions **par session** (aucun partage d'état transactionnel).

## Limites (documentées)

- Pas d'isolation multi-version (voir `XMLFORGE_TRANSACTIONS.md`) ;
- pas de transaction atomique **multi-documents** : les mutations couvrent un
  document (le Control Plane et le Data Plane sont cohérents via le miroir
  `catalog.xml`, restauré avec le snapshot au rollback) ;
- `resolve_table` par id global est en **O(nombre de bases)** (~0,4 ms/base,
  mesuré) : à optimiser si le nombre de bases devient grand.

## Tests

- 8 écritures TCP concurrentes : aucune perte, aucune corruption (Phase 7) ;
- 2/4/8/16 connexions simultanées : sessions isolées, timeouts, fermeture propre ;
- transactions concurrentes de sessions différentes.
