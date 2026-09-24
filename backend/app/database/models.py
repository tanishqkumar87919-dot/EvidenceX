import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    JSON,
    TypeDecorator,
)
from sqlalchemy.types import UserDefinedType
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Vector(UserDefinedType):
    """PostgreSQL pgvector type mapping.
    Maps to vector(dim) on PostgreSQL, and Text/String on SQLite fallback.
    """
    def __init__(self, dim: int = 768):
        self.dim = dim

    def get_col_spec(self, **kw):
        return f"vector({self.dim})"

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            if isinstance(value, (list, tuple)):
                return "[" + ",".join(str(float(x)) for x in value) + "]"
            return str(value)
        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            if isinstance(value, str):
                cleaned = value.strip("[]")
                if not cleaned:
                    return []
                return [float(x) for x in cleaned.split(",") if x.strip()]
            return value
        return process


class GUID(TypeDecorator):
    """Platform-independent GUID/UUID type.
    Uses PostgreSQL native UUID type, otherwise uses String(36).
    Gracefully coerces non-standard test IDs to deterministic UUIDs on PostgreSQL.
    """
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            val_str = str(value).strip()
            try:
                return str(uuid.UUID(val_str))
            except (ValueError, AttributeError):
                return str(uuid.uuid5(uuid.NAMESPACE_DNS, val_str))
        return str(value)

    def process_result_value(self, value, dialect):
        return None if value is None else str(value)



def generate_uuid() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class UserModel(Base):
    __tablename__ = "users"

    id = Column(GUID, primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="user")
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)

    investigations = relationship("InvestigationModel", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettingModel", back_populates="user", uselist=False, cascade="all, delete-orphan")


class InvestigationModel(Base):
    __tablename__ = "investigations"

    id = Column(GUID, primary_key=True, default=generate_uuid)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=True)
    input_mode = Column(String(20), nullable=False, default="LIVE", index=True)  # LIVE or DEMO
    input_type = Column(String(20), nullable=False, index=True)  # TEXT, IMAGE, URL, AUDIO
    status = Column(String(50), nullable=False, default="queued", index=True)  # queued, processing, completed, failed
    language = Column(String(10), nullable=False, default="en")
    verification_depth = Column(String(20), nullable=False, default="standard")  # quick, standard, deep
    evidence_preference = Column(String(20), nullable=False, default="balanced")  # balanced, official
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("input_mode IN ('LIVE', 'DEMO')", name="chk_inv_mode"),
        CheckConstraint("input_type IN ('TEXT', 'IMAGE', 'URL', 'AUDIO')", name="chk_inv_type"),
    )

    user = relationship("UserModel", back_populates="investigations")
    inputs = relationship("InputModel", back_populates="investigation", cascade="all, delete-orphan")
    claims = relationship("ClaimModel", back_populates="investigation", cascade="all, delete-orphan")
    verification_results = relationship("VerificationResultModel", back_populates="investigation", cascade="all, delete-orphan")
    timeline_events = relationship("TimelineEventModel", back_populates="investigation", cascade="all, delete-orphan")
    agent_events = relationship("AgentEventModel", back_populates="investigation", cascade="all, delete-orphan")
    copilot_messages = relationship("CopilotMessageModel", back_populates="investigation", cascade="all, delete-orphan")
    evidence_chunks = relationship("EvidenceChunkModel", back_populates="investigation", cascade="all, delete-orphan")


class InputModel(Base):
    __tablename__ = "inputs"

    id = Column(GUID, primary_key=True, default=generate_uuid)
    investigation_id = Column(GUID, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    input_type = Column(String(20), nullable=False)  # TEXT, IMAGE, URL, AUDIO
    original_text = Column(Text, nullable=True)
    image_storage_reference = Column(String(500), nullable=True)
    url = Column(String(2048), nullable=True)
    extracted_text = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)
    content_hash = Column(String(64), nullable=True, index=True)
    received_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    # Dedicated First-Class Audio Fields
    audio_storage_reference = Column(String(500), nullable=True)
    audio_filename = Column(String(255), nullable=True)
    audio_mime_type = Column(String(100), nullable=True)
    audio_duration = Column(Numeric(10, 2), nullable=True)
    audio_transcript = Column(Text, nullable=True, default=None)  # Strictly NULL in Phase 2
    audio_transcription_confidence = Column(Numeric(5, 4), nullable=True, default=None)  # Strictly NULL in Phase 2
    audio_transcription_status = Column(String(50), nullable=False, default="PENDING", index=True)  # PENDING, PROCESSING, COMPLETED, FAILED

    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)

    investigation = relationship("InvestigationModel", back_populates="inputs")


class ClaimModel(Base):
    __tablename__ = "claims"

    id = Column(GUID, primary_key=True, default=generate_uuid)
    investigation_id = Column(GUID, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    claim_type = Column(String(50), nullable=True)
    language = Column(String(10), nullable=False, default="en")
    context = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=False, default=0)
    extraction_confidence = Column(Numeric(5, 4), nullable=True)
    status = Column(String(50), nullable=False, default="extracted", index=True)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)

    investigation = relationship("InvestigationModel", back_populates="claims")
    tasks = relationship("ClaimTaskModel", back_populates="claim", cascade="all, delete-orphan")
    evidence_associations = relationship("ClaimEvidenceModel", back_populates="claim", cascade="all, delete-orphan")
    evidence_chunks = relationship("EvidenceChunkModel", back_populates="claim", cascade="all, delete-orphan")


class ClaimTaskModel(Base):
    __tablename__ = "claim_tasks"

    id = Column(GUID, primary_key=True, default=generate_uuid)
    claim_id = Column(GUID, ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True)
    task_description = Column(Text, nullable=False)
    search_query = Column(Text, nullable=True)
    task_status = Column(String(50), nullable=False, default="pending", index=True)
    completion_time = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)

    claim = relationship("ClaimModel", back_populates="tasks")


