import re
from typing import List, Dict, Tuple, Optional, Set
import spacy
from fastapi import HTTPException, status

from app.models import EvidenceFile, EvidenceLine
from app.schemas import EntityOccurrence, GroupedEntity

_nlp = None

def get_spacy_model():
    """
    Loads and caches the spaCy English model once per process.
    If unavailable, raises a clear HTTPException(503) explaining exact setup instructions.
    """
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_sm")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"spaCy model 'en_core_web_sm' is not available: {str(e)}. "
                    "Please install the model using 'python -m spacy download en_core_web_sm'."
                )
            )
    return _nlp

def set_spacy_model(nlp):
    """Allows testing harnesses to inject an NLP model or reset cache."""
    global _nlp
    _nlp = nlp

SUPPORTED_LABEL_MAP = {
    "PERSON": "Person",
    "ORG": "Organization",
    "GPE": "Location",
    "LOC": "Location",
    "DATE": "Date"
}

# Generic patterns for metadata location fields (never hardcoded to specific cities/places)
METADATA_LOCATION_PATTERN = re.compile(
    r'(?im)^[ \t]*(?:location|place|city|address|state|country)\s*:\s*([^\r\n]+)'
)

MONTH_NAMES = {
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
    'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'sept', 'oct', 'nov', 'dec'
}

HEADING_KEYWORDS_PATTERN = re.compile(
    r'(?i)\b(?:statement|report|investigation|memorandum|memo|affidavit|transcript|notice|summary|record|exhibit|document|brief)\b'
)

def build_line_index(lines: List[EvidenceLine]) -> Tuple[str, List[Tuple[int, int, int]]]:
    """
    Constructs full concatenated document text from ordered evidence lines
    and a character offset span map [(line_number, start_char, end_char)].
    Line ordering from evidence_lines is strictly preserved.
    """
    spans: List[Tuple[int, int, int]] = []
    current_char = 0
    text_chunks: List[str] = []
    for line in lines:
        content = line.content
        start_char = current_char
        end_char = start_char + len(content)
        spans.append((line.line_number, start_char, end_char))
        text_chunks.append(content)
        current_char = end_char + 1  # newline character
    full_text = "\n".join(text_chunks)
    return full_text, spans

def find_line_number(char_pos: int, spans: List[Tuple[int, int, int]]) -> int:
    """
    Determines which 1-based line number contains the given 0-based character position.
    Uses binary search over the monotonic line spans.
    """
    if not spans:
        return 1
    if char_pos <= spans[0][1]:
        return spans[0][0]
    if char_pos >= spans[-1][2]:
        return spans[-1][0]

    low = 0
    high = len(spans) - 1
    while low <= high:
        mid = (low + high) // 2
        line_num, start, end = spans[mid]
        if start <= char_pos <= end:
            return line_num
        elif char_pos < start:
            high = mid - 1
        else:
            # Check if char_pos falls on the newline separator
            if mid + 1 < len(spans) and char_pos < spans[mid + 1][1]:
                return line_num
            low = mid + 1

    idx = max(0, min(low, len(spans) - 1))
    return spans[idx][0]

def is_valid_location_value(val: str) -> bool:
    """
    Validates candidate value extracted from a labeled metadata field.
    Rejects empty, multiline, malformed, placeholder, or obviously non-location strings.
    """
    clean = val.strip()
    if not (2 <= len(clean) <= 100):
        return False
    if not re.search(r'[A-Za-z]', clean):
        return False
    if '@' in clean or '://' in clean or clean.lower().startswith('www.'):
        return False
    if re.match(r'^[0-9\W]+$', clean):
        return False
    placeholders = {'n/a', 'na', 'none', 'unknown', 'tbd', 'pending', 'unspecified', 'null', 'see below'}
    if clean.lower() in placeholders:
        return False
    return True

