// Web Speech API: síntese de voz pt-BR (com pulso do orbe) + reconhecimento opcional.
import { setOrbState } from "@/lib/orbBus";

export function speechSynthSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export interface SpeakOptions {
  rate?: number;
  pitch?: number;
  volume?: number;
  onStart?: () => void;
  onEnd?: () => void;
}

let pulseTimer: number | null = null;

function startPulse(): void {
  stopPulse();
  pulseTimer = window.setInterval(() => {
    // Oscilação entre ~0.45 e 1.0 enquanto o NEXUS fala.
    setOrbState("speaking", 0.72 + Math.sin(Date.now() / 90) * 0.28);
  }, 90);
}

function stopPulse(): void {
  if (pulseTimer !== null) {
    window.clearInterval(pulseTimer);
    pulseTimer = null;
  }
}

export function cancelSpeech(): void {
  if (speechSynthSupported()) window.speechSynthesis.cancel();
  stopPulse();
}

export function speak(text: string, opts: SpeakOptions = {}): void {
  cancelSpeech();
  let ended = false;
  const finish = () => {
    if (ended) return;
    ended = true;
    stopPulse();
    setOrbState("idle", 0.25);
    opts.onEnd?.();
  };
  opts.onStart?.();

  if (!speechSynthSupported()) {
    // Sem motor de voz disponível: mantém a cadência visual pela duração estimada.
    setOrbState("speaking", 0.6);
    startPulse();
    window.setTimeout(finish, Math.min(45000, 2200 + text.length * 55));
    return;
  }

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "pt-BR";
  const voices = window.speechSynthesis.getVoices();
  const ptVoices = voices.filter((v) => v.lang.toLowerCase().startsWith("pt"));
  utterance.voice = ptVoices.find((v) => /luciana|francisca|google/i.test(v.name)) ?? ptVoices[0] ?? null;
  utterance.rate = opts.rate ?? 1;
  utterance.pitch = opts.pitch ?? 1;
  utterance.volume = opts.volume ?? 1;
  utterance.onstart = () => startPulse();
  utterance.onboundary = () => setOrbState("speaking", 0.95);
  utterance.onend = finish;
  utterance.onerror = finish;
  // Rede de segurança: motores headless podem nunca disparar onend.
  window.setTimeout(finish, Math.min(120000, 4000 + text.length * 90));
  window.speechSynthesis.speak(utterance);
  if (window.speechSynthesis.speaking) startPulse();
  else {
    setOrbState("speaking", 0.6);
    startPulse();
    window.setTimeout(finish, Math.min(45000, 2200 + text.length * 55));
  }
}

/* ── Reconhecimento de voz (opcional; degrada com aviso) ─────────────── */

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onend: (() => void) | null;
}

type RecognitionCtor = new () => SpeechRecognitionLike;

export function recognitionSupported(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
}

function createRecognition(lang = "pt-BR"): SpeechRecognitionLike | null {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
  if (!Ctor) return null;
  const rec = new Ctor();
  rec.lang = lang;
  rec.interimResults = false;
  rec.continuous = false;
  rec.maxAlternatives = 1;
  return rec;
}

export interface ListenHandlers {
  onPartial?: (text: string) => void;
  onFinal: (text: string) => void;
  onError: (message: string) => void;
  onEnd?: () => void;
}

/** Escuta uma frase e finaliza. Retorna a função de cancelamento. */
export function listenOnce(handlers: ListenHandlers): () => void {
  const rec = createRecognition();
  if (!rec) {
    handlers.onError("Reconhecimento de voz não suportado neste navegador, senhor.");
    return () => undefined;
  }
  rec.onresult = (event) => {
    const last = event.results[event.results.length - 1];
    const text = last?.[0]?.transcript ?? "";
    handlers.onPartial?.(text);
    handlers.onFinal(text);
  };
  rec.onerror = (event) =>
    handlers.onError(event.error === "not-allowed" ? "Acesso ao microfone negado." : "Falha no reconhecimento de voz.");
  rec.onend = () => handlers.onEnd?.();
  try {
    rec.start();
  } catch {
    handlers.onError("Não foi possível iniciar o microfone.");
  }
  return () => rec.abort();
}