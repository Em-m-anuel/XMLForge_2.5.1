# PHASE 6K — Stabilisation, optimisation et validation produit

**Date** : 2026-09-09

---

## 1. État initial

`PHASE_6J_XML_ONLY_COMPLETE` — 322/322 tests backend, architecture XML-only
(Control Plane + Data Plane + Query = XML ; SQLite/SQLAlchemy/projection/ORM
retirés).

## 2. Bugs trouvés et corrigés

| # | Symptôme | Cause | Correction | Test de régression |
|---|---|---|---|---|
| 1 | `DELETE /databases/<id>` d'une base **importée** (avec lignes) → 404 « Base introuvable », alors que la base est listée | dans `xml_services.delete_database`, le catalogue était supprimé **avant** le Data Plane, or `delete_storage` relit la base depuis le catalogue | ordre inversé : Data Plane d'abord, catalogue ensuite | `test_import_then_delete_after_restart` |
| 2 | `flask xml-bootstrap` échouait (« Control Plane non initialisé ») sur installation vierge | le fail-closed de `create_app` s'exécutait au chargement du CLI, avant la commande de bootstrap | le check est ignoré pour la commande `xml-bootstrap` | vérifié en installation réelle (bootstrap + create-admin) |
| 3 | erreurs 401 JWT au format `{"msg": …}` non homogène avec le reste de l'API | handlers JWT manquants | ajout `unauthorized_loader`/`expired_token_loader`/`invalid_token_loader` → format `error_response` | `test_rest_errors_are_structured_no_traceback` |
| 4 | libellé frontend COMMON obsolète (« simple filtre », « partager explicitement ») | UI non alignée sur la sémantique validée | textes corrigés + sélecteur `common_permission` (VIEW/EDIT/MANAGE) en création/édition + modale d'accès adaptée pour COMMON | build + lint frontend |

## 3–5. Tests fonctionnels / frontend / REST

- **Backend** : 325 tests (suite complète) — auth, permissions, PERSONAL/COMMON,
  CRUD, DDL, contraintes, index, schéma, audit/history, TCP, corruption,
  concurrence, rollback, persistance, installation vierge.
- **Frontend** : `vitest` 10 tests passés (services, contextes, composants) ;
  `npm run build` OK ; `npm run lint` 0 erreur (3 avertissements préexistants de
  fast-refresh).
- **Frontend ↔ backend réel** : test `liveBackend.test.js` exécuté **contre un
  serveur Flask réel** (port 5000, mode XML) — register/login, base PERSONAL
  partagée (source `shared`), base COMMON collective (source `common`), CRUD
  table/colonne/ligne, export XML, import copie, conflit `expected_version` 409.
  **Passé.**

## 6. Tests TCP

Protocole inchangé sur le port **3307** (tests sur port éphémère, port de
production configuré) : AUTH, SELECT, INSERT, UPDATE, DELETE, DDL, index,
permissions, erreurs structurées (`MSG_ERROR`). TCP et REST partagent le même
`XmlQueryService` et le même `PermissionService`.

## 7–8. Tests permissions / sécurité (6K-Q)

- PERSONAL (owner/grant), COMMON collectif (VIEW/EDIT/MANAGE), inactif/absent ;
- aucun `password_hash`/`password` exposé par `/me` et `/users` ;
- fichiers XML **non servis** en HTTP (`/data/control/security.xml`,
  `/control/*`, path traversal `..` → 404) ;
- bcrypt, JWT + `token_version`, validation XSD, verrous, atomicité conservés.

## 9–11. Tests concurrence / corruption / persistence

- 8 écritures concurrentes sans perte, IDs non réutilisés, AUTO_INCREMENT
  persistant (`next_auto_increment`), compteur global `catalog.next_object_id`
  stable après redémarrage ;
- corruption XML → fail-closed (démarrage refusé) ; rollback par snapshots ;
- redémarrage : données relues depuis XML, aucun fichier SQLite créé.

