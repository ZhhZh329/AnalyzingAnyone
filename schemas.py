from pydantic import BaseModel, ConfigDict
from typing import Any


class LooseModel(BaseModel):
    model_config = ConfigDict(extra="allow")


# ── Data loading ──────────────────────────────────────────────

class Source(LooseModel):
    id: str
    type: str       # free string
    date: str
    content: str


class SubjectData(LooseModel):
    subject: str
    sources: list[Source]


# ── Extractor output ──────────────────────────────────────────

class Event(LooseModel):
    id: str
    date: str
    what: str
    source_ids: list[str]


class EventTimeline(LooseModel):
    subject: str
    events: list[Event]


# ── Discipline output (v1 legacy) ────────────────────────────

class DisciplineAnalysis(LooseModel):
    discipline: str
    anchored: dict[str, Any]
    emergent: list[dict] = []


# ── Lens-based discipline output (v2.1) ─────────────────────

class LensConstruct(LooseModel):
    construct_key: str
    assessment: str = ""
    finding: str = ""
    evidence_ids: list[str] = []
    local_support: str = ""  # strong | moderate | weak | not_applicable


class LensAnnotation(LooseModel):
    discipline: str
    lens: str
    constructs: list[LensConstruct] = []
    emergent_constructs: list[dict] = []


# ── Triangulation output (v1 legacy) ─────────────────────────

class Triangulation(LooseModel):
    subject: str
    convergences: list[dict] = []
    cross_echoes: list[dict] = []
    tensions: list[dict] = []
    overall_portrait: str = ""


# ── Evidence assembler output (v2) ───────────────────────────

class EvidenceCard(LooseModel):
    id: str
    source_id: str
    source_type: str
    date: str
    kind: str               # quote | event | stance | pattern | relation_move | third_party_attribution
    summary: str
    verbatim_quote: str = ""
    first_hand_level: str   # self_statement | direct_report | third_party_summary
    reliability_note: str = ""
    editorial_risk: str = ""    # low | medium | high
    timeline_refs: list[str] = []


class EvidenceAssembly(LooseModel):
    subject: str
    timeline: list[Event]
    evidence_cards: list[EvidenceCard]


# ── Synthesis output (v2) ─────────────────────────────────────

class Synthesis(LooseModel):
    subject: str
    summary_findings: list[dict] = []
    complementary_views: list[dict] = []
    tensions: list[dict] = []
    scenario_implications: list[dict] = []


# ── Critic output (v2) ───────────────────────────────────────

class CriticOutput(LooseModel):
    flagged_claims: list[dict] = []
    construct_confidence: list[dict] = []
    notes: list[str] = []
