# Fictional test fixtures only; no original case evidence is included.
import os
import shutil
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import EvidenceFile, EvidenceLine
from app.ner import (
    build_line_index,
    find_line_number,
    extract_entities_from_file,
    group_and_sort_entities,
    set_spacy_model,
    get_spacy_model,
    SUPPORTED_LABEL_MAP
)

TEST_DB_FILE = "test_phase4_entities.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"
TEST_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "test_storage_entities")

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_and_teardown_entities_env(monkeypatch):
    monkeypatch.setenv("CHRONICLE_STORAGE_DIR", TEST_STORAGE_DIR)
    app.dependency_overrides[get_db] = override_get_db
    os.makedirs(TEST_STORAGE_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass
    if os.path.exists(TEST_STORAGE_DIR):
        try:
            shutil.rmtree(TEST_STORAGE_DIR)
        except OSError:
            pass

client = TestClient(app)

class MockSpan:
    def __init__(self, text, label, start_char, end_char):
        self.text = text
        self.label_ = label
        self.start_char = start_char
        self.end_char = end_char

class MockDoc:
    def __init__(self, text, ents):
        self.text = text
        self.ents = ents

def make_mock_nlp(entities_to_return):
    def nlp(text):
        return MockDoc(text, entities_to_return)
    return nlp


# ---------------------------------------------------------------------------
# Unit Tests for Provenance Logic
# ---------------------------------------------------------------------------

def test_find_line_number_exact_and_multiline():
    # Line 1: "Alpha" (len 5, chars 0..5)
    # Line 2: "Beta"  (len 4, chars 6..10)
    # Line 3: "Gamma" (len 5, chars 11..16)
    spans = [(1, 0, 5), (2, 6, 10), (3, 11, 16)]

    assert find_line_number(0, spans) == 1
    assert find_line_number(4, spans) == 1
    assert find_line_number(5, spans) == 1  # newline between line 1 & 2
    assert find_line_number(6, spans) == 2
    assert find_line_number(9, spans) == 2
    assert find_line_number(10, spans) == 2 # newline between line 2 & 3
    assert find_line_number(11, spans) == 3
    assert find_line_number(15, spans) == 3


def test_build_line_index_preserves_ordering():
    l1 = EvidenceLine(line_number=1, content="First line")
    l2 = EvidenceLine(line_number=2, content="Second line")
    l3 = EvidenceLine(line_number=3, content="Third line")

    text, spans = build_line_index([l1, l2, l3])
    assert text == "First line\nSecond line\nThird line"
    assert len(spans) == 3
    assert spans[0] == (1, 0, 10)
    assert spans[1] == (2, 11, 22)
    assert spans[2] == (3, 23, 33)


def test_multiline_span_mapping():
    # Text: "Acme\nCorp"
    l1 = EvidenceLine(line_number=1, content="Acme")
    l2 = EvidenceLine(line_number=2, content="Corp")
    file_record = EvidenceFile(id=10, original_filename="doc.txt", lines=[l1, l2])

    mock_nlp = make_mock_nlp([MockSpan("Acme\nCorp", "ORG", 0, 9)])
    occs = extract_entities_from_file(file_record, nlp=mock_nlp)

    assert len(occs) == 1
    occ = occs[0]
    assert occ.text == "Acme\nCorp"
    assert occ.label == "ORG"
    assert occ.category == "Organization"
    assert occ.start_line == 1
    assert occ.end_line == 2


def test_repeated_mentions_grouped_under_one_display_name():
    l1 = EvidenceLine(line_number=1, content="David Mason was here.")
    l2 = EvidenceLine(line_number=2, content="Later, david mason returned.")
    file_record = EvidenceFile(id=20, original_filename="stmt.txt", lines=[l1, l2])

    mock_nlp = make_mock_nlp([
        MockSpan("David Mason", "PERSON", 0, 11),
        MockSpan("david mason", "PERSON", 30, 41)
    ])
    occs = extract_entities_from_file(file_record, nlp=mock_nlp)
    assert len(occs) == 2

    grouped = group_and_sort_entities(occs)
    assert len(grouped) == 1
    g = grouped[0]
    assert g.category == "Person"
    assert g.count == 2
    assert len(g.occurrences) == 2
    assert g.occurrences[0].start_line == 1
    assert g.occurrences[1].start_line == 2


# ---------------------------------------------------------------------------
# API Integration Tests
# ---------------------------------------------------------------------------

def test_entities_endpoint_nonexistent_case():
    res = client.get("/api/cases/9999/entities")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_entities_endpoint_empty_case():
    c = client.post("/api/cases", json={"case_number": "EMP-01", "title": "Empty Case"}).json()
    case_id = c["id"]

    res = client.get(f"/api/cases/{case_id}/entities")
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] == case_id
    assert data["total_groups"] == 0
    assert data["total_occurrences"] == 0
    assert data["entities"] == []
    assert data["category_counts"] == {"Person": 0, "Organization": 0, "Location": 0, "Date": 0}


