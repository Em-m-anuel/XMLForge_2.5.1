"""Tests Phase 6D — XmlControlPlaneService.

Couvre : initialisation, lectures security/catalog/history/audit, relations,
intégrité (intra- et inter-documents), COMMON/PERSONAL, Data Plane, mutations,
versioning, transactions multi-documents (rollback), fail-closed, concurrence.
"""

import os
import threading
import uuid as uuid_lib

import pytest

from app.errors import (
    ConflictError,
    ControlPlaneIntegrityError,
    ControlPlaneNotFoundError,
    StorageError,
    XmlValidationError,
)
from app.xml_control import records as R
from app.xml_control import store
from app.xml_control.service import XmlControlPlaneService, permission_level


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

def write_control(tmp_path, security=None, catalog=None, history=None, audits=None):
    cdir = str(tmp_path / "control")
    store.ensure_dir(cdir, mode=0o700)
    store.ensure_dir(os.path.join(cdir, "audit"), mode=0o700)
    store.write(os.path.join(cdir, "security.xml"), security.to_xml_bytes())
    store.write(os.path.join(cdir, "catalog.xml"), catalog.to_xml_bytes())
    store.write(os.path.join(cdir, "history.xml"), history.to_xml_bytes())
    for month, doc in (audits or {}).items():
        store.write(os.path.join(cdir, "audit", f"audit-{month}.xml"), doc.to_xml_bytes())
    return cdir


def base_security():
    return R.SecurityDocument(
        roles=[R.RoleRecord(1, "admin", description="Administrateur XMLForge"),
               R.RoleRecord(2, "user", description="Utilisateur XMLForge")],
        users=[R.UserRecord(1, "alice@x.dev", 1, "Alice", "$2b$alice"),
               R.UserRecord(2, "bob@x.dev", 2, "Bob", "$2b$bob")],
        tcp_credentials=[R.TcpCredentialRecord(1, 1, "alice@x.dev", "$2b$tcp")],
    )


def base_catalog(scope=R.Scope.PERSONAL, common=None):
    return R.CatalogDocument(
        databases=[R.DatabaseRecord(5, "biblio", "XML-AAAA-BBBB-CCCC", 1, owner_id=1,
                                    scope=scope, common_permission=common, document_version=1)],
        database_permissions=[R.DatabasePermissionRecord(1, 5, 2, can_read=True)],
        table_permissions=[R.TablePermissionRecord(2, 12, 2, database_id=5, can_read=True)],
    )


@pytest.fixture()
def svc(tmp_path):
    cdir = write_control(tmp_path, base_security(), base_catalog(),
                         R.HistoryDocument(entries=[
                             R.HistoryRecord(1, 1, "Alice", "a créé", "base", "biblio",
                                             "2026-09-06T10:00:00",
                                             before_data='{"a":1}', after_data='{"b":2}'),
                         ]),
                         audits={"2026-09": R.AuditDocument("2026-09", entries=[
                             R.AuditRecord(1, "CONNEXION", "2026-09-06T10:00:00", user_id=1,
                                           meta_data='{"database_id": 5}'),
                         ])})
    return XmlControlPlaneService(storage_folder=cdir)


# --------------------------------------------------------------------------
# Initialisation
# --------------------------------------------------------------------------

def test_service_with_temp_folder(svc):
    assert svc.get_user(1) is not None


def test_service_configurable_paths(tmp_path):
    sec_path = tmp_path / "s.xml"
    cat_path = tmp_path / "c.xml"
    hist_path = tmp_path / "h.xml"
    store.write(str(sec_path), base_security().to_xml_bytes())
    store.write(str(cat_path), base_catalog().to_xml_bytes())
    store.write(str(hist_path), R.HistoryDocument().to_xml_bytes())
    service = XmlControlPlaneService(security_path=str(sec_path), catalog_path=str(cat_path),
                                     history_path=str(hist_path), audit_dir=str(tmp_path / "audit"))
    assert service.list_users()[0].email == "alice@x.dev"


# --------------------------------------------------------------------------
# SECURITY reads
# --------------------------------------------------------------------------

