"""Run backend for E2E frontend tests — isolated XML-only"""
import os
import sys
import tempfile
import pathlib

# Ensure backend is importable
backend_root = pathlib.Path(__file__).parent.parent.parent / "XMLForge" / "backend"
sys.path.insert(0, str(backend_root))

from app import create_app
from app.config import TestingConfig
from app.xml_control import store
from app.xml_control.service import XmlControlPlaneService
from werkzeug.serving import make_server
import threading

tmp_root = tempfile.mkdtemp(prefix="xmlforge-e2e-")
xml_dir = os.path.join(tmp_root, "xml")
control_dir = os.path.join(tmp_root, "control")
store.ensure_dir(control_dir, mode=0o700)
XmlControlPlaneService(storage_folder=control_dir).bootstrap()
print(f"[E2E] tmp_root={tmp_root} control={control_dir} xml={xml_dir}")

class E2EConfig(TestingConfig):
    XML_STORAGE_FOLDER = xml_dir
    CONTROL_STORAGE_FOLDER = control_dir
    TCP_ENABLED = True
    TCP_HOST = "127.0.0.1"
    TCP_PORT = 3307
    TESTING = False
    FRONTEND_DIST_FOLDER = "/tmp/xmlforge-tests-no-frontend-dist"

app = create_app(E2EConfig)
# For shutdown test, we need real host/port
http_server = make_server("127.0.0.1", 5000, app, threaded=True)
http_server.daemon_threads = True
print(f"[E2E] HTTP 127.0.0.1:5000 TCP {app.tcp_server.host}:{app.tcp_server.port} running")

# Create admin via REST after server start in thread
def _create_admin():
    import time, json, urllib.request
    time.sleep(1.5)
    try:
        data = json.dumps({"full_name":"Admin E2E","email":"admin@xmlforge.local","password":"Admin123!"}).encode()
        req = urllib.request.Request("http://127.0.0.1:5000/api/register", data=data, headers={"Content-Type":"application/json"})
        urllib.request.urlopen(req, timeout=5).read()
        print("[E2E] admin registered")
    except Exception as e:
        print(f"[E2E] register maybe exists: {e}")
    try:
        # promote to admin via backend directly
        with app.app_context():
            from app.control_plane import get_backend
            backend = get_backend()
            user = backend.get_user_by_email("admin@xmlforge.local")
            if user:
                role = backend.get_role_by_name("admin") or backend.ensure_role("admin","Admin")
                backend.update_user_fields(user.id, {"role_id": role.id, "is_active": True})
                print("[E2E] admin promoted")
    except Exception as e:
        print(f"[E2E] promote error: {e}")

threading.Thread(target=_create_admin, daemon=True).start()

try:
    http_server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    try:
        if hasattr(app, 'tcp_server') and app.tcp_server:
            app.tcp_server.stop()
    except: pass
    http_server.shutdown()
