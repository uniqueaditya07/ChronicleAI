"""Read-only, case-scoped timeline and printable report helpers."""
import calendar
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
import hashlib
import os
import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Case, EvidenceFile, EvidenceLine
from app.schemas import AnalysisCitation, TimelineEvent, TimelineResponse
from app.storage import DEFAULT_STORAGE_DIR
from app.analysis_service import validate_analysis_payload, validate_and_filter_citations


TIMELINE_DISCLAIMER = (
    "Dates and descriptions are extracted from evidence statements, not verified event occurrences. "
    "No dates are inferred. Ambiguous, incomplete and invalid dates are listed separately."
)
MONTHS = {name.lower(): number for number, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): number for number, name in enumerate(calendar.month_abbr) if name})
MONTHS["sept"] = 9
MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)"
DATE_PATTERNS = [
    ("iso", re.compile(r"(?<![\w-])(\d{4})-(\d{2})-(\d{2})(?![\w-])")),
    ("day_month", re.compile(rf"\b(\d{{1,2}})\s+({MONTH})\.?\s+(\d{{4}})\b", re.I)),
    ("month_day", re.compile(rf"\b({MONTH})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.I)),
    ("numeric", re.compile(r"(?<![\w/])(\d{1,2})/(\d{1,2})/(\d{4})(?![\w/])")),
    ("partial", re.compile(rf"\b({MONTH})\.?\s+(\d{{4}})\b", re.I)),
    ("relative", re.compile(r"\b(?:yesterday|today|tomorrow|last\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))\b", re.I)),
]


def require_case(case_id: int, db: Session) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if case is None:
        raise HTTPException(404, "Case not found.")
    return case


def case_evidence(case_id: int, db: Session):
    files = db.query(EvidenceFile).filter(EvidenceFile.case_id == case_id).order_by(EvidenceFile.id).all()
    lines = (db.query(EvidenceLine).join(EvidenceFile)
             .filter(EvidenceFile.case_id == case_id)
             .order_by(EvidenceLine.evidence_file_id, EvidenceLine.line_number).all())
    return files, lines


def resolve_date(kind, match):
    values = match.groups()
    if kind == "partial":
        return None, "incomplete", "Month and year only; no day is assigned."
    if kind == "relative":
        return None, "incomplete", "Relative date has no reliable reference date."
    try:
        if kind == "iso":
            year, month, day = map(int, values)
        elif kind == "day_month":
            day, month, year = int(values[0]), MONTHS[values[1].lower()], int(values[2])
        elif kind == "month_day":
            month, day, year = MONTHS[values[0].lower()], int(values[1]), int(values[2])
        else:
            first, second, year = map(int, values)
            possibilities = set()
            for month, day in ((second, first), (first, second)):
                try:
                    possibilities.add(date(year, month, day).isoformat())
                except ValueError:
                    pass
            if len(possibilities) > 1:
                return None, "ambiguous", "Day/month order is ambiguous; no ordering is assigned."
            if len(possibilities) == 1:
                return possibilities.pop(), "explicit", "Only one calendar interpretation is valid."
            raise ValueError("Invalid calendar date")
        return date(year, month, day).isoformat(), "explicit", "Explicit calendar date in the cited text."
    except (ValueError, KeyError):
        return None, "invalid", "The written date is not a valid calendar date."


def build_timeline(case_id: int, db: Session) -> TimelineResponse:
    require_case(case_id, db)
    files, lines = case_evidence(case_id, db)
    filenames = {file.id: file.original_filename for file in files}
    events, undated = [], []
    for line in lines:
        mentions, occupied = [], []
        for kind, pattern in DATE_PATTERNS:
            for match in pattern.finditer(line.content):
                if any(match.start() < end and match.end() > start for start, end in occupied):
                    continue
                occupied.append(match.span())
                normalized, status, note = resolve_date(kind, match)
                mentions.append((match.start(), match.group(), normalized, status, note))
        for _, text, normalized, status, note in sorted(mentions):
            if len(mentions) > 1:
                note += " This line contains multiple dates; review the source before associating an event with a date."
            item = TimelineEvent(
                date_text=text, normalized_date=normalized, date_status=status,
                description=line.content, note=note,
                citations=[AnalysisCitation(evidence_file_id=line.evidence_file_id,
                    original_filename=filenames[line.evidence_file_id], start_line=line.line_number,
                    end_line=line.line_number, snippet=line.content[:120])],
            )
            (events if normalized else undated).append(item)
    events.sort(key=lambda event: (event.normalized_date, event.citations[0].evidence_file_id, event.citations[0].start_line))
    return TimelineResponse(case_id=case_id, events=events, undated=undated, disclaimer=TIMELINE_DISCLAIMER)


def evidence_integrity(file):
    # Reporting must never create storage directories or mutate the vault.
    case_dir = (Path(os.getenv("CHRONICLE_STORAGE_DIR", DEFAULT_STORAGE_DIR)) / f"case_{file.case_id}").resolve()
    path = (case_dir / file.stored_filename).resolve()
    if not path.is_relative_to(case_dir):
        return "unreadable", None
    if not path.is_file():
        return "missing", None
    try:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(65536), b""):
                digest.update(block)
        computed = digest.hexdigest()
        return ("verified" if computed.lower() == file.sha256_hash.lower() else "mismatch"), computed
    except OSError:
        return "unreadable", None


def build_report(case_id: int, analysis, db: Session) -> str:
    case = require_case(case_id, db)
    files, lines = case_evidence(case_id, db)
    file_map = {file.id: file.original_filename for file in files}
    line_map = {(line.evidence_file_id, line.line_number): line.content for line in lines}
    warnings, sections = [], {}
    questions = []
    if analysis is not None:
        try:
            if type(analysis.get("case_id")) is not int or analysis["case_id"] != case_id:
                raise ValueError("Wrong case")
            validate_analysis_payload(analysis)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(422, "Report analysis must be a valid snapshot for this case.") from None
        for section in ("summary", "documented_observations", "possible_interpretations"):
            sections[section] = validate_and_filter_citations(analysis[section],
                "possible_interpretation" if section == "possible_interpretations" else "documented_observation",
                file_map, set(line_map), line_map, warnings)
        questions = [question.strip() for question in analysis["unresolved_questions"] if question.strip()]
    timeline = build_timeline(case_id, db)
    cited = set()

    def citations(items):
        links = []
        for citation in items:
            for number in range(citation.start_line, citation.end_line + 1):
                cited.add((citation.evidence_file_id, number))
            links.append(f'<a href="#evidence-{citation.evidence_file_id}-L{citation.start_line}">{escape(citation.original_filename)}: L{citation.start_line}–{citation.end_line}</a>')
        return " · ".join(links)

    body = ["<h1>ChronicleAI Investigation Report</h1>",
        f"<h2>{escape(case.case_number)} — {escape(case.title)}</h2>",
        f"<p>Case ID: {case.id} · Status: {escape(case.status.value)} · Generated (UTC): {datetime.now(timezone.utc).isoformat()}</p>",
        f"<p>Created (UTC): {case.created_at.isoformat()} · Updated (UTC): {case.updated_at.isoformat()}</p>",
        f"<p>{escape(case.description or '')}</p>",
        "<p><strong>Evidence ≠ inference.</strong> AI statements require independent review. Valid references do not establish that a claim is true. This report is not a chain-of-custody certification.</p>",
        '<button onclick="window.print()">Print / Save as PDF</button>',
        "<h2>Evidence inventory and integrity at export</h2><table><thead><tr><th>File</th><th>Lines / bytes</th><th>Recorded SHA-256</th><th>Integrity / computed SHA-256</th></tr></thead><tbody>"]
    for file in files:
        integrity, computed = evidence_integrity(file)
        body.append(f"<tr><td>{escape(file.original_filename)}</td><td>{file.line_count} / {file.file_size}</td><td>{escape(file.sha256_hash)}</td><td>{integrity}<br>{computed or 'Unavailable'}</td></tr>")
    body.append("</tbody></table>")
    if not files:
        body.append("<p>No evidence has been uploaded.</p>")
    if analysis is None:
        body.append("<p><strong>No AI analysis snapshot supplied.</strong> Generate case analysis before exporting to include AI observations, interpretations, and questions. Export does not contact Gemini.</p>")
    else:
        body.append("<p>AI analysis snapshot: all included references were revalidated against this case at export. Statements are AI generated, not independently verified findings.</p>")
    for section, heading in (("summary", "AI case summary"), ("documented_observations", "Documented observations — AI statements about evidence"), ("possible_interpretations", "Possible interpretations — hypotheses, not facts")):
        body.append(f"<h2>{heading}</h2><ul>")
        for claim in sections.get(section, []):
            body.append(f"<li>{escape(claim.statement)}<br>{citations(claim.citations)}</li>")
        body.append("</ul>" if sections.get(section) else "</ul><p>No statements available.</p>")
    body.extend(["<h2>Evidence-linked timeline</h2>", f"<p>{escape(timeline.disclaimer)}</p><ul>"])
    for event in timeline.events + timeline.undated:
        body.append(f"<li><strong>{escape(event.normalized_date or event.date_text)} [{event.date_status}]</strong>: {escape(event.description)}<br>{escape(event.note)}<br>{citations(event.citations)}</li>")
    body.append("</ul>" if timeline.events or timeline.undated else "</ul><p>No recognized date mentions.</p>")
    body.append("<h2>Unresolved questions</h2><ul>")
    body.extend(f"<li>{escape(question)}</li>" for question in questions)
    body.append("</ul>" if questions else "</ul><p>No questions available.</p>")
    if warnings:
        body.append("<h2>Citation quality notices</h2><ul>" + "".join(f"<li>{escape(warning)}</li>" for warning in warnings) + "</ul>")
    body.append("<h2>Cited evidence excerpts</h2>")
    for file_id, number in sorted(cited):
        body.append(f'<p id="evidence-{file_id}-L{number}"><strong>{escape(file_map[file_id])}: L{number}</strong></p><pre>{escape(line_map[(file_id, number)])}</pre>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>ChronicleAI Case Report</title>'
        '<style>body{font:15px system-ui;max-width:1000px;margin:32px auto;padding:16px;color:#17283d}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:8px;text-align:left;overflow-wrap:anywhere}pre{white-space:pre-wrap}li{margin:12px 0}@media print{button{display:none}a{color:inherit}}</style>'
        '</head><body>' + "\n".join(body) + '</body></html>')