def test_entities_endpoint_no_entities_in_evidence():
    c = client.post("/api/cases", json={"case_number": "NOENT-01", "title": "No Entity Case"}).json()
    case_id = c["id"]

    # Upload empty-like text that contains no named entities
    client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("notes.txt", b"just numbers and random lowercase words: 123 456 foo bar", "text/plain")}
    )

    res = client.get(f"/api/cases/{case_id}/entities")
    assert res.status_code == 200
    data = res.json()
    assert data["total_groups"] == 0
    assert data["total_occurrences"] == 0


def test_entities_cross_case_isolation():
    # Case 1 with Alice Brooks
    c1 = client.post("/api/cases", json={"case_number": "ISO-01", "title": "Case 1"}).json()
    client.post(
        f"/api/cases/{c1['id']}/evidence",
        files={"file": ("case1.txt", b"Alice Brooks authorized the transfer in Pune on 15 October 2026.", "text/plain")}
    )

    # Case 2 with David Mason
    c2 = client.post("/api/cases", json={"case_number": "ISO-02", "title": "Case 2"}).json()
    client.post(
        f"/api/cases/{c2['id']}/evidence",
        files={"file": ("case2.txt", b"David Mason reviewed records for Acme Consulting in Mumbai.", "text/plain")}
    )

    # Fetch entities for Case 1
    res1 = client.get(f"/api/cases/{c1['id']}/entities")
    assert res1.status_code == 200
    data1 = res1.json()
    names1 = [e["display_text"] for e in data1["entities"]]

    # Fetch entities for Case 2
    res2 = client.get(f"/api/cases/{c2['id']}/entities")
    assert res2.status_code == 200
    data2 = res2.json()
    names2 = [e["display_text"] for e in data2["entities"]]

    # Assert Case 1 entities do NOT leak into Case 2
    assert any("Alice Brooks" in n for n in names1)
    assert not any("Alice Brooks" in n for n in names2)
    assert any("David Mason" in n for n in names2)
    assert not any("David Mason" in n for n in names1)


def test_entities_category_filter_and_pagination():
    c = client.post("/api/cases", json={"case_number": "PAG-01", "title": "Pagination Case"}).json()
    case_id = c["id"]

    content = (
        "David Mason met Alice Brooks on 12 October 2026 at Acme Consulting in Pune.\n"
        "Emma Sullivan visited Mumbai on 15 October 2026.\n"
        "Amit Verma arrived in Delhi on 16 October 2026."
    ).encode("utf-8")

    client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("investigation.txt", content, "text/plain")}
    )

    # 1. Filter by Person
    res_person = client.get(f"/api/cases/{case_id}/entities?category=Person")
    assert res_person.status_code == 200
    data_person = res_person.json()
    for ent in data_person["entities"]:
        assert ent["category"] == "Person"

    # 2. Pagination: page_size=2
    res_p1 = client.get(f"/api/cases/{case_id}/entities?page=1&page_size=2")
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert len(data_p1["entities"]) <= 2
    assert data_p1["page"] == 1
    assert data_p1["page_size"] == 2


