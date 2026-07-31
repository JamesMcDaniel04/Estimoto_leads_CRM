import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Mail, Plug, Sparkles, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import type { IngestResponse } from "../lib/types";

interface GmailStatus {
  configured: boolean;
  connected: { id: number; email: string; connected_at: string }[];
  last_poll: string | null;
  last_error: string | null;
  ingested_total: number;
}

interface ImapStatus {
  mailboxes: string[];
  last_poll: string | null;
  last_error: string | null;
  ingested_total: number;
}

export default function Inbox() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [rawText, setRawText] = useState("");
  const [busy, setBusy] = useState(false);
  const [gmail, setGmail] = useState<GmailStatus | null>(null);
  const [imap, setImap] = useState<ImapStatus | null>(null);

  const loadStatus = useCallback(() => {
    api.get<GmailStatus>("/api/gmail/status").then(setGmail).catch(() => {});
    api.get<ImapStatus>("/api/emails/imap-status").then(setImap).catch(() => {});
  }, []);
  useEffect(loadStatus, [loadStatus]);

  useEffect(() => {
    const result = searchParams.get("gmail");
    if (!result) return;
    if (result === "connected") toast.success("Gmail connected — inbound mail now auto-ingests");
    else toast.error("Gmail connection failed — try again");
    setSearchParams({}, { replace: true });
    loadStatus();
  }, [searchParams, setSearchParams, loadStatus]);

  async function connectGmail() {
    try {
      const { url } = await api.get<{ url: string }>("/api/gmail/auth-url");
      window.location.href = url;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Google OAuth not configured");
    }
  }

  async function disconnectGmail(id: number, email: string) {
    if (!confirm(`Disconnect ${email}? Auto-ingestion for it will stop.`)) return;
    try {
      await api.delete(`/api/gmail/account/${id}`);
      toast.success(`${email} disconnected`);
      loadStatus();
    } catch {
      toast.error("Failed to disconnect");
    }
  }

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
      <p className="mb-4 text-sm text-slate-500">
        Connect Gmail to auto-ingest inbound customer email, or paste an email / upload a .eml
        below. Contact details are extracted automatically and a lead is created or updated.
      </p>

      {gmail && gmail.connected.length > 0 && (
        <div
          className={`mb-3 flex items-start gap-3 rounded-xl border p-4 text-sm ${
            gmail.last_error
              ? "border-amber-300 bg-amber-50 text-amber-800"
              : "border-emerald-200 bg-emerald-50 text-emerald-800"
          }`}
        >
          <Mail size={16} className="mt-0.5 shrink-0" />
          <div className="flex-1">
            <div className="font-medium">Gmail auto-ingest active</div>
            {gmail.connected.map((a) => (
              <div key={a.id} className="mt-1 flex items-center gap-2 text-xs">
                <span className="font-mono">{a.email}</span>
                <button
                  onClick={() => disconnectGmail(a.id, a.email)}
                  title={`Disconnect ${a.email}`}
                  className="rounded p-0.5 opacity-60 hover:bg-white/60 hover:opacity-100"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
            <div className="mt-1 text-xs opacity-80">
              {gmail.last_poll
                ? `Last checked ${new Date(gmail.last_poll).toLocaleString()} · ${
                    gmail.ingested_total
                  } email${gmail.ingested_total === 1 ? "" : "s"} ingested since start`
                : "First poll pending…"}
              {gmail.last_error && <> · Error: {gmail.last_error}</>}
            </div>
          </div>
        </div>
      )}

      {gmail && gmail.connected.length === 0 && (
        <div className="mb-3 flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 text-sm">
          {gmail.configured ? (
            <>
              <span className="text-slate-600">
                No mailbox connected — connect hello@estimoto.io to auto-ingest inbound email.
              </span>
              <button
                onClick={connectGmail}
                className="flex shrink-0 items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700"
              >
                <Plug size={15} /> Connect Gmail
              </button>
            </>
          ) : (
            <span className="text-slate-500">
              Gmail integration not configured — set{" "}
              <code className="font-mono">GOOGLE_OAUTH_CLIENT_ID</code> and{" "}
              <code className="font-mono">GOOGLE_OAUTH_CLIENT_SECRET</code> in{" "}
              <code className="font-mono">backend/.env</code> (see backend/.env.example).
            </span>
          )}
        </div>
      )}

      {imap && imap.mailboxes.length > 0 && (
        <div className="mb-3 rounded-xl border border-slate-200 bg-white p-4 text-xs text-slate-500">
          IMAP fallback active: {imap.mailboxes.join(", ")}
          {imap.last_error && <> · Error: {imap.last_error}</>}
        </div>
      )}

      <form onSubmit={ingestText} className="mt-6">
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
