def test_list_users_requires_auth(client):
    response = client.get("/users")
    assert response.status_code == 401


def test_list_users_filters_by_role(client, auth_headers):
    admin_headers = auth_headers("Administrator")
    auth_headers("Maintenance Engineer")  # creates a second user with that role

    response = client.get("/users", params={"role": "Maintenance Engineer"}, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["role_name"] == "Maintenance Engineer"
