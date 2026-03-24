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


# ── Discipline output ─────────────────────────────────────────

class DisciplineAnalysis(LooseModel):
    discipline: str
    anchored: dict[str, Any]
    emergent: list[dict] = []


# ── Triangulation output ──────────────────────────────────────

class Triangulation(LooseModel):
    subject: str
    convergences: list[dict] = []
    cross_echoes: list[dict] = []
    tensions: list[dict] = []
    overall_portrait: str = ""
