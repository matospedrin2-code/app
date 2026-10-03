# NEXUS — Neural Executive System for Universal Support

HUD holográfico estilo JARVIS (azul neon #00F0FF) com briefing matinal via
Gemini 2.5 Flash, verificação facial por webcam e memória persistente.

## O que o app faz
1. **Lockscreen biométrico (`/auth`)** — console de boot, escaneamento facial
   (getUserMedia → frame JPEG → `POST /api/face-verify` → Gemini Vision responde
   SIM/NÃO) e frase de ativação "NEXUS, bom dia" (Web Speech API com fallback
   manual). Câmera bloqueada → botão "Prosseguir sem verificação". Ambos os
   caminhos setam `nexus_auto_briefing` no sessionStorage e navegam para `/`.
2. **HUD principal (`/`)** — orbe central reativo em canvas (pulsa com o TTS via
   `lib/orbBus`), feed de diálogo com efeito typewriter, cards glassmorphism que
   surgem em sequência ([CARD_CLIMA], [CARD_AGENDA], [CARD_EMAILS],
   [CARD_NOTICIAS], [CARD_SAUDE]) e dock de comandos (texto, voz, briefing,
   mudo). Briefing automático ao chegar do lockscreen; hidratação do último
   estado ao reabrir (memória persistente).
3. **Memória (`/timeline` + gaveta no header)** — linha do tempo completa de
   briefings e conversa (Mongo), filtro visual por tipo.
4. **Configurações (`/settings`)** — voz on/off, velocidade, tom, volume
   (localStorage `nexus_voice_on`, `nexus_rate`, `nexus_pitch`, `nexus_volume`)
   e botão de teste.

## Backend (FastAPI + motor, tudo sob /api)
- `POST /api/face-verify` `{image}` (data URL/base64) → `{verified, detail}`;
  nunca falha hard (indisponibilidade → verified=false + detalhe).
- `POST /api/briefing` `{face_verified}` → coleta paralela (Open-Meteo clima de
  Novorizonte-MG; AwesomeAPI USD/EUR/BTC-BRL; RSS G1 + Google News para Saúde,
  LGBTQIA+, Política, Tecnologia) + memória recente → Gemini 2.5 Flash
  (emergentintegrations, chave `EMERGENT_LLM_KEY` no backend/.env) → parse das
  tags [CARD_*] → grava em `briefings` → `{id, created_at, speech, full_text,
  cards[], face_verified, source: "gemini"|"local", context}`. Fallback local
  sintetiza o briefing sem IA se o Gemini falhar (source="local").
- `GET /api/briefing/latest` → último briefing ou `null`.
- `POST /api/chat` `{message}` (min_length=1) → resposta do NEXUS com memória;
  grava user+nexus em `interactions`; 422 se vazio.
- `GET /api/memory?limit=60` → eventos mesclados (briefing|user|nexus) desc.
- `GET/POST /api/status` — rota template original, mantida.
- Models: `backend/models/nexus.py` ↔ espelho TS em `frontend/src/lib/nexus.ts`.
- Indexes: `briefings.created_at_desc`, `interactions.created_at_desc`.

## Persona (System Instructions do Gemini)
Trata o usuário como "Senhor", pt-BR, polido/cirúrgico com sarcasmo sutil;
com [FACE_VERIFIED: TRUE] abre com "Bom dia, senhor. Só um instante enquanto
confirmo sua identidade."; respostas curtas para TTS; agenda/e-mails/saúde são
DEMONSTRAÇÃO (prontos para plugar integrações reais).

## Robustez (correções já validadas)
- Finanças: AwesomeAPI estoura cota (429) → fallback automático Frankfurter
  (USD/EUR→BRL, variação de 7 dias) + CoinGecko (BTC→BRL). Sempre há cotação.
- RSS: `findtext("source")` devolve str (bug corrigido); feed de Saúde usa
  `g1/saude` (bem-estar vinha vazio). 4 manchetes por categoria.
- Briefing: validação exige as 5 tags; até 2 tentativas no Gemini e, em resposta
  parcial, os painéis faltantes são completados pela síntese local
  (`_merge_missing_cards`). max_tokens=2048 evita truncamento.
- `/api/chat` injeta o `context` do último briefing, então follow-ups sobre
  clima/finanças/notícias respondem com dados reais.

## Credenciais
Nenhuma — app público, sem login. A chave LLM fica só no backend/.env.

## Dados sementes
Nenhum necessário — clima/finanças/notícias são coletados ao vivo; a memória
começa vazia e se popula a cada briefing/conversa.
