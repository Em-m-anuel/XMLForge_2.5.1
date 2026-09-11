"""Tests Phase 6A — infrastructure du Control Plane XML.

Couvre : configuration (CONTROL_BACKEND…), store (lecture/écriture atomique,
verrou, version/expected_version, checksum, snapshot/restore, validation XSD,
fail-closed), et préparation du dossier de stockage.
"""

import os
import threading

import pytest
from lxml import etree

from app import create_app
from app.config import Config, TestingConfig
from app.errors import ConflictError, StorageError, XmlValidationError
from app.xml_control import store

DOC_V1 = b'<?xml version="1.0" encoding="UTF-8"?>\n<doc version="1"><items/></doc>'
DOC_V2 = b'<?xml version="1.0" encoding="UTF-8"?>\n<doc version="2"><items><item name="x"/></items></doc>'

XSD = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="doc">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="items" minOccurs="0">
          <xs:complexType>
            <xs:sequence>
              <xs:element name="item" minOccurs="0" maxOccurs="unbounded">
                <xs:complexType>
                  <xs:attribute name="name" type="xs:string" use="required"/>
                </xs:complexType>
              </xs:element>
            </xs:sequence>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
      <xs:attribute name="version" type="xs:integer" use="required"/>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def test_config_defaults_are_xml_only():
    assert Config.CONTROL_BACKEND == "xml"
    assert Config.DATA_BACKEND == "xml"
    assert Config.QUERY_BACKEND == "xml"
    assert Config.SYNC_SQLITE_PROJECTION is False


def test_common_permission_default_invalid_raises():
    class _Cfg(Config):
        COMMON_PERMISSION_DEFAULT = "OWNER"
    with pytest.raises(RuntimeError):
        _Cfg.validate()


def test_audit_retention_invalid_raises():
    class _Cfg(Config):
        AUDIT_RETENTION_MONTHS = 0
    with pytest.raises(RuntimeError):
        _Cfg.validate()


def test_create_app_creates_control_folder(tmp_path):
    from app.xml_control import store as _s
    from app.xml_control.service import XmlControlPlaneService
    control = str(tmp_path / "control")
    _s.ensure_dir(control, mode=0o700)
    XmlControlPlaneService(storage_folder=control).bootstrap()

    class Cfg(TestingConfig):
        XML_STORAGE_FOLDER = str(tmp_path / "xml")
        CONTROL_STORAGE_FOLDER = control
    app = create_app(Cfg)
    assert os.path.isdir(control)


# --------------------------------------------------------------------------
# Répertoire et permissions
# --------------------------------------------------------------------------

def test_ensure_dir_creates_tree(tmp_path):
    target = tmp_path / "a" / "b" / "control"
    store.ensure_dir(str(target))
    assert os.path.isdir(str(target))


@pytest.mark.skipif(os.name != "posix", reason="bits POSIX non applicables sous Windows")
def test_ensure_dir_posix_permissions(tmp_path):
    target = tmp_path / "control"
    store.ensure_dir(str(target), mode=0o700)
    assert (os.stat(str(target)).st_mode & 0o777) == 0o700


# --------------------------------------------------------------------------
# Écriture / lecture atomique
# --------------------------------------------------------------------------

def test_write_read_roundtrip(tmp_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), DOC_V1)
    assert store.read(str(path)) == DOC_V1


def test_write_leaves_no_temp_file(tmp_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), DOC_V1)
    leftovers = [n for n in os.listdir(str(tmp_path)) if ".xmlforge-tmp-" in n]
    assert leftovers == []


def test_read_missing_fails_closed(tmp_path):
    with pytest.raises(StorageError):
        store.read(str(tmp_path / "absent.xml"))


def test_read_validated_missing_fails_closed(tmp_path):
    with pytest.raises(StorageError):
        store.read_validated(str(tmp_path / "absent.xml"), schema=None)


def test_no_silent_regeneration_on_mutate(tmp_path):
    with pytest.raises(StorageError):
        store.mutate(str(tmp_path / "absent.xml"), lambda root: None)


# --------------------------------------------------------------------------
# Checksum
# --------------------------------------------------------------------------

def test_checksum_consistent(tmp_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), DOC_V1)
    assert store.checksum(str(path)) == store.checksum_bytes(DOC_V1)
    assert store.verify_checksum(str(path), store.checksum_bytes(DOC_V1)) is True