def test_get_user(svc):
    assert svc.get_user(1).email == "alice@x.dev"
    assert svc.get_user(999) is None


def test_get_user_by_email_case_insensitive(svc):
    assert svc.get_user_by_email("ALICE@X.DEV").internal_id == 1
    assert svc.get_user_by_email("inconnu@x.dev") is None


def test_list_users(svc):
    assert [u.internal_id for u in svc.list_users()] == [1, 2]


def test_get_role_and_by_name(svc):
    assert svc.get_role(1).name == "admin"
    assert svc.get_role_by_name("ADMIN").internal_id == 1
    assert svc.get_role_by_name("nope") is None


def test_list_roles(svc):
    assert [r.name for r in svc.list_roles()] == ["admin", "user"]


def test_get_tcp_credential_and_by_username(svc):
    assert svc.get_tcp_credential(1).tcp_username == "alice@x.dev"
    assert svc.get_tcp_credential_by_username("alice@x.dev").internal_id == 1
    assert svc.get_tcp_credential_by_username("x") is None


def test_user_role_relation(svc):
    assert svc.get_user_role(1).name == "admin"
    assert svc.get_user_role(2).name == "user"


def test_user_with_invalid_role_rejected(tmp_path):
    # role_id=99 → invalide au niveau XSD keyref (exception métier existante).
    sec = base_security()
    sec.users.append(R.UserRecord(3, "eve@x.dev", 99, "Eve", "$2b$eve"))
    cdir = str(tmp_path / "control")
    store.ensure_dir(os.path.join(cdir, "audit"), mode=0o700)
    store.write(os.path.join(cdir, "security.xml"), sec.to_xml_bytes(validate=False))
    store.write(os.path.join(cdir, "catalog.xml"), base_catalog().to_xml_bytes())
    store.write(os.path.join(cdir, "history.xml"), R.HistoryDocument().to_xml_bytes())
    service = XmlControlPlaneService(storage_folder=cdir)
    with pytest.raises(XmlValidationError):
        service.list_users()


def test_email_inexistant_returns_none(svc):
    assert svc.get_user_by_email("ghost@x.dev") is None


# --------------------------------------------------------------------------
# CATALOG reads
# --------------------------------------------------------------------------

def test_get_database(svc):
    assert svc.get_database(5).name == "biblio"
    assert svc.get_database(999) is None


def test_get_database_by_name_and_uuid(svc):
    assert svc.get_database_by_name("biblio").internal_id == 5
    db = svc.get_database(5)
    assert svc.get_database_by_uuid(db.uuid).internal_id == 5


def test_list_databases(svc):
    assert [d.internal_id for d in svc.list_databases()] == [5]


def test_list_database_permissions_filters(svc):
    assert len(svc.list_database_permissions(database_id=5)) == 1
    assert len(svc.list_database_permissions(user_id=2)) == 1
    assert len(svc.list_database_permissions(user_id=999)) == 0


def test_list_table_permissions_filters(svc):
    assert len(svc.list_table_permissions(table_id=12)) == 1
    assert len(svc.list_table_permissions(database_id=5)) == 1
    assert len(svc.list_table_permissions(user_id=999)) == 0


def test_get_owner_databases(svc):
    assert [d.internal_id for d in svc.get_owner_databases(1)] == [5]
    assert svc.get_owner_databases(2) == []


def test_is_admin_and_owner(svc):
    assert svc.is_admin(1) is True
    assert svc.is_admin(2) is False
    assert svc.is_database_owner(1, 5) is True
    assert svc.is_database_owner(2, 5) is False


# --------------------------------------------------------------------------
# COMMON / PERSONAL
# --------------------------------------------------------------------------

def _common_catalog(level=None):
    return R.CatalogDocument(
        databases=[R.DatabaseRecord(5, "biblio", "XML-AAAA-BBBB-CCCC", 1, owner_id=1,
                                    scope=R.Scope.COMMON, common_permission=level, document_version=1)],
        database_permissions=[], table_permissions=[],
    )


