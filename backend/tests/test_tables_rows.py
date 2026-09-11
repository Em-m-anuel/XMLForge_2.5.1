from .conftest import register_and_login, auth


def prepare_database(client, token, name="data_db"):
    database = client.post('/databases', json={"name": name}, headers=auth(token)).get_json()["data"]
    return database


def test_individual_unlock_and_relogin(client):
    alice, alice_token = register_and_login(client, "Alice", "alice@example.com")
    bob, bob_token = register_and_login(client, "Bob", "bob@example.com")
    database = prepare_database(client, alice_token)
    client.post(
        f'/databases/{database["id"]}/permissions',
        json={"user_id": bob["id"], "can_read": True, "can_write": True},
        headers=auth(alice_token),
    )
    table = client.post('/tables', json={
        "name": "locked", "database_id": database["id"], "protected": True,
        "file_identifier": "TABLE-SECRET",
    }, headers=auth(alice_token)).get_json()["data"]
    client.post('/columns', json={
        "name": "id", "type": "INTEGER", "table_id": table["id"],
        "primary_key": True, "auto_increment": True, "key_identifier": "TABLE-SECRET",
    }, headers=auth(alice_token))

    assert client.post(f'/tables/{table["id"]}/rows', json={"data": {}}, headers=auth(bob_token)).status_code == 403
    assert client.post('/unlock-table', json={"table_id": table["id"], "key_identifier": "bad"}, headers=auth(bob_token)).status_code == 403
    assert client.post('/unlock-table', json={"table_id": table["id"], "key_identifier": "TABLE-SECRET"}, headers=auth(bob_token)).status_code == 200
    assert client.post(f'/tables/{table["id"]}/rows', json={"data": {}}, headers=auth(bob_token)).status_code == 201

    relogin = client.post('/login', json={"email": "bob@example.com", "password": "secret123"})
    new_token = relogin.get_json()["data"]["access_token"]
    assert client.post(f'/tables/{table["id"]}/rows', json={"data": {}}, headers=auth(new_token)).status_code == 403
    # Le secret n'est jamais exposé dans la liste publique.
    listed = client.get(f'/tables/{database["id"]}', headers=auth(new_token)).get_json()["data"][0]
    assert "file_identifier" not in listed


def test_rows_crud_filters_sort_pagination_and_constraints(client):
    _, token = register_and_login(client, "Alice", "alice@example.com")
    database = prepare_database(client, token)
    table = client.post('/tables', json={"name": "people", "database_id": database["id"]}, headers=auth(token)).get_json()["data"]
    for payload in [
        {"name": "id", "type": "INTEGER", "primary_key": True, "auto_increment": True, "nullable": False},
        {"name": "email", "type": "VARCHAR", "nullable": False, "unique": True, "index": True},
        {"name": "age", "type": "INTEGER", "nullable": True, "default": "18"},
    ]:
        payload["table_id"] = table["id"]
        assert client.post('/columns', json=payload, headers=auth(token)).status_code == 201
    for email, age in [("b@example.com", 30), ("a@example.com", 20), ("c@example.com", 40)]:
        assert client.post(f'/tables/{table["id"]}/rows', json={"data": {"email": email, "age": age}}, headers=auth(token)).status_code == 201
    duplicate = client.post(f'/tables/{table["id"]}/rows', json={"data": {"email": "a@example.com"}}, headers=auth(token))
    assert duplicate.status_code == 400
    invalid = client.post(f'/tables/{table["id"]}/rows', json={"data": {"email": "x@example.com", "age": "not-an-int"}}, headers=auth(token))
    assert invalid.status_code == 400

    response = client.get(
        f'/tables/{table["id"]}/rows?limit=1&offset=0&sort=age&order=DESC&filters=%7B%22email%22%3A%22c%40example.com%22%7D',
        headers=auth(token),
    ).get_json()["data"]
    assert response["total"] == 1 and response["rows"][0]["data"]["age"] == 40
    row_id = response["rows"][0]["id"]
    assert client.put(f'/tables/{table["id"]}/rows/{row_id}', json={"data": {"email": "c@example.com", "age": 41}}, headers=auth(token)).status_code == 200
    assert client.delete(f'/tables/{table["id"]}/rows/{row_id}', headers=auth(token)).status_code == 200
