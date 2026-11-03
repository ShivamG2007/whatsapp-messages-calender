from fastapi.testclient import TestClient

from brain.server import create_app


def test_health_and_queue(settings, processor):
    app = create_app(settings, processor=processor, start_background=False)
    client = TestClient(app)
    assert client.get("/health").json()["mode"] == "shadow"
    payload = {"id": "1", "chat_id": "c@g.us", "chat_name": "C", "sender": "A", "body": "hi", "timestamp": 1790000000}
    assert client.post("/messages", json=payload).status_code == 202
    assert app.state.inbox.qsize() == 1
    assert client.post("/messages", json={"id": "2"}).status_code == 422
