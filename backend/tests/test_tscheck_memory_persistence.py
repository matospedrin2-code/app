"""Memoria persistente: GET /api/memory ja contem eventos previos e
GET /api/briefing/latest reidrata o ultimo briefing (criterio #7)."""


def test_memory_has_seeded_events(client):
    resp = client.get("/memory")
    assert resp.status_code == 200, resp.text
    events = resp.json()
    assert isinstance(events, list)
    assert len(events) >= 11, f"esperado >=11 eventos, obtido {len(events)}"
    kinds = {e["kind"] for e in events}
    assert kinds & {"briefing", "user", "nexus"}
    for e in events:
        assert e.get("text") or e.get("cards")


def test_briefing_latest_returns_previous_briefing(client):
    resp = client.get("/briefing/latest")
    assert resp.status_code == 200, resp.text
    doc = resp.json()
    assert doc is not None
    assert doc.get("speech")
    assert "cards" in doc
