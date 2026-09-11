"""Tests Phase 6B — modèles du Control Plane XML + XSD + validation.

Couvre : security.xsd, catalog.xsd, history.xsd, audit.xsd, records.py
(sérialisation/désérialisation), gestion NULL, unicité, keyref, fail-closed
et protection XXE.
"""

import os

import pytest

from app.errors import XmlValidationError
from app.xml_control import records as R
from app.xml_control import store
from app.xml_control.records import (
    AuditDocument, AuditRecord,
    CatalogDocument, DatabasePermissionRecord, DatabaseRecord,
    CommonPermission, HistoryDocument, HistoryRecord,
    RoleRecord, Scope, SecurityDocument, TablePermissionRecord,
    TcpCredentialRecord, UserRecord,
)

XSD_DIR = R.schema_path("security.xsd").rsplit(os.sep, 1)[0]


def schema(name):
    return os.path.join(XSD_DIR, name)


def valid_roles():
    return [RoleRecord(1, "admin", description="Administrateur XMLForge"),
            RoleRecord(2, "user", description="Utilisateur XMLForge")]


def valid_user():
    return UserRecord(1, "alice@example.com", 2, "Alice", "$2b$12$hashhashhash",
                      is_active=True, token_version=1)


def valid_security():
    return SecurityDocument(roles=valid_roles(), users=[valid_user()],
                            tcp_credentials=[TcpCredentialRecord(1, 1, "alice@example.com", "$2b$12$tcp")])


def valid_database(scope=Scope.PERSONAL, common=None, internal_id=5, key="XML-AAAA-BBBB-CCCC"):
    return DatabaseRecord(internal_id, "bibliotheque", key, 3, owner_id=3, scope=scope,
                          common_permission=common, document_version=12)


def valid_catalog():
    return CatalogDocument(
        databases=[valid_database()],
        database_permissions=[DatabasePermissionRecord(1, 5, 7, can_read=True, can_write=True)],
        table_permissions=[TablePermissionRecord(2, 12, 7, database_id=5, can_read=True)],
    )


def assert_valid(xml_bytes, xsd):
    store.validate_bytes(xml_bytes, store.cached_schema(schema(xsd)))


def assert_invalid(xml_bytes, xsd):
    with pytest.raises(XmlValidationError):
        store.validate_bytes(xml_bytes, store.cached_schema(schema(xsd)))


def xml_bytes(root_text):
    return root_text.encode("utf-8")


# --------------------------------------------------------------------------
# Chargement des XSD
# --------------------------------------------------------------------------

def test_all_xsd_loadable():
    for name in ("security.xsd", "catalog.xsd", "history.xsd", "audit.xsd"):
        store.cached_schema(schema(name))  # ne doit pas lever


# --------------------------------------------------------------------------
# SECURITY
# --------------------------------------------------------------------------

def test_security_minimal_valid():
    doc = SecurityDocument()
    assert_valid(doc.to_xml_bytes(), "security.xsd")


def test_security_two_roles_valid():
    assert_valid(valid_security().to_xml_bytes(), "security.xsd")


def test_security_roundtrip_user():
    sec = valid_security()
    back = SecurityDocument.from_xml_bytes(sec.to_xml_bytes())
    assert back.users[0].email == "alice@example.com"
    assert back.users[0].role_id == 2
    assert back.users[0].is_active is True
    assert back.users[0].token_version == 1
    assert back.users[0].password_hash == "$2b$12$hashhashhash"


def test_security_user_email_unique():
    sec = valid_security()
    sec.users.append(UserRecord(2, "alice@example.com", 2, "Autre", "$2b$"))
    assert_invalid(sec.to_xml_bytes(validate=False), "security.xsd")


def test_security_duplicate_email_detected():
    raw = b"""<security version="1">
      <roles><role internal_id="1" name="admin"/><role internal_id="2" name="user"/></roles>
      <users>
        <user internal_id="1" email="dup@example.com" role_id="2"><full_name>A</full_name><password_hash>h</password_hash></user>
        <user internal_id="2" email="dup@example.com" role_id="2"><full_name>B</full_name><password_hash>h</password_hash></user>
      </users>
      <tcp_credentials/>
    </security>"""
    assert_invalid(raw, "security.xsd")


def test_security_role_id_valid():
    assert_valid(valid_security().to_xml_bytes(), "security.xsd")


