import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { speak, speechSynthSupported } from "@/lib/speech";

export default function Settings() {
  const [voiceOn, setVoiceOn] = useState(() => localStorage.getItem("nexus_voice_on") !== "0");
  const [rate, setRate] = useState(() => Number(localStorage.getItem("nexus_rate") ?? "1"));
  const [pitch, setPitch] = useState(() => Number(localStorage.getItem("nexus_pitch") ?? "1"));
  const [volume, setVolume] = useState(() => Number(localStorage.getItem("nexus_volume") ?? "1"));

  const update = (key: string, value: number | string) => localStorage.setItem(key, String(value));

  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-8 md:px-6">
      <header className="mb-8 flex items-center justify-between gap-4">
        <div>
          <h1 className="hud-glow font-heading text-3xl font-black uppercase tracking-tighter text-cyan-300">
            Configurações
          </h1>
          <p className="mt-1 font-mono text-xs uppercase tracking-[0.25em] text-cyan-400/70">
            Voz & interface do NEXUS
          </p>
        </div>
        <Link
          to="/"
          className="font-mono text-xs uppercase tracking-[0.25em] text-cyan-400/80 hover:text-cyan-300"
          data-testid="nexus-settings-back-link"
        >
          Voltar ao HUD
        </Link>
      </header>

      <main className="space-y-6" data-testid="nexus-settings-panel">
        <section className="hud-brackets rounded-lg border border-cyan-500/30 bg-slate-950/75 p-5 backdrop-blur-xl">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="font-mono text-xs uppercase tracking-[0.25em] text-cyan-400/80">
                Síntese de voz
              </h2>
              <p className="mt-1 text-sm text-slate-400">
                {speechSynthSupported()
                  ? "Web Speech API do navegador, em português."
                  : "Este navegador não suporta síntese de voz — o HUD opera em modo visual."}
              </p>
            </div>
            <Button
              variant={voiceOn ? "default" : "outline"}
              onClick={() => {
                const next = !voiceOn;
                setVoiceOn(next);
                update("nexus_voice_on", next ? "1" : "0");
              }}
              data-testid="nexus-setting-voice-toggle"
            >
              <Volume2 className="size-4" aria-hidden="true" />
              {voiceOn ? "Ativa" : "Silenciada"}
            </Button>
          </div>

          <div className="mt-6 space-y-5">
            {[
              { label: "Velocidade", value: rate, min: 0.6, max: 1.6, step: 0.05, key: "nexus_rate", testId: "nexus-setting-rate", display: `${rate.toFixed(2)}×` },
              { label: "Tom", value: pitch, min: 0.6, max: 1.6, step: 0.05, key: "nexus_pitch", testId: "nexus-setting-pitch", display: pitch.toFixed(2) },
              { label: "Volume", value: volume, min: 0, max: 1, step: 0.05, key: "nexus_volume", testId: "nexus-setting-volume", display: `${Math.round(volume * 100)}%` },
            ].map((control) => (
              <div key={control.key} className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor={control.testId} className="font-mono text-[11px] uppercase tracking-[0.25em] text-cyan-400/70">
                    {control.label}
                  </Label>
                  <span className="font-mono text-xs text-slate-300">{control.display}</span>
                </div>
                <Input
                  id={control.testId}
                  type="range"
                  min={control.min}
                  max={control.max}
                  step={control.step}
                  value={control.value}
                  onChange={(event) => {
                    const next = Number(event.target.value);
                    if (control.testId === "nexus-setting-rate") setRate(next);
                    if (control.testId === "nexus-setting-pitch") setPitch(next);
                    if (control.testId === "nexus-setting-volume") setVolume(next);
                    update(control.key, next);
                  }}
                  className="accent-cyan-400"
                  data-testid={control.testId}
                />
              </div>
            ))}
          </div>

          <Button
            variant="secondary"
            className="mt-6"
            onClick={() =>
              speak("Sistemas nominais, senhor. O NEXUS está completamente operacional.", {
                rate,
                pitch,
                volume,
              })
            }
            data-testid="nexus-setting-test-voice"
          >
            Testar voz
          </Button>
        </section>

        <p className="text-xs leading-relaxed text-slate-500">
          A memória persistente do NEXUS é armazenada no servidor — briefings e conversas permanecem
          disponíveis mesmo após fechar o aplicativo.
        </p>
      </main>
    </div>
  );
}