def test_missing_spacy_model_behavior(monkeypatch):
    c = client.post("/api/cases", json={"case_number": "MISS-01", "title": "Missing Model Case"}).json()
    case_id = c["id"]

    # Mock spacy.load to raise an OSError simulating missing model
    def mock_spacy_load(name):
        raise OSError(f"Can't find model '{name}'. It doesn't seem to be a Python package or valid path.")

    monkeypatch.setattr("spacy.load", mock_spacy_load)
    set_spacy_model(None)  # Reset cached model

    try:
        res = client.get(f"/api/cases/{case_id}/entities")
        assert res.status_code == 503
        detail = res.json()["detail"]
        assert "not available" in detail.lower()
        assert "python -m spacy download" in detail
    finally:
        set_spacy_model(None)  # Reset for subsequent tests


def test_no_mutation_of_evidence_or_hashes():
    c = client.post("/api/cases", json={"case_number": "MUT-01", "title": "Immutability Case"}).json()
    case_id = c["id"]

    raw_bytes = b"David Mason submitted statement on 15 October 2026 in Pune.\nSecond line unaltered."
    upload_res = client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("safe_doc.txt", raw_bytes, "text/plain")}
    ).json()

    evidence_id = upload_res["id"]
    recorded_hash = upload_res["sha256_hash"]

    # Call NER endpoints multiple times
    client.get(f"/api/cases/{case_id}/entities")
    client.get(f"/api/cases/{case_id}/entities/summary")

    # Verify integrity endpoint confirms no mutation
    verify_res = client.get(f"/api/cases/{case_id}/evidence/{evidence_id}/verify").json()
    assert verify_res["file_exists"] is True
    assert verify_res["hash_matched"] is True
    assert verify_res["stored_hash"] == recorded_hash
    assert verify_res["verification_status"] == "verified"