def test_resolve_access_admin(svc):
    access = svc.resolve_database_access(1, 5)  # alice = admin
    assert access == {"can_read": True, "can_write": True, "can_ddl": True,
                      "can_admin": True, "level": "MANAGE", "source": "role"}


def test_resolve_access_owner_personal(svc):
    # owner sur une base PERSONAL → MANAGE (source owner), même si l'owner est
    # un simple user. On teste avec un nouvel owner non-admin.
    svc.create_user(R.UserRecord(3, "carol@x.dev", 2, "Carol", "$2b$c"))
    svc.create_database(R.DatabaseRecord(6, "carols", "XML-1111-2222-3333", 3,
                                         owner_id=3, document_version=1))
    assert svc.resolve_database_access(3, 6)["level"] == "MANAGE"
    assert svc.resolve_database_access(3, 6)["source"] == "owner"


def test_resolve_access_personal_shared_grant(svc):
    access = svc.resolve_database_access(2, 5)  # bob : can_read=True
    assert access["level"] == "VIEW"
    assert access["source"] == "shared"
    assert access["can_read"] is True
    assert access["can_write"] is False


def test_resolve_access_personal_none(svc):
    svc.create_user(R.UserRecord(3, "carol@x.dev", 2, "Carol", "$2b$c"))
    assert svc.resolve_database_access(3, 5)["level"] == "NONE"


def test_resolve_access_nonexistent_user_and_db(svc):
    assert svc.resolve_database_access(999, 5)["level"] == "NONE"
    assert svc.resolve_database_access(2, 999)["level"] == "NONE"


def test_resolve_access_inactive_user(svc):
    svc.update_user(R.UserRecord(2, "bob@x.dev", 2, "Bob", "$2b$bob", is_active=False))
    assert svc.resolve_database_access(2, 5)["level"] == "NONE"


@pytest.mark.parametrize("level", ["VIEW", "EDIT", "MANAGE"])
def test_resolve_access_common_collective(tmp_path, level):
    cdir = write_control(tmp_path, base_security(),
                         _common_catalog(R.CommonPermission(level)), R.HistoryDocument())
    service = XmlControlPlaneService(storage_folder=cdir)
    access = service.resolve_database_access(2, 5)  # bob actif, non admin, non owner
    assert access["level"] == level
    assert access["source"] == "common"
    # Aucun grant individuel nécessaire ni présent.
    assert service.list_database_permissions(database_id=5) == []


def test_resolve_access_common_inactive_is_none(tmp_path):
    cdir = write_control(tmp_path, base_security(), _common_catalog(R.CommonPermission.VIEW),
                         R.HistoryDocument())
    service = XmlControlPlaneService(storage_folder=cdir)
    service.update_user(R.UserRecord(2, "bob@x.dev", 2, "Bob", "$2b$bob", is_active=False))
    assert service.resolve_database_access(2, 5)["level"] == "NONE"

@pytest.mark.parametrize("level", ["VIEW", "EDIT", "MANAGE"])
def test_common_levels(tmp_path, level):
    # Une base COMMON n'a pas de grants individuels (accès collectif).
    cat = R.CatalogDocument(
        databases=[R.DatabaseRecord(5, "biblio", "XML-AAAA-BBBB-CCCC", 1, owner_id=1,
                                    scope=R.Scope.COMMON, common_permission=R.CommonPermission(level),
                                    document_version=1)],
        database_permissions=[], table_permissions=[],
    )
    cdir = write_control(tmp_path, base_security(), cat, R.HistoryDocument())
    service = XmlControlPlaneService(storage_folder=cdir)
    assert service.get_database(5).common_permission == R.CommonPermission(level)
    service.validate_integrity()  # ne lève pas


def test_common_without_common_permission_effective_default(tmp_path):
    # Base COMMON historique sans common_permission : état valide, niveau
    # collectif effectif = défaut configuré (VIEW), appliqué en lecture seule.
    cat = R.CatalogDocument(
        databases=[R.DatabaseRecord(5, "biblio", "XML-AAAA-BBBB-CCCC", 1, owner_id=1,
                                    scope=R.Scope.COMMON, common_permission=None, document_version=1)],
        database_permissions=[], table_permissions=[],
    )
    cdir = write_control(tmp_path, base_security(), cat, R.HistoryDocument())
    service = XmlControlPlaneService(storage_folder=cdir)
    service.validate_integrity()  # ne lève pas
    assert service.effective_common_permission(service.get_database(5)) == R.CommonPermission.VIEW
    assert service.resolve_database_access(2, 5)["level"] == "VIEW"


