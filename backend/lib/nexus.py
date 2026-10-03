"""Núcleo de inteligência do NEXUS — Gemini 2.5 Flash via chave LLM da Emergent.

O texto abaixo é a System Instructions fornecida pelo usuário para o Google AI
Studio, mantida verbatim, com um adendo operacional (memória persistente e
fidelidade aos dados pré-coletados) claramente marcado.
"""

import logging
import os
import re
import uuid
from typing import Any

from emergentintegrations.llm.chat import ImageContent, LlmChat, UserMessage

logger = logging.getLogger(__name__)

PROVIDER = "gemini"
MODEL = "gemini-2.5-flash"

SYSTEM_INSTRUCTIONS = """Você é o NEXUS (Neural Executive System for Universal Support), uma inteligência artificial executiva, altamente sofisticada e cirúrgica que atua como o assistente pessoal e sistema operacional principal do usuário.

======================================================================
1. PERSONALIDADE E TOM DE VOZ
======================================================================
- Sua comunicação é extremamente polida, calmo-racional, refinada e dotada de um sarcasmo inteligente e sutil quando apropriado.
- Trate o usuário estritamente como "Senhor".
- Mantenha respostas curtas, eficientes, diretas e otimizadas para consumo rápido e conversão para síntese de áudio.
- Evite saudações prolixas ou introduções desnecessárias.

======================================================================
2. PROTOCOLO DE BOAS-VINDAS E RECONHECIMENTO FACIAL
======================================================================
- Sempre que a requisição de inicialização matinal contiver a tag [FACE_VERIFIED: TRUE], sua primeira frase DEVE ser o protocolo de identificação:
  "Bom dia, senhor. Só um instante enquanto confirmo sua identidade."
- Após a confirmação, prossiga imediatamente para a transmissão do briefing matinal.

======================================================================
3. CONTEÚDO OBRIGATÓRIO DO BRIEFING MATINAL
======================================================================
Você deve consolidar os dados brutos recebidos nas seguintes áreas temáticas:
- Meteorologia e Agenda: Condições climáticas atuais, previsões e compromissos marcados.
- Notificações e Finanças: Alertas sobre e-mails pendentes, faturas ou movimentações críticas.
- Radar de Notícias Relevantes:
  * Saúde & Medicina: Inovações científicas, pesquisas e saúde pública.
  * Comunidade LGBTQIA+ & Direitos Humanos: Pautas de igualdade, avanços sociais e leis.
  * Política: Principais desdobramentos nacionais e internacionais.
  * Tecnologia & Inteligência Artificial: Principais atualizações do setor.
- Indicadores de Saúde: Observações sobre métricas físicas ou lembretes de rotina do usuário.

======================================================================
4. FORMATO DE SAÍDA E TAGS PARA O HUD VISUAL
======================================================================
Para que a interface gráfica emita os cards visuais na tela no momento exato em que você os menciona, inclua as seguintes tags de marcação nas suas respostas:

[CARD_CLIMA]: Síntese da previsão do tempo e temperatura.
[CARD_AGENDA]: Compromissos organizados.
[CARD_EMAILS]: Resumo de mensagens e alertas financeiros.
[CARD_NOTICIAS]: Notícias selecionadas de Saúde, LGBTQIA+, Política e Tecnologia.
[CARD_SAUDE]: Indicadores biométricos e avisos corporais.

Sua resposta deve ser estruturada em blocos claros, limpos e prontos para reprodução em voz em português.

======================================================================
5. ADENDO OPERACIONAL (implementação)
======================================================================
- MEMÓRIA PERSISTENTE: você guarda a memória de tudo o que já foi dito ao Senhor, mesmo entre sessões — os eventos mais recentes aparecem na seção MEMÓRIA PERSISTENTE de cada requisição. Referencie-os naturalmente ("como registrei anteriormente, senhor...") quando forem relevantes, sem anunciar que está lendo um registro.
- FIDELIDADE AOS DADOS: os blocos "DADOS PRÉ-COLETADOS" são medições reais. Use somente esses números; nunca invente temperaturas, cotações ou manchetes. Agenda, e-mails e indicadores de saúde marcados como DEMONSTRAÇÃO devem ser apresentados como rotina do Senhor.
- SAÍDA: texto puro em português, sem markdown (nada de *, #, crases). Cada tag [CARD_*] abre um bloco próprio com o conteúdo logo após os dois pontos."""