def test_checksum_mismatch_detected(tmp_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), DOC_V1)
    assert store.verify_checksum(str(path), store.checksum_bytes(DOC_V2)) is False


# --------------------------------------------------------------------------
# Version / expected_version
# --------------------------------------------------------------------------

def test_get_version(tmp_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), DOC_V2)
    assert store.get_version(str(path)) == 2


def test_mutate_increments_version(tmp_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), DOC_V1)

    def add(root):
        etree.SubElement(root.find("items"), "item", name="a")

    root, _ = store.mutate(str(path), add)
    assert root.get("version") == "2"
    assert store.get_version(str(path)) == 2


def test_mutate_expected_version_ok(tmp_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), DOC_V1)
    store.mutate(str(path), lambda root: None, expected_version=1)  # ne lève pas
    assert store.get_version(str(path)) == 2


def test_mutate_expected_version_conflict(tmp_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), DOC_V1)
    store.mutate(str(path), lambda root: None)  # version -> 2
    with pytest.raises(ConflictError):
        store.mutate(str(path), lambda root: None, expected_version=1)


def test_mutate_mutator_exception_writes_nothing(tmp_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), DOC_V1)

    def boom(root):
        raise ValueError("boom")

    with pytest.raises(ValueError):
        store.mutate(str(path), boom)
    assert store.get_version(str(path)) == 1
    assert store.read(str(path)) == DOC_V1


# --------------------------------------------------------------------------
# Validation XSD / fail-closed
# --------------------------------------------------------------------------

@pytest.fixture()
def xsd_path(tmp_path):
    p = tmp_path / "doc.xsd"
    p.write_text(XSD, encoding="utf-8")
    return str(p)


def test_read_validated_ok(tmp_path, xsd_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), DOC_V1)
    root = store.read_validated(str(path), schema=xsd_path)
    assert root.tag == "doc"


def test_read_validated_invalid_content(tmp_path, xsd_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), b'<?xml version="1.0"?><doc><bad/></doc>')
    with pytest.raises(XmlValidationError):
        store.read_validated(str(path), schema=xsd_path)


def test_read_validated_corrupted_xml(tmp_path, xsd_path):
    path = tmp_path / "doc.xml"
    path.write_bytes(b"<doc><unclosed></doc>")
    with pytest.raises(XmlValidationError):
        store.read_validated(str(path), schema=xsd_path)


def test_mutate_validates_before_write(tmp_path, xsd_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), DOC_V1)

    def invalid(root):
        etree.SubElement(root, "bad")

    with pytest.raises(XmlValidationError):
        store.mutate(str(path), invalid, schema=xsd_path)
    # Rien n'a été écrit : version inchangée, contenu intact.
    assert store.get_version(str(path)) == 1
    assert store.read(str(path)) == DOC_V1


# --------------------------------------------------------------------------
# Snapshot / restore
# --------------------------------------------------------------------------

def test_snapshot_restore_roundtrip(tmp_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), DOC_V1)
    snap = store.snapshot(str(path))
    store.write(str(path), DOC_V2)
    assert store.read(str(path)) == DOC_V2
    store.restore(str(path), snap)
    assert store.read(str(path)) == DOC_V1


def test_snapshot_restore_absent(tmp_path):
    path = tmp_path / "doc.xml"
    snap = store.snapshot(str(path))
    assert snap.exists is False
    store.write(str(path), DOC_V1)
    store.restore(str(path), snap)
    assert not os.path.exists(str(path))


# --------------------------------------------------------------------------
# Verrou / concurrence
# --------------------------------------------------------------------------

def test_concurrent_mutate_is_serialized(tmp_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), DOC_V1)
    workers = 8

    def worker():
        def add(root):
            etree.SubElement(root.find("items"), "item", name="x")
        store.mutate(str(path), add)

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    root = store.read_validated(str(path), schema=None)
    assert root.get("version") == str(workers + 1)
    assert len(root.find("items")) == workers


def test_lock_releases_after_mutation(tmp_path):
    path = tmp_path / "doc.xml"
    store.write(str(path), DOC_V1)
    store.mutate(str(path), lambda root: None)
    # Le verrou est libéré : une nouvelle mutation immédiate doit réussir.
    store.mutate(str(path), lambda root: None)
    assert store.get_version(str(path)) == 3