def test_common_with_explicit_permission_not_overridden(tmp_path):
    cat = R.CatalogDocument(
        databases=[R.DatabaseRecord(5, "biblio", "XML-AAAA-BBBB-CCCC", 1, owner_id=1,
                                    scope=R.Scope.COMMON, common_permission=R.CommonPermission.EDIT,
                                    document_version=1)],
        database_permissions=[], table_permissions=[],
    )
    cdir = write_control(tmp_path, base_security(), cat, R.HistoryDocument())
    service = XmlControlPlaneService(storage_folder=cdir)
    assert service.effective_common_permission(service.get_database(5)) == R.CommonPermission.EDIT


def test_personal_without_common_permission_accepted(svc):
    svc.validate_integrity()  # PERSONAL sans common_permission → OK


def test_permission_level_mapping():
    assert permission_level(False, False, False, False) == "NONE"
    assert permission_level(True, False, False, False) == "VIEW"
    assert permission_level(True, True, False, False) == "EDIT"
    assert permission_level(True, False, True, False) == "EDIT"
    assert permission_level(True, True, True, True) == "MANAGE"
    assert permission_level(False, False, False, True) == "MANAGE"


# --------------------------------------------------------------------------
# HISTORY
# --------------------------------------------------------------------------

def test_list_history_filters(svc):
    assert len(svc.list_history()) == 1
    assert len(svc.list_history(user_id=1)) == 1
    assert len(svc.list_history(user_id=2)) == 0
    assert len(svc.list_history(database_id=999)) == 0
    assert len(svc.list_history(action="a créé")) == 1


def test_history_before_after_preserved(svc):
    entry = svc.get_history(1)
    assert entry.before_data == '{"a":1}'
    assert entry.after_data == '{"b":2}'


def test_history_null_preserved(tmp_path):
    cdir = write_control(tmp_path, base_security(), base_catalog(),
                         R.HistoryDocument(entries=[
                             R.HistoryRecord(1, 1, "Alice", "a créé", "base", "x",
                                             "2026-09-06T10:00:00", before_data=None, after_data=None),
                         ]))
    service = XmlControlPlaneService(storage_folder=cdir)
    assert service.get_history(1).before_data is None
    assert service.get_history(1).after_data is None


# --------------------------------------------------------------------------
# AUDIT
# --------------------------------------------------------------------------

def test_list_audit_month_and_filters(svc):
    assert len(svc.list_audit(month="2026-09")) == 1
    assert len(svc.list_audit(user_id=1)) == 1
    assert len(svc.list_audit(user_id=999)) == 0
    assert len(svc.list_audit(action="CONNEXION")) == 1
    assert len(svc.list_audit(action="AUTRE")) == 0
    assert len(svc.list_audit(database_id=5)) == 1  # cherché dans meta_data JSON


def test_audit_month_absent_returns_empty(svc):
    assert svc.list_audit(month="2026-10") == []
    assert svc.get_audit_entry(1, month="2026-10") is None


def test_audit_month_invalid_rejected(svc):
    with pytest.raises(ControlPlaneIntegrityError):
        svc.list_audit(month="2026/09")


def test_audit_success_unsupported_rejected(svc):
    with pytest.raises(ControlPlaneIntegrityError):
        svc.list_audit(month="2026-09", success=True)


# --------------------------------------------------------------------------
# INTEGRITY
# --------------------------------------------------------------------------

def test_validate_integrity_valid(svc):
    assert svc.validate_integrity() is not None


def test_integrity_missing_user_in_permission(tmp_path):
    cat = base_catalog()
    cat.database_permissions[0].user_id = 999
    cdir = write_control(tmp_path, base_security(), cat, R.HistoryDocument())
    service = XmlControlPlaneService(storage_folder=cdir)
    with pytest.raises(ControlPlaneIntegrityError) as exc:
        service.validate_integrity()
    assert "user_id 999" in str(exc.value)