class SourceModel(Base):
    __tablename__ = "sources"

    id = Column(GUID, primary_key=True, default=generate_uuid)
    url = Column(String(2048), unique=True, nullable=False, index=True)
    canonical_url = Column(String(2048), nullable=True)
    title = Column(String(500), nullable=True)
    publisher = Column(String(255), nullable=True)
    domain = Column(String(255), nullable=True, index=True)
    source_type = Column(String(50), nullable=True)
    author = Column(String(255), nullable=True)
    publication_date = Column(DateTime(timezone=True), nullable=True, index=True)
    retrieved_date = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    evidence_items = relationship("EvidenceModel", back_populates="source")
    evidence_chunks = relationship("EvidenceChunkModel", back_populates="source", cascade="all, delete-orphan")


class EvidenceModel(Base):
    __tablename__ = "evidence"

    id = Column(GUID, primary_key=True, default=generate_uuid)
    claim_id = Column(GUID, ForeignKey("claims.id", ondelete="CASCADE"), nullable=True, index=True)
    source_id = Column(GUID, ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False, index=True)
    exact_relevant_excerpt = Column(Text, nullable=False)
    relationship_type = Column("relationship", String(50), nullable=False, index=True)  # SUPPORTING, CONTRADICTING, INCONCLUSIVE
    relevance = Column(Numeric(5, 4), nullable=True)
    source_assessment = Column(JSON, default=dict, nullable=False)
    temporal_information = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    source = relationship("SourceModel", back_populates="evidence_items")
    claim = relationship("ClaimModel")
    claim_associations = relationship("ClaimEvidenceModel", back_populates="evidence", cascade="all, delete-orphan")


class ClaimEvidenceModel(Base):
    __tablename__ = "claim_evidence"

    claim_id = Column(GUID, ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True)
    evidence_id = Column(GUID, ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True, index=True)
    relationship_type = Column("relationship", String(50), nullable=False, default="SUPPORTING")
    relevance_score = Column(Numeric(5, 4), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    claim = relationship("ClaimModel", back_populates="evidence_associations")
    evidence = relationship("EvidenceModel", back_populates="claim_associations")


class VerificationResultModel(Base):
    __tablename__ = "verification_results"

    id = Column(GUID, primary_key=True, default=generate_uuid)
    investigation_id = Column(GUID, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_id = Column(GUID, ForeignKey("claims.id", ondelete="CASCADE"), nullable=True, index=True)
    verdict = Column(String(50), nullable=False)  # SUPPORTED, REFUTED, INSUFFICIENT_EVIDENCE
    model_confidence = Column(Numeric(5, 4), nullable=True)
    evidence_sufficiency = Column(String(50), nullable=True)
    supporting_count = Column(Integer, default=0, nullable=False)
    contradicting_count = Column(Integer, default=0, nullable=False)
    inconclusive_count = Column(Integer, default=0, nullable=False)
    explanation = Column(Text, nullable=True)
    generated_timestamp = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    investigation = relationship("InvestigationModel", back_populates="verification_results")


class TimelineEventModel(Base):
    __tablename__ = "timeline_events"

    id = Column(GUID, primary_key=True, default=generate_uuid)
    investigation_id = Column(GUID, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_id = Column(GUID, ForeignKey("claims.id", ondelete="CASCADE"), nullable=True)
    event_type = Column(String(100), nullable=False)
    event_date = Column(DateTime(timezone=True), nullable=False, index=True)
    source_reference = Column(String(500), nullable=True)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    investigation = relationship("InvestigationModel", back_populates="timeline_events")


class AgentEventModel(Base):
    __tablename__ = "agent_events"

    id = Column(GUID, primary_key=True, default=generate_uuid)
    investigation_id = Column(GUID, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    stage = Column(String(50), nullable=True)
    message = Column(Text, nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False, index=True)

    investigation = relationship("InvestigationModel", back_populates="agent_events")


class CopilotMessageModel(Base):
    __tablename__ = "copilot_messages"

    id = Column(GUID, primary_key=True, default=generate_uuid)
    investigation_id = Column(GUID, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # user, assistant, system
    message = Column(Text, nullable=False)
    citations = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    investigation = relationship("InvestigationModel", back_populates="copilot_messages")


class UserSettingModel(Base):
    __tablename__ = "user_settings"

    id = Column(GUID, primary_key=True, default=generate_uuid)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    language = Column(String(10), nullable=False, default="en")
    theme = Column(String(20), nullable=False, default="light")
    verification_depth = Column(String(20), nullable=False, default="standard")
    evidence_preference = Column(String(20), nullable=False, default="balanced")
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)

    user = relationship("UserModel", back_populates="settings")


class EvidenceChunkModel(Base):
    __tablename__ = "evidence_chunks"

    id = Column(GUID, primary_key=True, default=generate_uuid)
    investigation_id = Column(GUID, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_id = Column(GUID, ForeignKey("claims.id", ondelete="CASCADE"), nullable=True, index=True)
    source_id = Column(GUID, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False, default=0)
    content = Column(Text, nullable=False)
    heading = Column(Text, nullable=True)
    character_count = Column(Integer, nullable=False, default=0)
    token_count = Column(Integer, nullable=True)
    embedding = Column(Vector(768), nullable=True)
    embedding_model = Column(String(100), nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    investigation = relationship("InvestigationModel", back_populates="evidence_chunks")
    claim = relationship("ClaimModel", back_populates="evidence_chunks")
    source = relationship("SourceModel", back_populates="evidence_chunks")