def test_entities_summary_endpoint():
    c = client.post("/api/cases", json={"case_number": "SUM-01", "title": "Summary Case"}).json()
    case_id = c["id"]

    client.post(
        f"/api/cases/{case_id}/evidence",
        files={"file": ("doc.txt", b"David Mason visited Pune on 15 October 2026.", "text/plain")}
    )

    res = client.get(f"/api/cases/{case_id}/entities/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] == case_id
    assert data["evidence_files_processed"] == 1
    assert data["total_unique_entities"] > 0
    assert data["total_occurrences"] > 0
    assert isinstance(data["category_counts"], dict)


# ---------------------------------------------------------------------------
# Phase 4.1 Precision Post-Processing & Location Rule Tests
# ---------------------------------------------------------------------------

def test_metadata_location_extraction_offsets_and_lines():
    l1 = EvidenceLine(line_number=1, content="Witness Details")
    l2 = EvidenceLine(line_number=2, content="Location: Pune, Maharashtra")
    l3 = EvidenceLine(line_number=3, content="Place: Mumbai")
    l4 = EvidenceLine(line_number=4, content="City: Nagpur")
    l5 = EvidenceLine(line_number=5, content="Address: 12 Example Road, Pune")
    file_record = EvidenceFile(id=30, original_filename="meta.txt", lines=[l1, l2, l3, l4, l5])

    mock_nlp = make_mock_nlp([])  # spaCy extracts nothing
    occs = extract_entities_from_file(file_record, nlp=mock_nlp)

    assert len(occs) == 4
    # 1. Pune, Maharashtra
    assert occs[0].text == "Pune, Maharashtra"
    assert occs[0].category == "Location"
    assert occs[0].start_line == 2
    assert occs[0].end_line == 2
    assert occs[0].extraction_method == "metadata_rule"

    # 2. Mumbai
    assert occs[1].text == "Mumbai"
    assert occs[1].category == "Location"
    assert occs[1].start_line == 3

    # 3. Nagpur
    assert occs[2].text == "Nagpur"
    assert occs[2].category == "Location"
    assert occs[2].start_line == 4

    # 4. 12 Example Road, Pune
    assert occs[3].text == "12 Example Road, Pune"
    assert occs[3].category == "Location"
    assert occs[3].start_line == 5


def test_metadata_location_generic_values_and_rejections():
    lines = [
        EvidenceLine(line_number=1, content="City: Zurich"),
        EvidenceLine(line_number=2, content="Address: 45 Baker Street, London"),
        EvidenceLine(line_number=3, content="Place: N/A"),
        EvidenceLine(line_number=4, content="Location: http://example.com"),
        EvidenceLine(line_number=5, content="City: 12345"),
        EvidenceLine(line_number=6, content="State:   ")
    ]
    file_record = EvidenceFile(id=31, original_filename="generic.txt", lines=lines)
    mock_nlp = make_mock_nlp([])
    occs = extract_entities_from_file(file_record, nlp=mock_nlp)

    extracted_texts = [o.text for o in occs]
    assert "Zurich" in extracted_texts
    assert "45 Baker Street, London" in extracted_texts
    assert "N/A" not in extracted_texts
    assert "http://example.com" not in extracted_texts
    assert "12345" not in extracted_texts


def test_metadata_location_duplicate_suppression():
    l1 = EvidenceLine(line_number=1, content="City: Mumbai")
    file_record = EvidenceFile(id=32, original_filename="dup.txt", lines=[l1])

    # Text: "City: Mumbai" (chars: City: 0..5, space 5, Mumbai 6..12)
    mock_nlp = make_mock_nlp([MockSpan("Mumbai", "GPE", 6, 12)])
    occs = extract_entities_from_file(file_record, nlp=mock_nlp)

    assert len(occs) == 1
    assert occs[0].text == "Mumbai"
    assert occs[0].category == "Location"
    assert occs[0].extraction_method == "spacy_ner"


def test_structured_identifier_rejected_as_date():
    lines = [
        EvidenceLine(line_number=1, content="The payment reference was SYN-2026-0001."),
        EvidenceLine(line_number=2, content="Transaction ID: ABC-2025-0001 was approved."),
        EvidenceLine(line_number=3, content="Invoice Number: INV-2026-0042 attached.")
    ]
    file_record = EvidenceFile(id=33, original_filename="codes.txt", lines=lines)

    mock_nlp = make_mock_nlp([
        MockSpan("SYN-2026-0001", "DATE", 26, 39),
        MockSpan("ABC-2025-0001", "DATE", 57, 70),
        MockSpan("INV-2026-0042", "DATE", 102, 115),
    ])
    occs = extract_entities_from_file(file_record, nlp=mock_nlp)
    assert len(occs) == 0  # All identifier DATE false positives suppressed!


def test_genuine_dates_preserved():
    lines = [
        EvidenceLine(line_number=1, content="Meeting on 12 October 2026 at 10am."),
        EvidenceLine(line_number=2, content="Transfer date: 2026-10-12 verified."),
        EvidenceLine(line_number=3, content="Audit reported on 15/10/2026."),
        EvidenceLine(line_number=4, content="Notice filed on 12-Oct-2026.")
    ]
    file_record = EvidenceFile(id=34, original_filename="dates.txt", lines=lines)

    full_text, _ = build_line_index(lines)
    s1 = full_text.index("12 October 2026")
    s2 = full_text.index("2026-10-12")
    s3 = full_text.index("15/10/2026")
    s4 = full_text.index("12-Oct-2026")

    mock_nlp = make_mock_nlp([
        MockSpan("12 October 2026", "DATE", s1, s1 + len("12 October 2026")),
        MockSpan("2026-10-12", "DATE", s2, s2 + len("2026-10-12")),
        MockSpan("15/10/2026", "DATE", s3, s3 + len("15/10/2026")),
        MockSpan("12-Oct-2026", "DATE", s4, s4 + len("12-Oct-2026")),
    ])
    occs = extract_entities_from_file(file_record, nlp=mock_nlp)
    assert len(occs) == 4
    texts = [o.text for o in occs]
    assert "12 October 2026" in texts
    assert "2026-10-12" in texts
    assert "15/10/2026" in texts
    assert "12-Oct-2026" in texts


def test_structural_cross_line_heading_org_suppressed():
    lines = [
        EvidenceLine(line_number=1, content="WITNESS STATEMENT - TESTCASE FINANCIAL FRAUD INVESTIGATION"),
        EvidenceLine(line_number=2, content="Case Reference: TEST-001"),
        EvidenceLine(line_number=3, content="Actual Company: Acme Consulting Ltd")
    ]
    file_record = EvidenceFile(id=35, original_filename="heading.txt", lines=lines)
    full_text, _ = build_line_index(lines)

    bad_span_text = "WITNESS STATEMENT - TESTCASE FINANCIAL FRAUD INVESTIGATION\nCase Reference"
    bad_start = full_text.index(bad_span_text)
    bad_end = bad_start + len(bad_span_text)

    good_span_text = "Acme Consulting Ltd"
    good_start = full_text.index(good_span_text)
    good_end = good_start + len(good_span_text)

    mock_nlp = make_mock_nlp([
        MockSpan(bad_span_text, "ORG", bad_start, bad_end),
        MockSpan(good_span_text, "ORG", good_start, good_end),
    ])
    occs = extract_entities_from_file(file_record, nlp=mock_nlp)
    assert len(occs) == 1
    assert occs[0].text == "Acme Consulting Ltd"
    assert occs[0].start_line == 3


# ---------------------------------------------------------------------------
# Conservative ORG validation: deterministic model predictions, fictional text.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("content, candidate, rejected", [
    # All six reported false positives, with their relevant evidence context.
    ("Minimum 16 GB RAM and 512 GB SSD.", "RAM", True),
    ("Extracted: 2026-10-18 | Currency: INR", "INR", True),
    ("The unit price was INR 45000 each.", "INR 45000", True),
    ("The total budget was INR 450000.", "INR 450000", True),
    ("Document ID: PO-2026-104 | Source: Register", "PO-2026-104", True),
    ("Document ID: NOTES-2026-104 | Source: Notes", "NOTES-2026-104", True),
    # Conventional money formatting; malformed/partial tokens stay ambiguous.
    ("Paid INR 45,000.50.", "INR 45,000.50", True),
    ("Paid INR 4,50,000.00.", "INR 4,50,000.00", True),
    ("Paid INR 1,234,567.89.", "INR 1,234,567.89", True),
    ("Paid INR\t45000/-.", "INR\t45000/-", True),
    ("Paid INR\u00a045000.", "INR\u00a045000", True),
    ("Reversal INR -45000.00.", "INR -45000.00", True),
    ("Paid INR 45000.", "INR", True),
    ("Paid INR 4,50,000.00.", "INR", True),
    ("Currency code: INR", "INR", True),
    ("INR 45,00 was mentioned.", "INR 45,00", False),
    ("INR 45,00 was mentioned.", "INR", False),
    ("INR 45000.999 was mentioned.", "INR", False),
    ("INR 45000X was mentioned.", "INR 45000", False),
    ("INR 45000X was mentioned.", "INR", False),
    ("XINR 45000 was mentioned.", "INR 45000", False),
    ("INR-Labs made the announcement.", "INR", False),
    ("INRX made the announcement.", "INR", False),
    ("INR_Research made the announcement.", "INR", False),
    # RAM requires an immediately adjacent quantitative memory specification.
    ("Minimum 16GB RAM.", "RAM", True),
    ("Installed 32 GiB RAM.", "RAM", True),
    ("Specification: RAM: 16 GB.", "RAM", True),
    ("RAM 16 GB is required.", "RAM", True),
    ("RAM supplied 16 GB modules.", "RAM", False),
    ("The 16 GB order was approved by RAM.", "RAM", False),
    ("RAM-Technologies supplied memory.", "RAM", False),
    ("16 GB RAMX is listed.", "RAM", False),
    ("16 GB\nRAM approved the order.", "RAM", False),
    ("Currency:\nINR approved the order.", "INR", False),
    # Known document references and explicit labels, not arbitrary code names.
    ("Acknowledged PO-2026-104 by email.", "PO-2026-104", True),
    ("End of document NOTES-2026-104.", "NOTES-2026-104", True),
    ("Document ID: ABC-2026-009", "ABC-2026-009", True),
    ("Invoice Number: INV-2026-009", "INV-2026-009", True),
    ("Payment reference: PAY-2026-088", "PAY-2026-088", True),
    ("PO-2026-104 Labs supplied equipment.", "PO-2026-104 Labs", False),
    ("PO-2026-104A supplied equipment.", "PO-2026-104A", False),
    ("XPO-2026-104 supplied equipment.", "PO-2026-104", False),
    ("PO-2026-104-Labs supplied equipment.", "PO-2026-104", False),
    ("ABC-2026-009 supplied equipment.", "ABC-2026-009", False),
    ("Document ID: ABC_2026_009", "ABC_2026_009", True),
    ("Reference: Studio-54", "Studio-54", False),
    ("Document ID: 3M", "3M", False),
    # Positive controls and explicit organization metadata override appearances.
    ("Harbor Tech Distribution supplied laptops.", "Harbor Tech Distribution", False),
    ("Apex Office Supplies submitted a quotation.", "Apex Office Supplies", False),
    ("IBM reviewed the report.", "IBM", False),
    ("RBI issued a statement.", "RBI", False),
    ("3M supplied materials.", "3M", False),
    ("Studio-54 issued a statement.", "Studio-54", False),
    ("INR Technologies supplied equipment.", "INR Technologies", False),
    ("RAM Systems supplied equipment.", "RAM Systems", False),
    ("RAM approved the order.", "RAM", False),
    ("INR approved the order.", "INR", False),
    ("Company: PO-2026-104", "PO-2026-104", False),
    ("Supplier: INR 45000", "INR 45000", False),
    ("Organization: RAM", "RAM", False),
    ("Harbor Tech\nDistribution supplied equipment.", "Harbor Tech\nDistribution", False),
])
def test_conservative_org_validation(content, candidate, rejected):
    lines = [EvidenceLine(line_number=index + 1, content=line)
             for index, line in enumerate(content.split('\n'))]
    file_record = EvidenceFile(id=61, original_filename="org-validation.txt", lines=lines)
    start = content.index(candidate)
    end = start + len(candidate)
    occurrences = extract_entities_from_file(file_record, nlp=make_mock_nlp([
        MockSpan(candidate, "ORG", start, end)
    ]))
    assert len(occurrences) == (0 if rejected else 1)
    if not rejected:
        occurrence = occurrences[0]
        assert occurrence.text == candidate
        assert occurrence.label == "ORG"
        assert occurrence.category == "Organization"
        assert occurrence.evidence_file_id == 61
        assert occurrence.original_filename == "org-validation.txt"
        assert (occurrence.start_char, occurrence.end_char) == (start, end)
        assert occurrence.start_line == content[:start].count('\n') + 1
        assert occurrence.end_line == content[:end - 1].count('\n') + 1