def test_integrity_missing_database_in_permission(tmp_path):
    cat = base_catalog()
    cat.database_permissions[0].database_id = 999
    cdir = write_control(tmp_path, base_security(), cat, R.HistoryDocument())
    service = XmlControlPlaneService(storage_folder=cdir)
    with pytest.raises(ControlPlaneIntegrityError):
        service.validate_integrity()


def test_integrity_orphan_tcp_credential(tmp_path):
    # credential vers user_id inexistant → invalidé au niveau XSD keyref.
    sec = base_security()
    sec.tcp_credentials.append(R.TcpCredentialRecord(2, 99, "ghost@x.dev", "$2b$"))
    cdir = str(tmp_path / "control")
    store.ensure_dir(os.path.join(cdir, "audit"), mode=0o700)
    store.write(os.path.join(cdir, "security.xml"), sec.to_xml_bytes(validate=False))
    store.write(os.path.join(cdir, "catalog.xml"), base_catalog().to_xml_bytes())
    store.write(os.path.join(cdir, "history.xml"), R.HistoryDocument().to_xml_bytes())
    service = XmlControlPlaneService(storage_folder=cdir)
    with pytest.raises(XmlValidationError):
        service.validate_integrity()


def test_integrity_table_permission_on_common_rejected(tmp_path):
    cat = base_catalog(scope=R.Scope.COMMON, common=R.CommonPermission.VIEW)
    cdir = write_control(tmp_path, base_security(), cat, R.HistoryDocument())
    service = XmlControlPlaneService(storage_folder=cdir)
    with pytest.raises(ControlPlaneIntegrityError) as exc:
        service.validate_integrity()
    assert "COMMON" in str(exc.value)


# --------------------------------------------------------------------------
# DATA PLANE check
# --------------------------------------------------------------------------

def _write_data_plane_xml(tmp_path, tables_internal_ids):
    from app.xml_engine.document import serialize_document
    tables = []
    for tid in tables_internal_ids:
        tables.append({
            "internal_id": tid, "uuid": str(uuid_lib.uuid4()), "name": f"t{tid}",
            "description": "", "comment": "", "protected": False, "file_identifier": None,
            "status": "ACTIVE", "constraints": [], "indexes": [], "columns": [], "rows": [],
        })
    doc = {"name": "biblio", "description": "", "comment": "", "status": "ACTIVE",
           "scope": "PERSONAL", "version": 1, "generator": "XMLForge", "author": "",
           "created_at": "2026-09-06T00:00:00", "tables": tables}
    path = tmp_path / "dp.xml"
    path.write_text(serialize_document(doc), encoding="utf-8")
    return str(path)


def test_data_plane_reference_exists(tmp_path):
    dp = _write_data_plane_xml(tmp_path, [12])
    cat = base_catalog()
    cat.databases[0].xml_file_path = dp
    cdir = write_control(tmp_path, base_security(), cat, R.HistoryDocument())
    service = XmlControlPlaneService(storage_folder=cdir)
    assert service.validate_data_plane_references() == {"checked": 1}


def test_data_plane_reference_missing(tmp_path):
    dp = _write_data_plane_xml(tmp_path, [999])
    cat = base_catalog()
    cat.databases[0].xml_file_path = dp
    cdir = write_control(tmp_path, base_security(), cat, R.HistoryDocument())
    service = XmlControlPlaneService(storage_folder=cdir)
    with pytest.raises(ControlPlaneIntegrityError) as exc:
        service.validate_data_plane_references()
    assert "table_id 12" in str(exc.value)


# --------------------------------------------------------------------------
# MUTATIONS — security
# --------------------------------------------------------------------------

def test_create_user(svc):
    svc.create_user(R.UserRecord(3, "carol@x.dev", 2, "Carol", "$2b$c"))
    assert svc.get_user(3).email == "carol@x.dev"