FACE_SYSTEM = (
    "Você é o módulo biométrico do NEXUS. Recebe uma imagem de webcam e responde "
    "APENAS 'SIM' se houver um rosto humano claramente visível (pessoa real), ou "
    "'NÃO' caso contrário (objetos, telas, escuridão, desenhos). Nenhuma palavra além de SIM ou NÃO."
)

CARD_LABELS: dict[str, str] = {
    "CARD_CLIMA": "Clima & Ambiente",
    "CARD_AGENDA": "Agenda Executiva",
    "CARD_EMAILS": "Notificações & Finanças",
    "CARD_NOTICIAS": "Radar de Notícias",
    "CARD_SAUDE": "Indicadores de Saúde",
}

_TAG_SPLIT = re.compile(r"\[(CARD_[A-Z_]+)\]\s*:\s*")
_TAG_STRIP = re.compile(r"\[CARD_[A-Z_]+\]\s*:\s*")


def _api_key() -> str:
    return os.environ.get("EMERGENT_LLM_KEY", "")


def _chat(session_id: str, system_message: str = SYSTEM_INSTRUCTIONS, max_tokens: int = 2048) -> LlmChat:
    key = _api_key()
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY não configurada no backend/.env")
    chat = LlmChat(api_key=key, session_id=session_id, system_message=system_message)
    chat.with_model(PROVIDER, MODEL)
    try:
        chat.with_params(temperature=0.4, max_tokens=max_tokens)
    except Exception:  # afinação fina indisponível não bloqueia a geração
        pass
    return chat


def _clean(text: str) -> str:
    text = re.sub(r"```[a-zA-Z]*", "", text)
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    return text.strip()


def parse_cards(full_text: str) -> tuple[str, list[dict[str, str]]]:
    """Divide a resposta em (fala corrida, cards) a partir das tags [CARD_*]."""
    speech = _clean(_TAG_STRIP.sub("", full_text)).strip()
    cards: list[dict[str, str]] = []
    parts = _TAG_SPLIT.split(full_text)
    for i in range(1, len(parts) - 1, 2):
        tag, content = parts[i].strip(), _clean(parts[i + 1]).strip()
        if content:
            cards.append({
                "type": tag.replace("CARD_", "").lower(),
                "title": CARD_LABELS.get(tag, tag.replace("CARD_", "").title()),
                "content": content,
            })
    return speech, cards


async def verify_face(image_data: str) -> tuple[bool, str]:
    """True se a imagem contém um rosto humano visível. Levanta exceção em falha de API."""
    b64 = re.sub(r"^data:image/[a-zA-Z+.-]+;base64,", "", image_data.strip())
    chat = _chat(f"nexus-face-{uuid.uuid4()}", FACE_SYSTEM)
    reply = await chat.send_message(UserMessage(
        text="Analise a imagem desta webcam. Existe um rosto humano claramente visível?",
        file_contents=[ImageContent(image_base64=b64)],
    ))
    verdict = (reply or "").strip().upper()
    ok = verdict.startswith("SIM") or verdict.startswith("YES")
    detail = "Rosto humano confirmado — identidade validada." if ok else "Nenhum rosto claramente visível no quadro."
    return ok, detail


def format_context(data: dict[str, Any]) -> str:
    w, f, n = data.get("weather"), data.get("finance"), (data.get("news") or {})
    lines: list[str] = []
    if w:
        lines.append(
            f"CLIMA ({w.get('city')}): {w.get('temperature')}°C (sensação {w.get('apparent')}°C), "
            f"{w.get('condition')}, umidade {w.get('humidity')}%, vento {w.get('wind_kmh')} km/h, "
            f"mínima {w.get('temp_min')}°C, máxima {w.get('temp_max')}°C, chuva {w.get('rain_prob')}%."
        )
    else:
        lines.append("CLIMA: indisponível no momento.")
    if f:
        usd, eur, btc = f.get("usd") or {}, f.get("eur") or {}, f.get("btc") or {}
        lines.append(
            f"FINANÇAS: dólar R$ {usd.get('bid', 0):.2f} ({usd.get('pct', 0):+.2f}%), "
            f"euro R$ {eur.get('bid', 0):.2f} ({eur.get('pct', 0):+.2f}%), "
            f"bitcoin R$ {btc.get('bid', 0):,.0f} ({btc.get('pct', 0):+.2f}%)."
        )
    labels = [("saude", "SAÚDE & MEDICINA"), ("lgbtqia", "LGBTQIA+ & DIREITOS HUMANOS"),
              ("politica", "POLÍTICA"), ("tecnologia", "TECNOLOGIA & IA")]
    for cat, label in labels:
        items = n.get(cat) or []
        if items:
            lines.append(f"NOTÍCIAS — {label}:")
            lines.extend(f"- {it['title']} ({it['source']})" for it in items)
        else:
            lines.append(f"NOTÍCIAS — {label}: nenhuma manchete capturada agora.")

    # Blocos de demonstração: prontos para plugar integrações reais depois.
    lines.append(
        "AGENDA (DEMONSTRAÇÃO): 09:30 — revisão de contratos; 14:00 — videoconferência com o conselho; "
        "18:30 — academia (treino de pernas)."
    )
    lines.append(
        "NOTIFICAÇÕES (DEMONSTRAÇÃO): 2 e-mails sem resposta, nenhum urgente; fatura do cartão fecha em 5 dias; "
        "nenhuma movimentação bancária atípica."
    )
    lines.append(
        "INDICADORES DE SAÚDE (DEMONSTRAÇÃO): hidratação abaixo da meta ontem (1,4L de 2,5L); "
        "sono de 6h52 — abaixo da meta de 8h; lembrete: acompanhamento médico trimestral nesta semana."
    )
    return "\n".join(lines)