def is_identifier_date_false_positive(ent_text: str, preceding_line_text: str) -> bool:
    """
    Detects when spaCy incorrectly tags an alphanumeric reference/code as DATE.
    Preserves genuine dates (e.g. '12 October 2026', '2026-10-12', '15/10/2026', '12-Oct-2026').
    """
    clean = ent_text.strip()
    # 1. Genuine natural language dates containing month names are preserved
    tokens = re.findall(r'[A-Za-z]+', clean.lower())
    if any(t in MONTH_NAMES for t in tokens):
        return False

    # 2. Genuine purely numeric dates: YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, etc.
    if re.match(r'^\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}$', clean):
        return False

    # 3. Standard 4-digit year: "2026"
    if re.match(r'^\d{4}$', clean):
        return False

    # 4. Check for structured code format: alphanumeric with both letters and digits separated by - or _
    has_letters = bool(re.search(r'[A-Za-z]', clean))
    has_digits = bool(re.search(r'\d', clean))
    is_code_format = bool(re.match(r'^[A-Za-z0-9]+(?:[-_/#][A-Za-z0-9]+)+$', clean))

    # Check for preceding context reference cue on the same line
    context_cue = bool(re.search(
        r'(?i)\b(?:payment\s+reference|case\s+reference|reference|ref|invoice|inv|transaction|txn|id|code|voucher|tracking|serial|account|file\s+ref)\b',
        preceding_line_text
    ))

    if has_letters and has_digits and is_code_format:
        # If starts with letter code prefix followed by hyphen/digit (e.g. SYN-2026, INV-01, TEST-001)
        if re.match(r'^[A-Za-z]+[-_]\d', clean):
            return True
        if context_cue:
            return True

    return False

def is_header_org_false_positive(ent_text: str, ent_end_char: int, full_doc_text: str) -> bool:
    """
    Detects when an ORG span crosses over a document heading into a following metadata field label.
    Does NOT suppress genuine multi-line organizations (e.g. 'Acme\\nCorp').
    """
    if '\n' not in ent_text:
        return False

    parts = ent_text.split('\n')
    first_part = parts[0].strip()
    last_part = parts[-1].strip()

    # Check if first line contains document heading cues
    has_heading_keyword = bool(HEADING_KEYWORDS_PATTERN.search(first_part))

    # Check if last line transitions into a metadata field label (e.g. 'Case Reference' followed by ':')
    remaining = full_doc_text[ent_end_char : ent_end_char + 10].lstrip()
    is_followed_by_colon = remaining.startswith(':') or last_part.endswith(':')
    is_label_like = bool(re.match(r'^[A-Z][A-Za-z\s]{1,35}:?$', last_part))

    if has_heading_keyword and is_label_like and is_followed_by_colon:
        return True

    return False