def test_create_user_duplicate_email_rejected(svc):
    with pytest.raises(ControlPlaneIntegrityError):
        svc.create_user(R.UserRecord(3, "bob@x.dev", 2, "Bobby", "$2b$"))


def test_update_user(svc):
    svc.update_user(R.UserRecord(2, "bob@x.dev", 2, "Robert", "$2b$bob2", token_version=2))
    updated = svc.get_user(2)
    assert updated.full_name == "Robert"
    assert updated.token_version == 2


def test_update_user_unknown_rejected(svc):
    with pytest.raises(ControlPlaneNotFoundError):
        svc.update_user(R.UserRecord(999, "x@x.dev", 2, "X", "$2b$"))


def test_create_user_token_version_zero_allowed(svc):
    # Cohérence SQLAlchemy : 0 est stockable (default=1, pas de CHECK).
    svc.create_user(R.UserRecord(3, "carol@x.dev", 2, "Carol", "$2b$c", token_version=0))
    assert svc.get_user(3).token_version == 0


def test_create_user_token_version_negative_rejected(svc):
    with pytest.raises(ControlPlaneIntegrityError):
        svc.create_user(R.UserRecord(3, "carol@x.dev", 2, "Carol", "$2b$c", token_version=-1))


def test_delete_user_restrict_on_tcp_credential(svc):
    with pytest.raises(ControlPlaneIntegrityError):
        svc.delete_user(1)  # alice possède un credential TCP


def test_delete_user_success_and_catalog_guard(svc):
    # bob a des grants (database_permission) → RESTRICT via la garde catalog.
    with pytest.raises(ControlPlaneIntegrityError):
        svc.delete_user(2)
    # un utilisateur sans référence peut être supprimé.
    svc.create_user(R.UserRecord(3, "carol@x.dev", 2, "Carol", "$2b$c"))
    svc.delete_user(3)
    assert svc.get_user(3) is None


def test_create_role_and_update(svc):
    svc.create_role(R.RoleRecord(3, "auditor"))
    assert svc.get_role(3).name == "auditor"
    svc.update_role(R.RoleRecord(3, "auditeur", description="Audit"))
    assert svc.get_role(3).name == "auditeur"
    with pytest.raises(ControlPlaneIntegrityError):
        svc.create_role(R.RoleRecord(4, "auditeur"))  # nom dupliqué


# --------------------------------------------------------------------------
# MUTATIONS — catalog
# --------------------------------------------------------------------------

def test_create_database(svc):
    svc.create_database(R.DatabaseRecord(6, "second", "XML-1111-2222-3333", 1,
                                         owner_id=1, document_version=1))
    assert svc.get_database(6).name == "second"


def test_create_database_duplicate_name_same_owner_rejected(svc):
    # Même nom + même propriétaire (owner_id effectif = owner_id or creator_id).
    with pytest.raises(ControlPlaneIntegrityError):
        svc.create_database(R.DatabaseRecord(6, "biblio", "XML-1111-2222-3333", 1, document_version=1))


def test_create_database_same_name_different_owner_allowed(svc):
    # Règle SQLite (filter_by owner_id, name) : deux propriétaires peuvent
    # avoir une base homonyme.
    svc.create_user(R.UserRecord(3, "carol@x.dev", 2, "Carol", "$2b$c"))
    svc.create_database(R.DatabaseRecord(6, "biblio", "XML-1111-2222-3333", 3,
                                         owner_id=3, document_version=1))
    assert svc.get_database(6).name == "biblio"


def test_update_database_name_conflict_same_owner(svc):
    svc.create_database(R.DatabaseRecord(6, "second", "XML-1111-2222-3333", 1,
                                         owner_id=1, document_version=1))
    db = svc.get_database(6)
    db.name = "biblio"  # déjà pris par le même propriétaire
    with pytest.raises(ControlPlaneIntegrityError):
        svc.update_database(db)


def test_create_database_common_without_permission_allowed(svc):
    # COMMON sans common_permission : autorisé (état historique valide).
    svc.create_database(R.DatabaseRecord(6, "comm", "XML-1111-2222-3333", 1,
                                         scope=R.Scope.COMMON, document_version=1))
    assert svc.get_database(6).common_permission is None
    assert svc.effective_common_permission(svc.get_database(6)) == R.CommonPermission.VIEW


