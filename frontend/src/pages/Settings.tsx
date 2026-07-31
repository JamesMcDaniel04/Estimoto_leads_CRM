import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Plug, Sparkles, XCircle } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";

interface Integrations {
  ai_extraction: boolean;
  gmail: {
    configured: boolean;
    connected: { id: number; email: string }[];
    last_poll: string | null;
    last_error: string | null;
    ingested_total: number;
  };
  imap: { mailboxes: string[]; last_error: string | null };
}

function StatusDot({ on }: { on: boolean }) {
  return on ? (
    <CheckCircle2 size={16} className="text-emerald-500" />
  ) : (
    <XCircle size={16} className="text-slate-300" />
  );
}

export default function Settings() {
  const [data, setData] = useState<Integrations | null>(null);

  const load = useCallback(() => {
    api.get<Integrations>("/api/integrations").then(setData).catch(() => {});
  }, []);
  useEffect(load, [load]);

  async function connectGmail() {
    try {
      const { url } = await api.get<{ url: string }>("/api/gmail/auth-url");
      window.location.href = url;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Google OAuth not configured");
    }
  }

  async function disconnectGmail(id: number, email: string) {
    if (!confirm(`Disconnect ${email}?`)) return;
    await api.delete(`/api/gmail/account/${id}`);
    toast.success(`${email} disconnected`);
    load();
  }

  if (!data) return null;

  const card = "rounded-xl border border-slate-200 bg-white p-5";
  const code = "rounded bg-slate-100 px-1 py-0.5 font-mono text-xs";

  return (
    <div className="max-w-3xl">
      <h1 className="mb-1 text-2xl font-bold tracking-tight">Settings</h1>
      <p className="mb-6 text-sm text-slate-500">
        Integration status. Anything off here is configured via <code className={code}>backend/.env</code>{" "}
        (copy <code className={code}>backend/.env.example</code>) and a backend restart.
      </p>

      <div className="flex flex-col gap-4">
        <section className={card}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles size={16} className="text-slate-400" />
              <h2 className="text-sm font-semibold">AI email extraction & next-step suggestions</h2>
            </div>
            <StatusDot on={data.ai_extraction} />
          </div>
          <p className="mt-2 text-sm text-slate-500">
            {data.ai_extraction ? (
              "Enabled — Claude extracts contact details from inbound email and can suggest next steps on each lead."
            ) : (
              <>
                Off — emails are parsed with basic header rules only. Set{" "}
                <code className={code}>ANTHROPIC_API_KEY</code> in{" "}
                <code className={code}>backend/.env</code> and restart the backend to enable
                Claude extraction and per-lead next-step suggestions.
              </>
            )}
          </p>
        </section>

        <section className={card}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Plug size={16} className="text-slate-400" />
              <h2 className="text-sm font-semibold">Gmail auto-ingestion</h2>
            </div>
            <StatusDot on={data.gmail.connected.length > 0} />
          </div>
          <div className="mt-2 text-sm text-slate-500">
            {data.gmail.connected.length > 0 ? (
              <div className="flex flex-col gap-2">
                {data.gmail.connected.map((a) => (
                  <div key={a.id} className="flex items-center justify-between">
                    <span>
                      <span className="font-mono text-xs">{a.email}</span> — polling for unread mail
                      {data.gmail.last_poll &&
                        `, last checked ${new Date(data.gmail.last_poll).toLocaleTimeString()}`}
                      {`, ${data.gmail.ingested_total} ingested since start`}
                    </span>
                    <button
                      onClick={() => disconnectGmail(a.id, a.email)}
                      className="text-xs font-medium text-red-500 hover:underline"
                    >
                      Disconnect
                    </button>
                  </div>
                ))}
                {data.gmail.last_error && (
                  <div className="text-xs text-amber-600">Error: {data.gmail.last_error}</div>
                )}
              </div>
            ) : data.gmail.configured ? (
              <div className="flex items-center justify-between gap-4">
                <span>OAuth is configured — connect the mailbox to start auto-ingesting.</span>
                <button
                  onClick={connectGmail}
                  className="flex shrink-0 items-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700"
                >
                  <Plug size={14} /> Connect Gmail
                </button>
              </div>
            ) : (
              <div>
                <p className="mb-2">
                  Not configured. To connect <span className="font-mono text-xs">hello@estimoto.io</span>:
                </p>
                <ol className="list-decimal space-y-1 pl-5">
                  <li>
                    Set <code className={code}>GOOGLE_OAUTH_CLIENT_ID</code> and{" "}
                    <code className={code}>GOOGLE_OAUTH_CLIENT_SECRET</code> in{" "}
                    <code className={code}>backend/.env</code> (the Estimoto product's Google
                    OAuth client works).
                  </li>
                  <li>
                    In Google Cloud console, add{" "}
                    <code className={code}>http://localhost:8000/api/gmail/callback</code> to that
                    client's authorized redirect URIs and enable the Gmail API.
                  </li>
                  <li>Restart the backend — a Connect button will appear here.</li>
                </ol>
              </div>
            )}
          </div>
        </section>

        {data.imap.mailboxes.length > 0 && (
          <section className={card}>
            <h2 className="text-sm font-semibold">IMAP fallback</h2>
            <p className="mt-2 text-sm text-slate-500">
              Active for {data.imap.mailboxes.join(", ")}
              {data.imap.last_error && ` — error: ${data.imap.last_error}`}
            </p>
          </section>
        )}
      </div>
    </div>
  );
}
