import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, Upload } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import type { IngestResponse } from "../lib/types";

export default function Inbox() {
  const navigate = useNavigate();
  const [rawText, setRawText] = useState("");
  const [busy, setBusy] = useState(false);

  function handleResult(result: IngestResponse) {
    toast.success(
      `${result.lead_created ? "Lead created" : "Matched existing lead"} (${
        result.extraction_method === "claude" ? "AI extraction" : "basic extraction"
      })`
    );
    navigate(`/leads/${result.lead.id}`);
  }

  async function ingestText(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      handleResult(await api.post<IngestResponse>("/api/emails/ingest", { raw_text: rawText }));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ingestion failed");
    } finally {
      setBusy(false);
    }
  }

  async function ingestFile(file: File) {
    setBusy(true);
    const form = new FormData();
    form.append("file", file);
    try {
      handleResult(await api.postForm<IngestResponse>("/api/emails/ingest-eml", form));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Ingestion failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl">
      <h1 className="mb-1 text-2xl font-bold tracking-tight">Email Inbox</h1>
      <p className="mb-6 text-sm text-slate-500">
        Paste an inbound customer email (or upload a .eml file). Contact details are extracted
        automatically and a lead is created or updated.
      </p>

      <form onSubmit={ingestText}>
        <textarea
          value={rawText}
          onChange={(e) => setRawText(e.target.value)}
          rows={12}
          placeholder={
            "From: Jane Doe <jane@shop.com>\nSubject: Interested in Estimoto\n\nHi, we'd like a demo for our collision shop…"
          }
          className="w-full rounded-xl border border-slate-300 bg-white p-4 font-mono text-sm focus:border-slate-900 focus:outline-none"
        />
        <div className="mt-3 flex items-center gap-3">
          <button
            type="submit"
            disabled={busy || !rawText.trim()}
            className="flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
          >
            <Sparkles size={16} />
            {busy ? "Extracting…" : "Extract & create lead"}
          </button>
          <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100">
            <Upload size={16} />
            Upload .eml
            <input
              type="file"
              accept=".eml,message/rfc822"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) ingestFile(file);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      </form>
    </div>
  );
}
