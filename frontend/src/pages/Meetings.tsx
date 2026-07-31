import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Download, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, getToken } from "../lib/api";
import type { Lead, Meeting } from "../lib/types";

export default function Meetings() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [leads, setLeads] = useState<Map<number, Lead>>(new Map());

  function load() {
    Promise.all([api.get<Meeting[]>("/api/meetings"), api.get<Lead[]>("/api/leads")])
      .then(([ms, ls]) => {
        setMeetings(ms);
        setLeads(new Map(ls.map((l) => [l.id, l])));
      })
      .catch(() => toast.error("Failed to load meetings"));
  }
  useEffect(load, []);

  async function remove(id: number) {
    if (!confirm("Delete this meeting?")) return;
    try {
      await api.delete(`/api/meetings/${id}`);
      load();
    } catch {
      toast.error("Failed to delete meeting");
    }
  }

  async function downloadIcs(meeting: Meeting) {
    const resp = await fetch(`/api/meetings/${meeting.id}/ics`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `meeting-${meeting.id}.ics`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const now = new Date().toISOString();
  const upcoming = meetings.filter((m) => m.ends_at >= now);
  const past = meetings.filter((m) => m.ends_at < now);

  function MeetingRow({ meeting }: { meeting: Meeting }) {
    const lead = leads.get(meeting.lead_id);
    return (
      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4">
        <div>
          <div className="text-sm font-semibold">{meeting.title}</div>
          <div className="text-xs text-slate-500">
            {new Date(meeting.starts_at).toLocaleString()} –{" "}
            {new Date(meeting.ends_at).toLocaleTimeString()}
            {meeting.location && <> · {meeting.location}</>}
          </div>
          {lead && (
            <Link
              to={`/leads/${lead.id}`}
              className="text-xs font-medium text-slate-600 hover:underline"
            >
              {lead.name || lead.email}
              {lead.company && ` · ${lead.company}`}
            </Link>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => downloadIcs(meeting)}
            title="Download .ics invite"
            className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-100"
          >
            <Download size={15} />
          </button>
          <button
            onClick={() => remove(meeting.id)}
            title="Delete meeting"
            className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-red-50 hover:text-red-600"
          >
            <Trash2 size={15} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <h1 className="mb-1 text-2xl font-bold tracking-tight">Meetings</h1>
      <p className="mb-6 text-sm text-slate-500">
        Schedule meetings from a lead's page. Download the .ics to add it to your calendar and
        email the invite to the customer.
      </p>
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
        Upcoming
      </h2>
      <div className="mb-8 flex flex-col gap-2">
        {upcoming.map((m) => (
          <MeetingRow key={m.id} meeting={m} />
        ))}
        {upcoming.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400">
            No upcoming meetings.
          </div>
        )}
      </div>
      {past.length > 0 && (
        <>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
            Past
          </h2>
          <div className="flex flex-col gap-2 opacity-60">
            {past.map((m) => (
              <MeetingRow key={m.id} meeting={m} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
