import { STAGE_LABELS, type Stage } from "../lib/types";

const COLORS: Record<Stage, string> = {
  new: "bg-blue-100 text-blue-700",
  contacted: "bg-sky-100 text-sky-700",
  qualified: "bg-violet-100 text-violet-700",
  meeting_scheduled: "bg-amber-100 text-amber-700",
  proposal: "bg-orange-100 text-orange-700",
  won: "bg-emerald-100 text-emerald-700",
  lost: "bg-slate-200 text-slate-500",
};

export default function StageBadge({ stage }: { stage: Stage }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${COLORS[stage]}`}
    >
      {STAGE_LABELS[stage]}
    </span>
  );
}
