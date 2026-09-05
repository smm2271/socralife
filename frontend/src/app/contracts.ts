// Generated; edit contracts/openapi.yaml instead.
export interface Error {
  code: string;
  message: string;
  trace_id: string;
  details: Record<string, unknown>;
}
export interface User {
  id: string;
  email: string;
  name: string;
  csrf_token: string;
  ai_mode: "fake" | "compatible";
}
export interface Usage {
  daily_generations: number;
  daily_limit: number;
  storage_bytes: number;
  storage_limit_bytes: number;
  global_model_calls: number;
  global_limit: number;
}
export interface RecordCreate {
  type: "manual" | "blog" | "conversation" | "reflection" | "file";
  title: string;
  content: string;
  occurred_at?: string | null;
  source_reflection_id?: string | null;
}
export interface RecordUpdate {
  version: number;
  type?: "manual" | "blog" | "conversation" | "reflection" | "file";
  title?: string;
  content?: string;
  occurred_at?: string | null;
  source_reflection_id?: string | null;
}
export interface Record {
  id: string;
  user_id: string;
  version: number;
  created_at: string;
  updated_at: string;
  type: "manual" | "blog" | "conversation" | "reflection" | "file";
  title: string;
  content: string;
  occurred_at?: string | null;
  source_reflection_id?: string | null;
}
export interface EventCreate {
  title: string;
  description?: string;
  event_type?: string;
  started_at?: string | null;
  ended_at?: string | null;
  date_precision?: "day" | "month" | "year" | "unknown";
  tags?: Array<string>;
  user_verified?: boolean;
}
export interface EventUpdate {
  version: number;
  title?: string;
  description?: string;
  event_type?: string;
  started_at?: string | null;
  ended_at?: string | null;
  date_precision?: "day" | "month" | "year" | "unknown";
  tags?: Array<string>;
  user_verified?: boolean;
}
export interface Event {
  id: string;
  user_id: string;
  version: number;
  created_at: string;
  updated_at: string;
  title: string;
  description?: string;
  event_type?: string;
  started_at?: string | null;
  ended_at?: string | null;
  date_precision?: "day" | "month" | "year" | "unknown";
  tags?: Array<string>;
  user_verified?: boolean;
  available_slots?: number;
  total_slots?: number;
  evidence_count?: number;
  record_ids?: Array<string>;
  file_ids?: Array<string>;
}
export interface SlotCreate {
  name: string;
  category?: string;
  status?: "AVAILABLE" | "PENDING" | "EXPECTED" | "MISSING" | "NOT_REQUIRED" | "ARCHIVED";
  expected_at?: string | null;
  required?: boolean;
  linked_file_id?: string | null;
}
export interface SlotUpdate {
  version: number;
  name?: string;
  category?: string;
  status?: "AVAILABLE" | "PENDING" | "EXPECTED" | "MISSING" | "NOT_REQUIRED" | "ARCHIVED";
  expected_at?: string | null;
  required?: boolean;
  linked_file_id?: string | null;
}
export interface FileSlot {
  id: string;
  user_id: string;
  version: number;
  created_at: string;
  updated_at: string;
  event_id: string;
  name: string;
  category?: string;
  status: "AVAILABLE" | "PENDING" | "EXPECTED" | "MISSING" | "NOT_REQUIRED" | "ARCHIVED";
  expected_at?: string | null;
  required?: boolean;
  linked_file_id?: string | null;
}
export interface EventTemplate {
  id: string;
  name: string;
  description: string;
  slots: Array<SlotCreate>;
}
export interface TemplateApply {
  slots: Array<SlotCreate>;
}
export interface EventLink {
  record_id?: string | null;
  file_id?: string | null;
}
export interface File {
  id: string;
  user_id: string;
  version: number;
  created_at: string;
  updated_at: string;
  filename: string;
  mime_type: string;
  size: number;
  checksum: string;
  status: "QUARANTINED" | "SCANNING" | "CLEAN" | "REJECTED" | "FAILED";
  error?: string | null;
  record_id?: string | null;
}
export interface EvidenceCreate {
  source_type: "record" | "event" | "insight" | "reflection";
  source_id: string;
  source_version: number;
  excerpt: string;
  context?: string;
  occurred_at?: string | null;
  status?: "VALID" | "STALE" | "SOURCE_REMOVED";
}
export interface Evidence {
  id: string;
  user_id: string;
  version: number;
  created_at: string;
  updated_at: string;
  source_type: "record" | "event" | "insight" | "reflection";
  source_id: string;
  source_version: number;
  excerpt: string;
  context: string;
  occurred_at: string | null;
  status: "VALID" | "STALE" | "SOURCE_REMOVED";
}
export interface Observation {
  id: string;
  user_id: string;
  version: number;
  created_at: string;
  updated_at: string;
  statement: string;
  evidence_refs: Array<string>;
  status: string;
}
export interface Hypothesis {
  id: string;
  user_id: string;
  version: number;
  created_at: string;
  updated_at: string;
  session_id: string;
  statement: string;
  evidence_refs: Array<string>;
  counter_evidence_refs: Array<string>;
  uncertainty: string;
  status: "PROPOSED" | "CONFIRMED" | "REVISED" | "REJECTED";
  source_removed?: boolean;
}
export interface HypothesisFeedback {
  version: number;
  decision: "agree" | "partial" | "reject" | "explore";
  statement?: string;
}
export interface Insight {
  id: string;
  user_id: string;
  version: number;
  created_at: string;
  updated_at: string;
  statement: string;
  evidence_refs: Array<string>;
  source_hypothesis_id?: string | null;
  valid_from: string;
  last_confirmed_at: string;
  supersedes?: string | null;
  status: "ACTIVE" | "SUPERSEDED" | "WITHDRAWN" | "ARCHIVED" | "NEEDS_REVIEW";
}
export interface InsightUpdate {
  version: number;
  statement?: string;
  status?: "ACTIVE" | "WITHDRAWN" | "ARCHIVED";
}
export interface FeedbackResult {
  hypothesis: Hypothesis;
  insight: Insight | null;
}
export interface Reflection {
  id: string;
  user_id: string;
  version: number;
  created_at: string;
  updated_at: string;
  session_id: string;
  record_id?: string | null;
  question: string;
  core_conflict: string;
  evidence_refs: Array<string>;
  counter_evidence_refs: Array<string>;
  current_understanding: string;
  unknowns: Array<string>;
  actions: Array<string>;
  confirmed: boolean;
  source_removed?: boolean;
}
export interface ReflectionUpdate {
  version: number;
  question?: string;
  core_conflict?: string;
  evidence_refs?: Array<string>;
  counter_evidence_refs?: Array<string>;
  current_understanding?: string;
  unknowns?: Array<string>;
  actions?: Array<string>;
  confirmed?: boolean;
}
export interface ArtifactSave {
  version: number;
  confirmed: boolean;
}
export interface Action {
  id: string;
  user_id: string;
  version: number;
  created_at: string;
  updated_at: string;
  session_id?: string | null;
  reflection_id?: string | null;
  title: string;
  status: "PLANNED" | "IN_PROGRESS" | "COMPLETED" | "ABANDONED";
  result: string;
  result_record_id?: string | null;
}
export interface ActionCreate {
  title: string;
  session_id?: string | null;
  reflection_id?: string | null;
}
export interface ActionUpdate {
  version: number;
  title?: string;
  status?: "PLANNED" | "IN_PROGRESS" | "COMPLETED" | "ABANDONED";
  result?: string;
}
export interface Session {
  id: string;
  user_id: string;
  version: number;
  created_at: string;
  updated_at: string;
  title: string;
  intent?: "INFORMATION" | "EXPLORATION" | "CONFLICT" | "VALIDATION" | "ACTION" | "REFLECTION" | null;
  stage: "UNDERSTAND" | "RETRIEVE" | "EXPLORE" | "IDENTIFY" | "VERIFY" | "SYNTHESIZE" | "VISUALIZE" | "ACTION" | "RECORD";
  consecutive_questions: number;
}
export interface SessionCreate {
  title?: string;
}
export interface Message {
  id: string;
  user_id: string;
  version: number;
  created_at: string;
  updated_at: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  run_id?: string | null;
  ui: Array<Record<string, unknown>>;
  complete: boolean;
}
export interface MessageCreate {
  content: string;
}
export interface MessageAccepted {
  message_id: string;
  run_id: string;
  stream_url: string;
}
export interface Run {
  id: string;
  user_id: string;
  version: number;
  created_at: string;
  updated_at: string;
  session_id: string;
  message_id: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
  error?: string | null;
  trace_id: string;
}
export interface StreamEvent {
  schema_version: "1.0";
  event_id: string;
  run_id: string;
  sequence: number;
  occurred_at: string;
  type: "stage.changed" | "text.delta" | "ui.ready" | "artifact.ready" | "run.completed" | "run.failed" | "run.cancelled";
  payload: Record<string, unknown>;
}
export interface ContextItem {
  id: string;
  source_type: string;
  source_id: string;
  source_version: number;
  title: string;
  excerpt: string;
  occurred_at?: string | null;
  confirmed: boolean;
  status: string;
  counter_evidence?: boolean;
}
export interface Health {
  status: string;
  version: string;
}
export interface DevLogin {
  email: string;
  name?: string;
}
export interface RecordPage {
  items: Array<Record>;
  next_cursor: string | null;
}
export interface EventPage {
  items: Array<Event>;
  next_cursor: string | null;
}
export interface FileSlotPage {
  items: Array<FileSlot>;
  next_cursor: string | null;
}
export interface FilePage {
  items: Array<File>;
  next_cursor: string | null;
}
export interface EvidencePage {
  items: Array<Evidence>;
  next_cursor: string | null;
}
export interface ObservationPage {
  items: Array<Observation>;
  next_cursor: string | null;
}
export interface HypothesisPage {
  items: Array<Hypothesis>;
  next_cursor: string | null;
}
export interface InsightPage {
  items: Array<Insight>;
  next_cursor: string | null;
}
export interface ReflectionPage {
  items: Array<Reflection>;
  next_cursor: string | null;
}
export interface ActionPage {
  items: Array<Action>;
  next_cursor: string | null;
}
export interface SessionPage {
  items: Array<Session>;
  next_cursor: string | null;
}
export interface MessagePage {
  items: Array<Message>;
  next_cursor: string | null;
}
export interface EventTemplatePage {
  items: Array<EventTemplate>;
  next_cursor: string | null;
}
export type UIComponent = { schema_version: "1.0"; title?: string; type: "text"; text: string } |
{ schema_version: "1.0"; title?: string; type: "question"; text: string; purpose: string; target_uncertainty: string } |
{ schema_version: "1.0"; title?: string; type: "choice_cards"; choices: Array<{ id: string; label: string; description?: string }> } |
{ schema_version: "1.0"; title?: string; type: "evidence_card"; evidence_refs: Array<string>; text: string } |
{ schema_version: "1.0"; title?: string; type: "hypothesis_card"; hypothesis_id: string | null; version?: number; statement: string; evidence_refs: Array<string>; counter_evidence_refs?: Array<string>; uncertainty: string } |
{ schema_version: "1.0"; title?: string; type: "reflection_card"; reflection_id?: string | null; question: string; current_understanding: string; unknowns: Array<string>; actions: Array<string>; confirmed: boolean } |
{ schema_version: "1.0"; title?: string; type: "timeline"; items: Array<{ label: string; date: string | null; evidence_refs: Array<string>; confirmed: boolean }> } |
{ schema_version: "1.0"; title?: string; type: "comparison"; dimensions: Array<string>; options: Array<{ label: string; values: Array<string>; evidence_refs: Array<string>; confirmed: boolean }>; time_range: string } |
{ schema_version: "1.0"; title?: string; type: "action_card"; action_id?: string | null; text: string; purpose: string; review_prompt: string };
