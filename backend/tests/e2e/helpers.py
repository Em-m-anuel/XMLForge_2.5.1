"""Helpers de scénarios E2E, sans mock applicatif."""
from __future__ import annotations


def create_user(api, name, email, password="secret123"):
    user = api.register(name, email, password)
    token, logged_user = api.login(email, password)
    assert logged_user["id"] == user["id"]
    return user, token


def create_database(api, token, name, scope="PERSONAL", common_permission=None):
    payload = {"name": name, "scope": scope}
    if common_permission is not None:
        payload["common_permission"] = common_permission
    response = api.request("POST", "/api/databases", token=token, payload=payload)
    assert response.status_code == 201, response.json
    return response.json["data"]


def create_table(api, token, database_id, name, **extra):
    payload = {"name": name, "database_id": database_id, **extra}
    response = api.request("POST", "/api/tables", token=token, payload=payload)
    assert response.status_code == 201, response.json
    return response.json["data"]


def create_column(api, token, table_id, name, column_type, **extra):
    payload = {"name": name, "type": column_type, "table_id": table_id, **extra}
    response = api.request("POST", "/api/columns", token=token, payload=payload)
    assert response.status_code == 201, response.json
    return response.json["data"]


def grant_database(api, owner_token, database_id, user_id, **rights):
    response = api.request(
        "POST", f"/api/databases/{database_id}/permissions", token=owner_token,
        payload={"user_id": user_id, **rights},
    )
    assert response.status_code == 201, response.json
    return response.json["data"]