def test_security_role_id_invalid():
    raw = b"""<security version="1">
      <roles><role internal_id="1" name="admin"/><role internal_id="2" name="user"/></roles>
      <users>
        <user internal_id="1" email="a@b.c" role_id="99"><full_name>A</full_name><password_hash>h</password_hash></user>
      </users>
      <tcp_credentials/>
    </security>"""
    assert_invalid(raw, "security.xsd")


def test_security_token_version_valid():
    assert_valid(valid_security().to_xml_bytes(), "security.xsd")


def test_security_token_version_zero_accepted():
    # Cohérence avec SQLAlchemy : token_version INTEGER default=1 sans CHECK.
    # 0 est stockable (et coercé en 1 lors de la comparaison JWT via `or 1`).
    raw = valid_security().to_xml_bytes().replace(b'token_version="1"', b'token_version="0"')
    assert_valid(raw, "security.xsd")


def test_security_token_version_negative_rejected():
    raw = valid_security().to_xml_bytes().replace(b'token_version="1"', b'token_version="-1"')
    assert_invalid(raw, "security.xsd")


def test_security_tcp_credential_valid():
    sec = valid_security()
    back = SecurityDocument.from_xml_bytes(sec.to_xml_bytes())
    assert back.tcp_credentials[0].tcp_username == "alice@example.com"
    assert back.tcp_credentials[0].tcp_port == 3307


def test_security_tcp_username_unique():
    sec = valid_security()
    sec.tcp_credentials.append(TcpCredentialRecord(2, 2, "alice@example.com", "$2b$"))
    assert_invalid(sec.to_xml_bytes(validate=False), "security.xsd")


def test_security_tcp_user_id_invalid():
    sec = valid_security()
    sec.tcp_credentials.append(TcpCredentialRecord(2, 99, "bob@example.com", "$2b$"))
    assert_invalid(sec.to_xml_bytes(validate=False), "security.xsd")


def test_security_tcp_one_credential_per_user():
    sec = valid_security()
    sec.tcp_credentials.append(TcpCredentialRecord(2, 1, "other@example.com", "$2b$"))
    assert_invalid(sec.to_xml_bytes(validate=False), "security.xsd")


def test_security_tcp_port_out_of_range():
    sec = valid_security()
    sec.tcp_credentials[0].tcp_port = 70000
    assert_invalid(sec.to_xml_bytes(validate=False), "security.xsd")


def test_security_password_hash_required():
    raw = b"""<security version="1">
      <roles><role internal_id="1" name="admin"/><role internal_id="2" name="user"/></roles>
      <users>
        <user internal_id="1" email="a@b.c" role_id="2"><full_name>A</full_name></user>
      </users>
      <tcp_credentials/>
    </security>"""
    assert_invalid(raw, "security.xsd")


def test_security_no_revoked_tokens_element():
    raw = b"""<security version="1">
      <roles/><users/><tcp_credentials/>
      <revoked_tokens/>
    </security>"""
    assert_invalid(raw, "security.xsd")


def test_security_no_unlocks_element():
    raw = b"""<security version="1">
      <roles/><users/><tcp_credentials/>
      <unlocks/>
    </security>"""
    assert_invalid(raw, "security.xsd")


# --------------------------------------------------------------------------
# CATALOG
# --------------------------------------------------------------------------

def test_catalog_database_personal_valid():
    assert_valid(valid_catalog().to_xml_bytes(), "catalog.xsd")


def test_catalog_database_common_valid():
    cat = valid_catalog()
    cat.databases[0] = valid_database(scope=Scope.COMMON, common=CommonPermission.VIEW)
    assert_valid(cat.to_xml_bytes(), "catalog.xsd")


def test_catalog_common_view_edit_manage():
    for level in (CommonPermission.VIEW, CommonPermission.EDIT, CommonPermission.MANAGE):
        cat = valid_catalog()
        cat.databases[0] = valid_database(scope=Scope.COMMON, common=level)
        assert_valid(cat.to_xml_bytes(), "catalog.xsd")


def test_catalog_common_without_common_permission():
    # Règle documentée : common_permission est optionnel au niveau XSD ; la
    # valeur par défaut (VIEW) est appliquée par la couche métier.
    cat = valid_catalog()
    cat.databases[0] = valid_database(scope=Scope.COMMON, common=None)
    assert_valid(cat.to_xml_bytes(), "catalog.xsd")


