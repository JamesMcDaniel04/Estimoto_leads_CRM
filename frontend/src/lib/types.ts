export const STAGES = [
  "new",
  "contacted",
  "qualified",
  "meeting_scheduled",
  "proposal",
  "won",
  "lost",
] as const;

export type Stage = (typeof STAGES)[number];

export const STAGE_LABELS: Record<Stage, string> = {
  new: "New",
  contacted: "Contacted",
  qualified: "Qualified",
  meeting_scheduled: "Meeting Scheduled",
  proposal: "Proposal",
  won: "Won",
  lost: "Lost",
};

export interface Lead {
  id: number;
  name: string;
  email: string;
  phone: string;
  company: string;
  source: string;
  stage: Stage;
  estimated_value: number | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface Activity {
  id: number;
  type: string;
  body: string;
  created_at: string;
}

export interface EmailMessage {
  id: number;
  subject: string;
  sender: string;
  received_at: string;
  raw_body: string;
  extraction_json: string;
  extraction_method: string;
  mailbox: string;
}

export interface Meeting {
  id: number;
  lead_id: number;
  title: string;
  starts_at: string;
  ends_at: string;
  location: string;
  notes: string;
  created_at: string;
}

export interface LeadDetail extends Lead {
  emails: EmailMessage[];
  meetings: Meeting[];
  activities: Activity[];
}

export interface IngestResponse {
  lead: Lead;
  lead_created: boolean;
  extraction_method: string;
}