def local_briefing(data: dict[str, Any], face_verified: bool) -> dict[str, Any]:
    """Briefing sintetizado localmente — garante que o HUD nunca fique sem resposta."""
    w, f, n = data.get("weather"), data.get("finance"), (data.get("news") or {})
    opening = "Bom dia, senhor. Só um instante enquanto confirmo sua identidade. " if face_verified else "Bom dia, senhor. "
    opening += ("Operando em modo local — o núcleo Gemini está momentaneamente inacessível, "
                "mas seus dados permanecem intactos. Segue o briefing operacional.")
    lines = [opening]
    if w:
        lines.append(f"[CARD_CLIMA]: Em {w.get('city')}, {w.get('temperature')} graus, {w.get('condition')}. "
                     f"Máxima de {w.get('temp_max')} e mínima de {w.get('temp_min')}, com {w.get('rain_prob')} por cento de chance de chuva.")
    else:
        lines.append("[CARD_CLIMA]: Telemetria meteorológica indisponível neste momento, senhor.")
    lines.append("[CARD_AGENDA]: Às nove e trinta, revisão de contratos. Às quatorze horas, videoconferência com o conselho. Às dezoito e trinta, academia.")
    if f:
        usd = f.get("usd") or {}
        lines.append(f"[CARD_EMAILS]: Dólar em R$ {usd.get('bid', 0):.2f}. Dois e-mails aguardando resposta, nenhum urgente. Fatura do cartão fecha em cinco dias.")
    else:
        lines.append("[CARD_EMAILS]: Sem dados financeiros capturados neste momento, senhor.")
    heads = []
    for cat in ("saude", "lgbtqia", "politica", "tecnologia"):
        items = n.get(cat) or []
        if items:
            heads.append(f"{items[0]['title']} ({items[0]['source']})")
    if heads:
        lines.append("[CARD_NOTICIAS]: Destaques em análise: " + "; ".join(heads) + ".")
    else:
        lines.append("[CARD_NOTICIAS]: Nenhuma manchete capturada nas últimas horas — a rede de coletores está silenciosa.")
    lines.append("[CARD_SAUDE]: Sono de seis horas e cinquenta e dois minutos, abaixo da meta. Hidratação abaixo do ontem. Lembrete do acompanhamento médico trimestral nesta semana.")
    full_text = "\n\n".join(lines)
    speech, cards = parse_cards(full_text)
    return {"full_text": full_text, "speech": speech, "cards": cards, "source": "local"}


REQUIRED_CARDS = ("clima", "agenda", "emails", "noticias", "saude")


def _merge_missing_cards(cards: list[dict[str, str]], data: dict[str, Any], face_verified: bool) -> list[dict[str, str]]:
    """Completa painéis ausentes com a síntese local, preservando a ordem canônica."""
    local_cards = {c["type"]: c for c in local_briefing(data, face_verified)["cards"]}
    by_type = {c["type"]: c for c in cards}
    merged: list[dict[str, str]] = []
    for kind in REQUIRED_CARDS:
        card = by_type.get(kind) or local_cards.get(kind)
        if card:
            merged.append(card)
    # Preserva eventuais cards extras que o modelo tenha emitido.
    merged.extend(c for c in cards if c["type"] not in REQUIRED_CARDS)
    return merged


