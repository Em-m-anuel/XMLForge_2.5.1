"""
Service Sync - XML est source de vérité
Synchronise base logique à partir du XML :
- si table n'existe pas → créer
- si table existe → mettre à jour structure (description, protected, file_identifier, comment, archived)
- si colonne n'existe pas → créer
- si colonne existe → mettre à jour type, length, nullable, pk, fk, unique, ai, default, comment
- si colonne supprimée du XML → la supprimer de la structure logique
- Sauvegarde, historique, audit, notif frontend via socket
- SQL toujours généré depuis base logique, pas directement depuis XML
"""
import uuid as uuid_lib
from ..extensions import db
from ..models.database import Database
from ..models.table import Table
from ..models.column import Column
from ..utils.helpers import now_utc
from .history_service import HistoryService
from .audit_service import AuditService
from ..socket_events import emit_modification
from .import_service import ImportService

class SyncService:

    @staticmethod
    def sync_database_from_xml(database_id, xml_content, user_id, user_name, ip_address=None, provided_key=None):
        """
        Synchronise une base existante à partir d'un XML complet
        XML peut contenir <database> avec plusieurs <table>, ou un seul <table>, ou plusieurs <table> à la racine
        Logique :
        - Parse XML V3 via ImportService._parse_xml_v3
        - Pour chaque table dans XML:
          - Si table n'existe pas dans base → créer
          - Si existe → update description, protected, file_identifier, comment, status
        - Pour chaque table, sync colonnes:
          - Si colonne n'existe pas → créer
          - Si existe → update tous les champs
          - Si colonne en DB mais pas dans XML → supprimer (spec)
        - Ne supprime PAS les tables qui ne sont plus dans XML par défaut (pour éviter perte accidentelle), sauf si option delete_tables_not_in_xml=True
        - Génère SQL depuis nouvelle structure logique
        - Historique + Audit + Socket
        """
        database = Database.query.get(database_id)
        if not database:
            return None, "Base introuvable"

        if database.is_archived():
            return None, f"Base '{database.name}' archivée, synchronisation impossible. Restaurez-la d'abord."

        # Vérifier protection ? Si base a des tables protégées, il faut clé ? Pour sync global, on vérifie si une table protégée est concernée et que clé non fournie
        # Pour simplifier, on accepte provided_key pour toutes les tables protégées concernées

        try:
            db_info, tables_data = ImportService._parse_xml_v3(xml_content)
        except Exception as e:
            return None, f"Erreur parsing XML: {e}"

        # Si database_info contient description/comment, on peut mettre à jour la base elle-même
        # Mais spec dit XML représente complètement une base, donc on peut mettre à jour description/comment de la base si fournis
        before_db = database.to_dict(include_key=True)
        updated = False
        if db_info.get('description') and db_info['description'] != database.description:
            database.description = db_info['description']
            updated = True
        if db_info.get('comment') and db_info['comment'] != database.comment:
            database.comment = db_info['comment']
            updated = True

        if updated:
            database.last_modified_by_id = user_id
            database.last_modified_by_name = user_name
            database.updated_at = now_utc()

        # Index des tables existantes par nom
        existing_tables_by_name = {t.name: t for t in Table.query.filter_by(database_id=database_id).all()}

        created_tables = 0
        updated_tables = 0
        created_columns = 0
        updated_columns = 0
        deleted_columns = 0

        # Pour générer rapport
        sync_details = []

        for t_data in tables_data:
            t_name = t_data['name']
            existing_table = existing_tables_by_name.get(t_name)

            if not existing_table:
                # Créer table
                # Vérifier si on a file_identifier et protected
                new_table = Table(
                    uuid=str(uuid_lib.uuid4()),
                    name=t_name,
                    description=t_data.get('description',''),
                    database_id=database_id,
                    creator_id=user_id,
                    is_protected=t_data.get('protected', False),
                    file_identifier=t_data.get('file_identifier'),
                    comment=t_data.get('comment',''),
                    status=t_data.get('status','ACTIVE'),
                    last_modified_by_id=user_id,
                    last_modified_by_name=user_name,
                    created_at=now_utc(),
                    updated_at=now_utc()
                )
                db.session.add(new_table)
                db.session.flush()
                created_tables += 1
                existing_table = new_table
                sync_details.append(f"Table créée: {t_name}")
            else:
                # Mettre à jour table existante
                # Vérifier protection
                if existing_table.is_protected:
                    # Besoin clé
                    valid_keys = []
                    if existing_table.file_identifier:
                        valid_keys.append(existing_table.file_identifier)
                    if database.key_identifier:
                        valid_keys.append(database.key_identifier)
                    if provided_key and provided_key not in valid_keys:
                        # Si clé invalide pour cette table protégée, on skip ou erreur
                        # On continue mais on log une erreur
                        sync_details.append(f"Table {t_name} protégée, clé invalide, mise à jour ignorée")
                        continue
                    elif not provided_key and valid_keys:
                        # Pas de clé fournie mais table protégée, on skip
                        sync_details.append(f"Table {t_name} protégée, pas de clé fournie, mise à jour ignorée")
                        continue

                # Update fields
                before_table = existing_table.to_dict()
                changed = False
                if t_data.get('description','') and t_data['description'] != existing_table.description:
                    existing_table.description = t_data['description']
                    changed = True
                if t_data.get('comment','') is not None and t_data['comment'] != existing_table.comment:
                    existing_table.comment = t_data['comment']
                    changed = True
                # protected et file_identifier depuis XML
                if 'protected' in t_data:
                    if t_data['protected'] != existing_table.is_protected:
                        existing_table.is_protected = t_data['protected']
                        changed = True
                if t_data.get('file_identifier') is not None:
                    if t_data['file_identifier'] != existing_table.file_identifier:
                        existing_table.file_identifier = t_data['file_identifier']
                        changed = True
                # status archived
                if t_data.get('status') and t_data['status'] != existing_table.status:
                    existing_table.status = t_data['status']
                    changed = True

                if changed:
                    existing_table.last_modified_by_id = user_id
                    existing_table.last_modified_by_name = user_name
                    existing_table.updated_at = now_utc()
                    updated_tables += 1
                    sync_details.append(f"Table mise à jour: {t_name}")

            # Sync colonnes pour cette table
            existing_cols_by_name = {c.name: c for c in Column.query.filter_by(table_id=existing_table.id).all()}
            xml_col_names = set()

            for col_data in t_data['columns']:
                col_name = col_data['name']
                if not col_name:
                    continue
                xml_col_names.add(col_name)
                existing_col = existing_cols_by_name.get(col_name)

                if not existing_col:
                    # Créer colonne
                    new_col = Column(
                        uuid=str(uuid_lib.uuid4()),
                        name=col_data['name'],
                        type=col_data['type'],
                        length=col_data['length'],
                        nullable=col_data['nullable'],
                        primary_key=col_data['primary_key'],
                        foreign_key=col_data['foreign_key'],
                        unique=col_data['unique'],
                        auto_increment=col_data['auto_increment'],
                        default_value=col_data['default'],
                        creator_id=user_id,
                        table_id=existing_table.id,
                        comment=col_data.get('comment',''),
                        status=col_data.get('status','ACTIVE'),
                        last_modified_by_id=user_id,
                        last_modified_by_name=user_name,
                        created_at=now_utc(),
                        updated_at=now_utc()
                    )
                    db.session.add(new_col)
                    created_columns += 1
                    sync_details.append(f"  Colonne créée: {t_name}.{col_name}")
                else:
                    # Mettre à jour colonne existante
                    before_col = existing_col.to_dict()
                    changed_col = False

                    # Comparer chaque champ et mettre à jour si différent
                    for field in ['type','length','nullable','primary_key','foreign_key','unique','auto_increment','default','comment','status']:
                        # Mapping field names
                        xml_field_map = {
                            'type': 'type',
                            'length': 'length',
                            'nullable': 'nullable',
                            'primary_key': 'primary_key',
                            'foreign_key': 'foreign_key',
                            'unique': 'unique',
                            'auto_increment': 'auto_increment',
                            'default': 'default',
                            'comment': 'comment',
                            'status': 'status'
                        }
                        # col_data keys are same as our internal
                        if field in col_data:
                            # Pour default, comparer default_value vs default
                            current_val = getattr(existing_col, 'default_value' if field=='default' else field)
                            new_val = col_data[field]
                            # Normaliser bool
                            if isinstance(current_val, bool) and isinstance(new_val, bool):
                                if current_val != new_val:
                                    changed_col = True
                                    setattr(existing_col, field if field!='default' else 'default_value', new_val)
                            else:
                                # Pour string, comparer str
                                if str(current_val or '') != str(new_val or ''):
                                    changed_col = True
                                    if field == 'default':
                                        setattr(existing_col, 'default_value', new_val)
                                    else:
                                        setattr(existing_col, field, new_val)
                        elif field == 'comment' and col_data.get('comment') is not None:
                            if existing_col.comment != col_data['comment']:
                                existing_col.comment = col_data['comment']
                                changed_col = True

                    if changed_col:
                        existing_col.last_modified_by_id = user_id
                        existing_col.last_modified_by_name = user_name
                        existing_col.updated_at = now_utc()
                        updated_columns += 1
                        sync_details.append(f"  Colonne mise à jour: {t_name}.{col_name}")

            # Suppression colonnes qui ne sont plus dans XML (spec)
            for col_name, col_obj in existing_cols_by_name.items():
                if col_name not in xml_col_names:
                    # Supprimer colonne
                    db.session.delete(col_obj)
                    deleted_columns += 1
                    sync_details.append(f"  Colonne supprimée: {t_name}.{col_name}")

        db.session.commit()

        # Mettre à jour database last_modified
        database.last_modified_by_id = user_id
        database.last_modified_by_name = user_name
        database.updated_at = now_utc()
        db.session.commit()

        after_db = database.to_dict(include_key=True)

        # Historique
        HistoryService.log(
            user_id=user_id,
            user_name=user_name,
            action_type="a synchronisé",
            element_type="base",
            element_name=database.name,
            description=f"Sync XML: {created_tables} tables créées, {updated_tables} mises à jour, {created_columns} colonnes créées, {updated_columns} mises à jour, {deleted_columns} supprimées",
            database_id=database.id,
            ip_address=ip_address,
            before=before_db,
            after=after_db
        )

        AuditService.log(
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            action="SYNC_XML",
            element_type="base",
            element_name=database.name,
            description=f"Synchronisation XML base {database.name}: {created_tables}C {updated_tables}U tables, {created_columns}C {updated_columns}U {deleted_columns}D colonnes",
            meta={"database_id": database_id, "details": sync_details}
        )

        # Notifier frontend via socket
        emit_modification("base", database.to_dict(), user_name)

        # Générer SQL depuis nouvelle structure logique (spec: SQL toujours généré depuis base logique)
        from .export_service import ExportService
        sql_content, err = ExportService.export_database_to_sql(database_id)
        if err:
            sql_content = f"-- Erreur génération SQL: {err}"

        return {
            "database": database.to_dict(include_key=True),
            "created_tables": created_tables,
            "updated_tables": updated_tables,
            "created_columns": created_columns,
            "updated_columns": updated_columns,
            "deleted_columns": deleted_columns,
            "details": sync_details,
            "sql": sql_content
        }, None
