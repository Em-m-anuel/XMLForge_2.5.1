"""CLI d'export SQLite -> XML du Control Plane (Phase 6C).

Export déterministe : backup de ``xmlforge.db`` (copie + SHA-256), puis écriture
de ``data/control/security.xml``, ``catalog.xml``, ``history.xml`` et
``audit/audit-YYYY-MM.xml``. Ne modifie aucun comportement applicatif.

Usage :
    cd backend
    .venv/bin/python scripts/export_control_plane.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.xml_control.exporter import export_control_plane  # noqa: E402


def main():
    app = create_app(Config)
    with app.app_context():
        report = export_control_plane()
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
