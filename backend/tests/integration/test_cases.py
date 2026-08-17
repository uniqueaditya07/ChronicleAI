from fastapi.testclient import TestClient


def test_create_and_get_case(client: TestClient):
    payload = {
        "name": "Operation Bluebird",
        "description": "Cross-source chronology reconstruction",
    }
    response = client.post("/api/v1/cases", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Operation Bluebird"
    assert data["description"] == "Cross-source chronology reconstruction"
    assert data["status"] == "active"
    case_id = data["id"]

    # Fetch case by ID
    get_res = client.get(f"/api/v1/cases/{case_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["id"] == case_id
    assert get_data["name"] == "Operation Bluebird"


def test_list_cases(client: TestClient):
    client.post("/api/v1/cases", json={"name": "Case Alpha", "description": "First"})
    client.post("/api/v1/cases", json={"name": "Case Beta", "description": "Second"})

    res = client.get("/api/v1/cases")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


def test_update_case(client: TestClient):
    create_res = client.post("/api/v1/cases", json={"name": "Original Name"})
    case_id = create_res.json()["id"]

    update_res = client.patch(f"/api/v1/cases/{case_id}", json={"name": "Updated Name", "status": "archived"})
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["name"] == "Updated Name"
    assert updated_data["status"] == "archived"


def test_delete_case(client: TestClient):
    create_res = client.post("/api/v1/cases", json={"name": "To Be Deleted"})
    case_id = create_res.json()["id"]

    del_res = client.delete(f"/api/v1/cases/{case_id}")
    assert del_res.status_code == 204

    get_res = client.get(f"/api/v1/cases/{case_id}")
    assert get_res.status_code == 404