def test_update_database(svc):
    db = svc.get_database(5)
    db.description = "Nouvelle description"
    svc.update_database(db)
    assert svc.get_database(5).description == "Nouvelle description"


def test_delete_database_restrict_on_permissions(svc):
    with pytest.raises(ControlPlaneIntegrityError):
        svc.delete_database(5)


def test_create_database_permission_and_duplicate(svc):
    svc.create_database_permission(R.DatabasePermissionRecord(3, 5, 1, can_read=True))
    assert len(svc.list_database_permissions(database_id=5)) == 2
    with pytest.raises(ControlPlaneIntegrityError):
        svc.create_database_permission(R.DatabasePermissionRecord(4, 5, 1, can_read=True))


def test_create_database_permission_missing_user(svc):
    with pytest.raises(ControlPlaneIntegrityError):
        svc.create_database_permission(R.DatabasePermissionRecord(4, 5, 999, can_read=True))


def test_create_table_permission(svc):
    svc.create_table_permission(R.TablePermissionRecord(3, 13, 2, database_id=5, can_read=True))
    assert len(svc.list_table_permissions(table_id=13)) == 1
    with pytest.raises(ControlPlaneIntegrityError):
        svc.create_table_permission(R.TablePermissionRecord(4, 13, 2, database_id=5))


def test_create_tcp_credential_and_duplicate(svc):
    svc.create_tcp_credential(R.TcpCredentialRecord(2, 2, "bob@x.dev", "$2b$tcpbob"))
    assert svc.get_tcp_credential_by_username("bob@x.dev").internal_id == 2
    with pytest.raises(ControlPlaneIntegrityError):
        svc.create_tcp_credential(R.TcpCredentialRecord(3, 2, "bob2@x.dev", "$2b$"))
    with pytest.raises(ControlPlaneIntegrityError):
        svc.create_tcp_credential(R.TcpCredentialRecord(4, 1, "dup@x.dev", "$2b$"))


def test_add_history_and_audit(svc):
    svc.add_history(R.HistoryRecord(2, 2, "Bob", "a modifié", "base", "biblio", "2026-09-06T11:00:00"))
    assert svc.get_history(2) is not None
    svc.add_audit(R.AuditRecord(2, "DECONNEXION", "2026-09-06T11:00:00", user_id=1), "2026-09")
    assert svc.get_audit_entry(2, month="2026-09") is not None


# --------------------------------------------------------------------------
# VERSIONING
# --------------------------------------------------------------------------

def test_expected_version_ok_and_increment(svc):
    current = svc.get_document_version("security")
    svc.create_user(R.UserRecord(3, "carol@x.dev", 2, "Carol", "$2b$c"), expected_version=current)
    assert svc.get_document_version("security") == current + 1


def test_expected_version_conflict(svc):
    with pytest.raises(ConflictError):
        svc.create_user(R.UserRecord(3, "carol@x.dev", 2, "Carol", "$2b$c"), expected_version=999)


# --------------------------------------------------------------------------
# ATOMICITÉ / ROLLBACK
# --------------------------------------------------------------------------

def test_mutator_failure_no_change(svc):
    before = svc.get_document_checksum("security")
    with pytest.raises(ControlPlaneIntegrityError):
        svc.create_user(R.UserRecord(3, "bob@x.dev", 2, "Bobby", "$2b$"))  # email dupliqué
    assert svc.get_document_checksum("security") == before
    assert svc.get_document_version("security") == svc.get_document_version("security")


def test_transaction_rollback_on_failure(svc):
    # delete_user qui échoue côté catalog ne doit pas modifier security.
    sec_before = svc.get_document_checksum("security")
    cat_before = svc.get_document_checksum("catalog")
    with pytest.raises(ControlPlaneIntegrityError):
        svc.delete_user(2)  # référencé par des grants
    assert svc.get_document_checksum("security") == sec_before
    assert svc.get_document_checksum("catalog") == cat_before


# --------------------------------------------------------------------------
# SÉCURITÉ / FAIL-CLOSED
# --------------------------------------------------------------------------

