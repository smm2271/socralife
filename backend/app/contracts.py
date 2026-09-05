# Generated; edit contracts/openapi.yaml instead.
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Error(ContractModel):
    code: str
    message: str
    trace_id: str
    details: dict[str, Any]

class User(ContractModel):
    id: str
    email: str
    name: str
    csrf_token: str
    ai_mode: Literal['fake', 'compatible']

class Usage(ContractModel):
    daily_generations: int
    daily_limit: int
    storage_bytes: int
    storage_limit_bytes: int
    global_model_calls: int
    global_limit: int

class RecordCreate(ContractModel):
    type: Literal['manual', 'blog', 'conversation', 'reflection', 'file']
    title: str = Field(max_length=300)
    content: str = Field(max_length=200000)
    occurred_at: str | None = Field(default=None)
    source_reflection_id: str | None = Field(default=None)

class RecordUpdate(ContractModel):
    version: int
    type: Literal['manual', 'blog', 'conversation', 'reflection', 'file'] | None = Field(default=None)
    title: str | None = Field(default=None, max_length=300)
    content: str | None = Field(default=None, max_length=200000)
    occurred_at: str | None = Field(default=None)
    source_reflection_id: str | None = Field(default=None)

class Record(ContractModel):
    id: str
    user_id: str
    version: int = Field(ge=1)
    created_at: str
    updated_at: str
    type: Literal['manual', 'blog', 'conversation', 'reflection', 'file']
    title: str = Field(max_length=300)
    content: str = Field(max_length=200000)
    occurred_at: str | None = Field(default=None)
    source_reflection_id: str | None = Field(default=None)

class EventCreate(ContractModel):
    title: str = Field(max_length=300)
    description: str | None = Field(default=None, max_length=20000)
    event_type: str | None = Field(default=None)
    started_at: str | None = Field(default=None)
    ended_at: str | None = Field(default=None)
    date_precision: Literal['day', 'month', 'year', 'unknown'] | None = Field(default=None)
    tags: list[str] | None = Field(default=None)
    user_verified: bool | None = Field(default=None)

class EventUpdate(ContractModel):
    version: int
    title: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=20000)
    event_type: str | None = Field(default=None)
    started_at: str | None = Field(default=None)
    ended_at: str | None = Field(default=None)
    date_precision: Literal['day', 'month', 'year', 'unknown'] | None = Field(default=None)
    tags: list[str] | None = Field(default=None)
    user_verified: bool | None = Field(default=None)

class Event(ContractModel):
    id: str
    user_id: str
    version: int = Field(ge=1)
    created_at: str
    updated_at: str
    title: str = Field(max_length=300)
    description: str | None = Field(default=None, max_length=20000)
    event_type: str | None = Field(default=None)
    started_at: str | None = Field(default=None)
    ended_at: str | None = Field(default=None)
    date_precision: Literal['day', 'month', 'year', 'unknown'] | None = Field(default=None)
    tags: list[str] | None = Field(default=None)
    user_verified: bool | None = Field(default=None)
    available_slots: int | None = Field(default=None)
    total_slots: int | None = Field(default=None)
    evidence_count: int | None = Field(default=None)
    record_ids: list[str] | None = Field(default=None)
    file_ids: list[str] | None = Field(default=None)

class SlotCreate(ContractModel):
    name: str = Field(max_length=200)
    category: str | None = Field(default=None)
    status: Literal['AVAILABLE', 'PENDING', 'EXPECTED', 'MISSING', 'NOT_REQUIRED', 'ARCHIVED'] | None = Field(default=None)
    expected_at: str | None = Field(default=None)
    required: bool | None = Field(default=None)
    linked_file_id: str | None = Field(default=None)

class SlotUpdate(ContractModel):
    version: int
    name: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None)
    status: Literal['AVAILABLE', 'PENDING', 'EXPECTED', 'MISSING', 'NOT_REQUIRED', 'ARCHIVED'] | None = Field(default=None)
    expected_at: str | None = Field(default=None)
    required: bool | None = Field(default=None)
    linked_file_id: str | None = Field(default=None)

class FileSlot(ContractModel):
    id: str
    user_id: str
    version: int = Field(ge=1)
    created_at: str
    updated_at: str
    event_id: str
    name: str = Field(max_length=200)
    category: str | None = Field(default=None)
    status: Literal['AVAILABLE', 'PENDING', 'EXPECTED', 'MISSING', 'NOT_REQUIRED', 'ARCHIVED']
    expected_at: str | None = Field(default=None)
    required: bool | None = Field(default=None)
    linked_file_id: str | None = Field(default=None)

class EventTemplate(ContractModel):
    id: str
    name: str
    description: str
    slots: list[SlotCreate]

class TemplateApply(ContractModel):
    slots: list[SlotCreate]

class EventLink(ContractModel):
    record_id: str | None = Field(default=None)
    file_id: str | None = Field(default=None)