def test_org_validation_preserves_offsets_grouping_and_original_evidence():
    import hashlib
    content = (
        "Budget INR 450000.\n"
        "Harbor Tech Distribution quoted a price.\n"
        "harbor tech distribution confirmed delivery.\n"
        "Minimum 16 GB RAM.\n"
        "Apex Office Supplies acknowledged the request."
    )
    lines = [EvidenceLine(line_number=index + 1, content=line)
             for index, line in enumerate(content.split('\n'))]
    original_hash = hashlib.sha256(content.encode()).hexdigest()
    file_record = EvidenceFile(id=62, original_filename="org-provenance.txt", lines=lines,
                               sha256_hash=original_hash)
    spans = []
    for text in ["INR 450000", "Harbor Tech Distribution", "harbor tech distribution",
                 "RAM", "Apex Office Supplies"]:
        start = content.index(text)
        spans.append(MockSpan(text, "ORG", start, start + len(text)))
    # An identical accepted prediction must still be deduplicated by its offsets.
    spans.append(spans[1])
    occurrences = extract_entities_from_file(file_record, nlp=make_mock_nlp(spans))
    groups = group_and_sort_entities(occurrences)
    assert [(g.display_text, g.count) for g in groups] == [
        ("Apex Office Supplies", 1), ("Harbor Tech Distribution", 2)
    ]
    assert [o.start_line for o in groups[1].occurrences] == [2, 3]
    for occurrence in occurrences:
        assert content[occurrence.start_char:occurrence.end_char] == occurrence.text
        assert occurrence.evidence_file_id == 62
        assert occurrence.original_filename == "org-provenance.txt"
        assert occurrence.start_line == occurrence.end_line
        assert occurrence.extraction_method == "spacy_ner"
    assert "\n".join(line.content for line in file_record.lines) == content
    assert file_record.sha256_hash == original_hash
    assert hashlib.sha256(content.encode()).hexdigest() == original_hash


