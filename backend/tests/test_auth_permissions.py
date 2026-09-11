"""Tests auth + permissions (architecture XML-only, Phase 6J-B)."""

from flask_jwt_extended import create_access_token
from datetime import timedelta
from .conftest import register_and_login, auth


def test_auth_bad_password_inactive_and_logout_revocation(app, client):
    user, token = register_and_login(client, "Alice", "alice@example.com")
    assert client.post('/login', json={"email": user["email"], "password": "wrong"}).status_code == 401
    assert client.get('/me', headers=auth(token)).status_code == 200
    with app.app_context():
        expired = create_access_token(identity=str(user['id']), expires_delta=timedelta(seconds=-1),
                                      additional_claims={'token_version': 1})
    assert client.get('/me', headers=auth(expired)).status_code == 401
    assert client.post('/logout', headers=auth(token)).status_code == 200
    assert client.get('/me', headers=auth(token)).status_code == 401

    _, token2 = register_and_login(client, "Bob", "bob@example.com")
    with app.app_context():
        from app.control_plane import get_backend
        backend = get_backend()
        bob = backend.get_user_by_email("bob@example.com")
        backend.update_user_fields(bob.id, {"is_active": False, "token_version": bob.token_version + 1})
    assert client.get('/me', headers=auth(token2)).status_code == 401


def test_admin_can_create_user_with_persisted_role(app, client):
    admin, admin_token = register_and_login(client, "Platform Admin", "platform-admin@example.com")
    with app.app_context():
        from app.control_plane import get_backend
        backend = get_backend()
        admin_role = backend.get_role_by_name("admin")
        backend.update_user_fields(admin["id"], {"role_id": admin_role.id})
    response = client.post('/users', headers=auth(admin_token), json={
        "full_name": "Second Admin", "email": "second-admin@example.com",
        "password": "secret123", "role": "admin", "is_active": True,
    })
    assert response.status_code == 201, response.get_json()
    assert response.get_json()["data"]["role"] == "admin"


def test_personal_common_and_explicit_permissions(client):
    alice, alice_token = register_and_login(client, "Alice", "alice@example.com")
    bob, bob_token = register_and_login(client, "Bob", "bob@example.com")
    created = client.post('/databases', json={"name": "private_db", "scope": "PERSONAL"}, headers=auth(alice_token))
    database_id = created.get_json()["data"]["id"]
    assert client.get('/databases', headers=auth(bob_token)).get_json()["data"] == []
    assert client.put(f'/databases/{database_id}', json={"name": "stolen"}, headers=auth(bob_token)).status_code == 403

    grant = client.post(
        f'/databases/{database_id}/permissions',
        json={"user_id": bob["id"], "can_read": True, "can_write": True, "can_ddl": False},
        headers=auth(alice_token),
    )
    assert grant.status_code == 201
    assert len(client.get('/databases', headers=auth(bob_token)).get_json()["data"]) == 1
    assert client.put(f'/databases/{database_id}', json={"description": "shared"}, headers=auth(bob_token)).status_code == 200
    assert client.post('/tables', json={"name": "forbidden", "database_id": database_id}, headers=auth(bob_token)).status_code == 403


def test_common_collective_access(client):
    owner, owner_token = register_and_login(client, "Owner", "owner@example.com")
    other, other_token = register_and_login(client, "Other", "other@example.com")
    common = client.post('/databases', json={"name": "common_db", "scope": "COMMON",
                                             "common_permission": "VIEW"},
                         headers=auth(owner_token)).get_json()["data"]
    listed = {d["name"] for d in client.get('/databases', headers=auth(other_token)).get_json()["data"]}
    assert "common_db" in listed  # accès collectif automatique
    # grant individuel sur COMMON refusé
    g = client.post(f'/databases/{common["id"]}/permissions',
                    json={"user_id": other["id"], "can_read": True}, headers=auth(owner_token))
    assert g.status_code in (400, 403)
