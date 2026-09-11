# Migrations backend XMLForge

Le dépôt historique ne possédait pas Alembic et utilisait `db.create_all()` plus
deux fonctions d'ALTER ad hoc. La migration non destructive V5 est exécutée par
`app/schema_migrations.py` et enregistrée dans la table `schema_migrations`.

## V5 / V6

- ajoute `users.role_id` ;
- ajoute ownership/scope/chemins XML-projection/version/checksum/statut de sync à `databases` ;
- ajoute `columns.references`, `columns.on_delete`, `columns.on_update` et `columns.indexed` ;
- crée `roles`, `database_permissions`, `table_permissions` ;
- backfill `owner_id = creator_id` et `scope = PERSONAL` ;
- transforme uniquement l'ancien compte déjà existant `admin@example.com` en rôle admin ;
- donne le rôle `user` aux autres comptes ;
- ne supprime aucune donnée.

Les migrations destructives sont interdites dans ce runner. Une future adoption
d'Alembic pourra importer la version enregistrée comme baseline.
