import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../lib/api";
import { STAGES, STAGE_LABELS, type Lead, type Stage } from "../lib/types";

export default function Board() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [dragId, setDragId] = useState<number | null>(null);
  const [overStage, setOverStage] = useState<Stage | null>(null);
  const [dueCount, setDueCount] = useState(0);

  useEffect(() => {
    api.get<Lead[]>("/api/leads").then(setLeads).catch(() => toast.error("Failed to load leads"));
    api
      .get<unknown[]>("/api/followups")
      .then((f) => setDueCount(f.length))
      .catch(() => {});
  }, []);

  async function moveTo(stage: Stage) {
    setOverStage(null);
    if (dragId === null) return;
    const lead = leads.find((l) => l.id === dragId);
    setDragId(null);
    if (!lead || lead.stage === stage) return;
    const prev = leads;
    setLeads(leads.map((l) => (l.id === lead.id ? { ...l, stage } : l)));
    try {
      await api.patch(`/api/leads/${lead.id}`, { stage });
    } catch {
      setLeads(prev);
      toast.error("Failed to move lead");
    }
  }

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold tracking-tight">Pipeline</h1>
      {dueCount > 0 && (
        <Link
          to="/followups"
          className="mb-4 flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 hover:border-amber-300"
        >
          <span className="font-medium">
            {dueCount} lead{dueCount === 1 ? "" : "s"} need{dueCount === 1 ? "s" : ""} follow-up
          </span>
          <span className="text-xs font-semibold uppercase tracking-wide">View →</span>
        </Link>
      )}
      <div className="flex gap-3 overflow-x-auto pb-4">
        {STAGES.map((stage) => {
          const items = leads.filter((l) => l.stage === stage);
          return (
            <div
              key={stage}
              onDragOver={(e) => {
                e.preventDefault();
                setOverStage(stage);
              }}
              onDragLeave={() => setOverStage(null)}
              onDrop={() => moveTo(stage)}
              className={`w-64 shrink-0 rounded-xl border p-3 transition-colors ${
                overStage === stage
                  ? "border-slate-400 bg-slate-100"
                  : "border-slate-200 bg-white"
              }`}
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm font-semibold">{STAGE_LABELS[stage]}</span>
                <span className="rounded-full bg-slate-100 px-2 text-xs text-slate-500">
                  {items.length}
                </span>
              </div>
              <div className="flex flex-col gap-2">
                {items.map((lead) => (
                  <Link
                    key={lead.id}
                    to={`/leads/${lead.id}`}
                    draggable
                    onDragStart={() => setDragId(lead.id)}
                    className="block cursor-grab rounded-lg border border-slate-200 bg-white p-3 shadow-sm hover:border-slate-400"
                  >
                    <div className="text-sm font-medium">{lead.name || lead.email || "Unnamed"}</div>
                    {lead.company && (
                      <div className="text-xs text-slate-500">{lead.company}</div>
                    )}
                    {lead.estimated_value != null && (
                      <div className="mt-1 text-xs font-medium text-emerald-600">
                        ${lead.estimated_value.toLocaleString()}
                      </div>
                    )}
                  </Link>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
