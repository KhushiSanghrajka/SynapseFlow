import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def _wait_for_execution(client: TestClient, execution_id: str, timeout_seconds: float = 12.0):
    deadline = time.time() + timeout_seconds
    latest = None
    while time.time() < deadline:
        response = client.get(f"/api/executions/{execution_id}")
        assert response.status_code == 200
        latest = response.json()
        if latest["status"] in {"completed", "failed"}:
            return latest
        time.sleep(0.25)
    return latest


def test_agent_crud(client: TestClient):
    suffix = str(uuid.uuid4())[:8]
    payload = {
        "name": f"Test Agent {suffix}",
        "role": f"qa-role-{suffix}",
        "system_prompt": "You are a test agent.",
        "model": "openai/gpt-4.1",
        "tools": ["sanity-check"],
        "channels": ["web"],
        "memory": {},
        "guardrails": {},
    }

    create_response = client.post("/api/agents", json=payload)
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == payload["name"]

    read_response = client.get(f"/api/agents/{created['id']}")
    assert read_response.status_code == 200
    assert read_response.json()["role"] == payload["role"]

    update_response = client.put(f"/api/agents/{created['id']}", json={"role": f"updated-{suffix}"})
    assert update_response.status_code == 200
    assert update_response.json()["role"] == f"updated-{suffix}"

    delete_response = client.delete(f"/api/agents/{created['id']}")
    assert delete_response.status_code == 204

    assert client.get(f"/api/agents/{created['id']}").status_code == 404


def test_workflow_execution(client: TestClient):
    workflows_response = client.get("/api/workflows")
    assert workflows_response.status_code == 200
    workflows = workflows_response.json()
    assert workflows, "Seeded workflow expected."

    execute_response = client.post(
        "/api/executions",
        json={
            "workflow_id": workflows[0]["id"],
            "input_text": "Race update: drizzle likely in 10 laps, pace dropping on mediums.",
            "trigger_source": "test",
        },
    )
    assert execute_response.status_code == 202
    execution = execute_response.json()

    final = _wait_for_execution(client, execution["id"])
    assert final is not None
    assert final["status"] == "completed"
    assert "final_output" in final["output_payload"]
    assert isinstance(final["total_tokens"], int)


def test_inter_agent_message_delivery(client: TestClient):
    workflow_id = client.get("/api/workflows").json()[0]["id"]
    execute_response = client.post(
        "/api/executions",
        json={
            "workflow_id": workflow_id,
            "input_text": "Need F1 strategy with low risk and wet weather adaptation.",
            "trigger_source": "test",
        },
    )
    assert execute_response.status_code == 202
    execution_id = execute_response.json()["id"]

    final = _wait_for_execution(client, execution_id)
    assert final is not None
    assert final["status"] == "completed"

    messages_response = client.get(f"/api/monitoring/executions/{execution_id}/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) >= 1
