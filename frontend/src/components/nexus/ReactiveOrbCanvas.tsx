import { useEffect, useRef } from "react";
import { orbBus } from "@/lib/orbBus";

interface Particle {
  angle: number;
  radius: number;
  speed: number;
  size: number;
  offset: number;
}

const RINGS: ReadonlyArray<readonly [number, number, number, number]> = [
  // [raio relativo, velocidade angular, alpha, espessura]
  [0.5, 0.4, 0.5, 1.6],
  [0.64, -0.26, 0.35, 1],
  [0.76, 0.14, 0.2, 0.8],
];

/** Orbe central reativo — canvas em azul neon (#00F0FF); escala e brilho seguem a fala. */
export default function ReactiveOrbCanvas({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let width = 0;
    let height = 0;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);

    const particles: Particle[] = Array.from({ length: reduced ? 0 : 130 }, () => ({
      angle: Math.random() * Math.PI * 2,
      radius: Math.random(),
      speed: (0.2 + Math.random() * 0.9) * (Math.random() > 0.5 ? 1 : -1),
      size: 0.6 + Math.random() * 1.8,
      offset: Math.random() * Math.PI * 2,
    }));

    let raf = 0;
    let last = performance.now();
    let t = 0;
    let level = 0.25;

    const draw = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      t += dt;

      // Nível alvo a partir do barramento (fala, escuta, processamento…).
      const wobble = Math.sin(t * (orbBus.state === "speaking" ? 9 : 1.4)) * (orbBus.state === "speaking" ? 0.12 : 0.04);
      const target = Math.max(0.08, Math.min(1, orbBus.intensity + wobble));
      level += (target - level) * Math.min(1, dt * 6);

      const cx = width / 2;
      const cy = height / 2;
      const base = Math.min(width, height) / 2;
      const scale = 1 + level * 0.45;

      ctx.clearRect(0, 0, width, height);

      // Halo externo
      const coreR = base * 0.34 * scale;
      const halo = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 2.4);
      halo.addColorStop(0, `rgba(0, 240, 255, ${0.35 + level * 0.45})`);
      halo.addColorStop(0.45, `rgba(0, 160, 255, ${0.1 + level * 0.2})`);
      halo.addColorStop(1, "rgba(3, 7, 18, 0)");
      ctx.fillStyle = halo;
      ctx.beginPath();
      ctx.arc(cx, cy, coreR * 2.4, 0, Math.PI * 2);
      ctx.fill();

      // Anéis rotativos
      for (const [ringR, speed, alpha, thickness] of RINGS) {
        ctx.strokeStyle = `rgba(0, 240, 255, ${alpha * (0.4 + level * 0.6)})`;
        ctx.lineWidth = thickness;
        ctx.beginPath();
        const r = base * ringR * (1 + level * 0.18);
        ctx.ellipse(cx, cy, r, r * 0.94, t * speed, 0, Math.PI * 1.6);
        ctx.stroke();
      }

      // Partículas orbitais
      for (const p of particles) {
        p.angle += p.speed * dt * (0.4 + level * 2.2);
        const rr = base * (0.4 + p.radius * 0.52) * (1 + level * 0.14) + Math.sin(t * 1.3 + p.offset) * 3;
        const x = cx + Math.cos(p.angle) * rr;
        const y = cy + Math.sin(p.angle) * rr * 0.92;
        ctx.fillStyle = `rgba(0, 240, 255, ${0.22 + level * 0.55})`;
        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }

      // Núcleo
      ctx.fillStyle = `rgba(224, 255, 255, ${0.6 + level * 0.4})`;
      ctx.beginPath();
      ctx.arc(cx, cy, coreR * 0.3, 0, Math.PI * 2);
      ctx.fill();

      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      data-testid="nexus-reactive-orb"
      aria-hidden="true"
    />
  );
}