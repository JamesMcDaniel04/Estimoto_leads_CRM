import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CalendarPlus, Mail, Sparkles, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import StageBadge from "../components/StageBadge";
import { STAGES, STAGE_LABELS, type LeadDetail, type Stage } from "../lib/types";

const ACTIVITY_ICONS: Record<string, string> = {
  created: "🟢",
  email_ingested: "✉️",
  stage_changed: "🔀",
  meeting_scheduled: "📅",
  note: "📝",
};

export default function LeadDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [note, setNote] = useState("");
  const [showMeetingForm, setShowMeetingForm] = useState(false);
  const [meeting, setMeeting] = useState({ title: "", starts_at: "", duration: 30, location: "" });
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [suggesting, setSuggesting] = useState(false);

  const load = useCallback(() => {
    api
      .get<LeadDetail>(`/api/leads/${id}`)
      .then(setLead)
      .catch(() => {
        toast.error("Lead not found");
        navigate("/leads");
      });
  }, [id, navigate]);
  useEffect(load, [load]);

  if (!lead) return null;

  async function updateField(field: string, value: string | number | null) {
    try {
      await api.patch(`/api/leads/${lead!.id}`, { [field]: value });
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed");
    }
  }

  async function addNote(e: React.FormEvent) {
    e.preventDefault();
    if (!note.trim()) return;
    await api.post(`/api/leads/${lead!.id}/notes`, { body: note });
    setNote("");
    load();
  }

  async function scheduleMeeting(e: React.FormEvent) {
    e.preventDefault();
    const starts = new Date(meeting.starts_at);
    const ends = new Date(starts.getTime() + meeting.duration * 60_000);
    try {
      await api.post("/api/meetings", {
        lead_id: lead!.id,
        title: meeting.title,
        starts_at: starts.toISOString(),
        ends_at: ends.toISOString(),
        location: meeting.location,
      });
      setShowMeetingForm(false);
      setMeeting({ title: "", starts_at: "", duration: 30, location: "" });
      load();
      toast.success("Meeting scheduled");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to schedule");
    }
  }

  async function suggestNext() {
    setSuggesting(true);
    try {
      const resp = await api.post<{ suggestion: string }>(
        `/api/leads/${lead!.id}/suggest-next`,
        {}
      );
      setSuggestion(resp.suggestion);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Suggestion failed");
    } finally {
      setSuggesting(false);
    }
  }

  async function deleteLead() {
    if (!confirm(`Delete lead "${lead!.name || lead!.email}" and all its data?`)) return;
    await api.delete(`/api/leads/${lead!.id}`);
    toast.success("Lead deleted");
    navigate("/leads");
  }

  const inputCls =
    "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-900 focus:outline-none";

  return (
    <div className="max-w-5xl">
      <Link to="/leads" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900">
        <ArrowLeft size={14} /> All leads
      </Link>

      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {lead.name || lead.email || "Unnamed lead"}
          </h1>
          <div className="mt-1 flex items-center gap-2 text-sm text-slate-500">
            <StageBadge stage={lead.stage} />
            {lead.company && <span>{lead.company}</span>}
            <span>· source: {lead.source}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={lead.stage}
            onChange={(e) => updateField("stage", e.target.value as Stage)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            {STAGES.map((s) => (
              <option key={s} value={s}>
                {STAGE_LABELS[s]}
              </option>
            ))}
          </select>
          <button
            onClick={deleteLead}
            title="Delete lead"
            className="rounded-lg border border-slate-200 p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left: contact info + meetings + emails */}
        <div className="flex flex-col gap-6">
          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Contact
            </h2>
            <div className="grid grid-cols-2 gap-3">
              {(
                [
                  ["name", "Name"],
                  ["email", "Email"],
                  ["phone", "Phone"],
                  ["company", "Company"],
                ] as const
              ).map(([field, label]) => (
                <div key={field}>
                  <label className="mb-1 block text-xs text-slate-500">{label}</label>
                  <input
                    defaultValue={lead[field]}
                    onBlur={(e) => {
                      if (e.target.value !== lead[field]) updateField(field, e.target.value);
                    }}
                    className={inputCls}
                  />
                </div>
              ))}
              <div>
                <label className="mb-1 block text-xs text-slate-500">Est. value ($)</label>
                <input
                  type="number"
                  defaultValue={lead.estimated_value ?? ""}
                  onBlur={(e) => {
                    const v = e.target.value === "" ? null : Number(e.target.value);
                    if (v !== lead.estimated_value) updateField("estimated_value", v);
                  }}
                  className={inputCls}
                />
              </div>
            </div>
            <div className="mt-3">
              <label className="mb-1 block text-xs text-slate-500">Notes</label>
              <textarea
                defaultValue={lead.notes}
                rows={3}
                onBlur={(e) => {
                  if (e.target.value !== lead.notes) updateField("notes", e.target.value);
                }}
                className={inputCls}
              />
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
                Meetings
              </h2>
              <button
                onClick={() => setShowMeetingForm(!showMeetingForm)}
                className="flex items-center gap-1 rounded-lg bg-slate-900 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-slate-700"
              >
                <CalendarPlus size={14} /> Schedule
              </button>
            </div>
            {showMeetingForm && (
              <form onSubmit={scheduleMeeting} className="mb-3 flex flex-col gap-2 rounded-lg bg-slate-50 p-3">
                <input
                  placeholder="Title (e.g. Estimoto demo)"
                  value={meeting.title}
                  onChange={(e) => setMeeting({ ...meeting, title: e.target.value })}
                  required
                  className={inputCls}
                />
                <div className="flex gap-2">
                  <input
                    type="datetime-local"
                    value={meeting.starts_at}
                    onChange={(e) => setMeeting({ ...meeting, starts_at: e.target.value })}
                    required
                    className={inputCls}
                  />
                  <select
                    value={meeting.duration}
                    onChange={(e) => setMeeting({ ...meeting, duration: Number(e.target.value) })}
                    className="rounded-lg border border-slate-300 px-2 text-sm"
                  >
                    {[15, 30, 45, 60].map((m) => (
                      <option key={m} value={m}>
                        {m} min
                      </option>
                    ))}
                  </select>
                </div>
                <input
                  placeholder="Location or meeting link"
                  value={meeting.location}
                  onChange={(e) => setMeeting({ ...meeting, location: e.target.value })}
                  className={inputCls}
                />
                <button
                  type="submit"
                  className="rounded-lg bg-slate-900 py-2 text-sm font-semibold text-white hover:bg-slate-700"
                >
                  Schedule meeting
                </button>
              </form>
            )}
            <div className="flex flex-col gap-2">
              {lead.meetings.map((m) => (
                <div key={m.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                  <div className="font-medium">{m.title}</div>
                  <div className="text-xs text-slate-500">
                    {new Date(m.starts_at).toLocaleString()}
                    {m.location && <> · {m.location}</>}
                  </div>
                </div>
              ))}
              {lead.meetings.length === 0 && !showMeetingForm && (
                <div className="text-sm text-slate-400">No meetings yet.</div>
              )}
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Emails
            </h2>
            <div className="flex flex-col gap-2">
              {lead.emails.map((em) => (
                <details key={em.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                  <summary className="cursor-pointer">
                    <span className="inline-flex items-center gap-2 font-medium">
                      <Mail size={14} className="text-slate-400" />
                      {em.subject || "(no subject)"}
                    </span>
                    <span className="ml-2 text-xs text-slate-400">
                      {new Date(em.received_at).toLocaleDateString()} ·{" "}
                      {em.extraction_method === "claude" ? "AI extracted" : "basic extraction"}
                    </span>
                  </summary>
                  <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs text-slate-600">
                    {em.raw_body}
                  </pre>
                </details>
              ))}
              {lead.emails.length === 0 && (
                <div className="text-sm text-slate-400">No emails attached.</div>
              )}
            </div>
          </section>
        </div>

        {/* Right: activity timeline */}
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              Activity
            </h2>
            <button
              onClick={suggestNext}
              disabled={suggesting}
              title="Ask Claude for the best next action on this lead"
              className="flex items-center gap-1.5 rounded-lg border border-violet-200 bg-violet-50 px-2.5 py-1.5 text-xs font-semibold text-violet-700 hover:bg-violet-100 disabled:opacity-50"
            >
              <Sparkles size={13} />
              {suggesting ? "Thinking…" : "Suggest next step"}
            </button>
          </div>
          {suggestion && (
            <div className="mb-4 rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm text-violet-900">
              <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-violet-500">
                <Sparkles size={12} /> AI suggestion
              </div>
              {suggestion}
            </div>
          )}
          <form onSubmit={addNote} className="mb-4 flex gap-2">
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Add a note…"
              className={inputCls}
            />
            <button
              type="submit"
              className="shrink-0 rounded-lg bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-700"
            >
              Add
            </button>
          </form>
          <ol className="flex flex-col gap-3">
            {lead.activities.map((a) => (
              <li key={a.id} className="flex gap-3 text-sm">
                <span aria-hidden>{ACTIVITY_ICONS[a.type] ?? "•"}</span>
                <div>
                  <div className="text-slate-700">{a.body}</div>
                  <div className="text-xs text-slate-400">
                    {new Date(a.created_at).toLocaleString()}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}