class File(ContractModel):
    id: str
    user_id: str
    version: int = Field(ge=1)
    created_at: str
    updated_at: str
    filename: str
    mime_type: str
    size: int
    checksum: str
    status: Literal['QUARANTINED', 'SCANNING', 'CLEAN', 'REJECTED', 'FAILED']
    error: str | None = Field(default=None)
    record_id: str | None = Field(default=None)

class EvidenceCreate(ContractModel):
    source_type: Literal['record', 'event', 'insight', 'reflection']
    source_id: str
    source_version: int
    excerpt: str
    context: str | None = Field(default=None)
    occurred_at: str | None = Field(default=None)
    status: Literal['VALID', 'STALE', 'SOURCE_REMOVED'] | None = Field(default=None)

class Evidence(ContractModel):
    id: str
    user_id: str
    version: int = Field(ge=1)
    created_at: str
    updated_at: str
    source_type: Literal['record', 'event', 'insight', 'reflection']
    source_id: str
    source_version: int
    excerpt: str
    context: str
    occurred_at: str | None
    status: Literal['VALID', 'STALE', 'SOURCE_REMOVED']

class Observation(ContractModel):
    id: str
    user_id: str
    version: int = Field(ge=1)
    created_at: str
    updated_at: str
    statement: str
    evidence_refs: list[str]
    status: str

class Hypothesis(ContractModel):
    id: str
    user_id: str
    version: int = Field(ge=1)
    created_at: str
    updated_at: str
    session_id: str
    statement: str
    evidence_refs: list[str]
    counter_evidence_refs: list[str]
    uncertainty: str
    status: Literal['PROPOSED', 'CONFIRMED', 'REVISED', 'REJECTED']
    source_removed: bool | None = Field(default=None)

class HypothesisFeedback(ContractModel):
    version: int
    decision: Literal['agree', 'partial', 'reject', 'explore']
    statement: str | None = Field(default=None, max_length=10000)

class Insight(ContractModel):
    id: str
    user_id: str
    version: int = Field(ge=1)
    created_at: str
    updated_at: str
    statement: str
    evidence_refs: list[str]
    source_hypothesis_id: str | None = Field(default=None)
    valid_from: str
    last_confirmed_at: str
    supersedes: str | None = Field(default=None)
    status: Literal['ACTIVE', 'SUPERSEDED', 'WITHDRAWN', 'ARCHIVED', 'NEEDS_REVIEW']

class InsightUpdate(ContractModel):
    version: int
    statement: str | None = Field(default=None)
    status: Literal['ACTIVE', 'WITHDRAWN', 'ARCHIVED'] | None = Field(default=None)

class FeedbackResult(ContractModel):
    hypothesis: Hypothesis
    insight: Insight | None

class Reflection(ContractModel):
    id: str
    user_id: str
    version: int = Field(ge=1)
    created_at: str
    updated_at: str
    session_id: str
    record_id: str | None = Field(default=None)
    question: str
    core_conflict: str
    evidence_refs: list[str]
    counter_evidence_refs: list[str]
    current_understanding: str
    unknowns: list[str]
    actions: list[str]
    confirmed: bool
    source_removed: bool | None = Field(default=None)

class ReflectionUpdate(ContractModel):
    version: int
    question: str | None = Field(default=None)
    core_conflict: str | None = Field(default=None)
    evidence_refs: list[str] | None = Field(default=None)
    counter_evidence_refs: list[str] | None = Field(default=None)
    current_understanding: str | None = Field(default=None)
    unknowns: list[str] | None = Field(default=None)
    actions: list[str] | None = Field(default=None)
    confirmed: bool | None = Field(default=None)

class ArtifactSave(ContractModel):
    version: int
    confirmed: bool

class Action(ContractModel):
    id: str
    user_id: str
    version: int = Field(ge=1)
    created_at: str
    updated_at: str
    session_id: str | None = Field(default=None)
    reflection_id: str | None = Field(default=None)
    title: str
    status: Literal['PLANNED', 'IN_PROGRESS', 'COMPLETED', 'ABANDONED']
    result: str
    result_record_id: str | None = Field(default=None)

class ActionCreate(ContractModel):
    title: str
    session_id: str | None = Field(default=None)
    reflection_id: str | None = Field(default=None)

class ActionUpdate(ContractModel):
    version: int
    title: str | None = Field(default=None)
    status: Literal['PLANNED', 'IN_PROGRESS', 'COMPLETED', 'ABANDONED'] | None = Field(default=None)
    result: str | None = Field(default=None)

class Session(ContractModel):
    id: str
    user_id: str
    version: int = Field(ge=1)
    created_at: str
    updated_at: str
    title: str
    intent: Literal['INFORMATION', 'EXPLORATION', 'CONFLICT', 'VALIDATION', 'ACTION', 'REFLECTION'] | None = Field(default=None)
    stage: Literal['UNDERSTAND', 'RETRIEVE', 'EXPLORE', 'IDENTIFY', 'VERIFY', 'SYNTHESIZE', 'VISUALIZE', 'ACTION', 'RECORD']
    consecutive_questions: int