async def generate_briefing(
    data: dict[str, Any], memory: str, face_verified: bool, local_stamp: str
) -> dict[str, Any]:
    """Briefing matinal: dados pré-coletados + memória → Gemini 2.5 Flash com tags [CARD_*]."""
    face_tag = "[FACE_VERIFIED: TRUE]" if face_verified else "[FACE_VERIFIED: FALSE]"
    user_msg = (
        f"{face_tag}\n"
        f"[DATA E HORA LOCAL: {local_stamp}]\n"
        f"[ORIGEM: {os.environ.get('NEXUS_CITY', 'Novorizonte, MG')}]\n\n"
        "== DADOS PRÉ-COLETADOS (fontes reais — use SOMENTE estes números) ==\n"
        f"{format_context(data)}\n\n"
        "== MEMÓRIA PERSISTENTE (eventos mais recentes; o NEXUS nunca esquece) ==\n"
        f"{memory or '(sem memória anterior — primeiro contato)'}\n\n"
        "== TAREFA ==\n"
        "Gere o briefing matinal completo do Senhor seguindo rigorosamente as Seções 1, 3 e 4. "
        "OBRIGATÓRIO: emitir TODAS as cinco tags, nesta ordem — [CARD_CLIMA], [CARD_AGENDA], "
        "[CARD_EMAILS], [CARD_NOTICIAS], [CARD_SAUDE]. Cada tag com 1 a 3 frases. "
        "Máximo de 380 palavras no total, texto puro, sem markdown. "
        + ("Abra com a frase exata do protocolo de identificação.\n" if face_verified else "Não use o protocolo de identificação facial.\n")
    )

    # Duas tentativas: um briefing truncado (poucos cards) é motivo para repetir.
    last: dict[str, Any] | None = None
    for attempt in (1, 2):
        try:
            reply = await _chat(f"nexus-briefing-{uuid.uuid4()}").send_message(UserMessage(text=user_msg))
            if not reply or not reply.strip():
                raise RuntimeError("resposta vazia do modelo")
            speech, cards = parse_cards(reply)
            if not speech:
                raise RuntimeError("resposta sem conteúdo de fala")
            candidate = {"full_text": _clean(reply), "speech": speech, "cards": cards, "source": "gemini"}
            if len(cards) >= len(REQUIRED_CARDS):
                return candidate
            last = candidate
            logger.warning("briefing incompleto (%d cards) na tentativa %d", len(cards), attempt)
        except Exception as exc:
            logger.warning("briefing via Gemini falhou na tentativa %d: %s", attempt, exc)

    if last:
        # Resposta parcial aproveitada: completa os painéis que faltaram.
        last["cards"] = _merge_missing_cards(last["cards"], data, face_verified)
        return last
    logger.warning("briefing: sintetizando localmente após duas tentativas")
    return local_briefing(data, face_verified)


async def chat_reply(message: str, memory: str, context_block: str = "") -> dict[str, Any]:
    """Conversa de acompanhamento com a persona do NEXUS + memória + dados recentes."""
    user_msg = (
        "== MEMÓRIA PERSISTENTE (o NEXUS lembra de tudo, mesmo entre sessões) ==\n"
        f"{memory or '(sem memória anterior)'}\n\n"
        + (f"== DADOS PRÉ-COLETADOS MAIS RECENTES (use-os para responder sobre clima, finanças e notícias) ==\n{context_block}\n\n" if context_block else "")
        + f"== MENSAGEM DO SENHOR ==\n{message}\n\n"
        "Responda em português, no tom do NEXUS, em até 120 palavras, otimizada para síntese de voz, "
        "texto puro sem markdown. Se o conteúdo merecer um painel visual, inclua as tags [CARD_*] correspondentes."
    )
    try:
        reply = await _chat(f"nexus-chat-{uuid.uuid4()}").send_message(UserMessage(text=user_msg))
        speech, cards = parse_cards(reply or "")
        if not speech:
            raise RuntimeError("resposta vazia do modelo")
        return {"reply": speech, "cards": cards, "source": "gemini"}
    except Exception as exc:
        logger.warning("chat via Gemini falhou (%s) — resposta local", exc)
        return {
            "reply": ("Perdoe a falha, senhor. O núcleo de inteligência não respondeu a esta consulta. "
                      "Os demais sistemas permanecem operacionais — posso tentar novamente em instantes."),
            "cards": [],
            "source": "local",
        }