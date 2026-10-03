import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import {
  BrainCircuit,
  Mic,
  MicOff,
  Send,
  Settings,
  Sparkles,
  Volume2,
  VolumeX,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { buttonVariants } from "@/components/ui/button";
import ReactiveOrbCanvas from "@/components/nexus/ReactiveOrbCanvas";
import FloatingCardStream from "@/components/nexus/FloatingCardStream";
import NexusDialogueFeed, { type DialogueEntry } from "@/components/nexus/NexusDialogueFeed";
import MemoryTimelineDrawer from "@/components/nexus/MemoryTimelineDrawer";
import {
  fetchLatestBriefing,
  fetchMemory,
  runBriefing,
  sendChatMessage,
  type BriefingCard,
  type BriefingResponse,
} from "@/lib/nexus";
import { listenOnce, recognitionSupported, speak } from "@/lib/speech";
import { setOrbState } from "@/lib/orbBus";

export default function Home() {
  const queryClient = useQueryClient();
  const [briefing, setBriefing] = useState<BriefingResponse | null>(null);
  const [entries, setEntries] = useState<DialogueEntry[]>([]);
  const [live, setLive] = useState<{ id: string; text: string } | null>(null);
  const [cards, setCards] = useState<BriefingCard[]>([]);
  const [revealed, setRevealed] = useState(0);
  const [listening, setListening] = useState(false);
  const [command, setCommand] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [voiceOn, setVoiceOn] = useState(() => localStorage.getItem("nexus_voice_on") !== "0");

  const revealTimersRef = useRef<number[]>([]);
  const hydratedRef = useRef(false);
  const autoRunRef = useRef(false);

  // Memória persistente: reidrata o diálogo e o último briefing ao reabrir o app.
  const memoryQuery = useQuery({
    queryKey: ["memory"],
    queryFn: () => fetchMemory(40),
    refetchOnWindowFocus: false,
    retry: false,
  });
  const latestQuery = useQuery({
    queryKey: ["latest-briefing"],
    queryFn: fetchLatestBriefing,
    refetchOnWindowFocus: false,
    retry: false,
  });

  useEffect(() => {
    return () => {
      revealTimersRef.current.forEach((id) => window.clearTimeout(id));
      revealTimersRef.current = [];
    };
  }, []);

  const clearRevealTimers = useCallback(() => {
    revealTimersRef.current.forEach((id) => window.clearTimeout(id));
    revealTimersRef.current = [];
  }, []);

  const speakNexus = useCallback((text: string, onEnd?: () => void) => {
    const rate = Number(localStorage.getItem("nexus_rate") ?? "1");
    const volume = Number(localStorage.getItem("nexus_volume") ?? "1");
    speak(text, { rate, volume, onEnd });
  }, []);

  /** Apresenta uma transmissão do NEXUS: feed com typewriter + fala + cards em sequência. */
  const presentNexusMessage = useCallback(
    (id: string, text: string, nextCards: BriefingCard[], staggerMs = 0) => {
      clearRevealTimers();
      setEntries((prev) => [...prev, { id, role: "nexus", text }]);
      setLive({ id, text });
      setCards(nextCards);
      if (staggerMs > 0 && nextCards.length > 0) {
        setRevealed(0);
        nextCards.forEach((_, index) => {
          revealTimersRef.current.push(
            window.setTimeout(() => setRevealed(index + 1), staggerMs + index * 4500),
          );
        });
      } else {
        setRevealed(nextCards.length);
      }
      speakNexus(text, () => setLive(null));
    },
    [clearRevealTimers, speakNexus],
  );

  const { mutate: mutateBriefing, isPending: briefingPending } = useMutation({
    mutationFn: (faceVerified: boolean) => runBriefing(faceVerified),
    onSuccess: (data) => {
      setNotice(null);
      setBriefing(data);
      queryClient.invalidateQueries({ queryKey: ["memory"] });
      queryClient.invalidateQueries({ queryKey: ["latest-briefing"] });
      presentNexusMessage(data.id, data.speech, data.cards, 2500);
      toast.success("Briefing matinal transmitido, senhor.");
    },
    onError: () => {
      setNotice(null);
      toast.error("Falha na comunicação com o núcleo de inteligência.");
      setEntries((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "nexus",
          text: "Perdoe a falha, senhor. O canal com o núcleo está instável — tente novamente em instantes.",
        },
      ]);
    },
  });

  const { mutate: mutateChat, isPending: chatPending } = useMutation({
    mutationFn: (message: string) => sendChatMessage(message),
    onSuccess: (data) => {
      setNotice(null);
      queryClient.invalidateQueries({ queryKey: ["memory"] });
      presentNexusMessage(data.id, data.reply, data.cards);
    },
    onError: () => {
      setNotice(null);
      toast.error("Falha na transmissão da consulta, senhor.");
    },
  });

  // Frase de ativação vinda do lockscreen → briefing automático com [FACE_VERIFIED].
  useEffect(() => {
    if (autoRunRef.current) return;
    autoRunRef.current = true;
    if (sessionStorage.getItem("nexus_auto_briefing") === "1") {
      sessionStorage.removeItem("nexus_auto_briefing");
      const verified = sessionStorage.getItem("nexus_face_verified") === "1";
      sessionStorage.removeItem("nexus_face_verified");
      setNotice(verified
        ? "[FACE_VERIFIED: TRUE] — emitindo briefing matinal, senhor…"
        : "Emitindo briefing matinal, senhor…");
      mutateBriefing(verified);
    }
  }, [mutateBriefing]);

  useEffect(() => {
    if (hydratedRef.current) return;
    if (!memoryQuery.isSuccess || !latestQuery.isSuccess) return;
    hydratedRef.current = true;
    const events = (memoryQuery.data ?? []).slice(0, 8).reverse();
    if (events.length > 0) {
      setEntries(
        events.map((event) => ({
          id: event.id,
          role: event.kind === "user" ? ("user" as const) : ("nexus" as const),
          text: event.text,
        })),
      );
    }
    const last = latestQuery.data;
    if (last) {
      setBriefing(last);
      setCards(last.cards);
      setRevealed(last.cards.length);
    }
  }, [memoryQuery.isSuccess, latestQuery.isSuccess, memoryQuery.data, latestQuery.data]);

  useEffect(() => {
    if (briefingPending || chatPending) setOrbState("thinking", 0.7);
    else if (listening) setOrbState("listening", 0.55);
    else if (!window.speechSynthesis?.speaking) setOrbState("idle", 0.25);
  }, [briefingPending, chatPending, listening]);

  const submitMessage = (raw: string) => {
    const text = raw.trim();
    if (!text || chatPending) return;
    cancelSpeechSafe();
    setEntries((prev) => [...prev, { id: `user-${Date.now()}`, role: "user", text }]);
    setNotice("Processando consulta…");
    mutateChat(text);
  };

  const toggleMic = () => {
    if (listening) return;
    if (!recognitionSupported()) {
      toast.error("Reconhecimento de voz não suportado neste navegador — digite o comando, senhor.");
      return;
    }
    setListening(true);
    setOrbState("listening", 0.55);
    listenOnce({
      onFinal: (text) => submitMessage(text),
      onError: (message) => toast.error(message),
      onEnd: () => {
        setListening(false);
        setOrbState("idle", 0.25);
      },
    });
  };

  const toggleVoice = () => {
    const next = !voiceOn;
    setVoiceOn(next);
    localStorage.setItem("nexus_voice_on", next ? "1" : "0");
    if (!next) cancelSpeechSafe();
  };

  const weather = briefing?.context?.weather;
  const usd = briefing?.context?.finance?.usd;
  const memoryCount = memoryQuery.data?.length ?? 0;

  return (
    <div className="flex h-svh flex-col">
      <header className="sticky top-0 z-50 flex h-16 shrink-0 items-center justify-between border-b border-cyan-500/20 bg-slate-950/80 px-4 backdrop-blur-xl md:px-6">
        <div className="flex items-center gap-3">
          <BrainCircuit className="size-7 text-cyan-400" aria-hidden="true" />
          <div>
            <h1 className="hud-glow font-heading text-xl font-black uppercase tracking-tighter text-cyan-300">
              NEXUS
            </h1>
            <p className="font-mono text-[9px] uppercase tracking-[0.3em] text-cyan-400/60">
              Executive Operating System
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" data-testid="nexus-source-badge" className="font-mono">
            {briefingPending || chatPending
              ? "PROCESSANDO"
              : briefing?.source === "local"
                ? "MODO LOCAL"
                : briefing?.source === "gemini"
                  ? "NÚCLEO GEMINI"
                  : "STANDBY"}
          </Badge>
          <MemoryTimelineDrawer />
          <Link
            to="/settings"
            className={buttonVariants({ variant: "ghost", size: "icon" })}
            aria-label="Configurações"
            data-testid="nexus-settings-link"
          >
            <Settings className="size-4" aria-hidden="true" />
          </Link>
        </div>
      </header>

      <main className="mx-auto grid w-full max-w-7xl flex-1 grid-cols-1 gap-6 overflow-y-auto p-4 lg:grid-cols-12 lg:p-6">
        <section className="flex flex-col items-center gap-8 lg:col-span-5 lg:border-r lg:border-cyan-500/20 lg:pr-6">
          <ReactiveOrbCanvas className="h-64 w-64 md:h-80 md:w-80" />
          <dl className="w-full max-w-sm space-y-3" data-testid="nexus-telemetry">
            {[
              {
                label: "Clima · Novorizonte-MG",
                value: weather?.temperature != null ? `${weather.temperature}°C — ${weather.condition ?? ""}` : "—",
                testId: "nexus-telemetry-weather",
              },
              {
                label: "USD/BRL",
                value: usd?.bid != null ? `R$ ${usd.bid.toFixed(2)} (${(usd.pct ?? 0) >= 0 ? "+" : ""}${(usd.pct ?? 0).toFixed(2)}%)` : "—",
                testId: "nexus-telemetry-usd",
              },
              {
                label: "Memória persistente",
                value: `${memoryCount} registro${memoryCount === 1 ? "" : "s"}`,
                testId: "nexus-telemetry-memory",
              },
              {
                label: "Biometria facial",
                value: briefing == null ? "NÃO VERIFICADO" : briefing.face_verified ? "VERIFICADO" : "NÃO VERIFICADO",
                testId: "nexus-telemetry-face",
              },
            ].map((row) => (
              <div
                key={row.testId}
                className="flex items-center justify-between gap-4 border-b border-cyan-500/10 pb-2"
                data-testid={row.testId}
              >
                <dt className="font-mono text-[11px] uppercase tracking-[0.25em] text-cyan-400/70">
                  {row.label}
                </dt>
                <dd className="text-right font-mono text-sm text-slate-200">{row.value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="flex min-h-0 flex-col gap-6 lg:col-span-7">
          <NexusDialogueFeed
            entries={entries}
            live={live}
            notice={notice ?? (briefingPending || chatPending ? "Processando…" : null)}
          />
          <FloatingCardStream cards={cards} revealed={revealed} />
          {cards.length === 0 && !briefingPending && (
            <div className="hud-brackets rounded-lg border border-cyan-500/20 bg-slate-950/60 p-6 text-center backdrop-blur-xl">
              <p className="font-mono text-xs uppercase tracking-[0.25em] text-cyan-400/70">
                Aguardando primeira transmissão
              </p>
              <p className="mt-2 text-sm text-slate-400">
                Emita o briefing matinal, senhor — clima, finanças, notícias e indicadores serão
                consolidados pelo núcleo Gemini.
              </p>
            </div>
          )}
        </section>
      </main>

      <footer className="sticky bottom-0 z-40 shrink-0 border-t border-cyan-500/20 bg-slate-950/90 px-4 py-3 backdrop-blur-xl md:px-6">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-2">
          <Input
            value={command}
            onChange={(event) => setCommand(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && submitMessage(command)}
            placeholder="Ex.: NEXUS, resuma minhas pendências…"
            aria-label="Comando para o NEXUS"
            data-testid="nexus-command-input"
            className="min-w-40 flex-1"
          />
          <Button
            onClick={() => submitMessage(command)}
            disabled={!command.trim() || chatPending}
            data-testid="nexus-command-submit-btn"
            aria-label="Transmitir comando ao NEXUS"
          >
            <Send className="size-4" aria-hidden="true" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={toggleMic}
            data-testid="nexus-wake-mic-btn"
            aria-label={listening ? "Microfone ouvindo" : "Falar com o NEXUS"}
          >
            {listening ? <MicOff className="size-4" aria-hidden="true" /> : <Mic className="size-4" aria-hidden="true" />}
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              cancelSpeechSafe();
              setNotice("Emitindo briefing matinal, senhor…");
              mutateBriefing(briefing?.face_verified ?? false);
            }}
            disabled={briefingPending}
            data-testid="nexus-briefing-btn"
          >
            <Sparkles className="size-4" aria-hidden="true" />
            {briefingPending ? "Emitindo…" : "Briefing"}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleVoice}
            data-testid="nexus-voice-toggle-btn"
            aria-label={voiceOn ? "Silenciar síntese de voz" : "Ativar síntese de voz"}
          >
            {voiceOn ? <Volume2 className="size-4" aria-hidden="true" /> : <VolumeX className="size-4" aria-hidden="true" />}
          </Button>
        </div>
      </footer>
    </div>
  );
}

function cancelSpeechSafe() {
  if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
}