class SessionCreate(ContractModel):
    title: str | None = Field(default=None, max_length=300)

class Message(ContractModel):
    id: str
    user_id: str
    version: int = Field(ge=1)
    created_at: str
    updated_at: str
    session_id: str
    role: Literal['user', 'assistant']
    content: str
    run_id: str | None = Field(default=None)
    ui: list[dict[str, Any]]
    complete: bool

class MessageCreate(ContractModel):
    content: str = Field(min_length=1, max_length=20000)

class MessageAccepted(ContractModel):
    message_id: str
    run_id: str
    stream_url: str

class Run(ContractModel):
    id: str
    user_id: str
    version: int = Field(ge=1)
    created_at: str
    updated_at: str
    session_id: str
    message_id: str
    status: Literal['QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED']
    error: str | None = Field(default=None)
    trace_id: str

class StreamEvent(ContractModel):
    schema_version: Literal['1.0']
    event_id: str
    run_id: str
    sequence: int
    occurred_at: str
    type: Literal['stage.changed', 'text.delta', 'ui.ready', 'artifact.ready', 'run.completed', 'run.failed', 'run.cancelled']
    payload: dict[str, Any]

class ContextItem(ContractModel):
    id: str
    source_type: str
    source_id: str
    source_version: int
    title: str
    excerpt: str
    occurred_at: str | None = Field(default=None)
    confirmed: bool
    status: str
    counter_evidence: bool | None = Field(default=None)

class Health(ContractModel):
    status: str
    version: str

class DevLogin(ContractModel):
    email: str
    name: str | None = Field(default=None)

class RecordPage(ContractModel):
    items: list[Record]
    next_cursor: str | None

class EventPage(ContractModel):
    items: list[Event]
    next_cursor: str | None

class FileSlotPage(ContractModel):
    items: list[FileSlot]
    next_cursor: str | None

class FilePage(ContractModel):
    items: list[File]
    next_cursor: str | None

class EvidencePage(ContractModel):
    items: list[Evidence]
    next_cursor: str | None

class ObservationPage(ContractModel):
    items: list[Observation]
    next_cursor: str | None

class HypothesisPage(ContractModel):
    items: list[Hypothesis]
    next_cursor: str | None

class InsightPage(ContractModel):
    items: list[Insight]
    next_cursor: str | None

class ReflectionPage(ContractModel):
    items: list[Reflection]
    next_cursor: str | None

class ActionPage(ContractModel):
    items: list[Action]
    next_cursor: str | None

class SessionPage(ContractModel):
    items: list[Session]
    next_cursor: str | None

class MessagePage(ContractModel):
    items: list[Message]
    next_cursor: str | None

class EventTemplatePage(ContractModel):
    items: list[EventTemplate]
    next_cursor: str | None

Error.model_rebuild()
User.model_rebuild()
Usage.model_rebuild()
RecordCreate.model_rebuild()
RecordUpdate.model_rebuild()
Record.model_rebuild()
EventCreate.model_rebuild()
EventUpdate.model_rebuild()
Event.model_rebuild()
SlotCreate.model_rebuild()
SlotUpdate.model_rebuild()
FileSlot.model_rebuild()
EventTemplate.model_rebuild()
TemplateApply.model_rebuild()
EventLink.model_rebuild()
File.model_rebuild()
EvidenceCreate.model_rebuild()
Evidence.model_rebuild()
Observation.model_rebuild()
Hypothesis.model_rebuild()
HypothesisFeedback.model_rebuild()
Insight.model_rebuild()
InsightUpdate.model_rebuild()
FeedbackResult.model_rebuild()
Reflection.model_rebuild()
ReflectionUpdate.model_rebuild()
ArtifactSave.model_rebuild()
Action.model_rebuild()
ActionCreate.model_rebuild()
ActionUpdate.model_rebuild()
Session.model_rebuild()
SessionCreate.model_rebuild()
Message.model_rebuild()
MessageCreate.model_rebuild()
MessageAccepted.model_rebuild()
Run.model_rebuild()
StreamEvent.model_rebuild()
ContextItem.model_rebuild()
Health.model_rebuild()
DevLogin.model_rebuild()
RecordPage.model_rebuild()
EventPage.model_rebuild()
FileSlotPage.model_rebuild()
FilePage.model_rebuild()
EvidencePage.model_rebuild()
ObservationPage.model_rebuild()
HypothesisPage.model_rebuild()
InsightPage.model_rebuild()
ReflectionPage.model_rebuild()
ActionPage.model_rebuild()
SessionPage.model_rebuild()
MessagePage.model_rebuild()
EventTemplatePage.model_rebuild()
