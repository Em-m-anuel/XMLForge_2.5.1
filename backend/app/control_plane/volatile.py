"""Stockage volatil (mémoire) des tokens révoqués — Phase 6I.

Stockage mémoire des JWT révoqués au logout (``DATA_BACKEND=xml``, seule
implémentation) : l'invalidation persistante repose sur ``user.token_version``
(décision Phase 6) ; ce store mémoire complète le logout.
"""

from __future__ import annotations

import threading
from datetime import datetime

_revoked = {}
_lock = threading.Lock()


def revoke_token(jti, expires_at):
    with _lock:
        _revoked[jti] = expires_at
        _prune()


def is_revoked(jti):
    with _lock:
        _prune()
        return jti in _revoked


def _prune():
    now = datetime.utcnow()
    for key in [k for k, v in _revoked.items() if v is not None and v < now]:
        _revoked.pop(key, None)


def clear():
    with _lock:
        _revoked.clear()
