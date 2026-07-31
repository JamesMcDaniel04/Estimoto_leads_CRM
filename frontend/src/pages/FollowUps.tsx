import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Clock } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import StageBadge from "../components/StageBadge";
import type { Lead } from "../lib/types";

export interface FollowUp {
  lead: Lead;
  reason: string;
  priority: number;
  days_idle: number;
}

const PRIORITY_STYLES: Record<number, { label: string; cls: string; icon: typeof Clock }> = {
  1: { label: "Act today", cls: "border-red-200 bg-red-50", icon: AlertTriangle },
  2: { label: "Due", cls: "border-amber-200 bg-amber-50", icon: Clock },
  3: { label: "Getting stale", cls: "border-slate-200 bg-white", icon: Clock },
};

export default function FollowUps() {
  const [items, setItems] = useState<FollowUp[] | null>(null);

  useEffect(() => {
    api
      .get<FollowUp[]>("/api/followups")
      .then(setItems)
      .catch(() => toast.error("Failed to load follow-ups"));
  }, []);

  if (items === null) return null;

  return (
    <div className="max-w-3xl">
      <h1 className="mb-1 text-2xl font-bold tracking-tight">Follow-ups</h1>
      <p className="mb-6 text-sm text-slate-500">
        Leads that need attention, highest urgency first — new leads waiting on first contact,
        conversations gone quiet, meetings needing recaps, and outstanding proposals.
      </p>

      {items.length === 0 ? (
        <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-6 text-sm text-emerald-800">
          <CheckCircle2 size={18} />
          All caught up — no leads need follow-up right now.
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((f) => {
            const style = PRIORITY_STYLES[f.priority] ?? PRIORITY_STYLES[3];
            const Icon = style.icon;
            return (
              <Link
                key={f.lead.id}
                to={`/leads/${f.lead.id}`}
                className={`block rounded-xl border p-4 transition-shadow hover:shadow-md ${style.cls}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Icon size={15} className={f.priority === 1 ? "text-red-500" : "text-amber-500"} />
                    <span className="text-sm font-semibold">
                      {f.lead.name || f.lead.email || "Unnamed lead"}
                    </span>
                    {f.lead.company && (
                      <span className="text-sm text-slate-500">· {f.lead.company}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
                      {style.label}
                    </span>
                    <StageBadge stage={f.lead.stage} />
                  </div>
                </div>
                <div className="mt-1 text-sm text-slate-600">{f.reason}</div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
