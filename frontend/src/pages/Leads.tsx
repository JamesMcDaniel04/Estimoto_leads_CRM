import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import StageBadge from "../components/StageBadge";
import type { Lead } from "../lib/types";

export default function Leads() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", phone: "", company: "" });

  function load() {
    api.get<Lead[]>("/api/leads").then(setLeads).catch(() => toast.error("Failed to load leads"));
  }
  useEffect(load, []);

  async function createLead(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/api/leads", form);
      setForm({ name: "", email: "", phone: "", company: "" });
      setShowForm(false);
      load();
      toast.success("Lead created");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create lead");
    }
  }

  return (
    <div className="max-w-4xl">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Leads</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700"
        >
          <Plus size={16} /> New lead
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={createLead}
          className="mb-4 grid grid-cols-2 gap-3 rounded-xl border border-slate-200 bg-white p-4"
        >
          {(["name", "email", "phone", "company"] as const).map((field) => (
            <input
              key={field}
              placeholder={field[0].toUpperCase() + field.slice(1)}
              value={form[field]}
              onChange={(e) => setForm({ ...form, [field]: e.target.value })}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-900 focus:outline-none"
            />
          ))}
          <button
            type="submit"
            className="col-span-2 rounded-lg bg-slate-900 py-2 text-sm font-semibold text-white hover:bg-slate-700"
          >
            Create
          </button>
        </form>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Stage</th>
              <th className="px-4 py-3">Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {leads.map((lead) => (
              <tr key={lead.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium">
                  <Link to={`/leads/${lead.id}`} className="hover:underline">
                    {lead.name || "Unnamed"}
                  </Link>
                </td>
                <td className="px-4 py-3 text-slate-600">{lead.company}</td>
                <td className="px-4 py-3 text-slate-600">{lead.email}</td>
                <td className="px-4 py-3">
                  <StageBadge stage={lead.stage} />
                </td>
                <td className="px-4 py-3 text-slate-500">{lead.source}</td>
              </tr>
            ))}
            {leads.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-400">
                  No leads yet — ingest an email or add one manually.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
