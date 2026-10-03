import { motion } from "motion/react";
import { CalendarDays, CloudSun, HeartPulse, LayoutGrid, Mail, Newspaper } from "lucide-react";
import type { BriefingCard } from "@/lib/nexus";

const ICONS: Record<string, typeof CloudSun> = {
  clima: CloudSun,
  agenda: CalendarDays,
  emails: Mail,
  noticias: Newspaper,
  saude: HeartPulse,
};

interface FloatingCardStreamProps {
  cards: BriefingCard[];
  revealed: number;
}

/** Painéis glassmorphism que surgem em sequência conforme as tags [CARD_*] chegam. */
export default function FloatingCardStream({ cards, revealed }: FloatingCardStreamProps) {
  const visible = cards.slice(0, Math.max(0, revealed));
  return (
    <div className="grid gap-4 md:grid-cols-2" data-testid="nexus-card-stream">
      {visible.map((card, index) => {
        const Icon = ICONS[card.type] ?? LayoutGrid;
        return (
          <motion.article
            key={`${card.type}-${index}`}
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: "easeOut" }}
            data-testid={`nexus-card-${card.type}`}
            className="hud-brackets relative rounded-lg border border-cyan-500/30 bg-slate-950/75 p-5 shadow-[0_0_25px_rgba(0,240,255,0.08)] backdrop-blur-xl"
          >
            <header className="mb-2 flex items-center gap-2">
              <Icon className="size-4 text-cyan-400" aria-hidden="true" />
              <h3 className="font-mono text-xs uppercase tracking-[0.25em] text-cyan-400/80">
                {card.title}
              </h3>
            </header>
            <p className="whitespace-pre-line text-sm leading-relaxed text-slate-300">
              {card.content}
            </p>
          </motion.article>
        );
      })}
    </div>
  );
}