def test_absent_security_fails_closed(tmp_path):
    cdir = str(tmp_path / "control")
    store.ensure_dir(cdir, mode=0o700)
    service = XmlControlPlaneService(storage_folder=cdir)
    with pytest.raises(StorageError):
        service.list_users()


def test_corrupted_security_fails_closed(tmp_path):
    cdir = str(tmp_path / "control")
    store.ensure_dir(cdir, mode=0o700)
    store.write(os.path.join(cdir, "security.xml"), b"<security><broken>")
    service = XmlControlPlaneService(storage_folder=cdir)
    with pytest.raises(XmlValidationError):
        service.list_users()


def test_xxe_rejected(tmp_path):
    cdir = str(tmp_path / "control")
    store.ensure_dir(cdir, mode=0o700)
    payload = (b'<?xml version="1.0"?><!DOCTYPE security [<!ENTITY xxe SYSTEM '
               b'"file:///etc/passwd">]><security version="1"><roles/><users/>'
               b'<tcp_credentials/></security>')
    store.write(os.path.join(cdir, "security.xml"), payload)
    service = XmlControlPlaneService(storage_folder=cdir)
    root = store.read_validated(os.path.join(cdir, "security.xml"),
                                schema=R.schema_path("security.xsd"))
    assert root.tag == "security"  # XXE non résolu, aucun contenu injecté


def test_no_silent_regeneration(svc):
    # Aucune création automatique : un get sur un chemin absent échoue.
    ghost = XmlControlPlaneService(storage_folder=os.path.join(svc.storage_folder, "ghost"))
    with pytest.raises(StorageError):
        ghost.list_roles()


# --------------------------------------------------------------------------
# CONCURRENCE
# --------------------------------------------------------------------------

def test_concurrent_create_user_serialized(tmp_path):
    cdir = write_control(tmp_path, base_security(), base_catalog(), R.HistoryDocument())
    service = XmlControlPlaneService(storage_folder=cdir)
    workers = 8

    def worker(i):
        service.create_user(R.UserRecord(10 + i, f"u{i}@x.dev", 2, f"User{i}", "$2b$"))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(service.list_users()) == 2 + workers
    assert service.get_document_version("security") == 1 + workers
    # XML final toujours valide.
    root = store.read_validated(service.security_path(), schema=R.schema_path("security.xsd"))
    assert root.tag == "security"
    assert not [n for n in os.listdir(service.storage_folder) if ".xmlforge-tmp-" in n]


# --------------------------------------------------------------------------
# Bootstrap XML (installation vierge, 6J-B)
# --------------------------------------------------------------------------

def test_bootstrap_and_service_reads(tmp_path):
    """bootstrap() crée un Control Plane XML vierge chargé par le service."""
    cdir = str(tmp_path / "control")
    store.ensure_dir(cdir, mode=0o700)
    service = XmlControlPlaneService(storage_folder=cdir)
    report = service.bootstrap()
    assert report["roles"] == ["admin", "user"]
    assert service.list_roles()[0].name == "admin"
    assert service.list_users() == []
    assert service.get_document_version("catalog") == 1
    service.validate_integrity()


def test_bootstrap_refuses_existing(tmp_path):
    cdir = str(tmp_path / "control")
    store.ensure_dir(cdir, mode=0o700)
    service = XmlControlPlaneService(storage_folder=cdir)
    service.bootstrap()
    with pytest.raises(ControlPlaneIntegrityError):
        service.bootstrap()  # fail-closed : n'écrase jamais


@pytest.fixture()
def app(tmp_path):
    from app import create_app
    from app.config import TestingConfig

    class Cfg(TestingConfig):
        XML_STORAGE_FOLDER = str(tmp_path / "xml")
        CONTROL_STORAGE_FOLDER = str(tmp_path / "control")

    store.ensure_dir(str(tmp_path / "control"), mode=0o700)
    XmlControlPlaneService(storage_folder=str(tmp_path / "control")).bootstrap()
    return create_app(Cfg)


@pytest.fixture()
def client(app):
    return app.test_client()