def test_org_validation_api_counts_filters_pagination_and_integrity(monkeypatch):
    # The model is deliberately deterministic; this test does not load/download it.
    rows = [
        ("Currency: INR", "INR", "ORG"),
        ("Price INR 45000.", "INR 45000", "ORG"),
        ("Budget INR 450000.", "INR 450000", "ORG"),
        ("Minimum 16 GB RAM.", "RAM", "ORG"),
        ("Document ID: PO-2026-104", "PO-2026-104", "ORG"),
        ("Document ID: NOTES-2026-104", "NOTES-2026-104", "ORG"),
        ("Harbor Tech Distribution delivered.", "Harbor Tech Distribution", "ORG"),
        ("harbor tech distribution confirmed.", "harbor tech distribution", "ORG"),
        ("Apex Office Supplies replied.", "Apex Office Supplies", "ORG"),
        ("IBM reviewed the documents.", "IBM", "ORG"),
        ("Anika Rao reviewed the report.", "Anika Rao", "PERSON"),
    ]
    content = "\n".join(row[0] for row in rows)
    spans = []
    offset = 0
    for line, candidate, label in rows:
        start = offset + line.index(candidate)
        spans.append(MockSpan(candidate, label, start, start + len(candidate)))
        offset += len(line) + 1
    monkeypatch.setattr("app.api.entities.get_spacy_model", lambda: make_mock_nlp(spans))
    case = client.post("/api/cases", json={"case_number": "ORG-RULES-01", "title": "ORG validation"}).json()
    case_id = case["id"]
    uploaded = client.post(f"/api/cases/{case_id}/evidence",
                          files={"file": ("org-rules.txt", content.encode(), "text/plain")})
    assert uploaded.status_code == 201
    evidence = uploaded.json()
    response = client.get(f"/api/cases/{case_id}/entities")
    assert response.status_code == 200
    data = response.json()
    assert data["total_groups"] == 4
    assert data["total_occurrences"] == 5
    assert data["category_counts"] == {"Person": 1, "Organization": 3, "Location": 0, "Date": 0}
    assert [g["display_text"] for g in data["entities"]] == [
        "Anika Rao", "Apex Office Supplies", "Harbor Tech Distribution", "IBM"
    ]
    for group in data["entities"]:
        for occurrence in group["occurrences"]:
            assert occurrence["evidence_file_id"] == evidence["id"]
            assert occurrence["original_filename"] == "org-rules.txt"
            assert content[occurrence["start_char"]:occurrence["end_char"]] == occurrence["text"]
            assert occurrence["start_line"] == content[:occurrence["start_char"]].count('\n') + 1
            assert occurrence["end_line"] == occurrence["start_line"]
    pages = [client.get(f"/api/cases/{case_id}/entities?category=organization&page={page}&page_size=2").json()
             for page in [1, 2]]
    assert all(page["total_groups"] == 3 and page["total_occurrences"] == 4 for page in pages)
    assert all(page["category_counts"] == data["category_counts"] for page in pages)
    assert [g["display_text"] for page in pages for g in page["entities"]] == [
        "Apex Office Supplies", "Harbor Tech Distribution", "IBM"
    ]
    assert all(g["category"] == "Organization" for page in pages for g in page["entities"])
    summary = client.get(f"/api/cases/{case_id}/entities/summary").json()
    assert summary["total_unique_entities"] == 4
    assert summary["total_occurrences"] == 5
    assert summary["category_counts"] == data["category_counts"]
    verification = client.get(f"/api/cases/{case_id}/evidence/{evidence['id']}/verify").json()
    assert verification["verification_status"] == "verified"
    assert verification["stored_hash"] == evidence["sha256_hash"]
    assert verification["hash_matched"] is True
