"""Comando de acompanhamento via POST /api/chat: resposta do NEXUS deve tratar
o usuario como 'senhor' e usar o contexto mais recente (criterio #6)."""

import httpx


def test_chat_reply_uses_persona_and_context(client):
    resp = client.post(
        "/chat",
        json={"message": "NEXUS, resuma as noticias de tecnologia em uma frase."},
        timeout=httpx.Timeout(90.0),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("reply")
    reply_lower = body["reply"].lower()
    assert "senhor" in reply_lower, f"resposta nao trata como 'senhor': {body['reply'][:200]}"
    assert len(body["reply"]) > 20


def test_chat_persisted_in_memory(client):
    unique_tag = "tscheck-chat-memoria"
    resp = client.post(
        "/chat",
        json={"message": f"NEXUS, apenas confirme recebimento ({unique_tag})."},
        timeout=httpx.Timeout(90.0),
    )
    assert resp.status_code == 200, resp.text

    mem = client.get("/memory", params={"limit": 20})
    assert mem.status_code == 200, mem.text
    events = mem.json()
    assert any(unique_tag in (e.get("text") or "") for e in events), (
        "mensagem do usuario nao apareceu em /api/memory apos o chat"
    )