def test_catalog_scope_invalid():
    raw = valid_catalog().to_xml_bytes().replace(b'scope="PERSONAL"', b'scope="PUBLIC"')
    assert_invalid(raw, "catalog.xsd")


def test_catalog_common_permission_invalid():
    cat = valid_catalog()
    cat.databases[0] = valid_database(scope=Scope.COMMON, common=None)
    raw = cat.to_xml_bytes().replace(b'scope="COMMON"', b'scope="COMMON" common_permission="OWNER"')
    assert_invalid(raw, "catalog.xsd")


def test_catalog_key_identifier_format():
    cat = valid_catalog()
    cat.databases[0].key_identifier = "ABC-1234"
    assert_invalid(cat.to_xml_bytes(validate=False), "catalog.xsd")


def test_catalog_key_identifier_unique():
    cat = valid_catalog()
    cat.databases.append(valid_database(internal_id=6, key="XML-AAAA-BBBB-CCCC"))
    assert_invalid(cat.to_xml_bytes(validate=False), "catalog.xsd")


def test_catalog_database_permission_valid():
    assert_valid(valid_catalog().to_xml_bytes(), "catalog.xsd")


def test_catalog_permission_boolean_invalid():
    raw = valid_catalog().to_xml_bytes().replace(b'can_read="true"', b'can_read="maybe"')
    assert_invalid(raw, "catalog.xsd")


def test_catalog_table_permission_valid():
    assert_valid(valid_catalog().to_xml_bytes(), "catalog.xsd")


def test_catalog_duplicate_database_permission():
    cat = valid_catalog()
    cat.database_permissions.append(DatabasePermissionRecord(3, 5, 7, can_read=True))
    assert_invalid(cat.to_xml_bytes(validate=False), "catalog.xsd")


def test_catalog_duplicate_table_permission():
    cat = valid_catalog()
    cat.table_permissions.append(TablePermissionRecord(3, 12, 7, database_id=5))
    assert_invalid(cat.to_xml_bytes(validate=False), "catalog.xsd")


def test_catalog_no_table_column_row_definitions():
    raw = valid_catalog().to_xml_bytes().replace(
        b"</catalog>",
        b"<tables><table name=\"x\"/></tables></catalog>",
    )
    assert_invalid(raw, "catalog.xsd")


def test_catalog_roundtrip_database():
    cat = valid_catalog()
    back = CatalogDocument.from_xml_bytes(cat.to_xml_bytes())
    assert back.databases[0].scope == Scope.PERSONAL
    assert back.databases[0].key_identifier == "XML-AAAA-BBBB-CCCC"
    assert back.database_permissions[0].can_write is True


# --------------------------------------------------------------------------
# HISTORY
# --------------------------------------------------------------------------

def test_history_entry_valid():
    doc = HistoryDocument(entries=[
        HistoryRecord(1, 3, "Alice", "a modifié", "base", "bibliotheque",
                      "2026-09-06T10:00:00", before_data='{"name":"a"}', after_data='{"name":"b"}'),
    ])
    assert_valid(doc.to_xml_bytes(), "history.xsd")


def test_history_null_before_after():
    doc = HistoryDocument(entries=[
        HistoryRecord(1, 3, "Alice", "a créé", "base", "bibliotheque",
                      "2026-09-06T10:00:00", before_data=None, after_data=None),
    ])
    back = HistoryDocument.from_xml_bytes(doc.to_xml_bytes())
    assert back.entries[0].before_data is None
    assert back.entries[0].after_data is None


def test_history_complex_before_after():
    complex_json = '{"rows":[1,2,3],"nested":{"k":"v"},"null":null}'
    doc = HistoryDocument(entries=[
        HistoryRecord(1, 3, "Alice", "a modifié", "base", "bibliotheque",
                      "2026-09-06T10:00:00", before_data=complex_json),
    ])
    back = HistoryDocument.from_xml_bytes(doc.to_xml_bytes())
    assert back.entries[0].before_data == complex_json


def test_history_missing_action_type_rejected():
    raw = b"""<history version="1"><entries>
      <entry internal_id="1" user_id="3" user_name="Alice" element_type="base" element_name="x" created_at="2026-09-06T10:00:00"/>
    </entries></history>"""
    assert_invalid(raw, "history.xsd")


# --------------------------------------------------------------------------
# AUDIT
# --------------------------------------------------------------------------

