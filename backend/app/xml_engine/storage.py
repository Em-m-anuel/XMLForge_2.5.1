"""Verrous et I/O atomiques pour les fichiers XML (Phase 6J-B).

Primitives minimales : verrou de fichier, écriture atomique, suppression sûre.
Compatibles POSIX et Windows. Aucune dépendance SQLite.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
import threading

from ..errors import StorageError

try:  # Unix/Linux ; fallback thread-only sur Windows.
    import fcntl
except ImportError:  # pragma: no cover - attendu sous Windows
    fcntl = None

IS_WINDOWS = os.name == "nt"
WINDOWS_REPLACE_ATTEMPTS = 5
WINDOWS_REPLACE_DELAY_SECONDS = 0.05

_locks = {}
_locks_guard = threading.Lock()


def _thread_lock(key):
    with _locks_guard:
        return _locks.setdefault(key, threading.RLock())


@contextlib.contextmanager
def database_lock(lock_path):
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    lock = _thread_lock(os.path.normcase(os.path.abspath(lock_path)))
    with lock:
        handle = open(lock_path, "a+b")
        try:
            if fcntl:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            if fcntl:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()


def _is_windows_access_denied(exc):
    return isinstance(exc, PermissionError) or getattr(exc, "winerror", None) == 5


def _attempt_count():
    return WINDOWS_REPLACE_ATTEMPTS if IS_WINDOWS else 1


def _sleep_before_retry(attempt):
    import time
    time.sleep(WINDOWS_REPLACE_DELAY_SECONDS * (attempt + 1))


def safe_unlink(path, *, missing_ok=True):
    attempts = _attempt_count()
    last_error = None
    for attempt in range(attempts):
        try:
            os.unlink(path)
            return True
        except FileNotFoundError:
            if missing_ok:
                return False
            raise
        except OSError as exc:
            last_error = exc
            if not IS_WINDOWS or not _is_windows_access_denied(exc) or attempt == attempts - 1:
                raise
            _sleep_before_retry(attempt)
    if last_error:  # pragma: no cover - garde défensive
        raise last_error
    return False


def _fsync_file(path):
    try:
        with open(path, "a+b") as stream:
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        pass


def _copy_delete_fallback(source, destination):
    import shutil
    directory = os.path.dirname(destination)
    fd, copied = tempfile.mkstemp(prefix=".xmlforge-copy-", dir=directory)
    os.close(fd)
    try:
        shutil.copy2(source, copied)
        _fsync_file(copied)
        safe_unlink(destination, missing_ok=True)
        promoted = False
        for attempt in range(_attempt_count()):
            try:
                os.replace(copied, destination)
                promoted = True
                break
            except OSError as exc:
                if not IS_WINDOWS or not _is_windows_access_denied(exc) or attempt == _attempt_count() - 1:
                    raise
                _sleep_before_retry(attempt)
        if not promoted:  # pragma: no cover - garde défensive
            raise StorageError(f"Promotion de la copie impossible vers {destination}")
        safe_unlink(source, missing_ok=True)
    except Exception:
        try:
            os.unlink(copied)
        except OSError:
            pass
        raise


def safe_replace(source, destination):
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    attempts = _attempt_count()
    last_error = None
    for attempt in range(attempts):
        try:
            os.replace(source, destination)
            return
        except OSError as exc:
            last_error = exc
            if not IS_WINDOWS or not _is_windows_access_denied(exc):
                raise
            if attempt < attempts - 1:
                _sleep_before_retry(attempt)
    if IS_WINDOWS and last_error and _is_windows_access_denied(last_error):
        _copy_delete_fallback(source, destination)
        return
    if last_error:  # pragma: no cover
        raise last_error


def atomic_write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = content.encode("utf-8") if isinstance(content, str) else content
    fd, temporary = tempfile.mkstemp(prefix=".xmlforge-tmp-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        safe_replace(temporary, path)
    except Exception as exc:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise StorageError(f"Écriture atomique impossible pour {path}: {exc}") from exc