def extract_entities_from_file(
    file_record: EvidenceFile,
    nlp=None
) -> List[EntityOccurrence]:
    """
    Extracts provenance-linked Named Entities from a single evidence file.
    Uses spaCy NER supplemented with deterministic metadata-aware location extraction
    and precision post-processing filters for structured identifiers and header artifacts.
    Does not mutate original evidence or lines.
    """
    if nlp is None:
        nlp = get_spacy_model()

    lines = file_record.lines
    if not lines:
        return []

    full_text, line_spans = build_line_index(lines)
    if not full_text.strip():
        return []

    doc = nlp(full_text)

    occurrences: List[EntityOccurrence] = []
    seen_spans: Set[Tuple[int, int]] = set()

    # --- Pass 1: Filtered spaCy Named Entities ---
    for ent in doc.ents:
        if ent.label_ not in SUPPORTED_LABEL_MAP:
            continue

        raw_text = ent.text
        # Filter empty or whitespace-only entities
        if not raw_text or not raw_text.strip():
            continue

        # Post-Processing 1: Suppress structured identifiers falsely tagged as DATE
        if ent.label_ == "DATE":
            line_start = full_text.rfind('\n', 0, ent.start_char)
            line_start = 0 if line_start == -1 else line_start + 1
            preceding_line_text = full_text[line_start:ent.start_char]
            if is_identifier_date_false_positive(raw_text, preceding_line_text):
                continue

        # Post-Processing 2: Suppress document heading artifacts falsely tagged as ORG
        if ent.label_ == "ORG":
            if is_header_org_false_positive(raw_text, ent.end_char, full_text):
                continue

        # Prevent duplicate spans from repeated extraction
        span_key = (ent.start_char, ent.end_char)
        if span_key in seen_spans:
            continue
        seen_spans.add(span_key)

        category = SUPPORTED_LABEL_MAP[ent.label_]
        start_line = find_line_number(ent.start_char, line_spans)
        last_char = max(ent.start_char, ent.end_char - 1)
        end_line = find_line_number(last_char, line_spans)

        occurrences.append(
            EntityOccurrence(
                evidence_file_id=file_record.id,
                original_filename=file_record.original_filename,
                text=raw_text,
                label=ent.label_,
                category=category,
                start_line=start_line,
                end_line=end_line,
                start_char=ent.start_char,
                end_char=ent.end_char,
                extraction_method="spacy_ner"
            )
        )

    # --- Pass 2: Metadata-Aware Location Extraction Supplement ---
    for match in METADATA_LOCATION_PATTERN.finditer(full_text):
        raw_val = match.group(1)
        val = raw_val.strip()
        if not is_valid_location_value(val):
            continue

        leading_ws = len(raw_val) - len(raw_val.lstrip())
        trailing_ws = len(raw_val) - len(raw_val.rstrip())
        loc_start_char = match.start(1) + leading_ws
        loc_end_char = match.end(1) - trailing_ws

        # Do not duplicate if spaCy already extracted an entity at this exact span
        span_key = (loc_start_char, loc_end_char)
        if span_key in seen_spans:
            continue
        # Also check for overlapping location span
        if any(
            occ.category == "Location" and (occ.start_char <= loc_start_char < occ.end_char or loc_start_char <= occ.start_char < loc_end_char)
            for occ in occurrences
        ):
            continue

        seen_spans.add(span_key)
        start_line = find_line_number(loc_start_char, line_spans)
        last_char = max(loc_start_char, loc_end_char - 1)
        end_line = find_line_number(last_char, line_spans)

        occurrences.append(
            EntityOccurrence(
                evidence_file_id=file_record.id,
                original_filename=file_record.original_filename,
                text=val,
                label="LOC",
                category="Location",
                start_line=start_line,
                end_line=end_line,
                start_char=loc_start_char,
                end_char=loc_end_char,
                extraction_method="metadata_rule"
            )
        )

    return occurrences

def group_and_sort_entities(
    occurrences: List[EntityOccurrence]
) -> List[GroupedEntity]:
    """
    Groups occurrences by category and case-insensitive, whitespace-normalized name.
    Selects representative display text and orders groups deterministically.
    """
    groups: Dict[Tuple[str, str], List[EntityOccurrence]] = {}

    for occ in occurrences:
        norm_name = " ".join(occ.text.strip().split()).lower()
        key = (occ.category, norm_name)
        if key not in groups:
            groups[key] = []
        groups[key].append(occ)

    grouped_list: List[GroupedEntity] = []
    for (category, _), occ_list in groups.items():
        # Pick the most common casing as display text (deterministic tie-breaker: first seen)
        casing_counts: Dict[str, int] = {}
        for occ in occ_list:
            c = occ.text.strip()
            casing_counts[c] = casing_counts.get(c, 0) + 1
        display_text = max(casing_counts.keys(), key=lambda k: (casing_counts[k], -len(k)))

        # Deterministic sorting of occurrences
        sorted_occs = sorted(
            occ_list,
            key=lambda o: (o.original_filename, o.evidence_file_id, o.start_line, o.start_char)
        )

        grouped_list.append(
            GroupedEntity(
                category=category,
                display_text=display_text,
                count=len(sorted_occs),
                occurrences=sorted_occs
            )
        )

    # Sort groups deterministically: display_text alphabetically, then category
    grouped_list.sort(key=lambda g: (g.display_text.lower(), g.category))
    return grouped_list