def test_audit_monthly_valid():
    doc = AuditDocument("2026-09", entries=[
        AuditRecord(1, "CONNEXION", "2026-09-06T10:00:00", user_id=None, meta_data='{"a":1}'),
    ])
    assert_valid(doc.to_xml_bytes(), "audit.xsd")


def test_audit_month_format():
    doc = AuditDocument("2026-09", entries=[])
    assert_valid(doc.to_xml_bytes(), "audit.xsd")
    bad = AuditDocument("2026/09", entries=[])
    assert_invalid(bad.to_xml_bytes(validate=False), "audit.xsd")


def test_audit_success_field_not_in_model():
    # "success" n'existe pas dans le modèle AuditLog réel : attribut rejeté.
    raw = b"""<audit version="1" month="2026-09"><entries>
      <entry internal_id="1" action="CONNEXION" timestamp="2026-09-06T10:00:00" success="true"/>
    </entries></audit>"""
    assert_invalid(raw, "audit.xsd")


def test_audit_action_non_empty():
    raw = b"""<audit version="1" month="2026-09"><entries>
      <entry internal_id="1" action="" timestamp="2026-09-06T10:00:00"/>
    </entries></audit>"""
    assert_invalid(raw, "audit.xsd")


def test_audit_entry_missing_timestamp_rejected():
    raw = b"""<audit version="1" month="2026-09"><entries>
      <entry internal_id="1" action="CONNEXION"/>
    </entries></audit>"""
    assert_invalid(raw, "audit.xsd")


def test_audit_roundtrip_nullable_user():
    doc = AuditDocument("2026-09", entries=[
        AuditRecord(1, "ERREUR_CONNEXION", "2026-09-06T10:00:00", user_id=None,
                    user_name=None, ip_address="127.0.0.1", meta_data='{"email":"x@y.z"}'),
    ])
    back = AuditDocument.from_xml_bytes(doc.to_xml_bytes())
    assert back.entries[0].user_id is None
    assert back.entries[0].meta_data == '{"email":"x@y.z"}'


# --------------------------------------------------------------------------
# GÉNÉRAL
# --------------------------------------------------------------------------

def test_version_required():
    raw = b"""<security><roles/><users/><tcp_credentials/></security>"""
    assert_invalid(raw, "security.xsd")


def test_version_invalid_rejected():
    raw = b"""<security version="abc"><roles/><users/><tcp_credentials/></security>"""
    assert_invalid(raw, "security.xsd")
    raw_zero = b"""<security version="0"><roles/><users/><tcp_credentials/></security>"""
    assert_invalid(raw_zero, "security.xsd")


def test_malformed_xml_rejected():
    with pytest.raises(XmlValidationError):
        store.parse_safely(b"<security><unclosed></security>")


def test_xxe_not_expanded():
    payload = (b'<?xml version="1.0"?><!DOCTYPE security [<!ENTITY xxe SYSTEM '
               b'"file:///etc/passwd">]><security version="1"><roles/><users>'
               b'<user internal_id="1" email="a@b.c" role_id="1" is_active="true" '
               b'token_version="1"><full_name>&xxe;</full_name><password_hash>x</password_hash>'
               b'</user></users><tcp_credentials/></security>')
    root = store.parse_safely(payload)
    assert "root:" not in (root.findtext("users/user/full_name") or "")


def test_validation_via_store_read_validated(tmp_path):
    path = tmp_path / "security.xml"
    store.write(str(path), valid_security().to_xml_bytes())
    root = store.read_validated(str(path), schema=schema("security.xsd"))
    assert root.tag == "security"


def test_read_validated_fails_on_invalid(tmp_path):
    path = tmp_path / "security.xml"
    store.write(str(path), b"<security><bad/></security>")
    with pytest.raises(XmlValidationError):
        store.read_validated(str(path), schema=schema("security.xsd"))


def test_null_vs_empty_string_distinction():
    # last_login absent -> None ; description vide -> "" (préservé).
    sec = SecurityDocument(roles=[RoleRecord(1, "admin")],
                           users=[UserRecord(1, "a@b.c", 1, "A", "$2b$")])
    back = SecurityDocument.from_xml_bytes(sec.to_xml_bytes())
    assert back.users[0].last_login is None
    doc = HistoryDocument(entries=[
        HistoryRecord(1, 3, "Alice", "a créé", "base", "x", "2026-09-06T10:00:00", description=""),
    ])
    back_h = HistoryDocument.from_xml_bytes(doc.to_xml_bytes())
    assert back_h.entries[0].description == ""