## 12. Benchmarks Data Plane (6K-J/K)

Mesures réelles (moteur XML, 3–5 itérations, médiane) :

| Lignes | taille XML | parse | serialize | INSERT (deepcopy+moteur) | SELECT WHERE |
|---|---|---|---|---|---|
| 100 | 16,0 KB | 1,3 ms | 1,6 ms | 0,6 ms | 0,49 ms |
| 500 | 76,6 KB | 5,9 ms | 7,1 ms | 2,7 ms | 2,24 ms |
| 1 000 | 152,4 KB | 12,4 ms | 14,9 ms | 5,4 ms | 4,58 ms |
| 5 000 | 770,5 KB | 67,3 ms | 79,2 ms | 27,8 ms | 23,42 ms |
| 10 000 | 1 543,1 KB | 134,6 ms | 162,1 ms | 67,3 ms | 48,49 ms |

**Profil** : coût **linéaire** dominé par le parse + la sérialisation lxml
(≈ 13–16 ms / 1000 lignes) ; l'écriture (write amplification) reste linéaire et
prévisible. Aucun goulot non-linéaire, aucun bug de performance.

## 13. Optimisations effectuées

**Aucune optimisation lourde** (décision 6K-K) : les mesures montrent un coût
linéaire prévisible sans anomalie ; l'introduction d'un cache global complexe
serait prématurée et risquerait de masquer la source de vérité XML. Limitation
documentée (voir §14).

## 14. Limitations restantes (honnêtes)

1. **Write amplification** : chaque mutation réécrit le document complet
   (~300–400 ms à 10 000 lignes, dominé par lxml). Optimisation différée
   (parsing/sérialisation incrémentaux ou segmentation XML si un besoin produit
   réel l'exige).
2. `resolve_table` par id global scanne les documents (O(bases)) — non optimisé,
   mesuré acceptable pour le volume courant.
3. `creator_id`/`created_at` des **lignes** ne sont pas persistés dans le
   document Data Plane (tables/colonnes le sont).

## 15. Architecture finale

```
Frontend (React) ── REST ── Services XMLForge
                                ├── Control Plane XML (security/catalog/history/audit)
                                └── Data Plane XML (tables/colonnes/lignes)
                                └── XML Native Engine → XML Storage → fichiers XML
TCP 3307 ───────────────────────┘  (mêmes services, mêmes permissions)
```

Aucune autre source de vérité ; aucun chemin SQLite/SQLAlchemy.

## 16. Nombre de tests

| | |
|---|---|
| tests backend avant | 322 |
| tests backend après | **325** |
| tests backend ajoutés | 3 (import+delete après restart, sécurité, erreurs structurées) |
| tests réécrits | 0 |
| tests supprimés | 0 |
| tests frontend | 10 unitaires passés + 1 live (backend réel) passé |

## 17. Compatibilité

REST, TCP 3307, frontend (build+lint+tests), XML (XSD), import/export SQL↔XML
(sans SQLite), convertisseurs : **confirmés**.

## 18. Sécurité

bcrypt, JWT + `token_version`, contrôle d'accès unique (REST+TCP), fichiers
Control Plane en 0700/0600, aucun fichier XML servi en HTTP, aucune fuite de
hash/secret, erreurs REST sans traceback, path traversal → 404.

## 19. Installation

Installation vierge démontrée (bootstrap → create-admin → REST/TCP/CRUD →
redémarrage) sans création de fichier SQLite.

## 20. Conclusion

XMLForge est stable en architecture XML-only : Control Plane, Data Plane et
moteur de requêtes sont XML ; REST, TCP 3307 et le frontend sont validés (y
compris en intégration réelle frontend↔backend) ; les bugs fonctionnels
détectés ont été corrigés avec tests de régression ; les performances sont
linéaires, mesurées et documentées sans optimisation prématurée ; la sécurité
et l'installation vierge sont vérifiées.

PHASE_6K_STABLE_COMPLETE
