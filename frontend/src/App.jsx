import { useState, useEffect, useRef } from 'react';
import './App.css';

// Helper component to highlight matching search text safely without dangerouslySetInnerHTML
function HighlightMatch({ text, query }) {
  if (!query || !query.trim() || !text) {
    return <span>{text}</span>;
  }

  const q = query.trim().toLowerCase();
  const lowerText = text.toLowerCase();
  const parts = [];
  let startIndex = 0;
  let matchIndex = lowerText.indexOf(q, startIndex);

  while (matchIndex !== -1) {
    if (matchIndex > startIndex) {
      parts.push(text.substring(startIndex, matchIndex));
    }
    parts.push(
      <mark key={startIndex} className="search-highlight">
        {text.substring(matchIndex, matchIndex + q.length)}
      </mark>
    );
    startIndex = matchIndex + q.length;
    matchIndex = lowerText.indexOf(q, startIndex);
  }

  if (startIndex < text.length) {
    parts.push(text.substring(startIndex));
  }

  return <span>{parts}</span>;
}

function EvidenceCitations({ citations, onOpen }) {
  return <div className="claim-citations">{citations.map((citation, index) => (
    <button key={index} type="button" className="citation-pill"
      onClick={() => onOpen(citation, citation.start_line)}>
      {citation.original_filename}: L{citation.start_line}{citation.end_line !== citation.start_line ? `–${citation.end_line}` : ''} &rarr;
    </button>
  ))}</div>;
}

function App() {
  const [healthStatus, setHealthStatus] = useState('checking');
  const [currentView, setCurrentView] = useState('dashboard'); // 'dashboard' | 'cases' | 'new-case' | 'case-detail'
  const [selectedCaseId, setSelectedCaseId] = useState(null);

  // Stats state
  const [stats, setStats] = useState({ total_cases: 0, open_cases: 0, in_progress_cases: 0, closed_cases: 0 });
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsError, setStatsError] = useState(null);

  // Cases list state
  const [cases, setCases] = useState([]);
  const [casesLoading, setCasesLoading] = useState(false);
  const [casesError, setCasesError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Single Case Detail state
  const [currentCase, setCurrentCase] = useState(null);
  const [caseLoading, setCaseLoading] = useState(false);
  const [caseError, setCaseError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState({ title: '', description: '', status: 'Open' });
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState(null);

  // New Case Form state
  const [newCaseForm, setNewCaseForm] = useState({ case_number: '', title: '', description: '', status: 'Open' });
  const [newCaseSubmitting, setNewCaseSubmitting] = useState(false);
  const [newCaseError, setNewCaseError] = useState(null);

  // Evidence State
  const [evidenceFiles, setEvidenceFiles] = useState([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [uploadResults, setUploadResults] = useState([]);
  const fileInputRef = useRef(null);

  // Evidence Search State
  const [evidenceSearchInput, setEvidenceSearchInput] = useState('');
  const [activeSearchQuery, setActiveSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null); // SearchResponse object
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [, setSearchPage] = useState(1);

  // Phase 4: Entity Explorer State
  const [entitiesData, setEntitiesData] = useState(null);
  const [entitiesLoading, setEntitiesLoading] = useState(false);
  const [entitiesError, setEntitiesError] = useState(null);
  const [entityCategoryFilter, setEntityCategoryFilter] = useState('ALL');
  const [entityPage, setEntityPage] = useState(1);
  const [expandedEntities, setExpandedEntities] = useState({});

  // Phase 5: AI Case Analysis State
  const [analysisData, setAnalysisData] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState(null);
  const chatSequence = useRef(0);
  const [timelineData, setTimelineData] = useState(null);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineError, setTimelineError] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState(null);

  const apiError = (detail, fallback) => {
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail.map(item => typeof item?.msg === 'string' ? item.msg : '')
        .filter(Boolean);
      if (messages.length) return messages.join('; ');
    }
    return fallback;
  };
  const formatTimestamp = (value) => {
    if (!value) return 'Unavailable';
    const utc = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : value + 'Z';
    return new Date(utc).toLocaleString();
  };

  // Evidence Inspector Modal / Drawer
  const INSPECTOR_PAGE_SIZE = 2000;
  const [inspectedFile, setInspectedFile] = useState(null);
  const [inspectedLines, setInspectedLines] = useState([]);
  const [inspectorPage, setInspectorPage] = useState(1);
  const [inspectorNotice, setInspectorNotice] = useState(null);
  const [linesLoading, setLinesLoading] = useState(false);
  const [linesError, setLinesError] = useState(null);
  const [verifyStatus, setVerifyStatus] = useState(null);
  const [copySuccess, setCopySuccess] = useState(false);
  const [targetLineNumber, setTargetLineNumber] = useState(null);
  const lineRefs = useRef({});

  // Ref identity changes synchronously on navigation, before React's next render.
  // Abort is best-effort; identity checks remain authoritative after every await.
  const navigationRef = useRef({ caseId: null, view: 'dashboard', generation: 0 });
  const requestsRef = useRef({});
  const cancelRequest = (key) => {
    const previous = requestsRef.current[key];
    delete requestsRef.current[key];
    previous?.controller.abort();
  };
  const invalidateRequests = () => {
    navigationRef.current.generation += 1;
    Object.keys(requestsRef.current).forEach(cancelRequest);
  };
  const beginRequest = (key) => {
    cancelRequest(key);
    const controller = new AbortController();
    const generation = navigationRef.current.generation;
    const request = {
      controller,
      signal: controller.signal,
      isCurrent: () => requestsRef.current[key] === request
        && navigationRef.current.generation === generation,
    };
    requestsRef.current[key] = request;
    return request;
  };
  const isActiveCase = (id) => navigationRef.current.view === 'case-detail'
    && navigationRef.current.caseId === id;

  const closeInspector = () => {
    cancelRequest('inspector');
    cancelRequest('verify');
    cancelRequest('copy');
    setInspectedFile(null);
    setInspectedLines([]);
    setInspectorPage(1);
    setInspectorNotice(null);
    setLinesLoading(false);
    setLinesError(null);
    setVerifyStatus(null);
    setCopySuccess(false);
    setTargetLineNumber(null);
    lineRefs.current = {};
  };

  const resetCaseState = () => {
    setCurrentCase(null);
    setCaseError(null);
    setCaseLoading(false);
    setIsEditing(false);
    setEditSaving(false);
    setEditError(null);
    setEvidenceFiles([]);
    setEvidenceLoading(false);
    setEvidenceError(null);
    setUploadProgress(null);
    setUploadResults([]);
    setSearchResults(null);
    setSearchLoading(false);
    setSearchError(null);
    setEvidenceSearchInput('');
    setActiveSearchQuery('');
    setEntitiesData(null);
    setEntitiesLoading(false);
    setEntitiesError(null);
    setEntityCategoryFilter('ALL');
    setEntityPage(1);
    setExpandedEntities({});
    setAnalysisData(null);
    setAnalysisLoading(false);
    setAnalysisError(null);
    setChatInput('');
    setChatMessages([]);
    setChatLoading(false);
    setChatError(null);
    setTimelineData(null);
    setTimelineLoading(false);
    setTimelineError(null);
    setReportLoading(false);
    setReportError(null);
    setNewCaseSubmitting(false);
    setStatsLoading(false);
    setCasesLoading(false);
    closeInspector();
  };

  const navigateToView = (view) => {
    if (navigationRef.current.view === view && navigationRef.current.caseId === null) return;
    invalidateRequests();
    navigationRef.current.view = view;
    navigationRef.current.caseId = null;
    resetCaseState();
    setSelectedCaseId(null);
    setCurrentView(view);
  };

  useEffect(() => () => {
    invalidateRequests();
  }, []);

  // Check backend health
  useEffect(() => {
    const checkBackendHealth = async () => {
      try {
        const response = await fetch('/api/health');
        if (response.ok) {
          const data = await response.json();
          if (data.status === 'ok') {
            setHealthStatus('connected');
          } else {
            setHealthStatus('unavailable');
          }
        } else {
          setHealthStatus('unavailable');
        }
      } catch {
        setHealthStatus('unavailable');
      }
    };

    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  // Fetch Dashboard Stats
  const fetchStats = async () => {
    const request = beginRequest('stats');
    setStatsLoading(true);
    setStatsError(null);
    try {
      const res = await fetch('/api/cases/stats', { signal: request.signal });
      if (!request.isCurrent()) return;
      if (res.ok) {
        const data = await res.json();
        if (!request.isCurrent()) return;
        setStats(data);
      } else {
        setStatsError('Unable to load case metrics');
      }
    } catch {
      if (!request.isCurrent()) return;
      setStatsError('Network error loading case metrics');
    } finally {
      if (request.isCurrent()) setStatsLoading(false);
    }
  };

  // Fetch Cases list
  const fetchCases = async (query = searchQuery, status = statusFilter) => {
    const request = beginRequest('cases');
    setCasesLoading(true);
    setCasesError(null);
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.append('search', query.trim());
      if (status) params.append('status', status);

      const url = `/api/cases${params.toString() ? '?' + params.toString() : ''}`;
      const res = await fetch(url, { signal: request.signal });
      if (!request.isCurrent()) return;
      if (res.ok) {
        const data = await res.json();
        if (!request.isCurrent()) return;
        setCases(data);
      } else {
        setCasesError('Failed to fetch investigation cases');
      }
    } catch {
      if (!request.isCurrent()) return;
      setCasesError('Network error connecting to API');
    } finally {
      if (request.isCurrent()) setCasesLoading(false);
    }
  };

  const fetchTimeline = async (caseId) => {
    if (!isActiveCase(caseId)) return;
    const request = beginRequest('timeline');
    setTimelineLoading(true);
    setTimelineError(null);
    try {
      const response = await fetch(`/api/cases/${caseId}/timeline`, { signal: request.signal });
      const data = await response.json();
      if (!request.isCurrent()) return;
      if (response.ok) setTimelineData(data);
      else setTimelineError(apiError(data.detail, 'Unable to load the case timeline.'));
    } catch {
      if (request.isCurrent()) setTimelineError('Network error loading the case timeline.');
    } finally {
      if (request.isCurrent()) setTimelineLoading(false);
    }
  };

  // Fetch single case detail
  const fetchCaseDetail = async (id) => {
    if (!isActiveCase(id)) return;
    const request = beginRequest('details');
    setCaseLoading(true);
    setCaseError(null);
    try {
      const res = await fetch(`/api/cases/${id}`, { signal: request.signal });
      if (!request.isCurrent()) return;
      if (res.ok) {
        const data = await res.json();
        if (!request.isCurrent()) return;
        setCurrentCase(data);
        setEditForm({ title: data.title, description: data.description || '', status: data.status });
        fetchEvidenceList(id);
        fetchEntities(id, 'ALL', 1);
        fetchTimeline(id);
      } else if (res.status === 404) {
        setCaseError('Case not found');
      } else {
        setCaseError('Failed to load case details');
      }
    } catch {
      if (!request.isCurrent()) return;
      setCaseError('Network error connecting to API');
    } finally {
      if (request.isCurrent()) setCaseLoading(false);
    }
  };

  // Fetch Evidence List for a case
  const fetchEvidenceList = async (caseId) => {
    if (!isActiveCase(caseId)) return;
    const request = beginRequest('evidence');
    setEvidenceLoading(true);
    setEvidenceError(null);
    try {
      const res = await fetch(`/api/cases/${caseId}/evidence`, { signal: request.signal });
      if (!request.isCurrent()) return;
      if (res.ok) {
        const data = await res.json();
        if (!request.isCurrent()) return;
        setEvidenceFiles(data);
      } else {
        setEvidenceError('Failed to load case evidence');
      }
    } catch {
      if (!request.isCurrent()) return;
      setEvidenceError('Network error loading case evidence');
    } finally {
      if (request.isCurrent()) setEvidenceLoading(false);
    }
  };

  // Fetch Case Entities (Phase 4)
  const fetchEntities = async (caseId, category = 'ALL', page = 1) => {
    if (!isActiveCase(caseId)) return;
    const request = beginRequest('entities');
    setEntitiesLoading(true);
    setEntitiesError(null);
    try {
      const params = new URLSearchParams();
      if (category && category !== 'ALL') {
        params.append('category', category);
      }
      params.append('page', page);
      params.append('page_size', 50);

      const res = await fetch(`/api/cases/${caseId}/entities?${params.toString()}`, { signal: request.signal });
      const data = await res.json();
      if (!request.isCurrent()) return;
      if (res.ok) {
        setEntitiesData(data);
        // Expand first 5 entities by default so investigator sees provenance citations immediately
        const initialExpanded = {};
        (data.entities || []).slice(0, 5).forEach((ent) => {
          initialExpanded[`${ent.category}_${ent.display_text}`] = true;
        });
        setExpandedEntities(initialExpanded);
      } else {
        setEntitiesError(apiError(data.detail, 'Failed to extract named entities.'));
      }
    } catch {
      if (!request.isCurrent()) return;
      setEntitiesError('Network error loading case entities.');
    } finally {
      if (request.isCurrent()) setEntitiesLoading(false);
    }
  };

  const toggleEntityExpand = (key) => {
    setExpandedEntities((prev) => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  // Search Evidence Lines
  const executeEvidenceSearch = async (queryText, pageNum = 1) => {
    if (!isActiveCase(selectedCaseId)) return;
    const request = beginRequest('search');
    const q = queryText.trim();
    if (!q) {
      setSearchLoading(false);
      setSearchError('Please enter a search term or phrase.');
      return;
    }

    setSearchLoading(true);
    setSearchError(null);
    setActiveSearchQuery(q);
    setSearchPage(pageNum);

    try {
      const res = await fetch(
        `/api/cases/${selectedCaseId}/search?q=${encodeURIComponent(q)}&page=${pageNum}&page_size=15`,
        { signal: request.signal }
      );
      const data = await res.json();
      if (!request.isCurrent()) return;
      if (res.ok) {
        setSearchResults(data);
      } else {
        setSearchError(apiError(data.detail, 'Search request failed.'));
      }
    } catch {
      if (!request.isCurrent()) return;
      setSearchError('Network error executing search.');
    } finally {
      if (request.isCurrent()) setSearchLoading(false);
    }
  };

  const handleSearchSubmitCase = (e) => {
    e.preventDefault();
    executeEvidenceSearch(evidenceSearchInput, 1);
  };

  const handleClearEvidenceSearch = () => {
    cancelRequest('search');
    setSearchLoading(false);
    setEvidenceSearchInput('');
    setActiveSearchQuery('');
    setSearchResults(null);
    setSearchError(null);
  };

  // Initial load
  useEffect(() => {
    if (currentView === 'dashboard') {
      fetchStats();
      fetchCases();
    } else if (currentView === 'cases') {
      fetchCases();
    } else if (currentView === 'case-detail' && selectedCaseId) {
      fetchCaseDetail(selectedCaseId);
    }
  }, [currentView, selectedCaseId]);

  // Handle Search & Filter trigger for case registry
  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchCases();
  };

  // Handle Create Case
  const handleCreateCase = async (e) => {
    e.preventDefault();
    const request = beginRequest('create');
    setNewCaseSubmitting(true);
    setNewCaseError(null);

    try {
      const res = await fetch('/api/cases', {
        method: 'POST',
        signal: request.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCaseForm)
      });
      const data = await res.json();
      if (!request.isCurrent()) return;
      if (res.ok) {
        setNewCaseForm({ case_number: '', title: '', description: '', status: 'Open' });
        navigateToCase(data.id);
      } else {
        setNewCaseError(apiError(data.detail, 'Failed to create case'));
      }
    } catch {
      if (!request.isCurrent()) return;
      setNewCaseError('Network error creating case');
    } finally {
      if (request.isCurrent()) setNewCaseSubmitting(false);
    }
  };

  // Handle Update Case
  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!isActiveCase(selectedCaseId)) return;
    const request = beginRequest('edit');
    // An earlier detail read must not undo an edit that completes first.
    cancelRequest('details');
    setCaseLoading(false);
    setEditSaving(true);
    setEditError(null);

    try {
      const res = await fetch(`/api/cases/${selectedCaseId}`, {
        method: 'PATCH',
        signal: request.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm)
      });
      const data = await res.json();
      if (!request.isCurrent()) return;
      if (res.ok) {
        setCurrentCase(data);
        setIsEditing(false);
      } else {
        setEditError(apiError(data.detail, 'Failed to update case'));
      }
    } catch {
      if (!request.isCurrent()) return;
      setEditError('Network error updating case');
    } finally {
      if (request.isCurrent()) setEditSaving(false);
    }
  };

  // Handle Multi-file Upload
  const handleFileUpload = async (e) => {
    if (!isActiveCase(selectedCaseId)) return;
    const files = Array.from(e.target.files);
    if (!files.length) return;
    const request = beginRequest('upload');

    setUploadProgress(`Ingesting ${files.length} file(s)...`);
    const results = [];

    for (const file of files) {
      if (!request.isCurrent()) return;
      if (!file.name.toLowerCase().endsWith('.txt')) {
        results.push({
          name: file.name,
          status: 'error',
          message: 'Unsupported format. Only .txt evidence files are allowed.'
        });
        continue;
      }
      if (file.size > 5 * 1024 * 1024) {
        results.push({
          name: file.name,
          status: 'error',
          message: `File exceeds 5 MB limit (${(file.size / (1024 * 1024)).toFixed(2)} MB).`
        });
        continue;
      }

      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await fetch(`/api/cases/${selectedCaseId}/evidence`, {
          method: 'POST',
          signal: request.signal,
          body: formData
        });
        const data = await res.json();
        if (!request.isCurrent()) return;
        if (res.ok) {
          results.push({
            name: file.name,
            status: 'success',
            message: `Ingested & indexed ${data.line_count} lines (SHA-256: ${data.sha256_hash.substring(0, 12)}...)`
          });
        } else {
          results.push({
            name: file.name,
            status: 'error',
            message: apiError(data.detail, 'Ingestion failed')
          });
        }
      } catch {
        if (!request.isCurrent()) return;
        results.push({
          name: file.name,
          status: 'error',
          message: 'Network error communicating with ingestion service'
        });
      }
    }

    if (!request.isCurrent()) return;
    if (results.some(result => result.status === 'success')) {
      cancelRequest('analysis');
      cancelRequest('chat');
      cancelRequest('report');
      setAnalysisData(null);
      setAnalysisLoading(false);
      setAnalysisError(null);
      setChatMessages([]);
      setChatLoading(false);
      setChatError(null);
      setReportLoading(false);
      setReportError(null);
    }
    setUploadResults(results);
    setUploadProgress(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    fetchEvidenceList(selectedCaseId);
    fetchEntities(selectedCaseId, entityCategoryFilter, 1);
    fetchTimeline(selectedCaseId);
  };

  // All file/page loads share the same request identity, including fallback loads.
  const loadInspectorPage = async (file, page, targetLine = null, notice = null) => {
    if (!isActiveCase(file.case_id)) return;
    const request = beginRequest('inspector');
    setInspectorPage(page);
    setInspectorNotice(notice);
    setInspectedLines([]);
    lineRefs.current = {};
    setLinesLoading(true);
    setLinesError(null);
    setTargetLineNumber(targetLine);

    try {
      const res = await fetch(`/api/cases/${file.case_id}/evidence/${file.id}/lines?page=${page}&page_size=${INSPECTOR_PAGE_SIZE}`, { signal: request.signal });
      if (!request.isCurrent()) return;
      if (res.ok) {
        const data = await res.json();
        if (!request.isCurrent()) return;
        const lastPage = Math.max(1, Math.ceil(data.total_lines / INSPECTOR_PAGE_SIZE));
        setInspectedFile((prev) => prev ? { ...prev, line_count: data.total_lines } : prev);
        if ((targetLine !== null && targetLine > data.total_lines) || page > lastPage) {
          const message = 'Requested line or page is outside this evidence file. Showing the first page.';
          if (page !== 1) {
            await loadInspectorPage(file, 1, null, message);
            return;
          }
          setTargetLineNumber(null);
          setInspectorNotice(message);
        }
        setInspectedLines(data.lines);
      } else {
        setLinesError('Failed to load indexed lines.');
      }
    } catch {
      if (!request.isCurrent()) return;
      setLinesError('Network error loading evidence content.');
    } finally {
      if (request.isCurrent()) setLinesLoading(false);
    }
  };

  // Inspect evidence with an optional 1-based citation/search target.
  const handleOpenInspector = async (fileOrMeta, targetLine = null) => {
    const evidenceId = fileOrMeta.evidence_file_id || fileOrMeta.id;
    const caseId = fileOrMeta.case_id || selectedCaseId;
    if (!isActiveCase(caseId)) return;
    closeInspector();
    const file = evidenceFiles.find((item) => item.id === evidenceId) || {
      id: evidenceId,
      case_id: caseId,
      original_filename: fileOrMeta.original_filename,
      sha256_hash: fileOrMeta.sha256_hash,
      encoding: fileOrMeta.encoding || 'utf-8',
      line_count: fileOrMeta.line_count || 0,
      file_size: fileOrMeta.file_size || 0,
    };
    const validTarget = Number.isSafeInteger(targetLine) && targetLine >= 1;
    const target = validTarget ? targetLine : null;
    const page = validTarget ? Math.floor((targetLine - 1) / INSPECTOR_PAGE_SIZE) + 1 : 1;
    const notice = targetLine !== null && !validTarget
      ? 'Invalid line reference. Showing the first page.' : null;
    setInspectedFile(file);
    await loadInspectorPage(file, page, target, notice);
  };

  const handleInspectorPageChange = async (page) => {
    if (!inspectedFile || !isActiveCase(inspectedFile.case_id)) return;
    const lastPage = Math.max(1, Math.ceil(inspectedFile.line_count / INSPECTOR_PAGE_SIZE));
    // Permit retrying the current page if its initial metadata was unavailable.
    if (!Number.isSafeInteger(page) || page < 1 || (page > lastPage && page !== inspectorPage)) {
      setInspectorNotice('That page is outside this evidence file.');
      return;
    }
    await loadInspectorPage(inspectedFile, page, targetLineNumber);
  };

  // Auto-scroll to target line when inspector opens with targetLineNumber
  useEffect(() => {
    if (targetLineNumber && inspectedLines.length > 0) {
      const el = lineRefs.current[targetLineNumber];
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [targetLineNumber, inspectedLines]);

  // Verify Evidence Integrity
  const handleVerifyIntegrity = async (fileId) => {
    if (!isActiveCase(selectedCaseId) || inspectedFile?.id !== fileId) return;
    const request = beginRequest('verify');
    setVerifyStatus('verifying');
    try {
      const res = await fetch(`/api/cases/${selectedCaseId}/evidence/${fileId}/verify`, { signal: request.signal });
      const data = await res.json();
      if (!request.isCurrent()) return;
      if (res.ok) {
        setVerifyStatus(data);
      } else {
        setVerifyStatus({
          verification_status: 'error',
          message: apiError(data.detail, 'Verification request failed.')
        });
      }
    } catch {
      if (!request.isCurrent()) return;
      setVerifyStatus({
        verification_status: 'error',
        message: 'Network error executing verification.'
      });
    }
  };

  const handleCopyHash = async (hash) => {
    const request = beginRequest('copy');
    try {
      await navigator.clipboard.writeText(hash);
      if (!request.isCurrent()) return;
      setCopySuccess(true);
      setTimeout(() => {
        if (request.isCurrent()) setCopySuccess(false);
      }, 2000);
    } catch {
      if (request.isCurrent()) setCopySuccess(false);
    }
  };

  const navigateToCase = (id) => {
    if (isActiveCase(id)) return;
    invalidateRequests();
    navigationRef.current.caseId = id;
    navigationRef.current.view = 'case-detail';
    resetCaseState();
    setSelectedCaseId(id);
    setCurrentView('case-detail');
  };

  // Trigger Phase 5 AI Evidence Analysis
  const handleTriggerAnalysis = async () => {
    if (!isActiveCase(selectedCaseId)) return;
    const request = beginRequest('analysis');
    setAnalysisLoading(true);
    setAnalysisError(null);

    const controller = request.controller;
    const timeoutId = setTimeout(() => controller.abort(), 75000);

    try {
      const res = await fetch(`/api/cases/${selectedCaseId}/analysis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
      });

      let data = null;
      try {
        data = await res.json();
      } catch {
        data = null;
      }

      if (!request.isCurrent()) return;
      if (res.ok && data) {
        setAnalysisData(data);
      } else {
        const errorDetail = data && data.detail
          ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
          : `Analysis request failed with HTTP ${res.status}.`;
        setAnalysisError(errorDetail);
      }
    } catch (err) {
      if (!request.isCurrent()) return;
      if (err.name === 'AbortError') {
        setAnalysisError('Analysis request timed out after 75 seconds. The Gemini service may be overloaded—please try again.');
      } else {
        setAnalysisError('Network error connecting to analysis service.');
      }
    } finally {
      clearTimeout(timeoutId);
      if (request.isCurrent()) setAnalysisLoading(false);
    }
  };

  const clearChat = () => {
    cancelRequest('chat');
    setChatMessages([]);
    setChatInput('');
    setChatLoading(false);
    setChatError(null);
  };

  const handleSendChat = async (event) => {
    event.preventDefault();
    if (!isActiveCase(selectedCaseId)) return;
    const question = chatInput.trim();
    if (!question) { setChatError('Enter a question about this case.'); return; }
    const request = beginRequest('chat');
    const id = ++chatSequence.current;
    const history = chatMessages.filter(message => message.case_id === selectedCaseId && message.answer)
      .slice(-6).map(message => ({ case_id: selectedCaseId, question: message.question }));
    setChatMessages(previous => previous.filter(message => message.status !== 'pending')
      .concat({ id, case_id: selectedCaseId, question, status: 'pending' }));
    setChatInput('');
    setChatLoading(true);
    setChatError(null);
    const timeout = setTimeout(() => request.controller.abort(), 75000);
    try {
      const response = await fetch(`/api/cases/${selectedCaseId}/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: request.signal,
        body: JSON.stringify({ question, history }),
      });
      const data = await response.json();
      if (!request.isCurrent()) return;
      if (!response.ok) throw new Error(apiError(data.detail, 'Unable to answer this question.'));
      setChatMessages(previous => previous.map(message => message.id === id
        ? { ...message, status: 'done', answer: data } : message));
    } catch (error) {
      if (!request.isCurrent()) return;
      setChatError(error.name === 'AbortError' ? 'Chat timed out after 75 seconds. Please try again.' : error.message || 'Chat request failed.');
      setChatMessages(previous => previous.map(message => message.id === id ? { ...message, status: 'error' } : message));
    } finally {
      clearTimeout(timeout);
      if (request.isCurrent()) setChatLoading(false);
    }
  };

  const handleExportReport = async () => {
    if (!isActiveCase(selectedCaseId)) return;
    const request = beginRequest('report');
    setReportLoading(true);
    setReportError(null);
    try {
      const response = await fetch(`/api/cases/${selectedCaseId}/report`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: request.signal,
        body: JSON.stringify({ analysis: analysisData }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(apiError(data.detail, 'Report export failed.'));
      }
      const blob = await response.blob();
      if (!request.isCurrent()) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `ChronicleAI-case-${selectedCaseId}.html`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      if (request.isCurrent()) setReportError(error.message || 'Report export failed.');
    } finally {
      if (request.isCurrent()) setReportLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="brand-group">
          <div className="logo" onClick={() => navigateToView('dashboard')}>ChronicleAI</div>
          <span className="platform-tag">Digital Evidence System</span>
        </div>
        <nav className="nav-links">
          <button
            className={`nav-button ${currentView === 'dashboard' ? 'active' : ''}`}
            onClick={() => navigateToView('dashboard')}
          >
            Dashboard
          </button>
          <button
            className={`nav-button ${currentView === 'cases' ? 'active' : ''}`}
            onClick={() => { navigateToView('cases'); fetchCases(); }}
          >
            All Cases
          </button>
          <button
            className="nav-button primary"
            onClick={() => { setNewCaseError(null); navigateToView('new-case'); }}
          >
            + New Case
          </button>
        </nav>
        <div className="status-indicator">
          <span className={`status-dot ${healthStatus}`}></span>
          {healthStatus === 'checking' && 'Checking backend...'}
          {healthStatus === 'connected' && 'System operational'}
          {healthStatus === 'unavailable' && 'Backend unavailable'}
        </div>
      </header>

      {/* Main Body */}
      <main className="main-content">
        {/* DASHBOARD VIEW */}
        {currentView === 'dashboard' && (
          <div className="view-container">
            <div className="view-header">
              <div>
                <h1 className="view-title">Investigation Dashboard</h1>
                <p className="view-subtitle">Overview of current evidence cases and operational status</p>
              </div>
              <button className="btn-secondary" onClick={() => { fetchStats(); fetchCases(); }}>
                Refresh Data
              </button>
            </div>

            {/* Metric Cards */}
            <div className="metrics-grid">
              <div className="metric-card">
                <span className="metric-label">Total Cases</span>
                <span className="metric-value">{statsLoading ? '...' : stats.total_cases}</span>
              </div>
              <div className="metric-card open">
                <span className="metric-label">Open Cases</span>
                <span className="metric-value">{statsLoading ? '...' : stats.open_cases}</span>
              </div>
              <div className="metric-card progress">
                <span className="metric-label">In Progress</span>
                <span className="metric-value">{statsLoading ? '...' : stats.in_progress_cases}</span>
              </div>
              <div className="metric-card closed">
                <span className="metric-label">Closed</span>
                <span className="metric-value">{statsLoading ? '...' : stats.closed_cases}</span>
              </div>
            </div>
            {statsError && <div className="alert-banner error">{statsError}</div>}

            {/* Recent Cases Preview */}
            <div className="section-header">
              <h2>Recent Investigation Records</h2>
              <button className="link-button" onClick={() => navigateToView('cases')}>View all cases &rarr;</button>
            </div>

            {casesLoading ? (
              <div className="loading-state">Loading recent records...</div>
            ) : casesError ? (
              <div className="alert-banner error">{casesError}</div>
            ) : cases.length === 0 ? (
              <div className="empty-card">
                <h3>No investigation cases registered yet</h3>
                <p>Register your first case to begin organizing evidence records.</p>
                <button className="btn-primary" onClick={() => navigateToView('new-case')}>
                  Create Investigation Case
                </button>
              </div>
            ) : (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Case Number</th>
                      <th>Title</th>
                      <th>Status</th>
                      <th>Registered (local time)</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cases.slice(0, 5).map((c) => (
                      <tr key={c.id}>
                        <td className="case-num-cell">{c.case_number}</td>
                        <td className="case-title-cell">{c.title}</td>
                        <td><span className={`status-pill ${c.status.toLowerCase().replace(' ', '-')}`}>{c.status}</span></td>
                        <td>{formatTimestamp(c.created_at)}</td>
                        <td>
                          <button className="btn-table-action" onClick={() => navigateToCase(c.id)}>
                            Inspect Case
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ALL CASES VIEW */}
        {currentView === 'cases' && (
          <div className="view-container">
            <div className="view-header">
              <div>
                <h1 className="view-title">Case Registry</h1>
                <p className="view-subtitle">Search, filter, and inspect case files</p>
              </div>
              <button className="btn-primary" onClick={() => navigateToView('new-case')}>
                + New Case
              </button>
            </div>

            {/* Filter Bar */}
            <form className="filter-bar" onSubmit={handleSearchSubmit}>
              <input
                type="text"
                placeholder="Search by case number or title..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input-search"
              />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="select-filter"
              >
                <option value="">All Statuses</option>
                <option value="Open">Open</option>
                <option value="In Progress">In Progress</option>
                <option value="Closed">Closed</option>
              </select>
              <button type="submit" className="btn-secondary">Search</button>
              {(searchQuery || statusFilter) && (
                <button
                  type="button"
                  className="btn-text"
                  onClick={() => { setSearchQuery(''); setStatusFilter(''); fetchCases('', ''); }}
                >
                  Clear Filters
                </button>
              )}
            </form>

            {casesLoading ? (
              <div className="loading-state">Loading registry...</div>
            ) : casesError ? (
              <div className="alert-banner error">{casesError}</div>
            ) : cases.length === 0 ? (
              <div className="empty-card">
                <h3>No matching cases found</h3>
                <p>Try refining your search terms or status filters.</p>
              </div>
            ) : (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Case Number</th>
                      <th>Title</th>
                      <th>Status</th>
                      <th>Created (local time)</th>
                      <th>Last Updated</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cases.map((c) => (
                      <tr key={c.id}>
                        <td className="case-num-cell">{c.case_number}</td>
                        <td className="case-title-cell">{c.title}</td>
                        <td><span className={`status-pill ${c.status.toLowerCase().replace(' ', '-')}`}>{c.status}</span></td>
                        <td>{formatTimestamp(c.created_at)}</td>
                        <td>{formatTimestamp(c.updated_at)}</td>
                        <td>
                          <button className="btn-table-action" onClick={() => navigateToCase(c.id)}>
                            Inspect
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* CREATE CASE VIEW */}
        {currentView === 'new-case' && (
          <div className="view-container max-w-form">
            <div className="view-header">
              <div>
                <h1 className="view-title">Register Investigation Case</h1>
                <p className="view-subtitle">Create a new case file to group and track evidence</p>
              </div>
              <button className="btn-secondary" onClick={() => navigateToView('cases')}>Cancel</button>
            </div>

            {newCaseError && <div className="alert-banner error">{newCaseError}</div>}

            <form className="form-card" onSubmit={handleCreateCase}>
              <div className="form-group">
                <label htmlFor="case_number">Case Number <span className="required">*</span></label>
                <input
                  id="case_number" maxLength={100}
                  type="text"
                  placeholder="e.g. CR-2026-9042"
                  value={newCaseForm.case_number}
                  onChange={(e) => setNewCaseForm({ ...newCaseForm, case_number: e.target.value })}
                  required
                />
                <span className="field-hint">Unique identifier for institutional chain-of-custody.</span>
              </div>

              <div className="form-group">
                <label htmlFor="title">Case Title <span className="required">*</span></label>
                <input
                  id="title" maxLength={255}
                  type="text"
                  placeholder="e.g. Unauthorized Financial Disclosures"
                  value={newCaseForm.title}
                  onChange={(e) => setNewCaseForm({ ...newCaseForm, title: e.target.value })}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="status">Initial Status</label>
                <select
                  id="status"
                  value={newCaseForm.status}
                  onChange={(e) => setNewCaseForm({ ...newCaseForm, status: e.target.value })}
                >
                  <option value="Open">Open</option>
                  <option value="In Progress">In Progress</option>
                  <option value="Closed">Closed</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="description">Case Description</label>
                <textarea
                  id="description"
                  rows="4"
                  placeholder="Summary of allegations, scope of inquiry, or investigative background..."
                  value={newCaseForm.description}
                  onChange={(e) => setNewCaseForm({ ...newCaseForm, description: e.target.value })}
                ></textarea>
              </div>

              <div className="form-actions">
                <button type="submit" className="btn-primary" disabled={newCaseSubmitting}>
                  {newCaseSubmitting ? 'Registering...' : 'Register Case'}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* CASE DETAIL VIEW */}
        {currentView === 'case-detail' && (
          <div className="view-container">
            <div className="breadcrumb">
              <span className="crumb-link" onClick={() => navigateToView('cases')}>Cases</span>
              <span className="crumb-separator">/</span>
              <span className="crumb-current">{currentCase ? currentCase.case_number : 'Case Detail'}</span>
            </div>

            {caseLoading ? (
              <div className="loading-state">Loading case details...</div>
            ) : caseError ? (
              <div className="alert-banner error">{caseError}</div>
            ) : currentCase ? (
              <div className="case-detail-layout">
                {/* Main Case Info Card */}
                <div className="detail-card">
                  <div className="detail-card-header">
                    <div>
                      <div className="detail-meta-top">
                        <span className="badge-case-number">{currentCase.case_number}</span>
                        <span className={`status-pill ${currentCase.status.toLowerCase().replace(' ', '-')}`}>
                          {currentCase.status}
                        </span>
                      </div>
                      <h1 className="detail-title">{currentCase.title}</h1>
                    </div>
                    {!isEditing && (
                      <button className="btn-secondary" onClick={() => setIsEditing(true)}>
                        Edit Case
                      </button>
                    )}
                  </div>

                  {isEditing ? (
                    <form className="edit-form" onSubmit={handleSaveEdit}>
                      {editError && <div className="alert-banner error">{editError}</div>}
                      <div className="form-group">
                        <label>Title <span className="required">*</span></label>
                        <input
                          type="text"
                          value={editForm.title}
                          onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                          required
                        />
                      </div>
                      <div className="form-group">
                        <label>Status</label>
                        <select
                          value={editForm.status}
                          onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                        >
                          <option value="Open">Open</option>
                          <option value="In Progress">In Progress</option>
                          <option value="Closed">Closed</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Description</label>
                        <textarea
                          rows="4"
                          value={editForm.description}
                          onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                        ></textarea>
                      </div>
                      <div className="form-actions">
                        <button type="submit" className="btn-primary" disabled={editSaving}>
                          {editSaving ? 'Saving...' : 'Save Changes'}
                        </button>
                        <button type="button" className="btn-secondary" onClick={() => setIsEditing(false)}>
                          Cancel
                        </button>
                      </div>
                    </form>
                  ) : (
                    <div className="detail-body">
                      <div className="detail-description-section">
                        <h3>Investigation Summary</h3>
                        <p className="detail-description-text">
                          {currentCase.description || 'No detailed description provided for this case.'}
                        </p>
                      </div>

                      <div className="detail-timestamps">
                        <div>
                          <span className="ts-label">Created At (local time):</span>{' '}
                          <span>{formatTimestamp(currentCase.created_at)}</span>
                        </div>
                        <div>
                          <span className="ts-label">Last Updated (local time):</span>{' '}
                          <span>{formatTimestamp(currentCase.updated_at)}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* PHASE 3: EVIDENCE SEARCH SECTION */}
                <div className="detail-card search-section">
                  <div className="search-section-header">
                    <div>
                      <h2>Cross-File Evidence Search</h2>
                      <p className="section-subtext">
                        Exact case-scoped line retrieval across all uploaded TXT evidence files
                      </p>
                    </div>
                  </div>

                  <form className="search-bar" onSubmit={handleSearchSubmitCase}>
                    <input
                      type="text"
                      className="search-input-field"
                      placeholder="Search names, phrases, invoice references, or monetary amounts..."
                      value={evidenceSearchInput}
                      onChange={(e) => setEvidenceSearchInput(e.target.value)}
                    />
                    <button type="submit" className="btn-primary" disabled={searchLoading}>
                      {searchLoading ? 'Searching...' : 'Search Evidence'}
                    </button>
                    {(activeSearchQuery || searchResults) && (
                      <button type="button" className="btn-secondary" onClick={handleClearEvidenceSearch}>
                        Clear
                      </button>
                    )}
                  </form>

                  {searchError && <div className="alert-banner error search-error-banner">{searchError}</div>}

                  {/* Search Results Area */}
                  {searchLoading && (
                    <div className="loading-state">Querying indexed evidence lines...</div>
                  )}

                  {!searchLoading && searchResults && (
                    <div className="search-results-container">
                      <div className="search-results-summary">
                        <span>
                          Found <strong>{searchResults.total_matches}</strong> matching line{searchResults.total_matches === 1 ? '' : 's'} for &ldquo;<em>{searchResults.query}</em>&rdquo;
                        </span>
                        {searchResults.total_matches > searchResults.page_size && (
                          <span className="pagination-count">
                            Page {searchResults.page} of {Math.ceil(searchResults.total_matches / searchResults.page_size)}
                          </span>
                        )}
                      </div>

                      {searchResults.total_matches === 0 ? (
                        <div className="empty-search-state">
                          <p>No matching evidence records found in this investigation.</p>
                          <span className="empty-subtext">Check for typographical variations or search for partial keywords.</span>
                        </div>
                      ) : (
                        <div className="search-cards-list">
                          {searchResults.results.map((item, idx) => (
                            <div key={idx} className="search-result-card">
                              <div className="result-card-header">
                                <div className="result-card-meta">
                                  <span className="provenance-file">&#128196; {item.original_filename}</span>
                                  <span className="provenance-line">Line {item.line_number}</span>
                                  <span className="provenance-hash" title={item.sha256_hash}>
                                    SHA-256: {item.sha256_hash.substring(0, 14)}...
                                  </span>
                                </div>
                                <button
                                  className="btn-table-action"
                                  onClick={() => handleOpenInspector(item, item.line_number)}
                                >
                                  Open in Inspector &rarr;
                                </button>
                              </div>
                              <div className="result-card-snippet">
                                <span className="snippet-line-badge">{item.line_number}</span>
                                <span className="snippet-text">
                                  <HighlightMatch text={item.line_content} query={searchResults.query} />
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Pagination Controls */}
                      {searchResults.total_matches > searchResults.page_size && (
                        <div className="search-pagination-bar">
                          <button
                            className="btn-secondary"
                            disabled={searchResults.page <= 1}
                            onClick={() => executeEvidenceSearch(searchResults.query, searchResults.page - 1)}
                          >
                            &larr; Previous Page
                          </button>
                          <span className="page-indicator">
                            Page {searchResults.page} of {Math.ceil(searchResults.total_matches / searchResults.page_size)}
                          </span>
                          <button
                            className="btn-secondary"
                            disabled={
                              searchResults.page >= Math.ceil(searchResults.total_matches / searchResults.page_size)
                            }
                            onClick={() => executeEvidenceSearch(searchResults.query, searchResults.page + 1)}
                          >
                            Next Page &rarr;
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* PHASE 4: NAMED ENTITY EXPLORER */}
                <div className="detail-card entity-section">
                  <div className="entity-section-header">
                    <div>
                      <h2>Named Entity Explorer</h2>
                      <p className="section-subtext">
                        Case-scoped Named Entity Recognition (spaCy) with precise evidence line provenance
                      </p>
                    </div>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => fetchEntities(selectedCaseId, entityCategoryFilter, entityPage)}
                      disabled={entitiesLoading}
                    >
                      {entitiesLoading ? 'Extracting...' : '↻ Re-extract Entities'}
                    </button>
                  </div>

                  {/* Category Filter Tabs */}
                  <div className="entity-filter-bar">
                    <button
                      type="button"
                      className={`filter-tab ${entityCategoryFilter === 'ALL' ? 'active' : ''}`}
                      onClick={() => {
                        setEntityCategoryFilter('ALL');
                        setEntityPage(1);
                        fetchEntities(selectedCaseId, 'ALL', 1);
                      }}
                    >
                      All
                      {entitiesData?.category_counts && (
                        <span className="tab-count">
                          {Object.values(entitiesData.category_counts).reduce((a, b) => a + b, 0)}
                        </span>
                      )}
                    </button>
                    <button
                      type="button"
                      className={`filter-tab ${entityCategoryFilter === 'Person' ? 'active' : ''}`}
                      onClick={() => {
                        setEntityCategoryFilter('Person');
                        setEntityPage(1);
                        fetchEntities(selectedCaseId, 'Person', 1);
                      }}
                    >
                      People
                      {entitiesData?.category_counts?.Person !== undefined && (
                        <span className="tab-count count-person">{entitiesData.category_counts.Person}</span>
                      )}
                    </button>
                    <button
                      type="button"
                      className={`filter-tab ${entityCategoryFilter === 'Organization' ? 'active' : ''}`}
                      onClick={() => {
                        setEntityCategoryFilter('Organization');
                        setEntityPage(1);
                        fetchEntities(selectedCaseId, 'Organization', 1);
                      }}
                    >
                      Organizations
                      {entitiesData?.category_counts?.Organization !== undefined && (
                        <span className="tab-count count-org">{entitiesData.category_counts.Organization}</span>
                      )}
                    </button>
                    <button
                      type="button"
                      className={`filter-tab ${entityCategoryFilter === 'Location' ? 'active' : ''}`}
                      onClick={() => {
                        setEntityCategoryFilter('Location');
                        setEntityPage(1);
                        fetchEntities(selectedCaseId, 'Location', 1);
                      }}
                    >
                      Locations
                      {entitiesData?.category_counts?.Location !== undefined && (
                        <span className="tab-count count-loc">{entitiesData.category_counts.Location}</span>
                      )}
                    </button>
                    <button
                      type="button"
                      className={`filter-tab ${entityCategoryFilter === 'Date' ? 'active' : ''}`}
                      onClick={() => {
                        setEntityCategoryFilter('Date');
                        setEntityPage(1);
                        fetchEntities(selectedCaseId, 'Date', 1);
                      }}
                    >
                      Dates
                      {entitiesData?.category_counts?.Date !== undefined && (
                        <span className="tab-count count-date">{entitiesData.category_counts.Date}</span>
                      )}
                    </button>
                  </div>

                  {/* Error State */}
                  {entitiesError && (
                    <div className="alert-banner error entity-error-banner">
                      <strong>NER Notice:</strong> {entitiesError}
                    </div>
                  )}

                  {/* Loading State */}
                  {entitiesLoading && (
                    <div className="loading-state">
                      Processing case evidence with spaCy NLP pipeline...
                    </div>
                  )}

                  {/* Entities Content */}
                  {!entitiesLoading && entitiesData && (
                    <div className="entities-content-area">
                      <div className="entities-summary-bar">
                        <span>
                          Found <strong>{entitiesData.total_groups}</strong> distinct {entityCategoryFilter === 'ALL' ? 'named entit' + (entitiesData.total_groups === 1 ? 'y' : 'ies') : entityCategoryFilter.toLowerCase() + (entitiesData.total_groups === 1 ? '' : 's')} ({entitiesData.total_occurrences} citation{entitiesData.total_occurrences === 1 ? '' : 's'})
                        </span>
                        {entitiesData.total_groups > entitiesData.page_size && (
                          <span className="pagination-count">
                            Page {entitiesData.page} of {Math.ceil(entitiesData.total_groups / entitiesData.page_size)}
                          </span>
                        )}
                      </div>

                      {entitiesData.total_groups === 0 ? (
                        <div className="empty-entities-state">
                          <p>No {entityCategoryFilter === 'ALL' ? 'named entities' : entityCategoryFilter.toLowerCase() + ' entities'} discovered in this case&rsquo;s evidence.</p>
                          <span className="empty-subtext">Ingest text evidence documents containing names, organizations, places, or dates.</span>
                        </div>
                      ) : (
                        <div className="entity-cards-list">
                          {entitiesData.entities.map((entity, idx) => {
                            const key = `${entity.category}_${entity.display_text}`;
                            const isExpanded = !!expandedEntities[key];
                            return (
                              <div key={idx} className="entity-card">
                                <div
                                  className="entity-card-header"
                                  onClick={() => toggleEntityExpand(key)}
                                  role="button"
                                  tabIndex={0}
                                >
                                  <div className="entity-card-main">
                                    <span className={`entity-category-badge badge-${entity.category.toLowerCase()}`}>
                                      {entity.category}
                                    </span>
                                    <span className="entity-display-text">{entity.display_text}</span>
                                    <span className="entity-mention-count">
                                      {entity.count} mention{entity.count === 1 ? '' : 's'}
                                    </span>
                                  </div>
                                  <button
                                    type="button"
                                    className="btn-expand-toggle"
                                    aria-label={isExpanded ? 'Collapse provenance' : 'Expand provenance'}
                                  >
                                    {isExpanded ? '▲ Hide Citations' : '▼ View Citations'}
                                  </button>
                                </div>

                                {isExpanded && (
                                  <div className="entity-occurrences-drawer">
                                    <div className="occurrences-header">
                                      <span>Evidence Provenance Citations:</span>
                                    </div>
                                    <div className="occurrences-list">
                                      {entity.occurrences.map((occ, occIdx) => {
                                        const lineDisplay = occ.start_line === occ.end_line
                                          ? `Line ${occ.start_line}`
                                          : `Lines ${occ.start_line}–${occ.end_line}`;
                                        return (
                                          <div key={occIdx} className="occurrence-row">
                                            <div className="occurrence-meta">
                                              <span className="occ-file">&#128196; {occ.original_filename}</span>
                                              <span className="occ-line-badge">{lineDisplay}</span>
                                              <span className="occ-spacy-tag">
                                                {occ.extraction_method === 'metadata_rule' ? 'method: metadata_rule' : `label: ${occ.label}`}
                                              </span>
                                              <span className="occ-text-quote">&ldquo;{occ.text}&rdquo;</span>
                                            </div>
                                            <button
                                              type="button"
                                              className="btn-table-action"
                                              onClick={(e) => {
                                                e.stopPropagation();
                                                handleOpenInspector(occ, occ.start_line);
                                              }}
                                            >
                                              Open in Inspector &rarr;
                                            </button>
                                          </div>
                                        );
                                      })}
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {/* Pagination Controls */}
                      {entitiesData.total_groups > entitiesData.page_size && (
                        <div className="entities-pagination-bar">
                          <button
                            type="button"
                            className="btn-secondary"
                            disabled={entitiesData.page <= 1}
                            onClick={() => {
                              const prevPage = entitiesData.page - 1;
                              setEntityPage(prevPage);
                              fetchEntities(selectedCaseId, entityCategoryFilter, prevPage);
                            }}
                          >
                            &larr; Previous Page
                          </button>
                          <span className="page-indicator">
                            Page {entitiesData.page} of {Math.ceil(entitiesData.total_groups / entitiesData.page_size)}
                          </span>
                          <button
                            type="button"
                            className="btn-secondary"
                            disabled={entitiesData.page >= Math.ceil(entitiesData.total_groups / entitiesData.page_size)}
                            onClick={() => {
                              const nextPage = entitiesData.page + 1;
                              setEntityPage(nextPage);
                              fetchEntities(selectedCaseId, entityCategoryFilter, nextPage);
                            }}
                          >
                            Next Page &rarr;
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* PHASE 5: AI EVIDENCE-GROUNDED CASE ANALYSIS */}
                <div className="detail-card ai-analysis-section">
                  <div className="ai-analysis-header">
                    <div className="ai-header-titles">
                      <div className="ai-title-badge-row">
                        <h2>AI Case Analysis</h2>
                        <span className="badge-ai-model">Gemini Powered</span>
                      </div>
                      <p className="section-subtext">Evidence-grounded synthesis, observations, and structured provenance</p>
                    </div>

                    <div className="ai-action-group">
                      <button
                        type="button"
                        className="btn-primary-action ai-run-btn"
                        onClick={handleTriggerAnalysis}
                        disabled={analysisLoading}
                      >
                        {analysisLoading ? (
                          <>
                            <span className="spinner-inline"></span> Analyzing Case...
                          </>
                        ) : analysisData ? (
                          '↻ Re-run Analysis'
                        ) : (
                          '⚡ Generate Case Analysis'
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Provider Disclosure Banner */}
                  <div className="ai-disclosure-banner">
                    <span className="disclosure-icon">ℹ️</span>
                    <div className="disclosure-text">
                      <strong>External Provider Disclosure:</strong> Analysis is generated via Google Gemini using strictly indexed evidence from this case.
                      Inferences and hypotheses are automated and must be independently verified against primary evidence records.
                    </div>
                  </div>

                  {/* Error or Missing Key banner */}
                  {analysisError && (
                    <div className={`alert-banner ${analysisError.includes('503') || analysisError.includes('not configured') || analysisError.includes('overloaded') || analysisError.includes('unavailable') || analysisError.includes('timed out') ? 'warning' : 'error'}`}>
                      <strong>{analysisError.includes('not configured') ? 'Gemini API Key Required' : 'Analysis Service Notice'}:</strong> {analysisError}
                      {analysisError.includes('not configured') && (
                        <div className="ai-config-hint">
                          To enable AI Case Analysis, set <code>GEMINI_API_KEY=your_key</code> in the backend process environment (or a Windows user environment variable) and restart the backend.
                        </div>
                      )}
                    </div>
                  )}

                  {/* Loading State */}
                  {analysisLoading && (
                    <div className="ai-loading-card">
                      <div className="ai-loading-spinner"></div>
                      <p className="ai-loading-text">Synthesizing case evidence and validating source line citations...</p>
                      <span className="ai-loading-subtext">Cross-referencing claims against indexed evidence lines</span>
                    </div>
                  )}

                  {/* Results Display */}
                  {analysisData && !analysisLoading && (
                    <div className="ai-results-container">
                      {/* Scope and Model Meta */}
                      <div className="ai-scope-bar">
                        <span className="scope-item">
                          <strong>Model:</strong> {analysisData.model_used}
                        </span>
                        <span className="scope-item">
                          <strong>Files Scoped:</strong> {analysisData.evidence_scope.file_count}
                        </span>
                        <span className="scope-item">
                          <strong>Indexed Lines:</strong> {analysisData.evidence_scope.line_count}
                        </span>
                        <span className="scope-item">
                          <strong>Context Size:</strong> {analysisData.evidence_scope.total_characters.toLocaleString()} chars
                        </span>
                      </div>

                      {/* Warnings / Quarantined items banner if any */}
                      {analysisData.warnings && analysisData.warnings.length > 0 && (
                        <div className="ai-warnings-box">
                          <div className="warnings-header">⚠️ Evidentiary Quality Notices ({analysisData.warnings.length})</div>
                          <ul className="warnings-list">
                            {analysisData.warnings.map((w, idx) => (
                              <li key={idx}>{w}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* 1. Summary */}
                      {analysisData.summary && analysisData.summary.length > 0 && (
                        <div className="ai-section-block">
                          <h3 className="ai-section-title">Case Summary</h3>
                          <div className="ai-claims-list">
                            {analysisData.summary.map((claim, cIdx) => (
                              <div key={cIdx} className="ai-claim-card summary-card">
                                <p className="claim-statement">{claim.statement}</p>
                                {claim.citations && claim.citations.length > 0 && (
                                  <div className="claim-citations">
                                    <span className="citations-label">Sources:</span>
                                    {claim.citations.map((cit, citIdx) => (
                                      <button
                                        key={citIdx}
                                        type="button"
                                        className="citation-pill"
                                        title={`Jump to line ${cit.start_line} in ${cit.original_filename}`}
                                        onClick={() => handleOpenInspector(cit, cit.start_line)}
                                      >
                                        📄 {cit.original_filename} : L{cit.start_line}{cit.end_line !== cit.start_line ? `-${cit.end_line}` : ''} &rarr;
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* 2. Documented Observations */}
                      <div className="ai-section-block">
                        <div className="ai-section-header-row">
                          <h3 className="ai-section-title">Documented Observations</h3>
                          <span className="badge-section-type verified-fact">Direct Evidence</span>
                        </div>
                        <p className="ai-section-desc">Facts explicitly stated within the ingested evidence records.</p>
                        {analysisData.documented_observations && analysisData.documented_observations.length > 0 ? (
                          <div className="ai-claims-list">
                            {analysisData.documented_observations.map((claim, cIdx) => (
                              <div key={cIdx} className="ai-claim-card observation-card">
                                <div className="claim-statement-row">
                                  <span className="claim-bullet">•</span>
                                  <p className="claim-statement">{claim.statement}</p>
                                </div>
                                {claim.citations && claim.citations.length > 0 && (
                                  <div className="claim-citations">
                                    <span className="citations-label">Provenance:</span>
                                    {claim.citations.map((cit, citIdx) => (
                                      <button
                                        key={citIdx}
                                        type="button"
                                        className="citation-pill"
                                        title={cit.snippet ? `Snippet: "${cit.snippet}"` : `Jump to line ${cit.start_line}`}
                                        onClick={() => handleOpenInspector(cit, cit.start_line)}
                                      >
                                        📄 {cit.original_filename} : L{cit.start_line}{cit.end_line !== cit.start_line ? `-${cit.end_line}` : ''} &rarr;
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="empty-subtext">No direct observations were extracted.</p>
                        )}
                      </div>

                      {/* 3. Possible Interpretations */}
                      <div className="ai-section-block">
                        <div className="ai-section-header-row">
                          <h3 className="ai-section-title">Possible Interpretations</h3>
                          <span className="badge-section-type tentative-inference">Hypothesis / Inference</span>
                        </div>
                        <p className="ai-section-desc">Tentative investigative hypotheses. Not definitive findings of fact.</p>
                        {analysisData.possible_interpretations && analysisData.possible_interpretations.length > 0 ? (
                          <div className="ai-claims-list">
                            {analysisData.possible_interpretations.map((claim, cIdx) => (
                              <div key={cIdx} className="ai-claim-card interpretation-card">
                                <div className="claim-statement-row">
                                  <span className="claim-bullet">💡</span>
                                  <p className="claim-statement">{claim.statement}</p>
                                </div>
                                {claim.citations && claim.citations.length > 0 && (
                                  <div className="claim-citations">
                                    <span className="citations-label">Grounded In:</span>
                                    {claim.citations.map((cit, citIdx) => (
                                      <button
                                        key={citIdx}
                                        type="button"
                                        className="citation-pill inference-pill"
                                        title={cit.snippet ? `Snippet: "${cit.snippet}"` : `Jump to line ${cit.start_line}`}
                                        onClick={() => handleOpenInspector(cit, cit.start_line)}
                                      >
                                        📄 {cit.original_filename} : L{cit.start_line}{cit.end_line !== cit.start_line ? `-${cit.end_line}` : ''} &rarr;
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="empty-subtext">No interpretations provided.</p>
                        )}
                      </div>

                      {/* 4. Unresolved Questions */}
                      {analysisData.unresolved_questions && analysisData.unresolved_questions.length > 0 && (
                        <div className="ai-section-block">
                          <div className="ai-section-header-row">
                            <h3 className="ai-section-title">Unresolved Questions & Evidentiary Gaps</h3>
                            <span className="badge-section-type question-tag">Gaps / Inquiries</span>
                          </div>
                          <p className="ai-section-desc">Key ambiguities or unverified questions warranting further investigation.</p>
                          <div className="ai-questions-list">
                            {analysisData.unresolved_questions.map((q, qIdx) => (
                              <div key={qIdx} className="ai-question-item">
                                <span className="question-icon">❓</span>
                                <span className="question-text">{q}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Idle Placeholder */}
                  {!analysisData && !analysisLoading && !analysisError && (
                    <div className="ai-empty-prompt">
                      <div className="ai-empty-icon">🔍</div>
                      <h4>On-Demand Evidentiary Synthesis</h4>
                      <p>
                        Click <strong>Generate Case Analysis</strong> above to produce a citation-grounded summary,
                        objective observations, tentative hypotheses, and investigative questions from the indexed evidence.
                      </p>
                    </div>
                  )}
                </div>

                <section className="detail-card" aria-label="Case-specific AI chat">
                  <div className="detail-card-header">
                    <div><h2>Ask This Case</h2><p className="section-subtext">Evidence-grounded questions and follow-ups with source citations</p></div>
                    <button className="btn-secondary" onClick={clearChat} disabled={chatMessages.length === 0}>Clear Conversation</button>
                  </div>
                  <p className="section-subtext">Uses Google Gemini. Conversation stays in this case view and clears when you leave. Previous questions provide context, never evidence.</p>
                  <form className="search-bar" onSubmit={handleSendChat}>
                    <input className="search-input-field" aria-label="Question about this case" maxLength={2000}
                      placeholder="What does the evidence say about the payment approval?"
                      value={chatInput} onChange={event => setChatInput(event.target.value)} />
                    <button className="btn-primary" disabled={chatLoading || !chatInput.trim()}>{chatLoading ? 'Answering…' : 'Ask Case'}</button>
                  </form>
                  {chatError && <div className="alert-banner error" role="alert">{chatError}</div>}
                  {chatMessages.length === 0 && <p className="empty-subtext">Ask a question after uploading evidence. Unsupported questions will be acknowledged without an invented answer.</p>}
                  <div aria-live="polite">
                    {chatMessages.map(message => (
                      <article key={message.id} className="ai-section-block">
                        <h3>You asked: {message.question}</h3>
                        {message.status === 'pending' && <p>Reading this case’s indexed evidence…</p>}
                        {message.status === 'error' && <p>No answer returned. You can ask again.</p>}
                        {message.answer && <>
                          <p className={message.answer.answer_status === 'grounded' ? 'section-subtext' : 'alert-banner warning'}>{message.answer.message}</p>
                          {[
                            ['summary', 'Answer summary — statements about evidence'],
                            ['documented_observations', 'Documented observations'],
                            ['possible_interpretations', 'Possible interpretations — not established facts'],
                          ].map(([section, heading]) => message.answer[section]?.length > 0 && (
                            <div key={section}><h4>{heading}</h4>{message.answer[section].map((claim, index) => (
                              <div key={index} className="ai-claim-card"><p>{claim.statement}</p>
                                <EvidenceCitations citations={claim.citations} onOpen={handleOpenInspector} />
                              </div>
                            ))}</div>
                          ))}
                          {message.answer.unresolved_questions?.length > 0 && <><h4>Unresolved questions</h4><ul>{message.answer.unresolved_questions.map((question, index) => <li key={index}>{question}</li>)}</ul></>}
                          {message.answer.warnings?.length > 0 && <div className="ai-warnings-box"><strong>Citation quality notices</strong><ul>{message.answer.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></div>}
                        </>}
                      </article>
                    ))}
                  </div>
                </section>

                <section className="detail-card" aria-label="Evidence-linked timeline">
                  <div className="detail-card-header">
                    <div><h2>Evidence-Linked Timeline</h2><p className="section-subtext">Dated statements and their original evidence lines</p></div>
                    <button className="btn-secondary" disabled={timelineLoading} onClick={() => fetchTimeline(selectedCaseId)}>Refresh Timeline</button>
                  </div>
                  {timelineLoading && <div className="loading-state">Reading dates from indexed evidence…</div>}
                  {timelineError && <div className="alert-banner error" role="alert">{timelineError}</div>}
                  {!timelineLoading && timelineData && <>
                    <p className="section-subtext">{timelineData.disclaimer}</p>
                    {[
                      ['events', 'Chronological dated statements'], ['undated', 'Ambiguous, incomplete or invalid date mentions'],
                    ].map(([section, heading]) => timelineData[section].length > 0 && (
                      <div key={section}><h3>{heading}</h3>{timelineData[section].map((entry, index) => (
                        <article className="ai-claim-card" key={index}>
                          <strong>{entry.normalized_date || entry.date_text}</strong>{' '}
                          <span className="badge-section-type">{entry.date_status}</span>
                          <p>{entry.description}</p><p className="section-subtext">{entry.note}</p>
                          <EvidenceCitations citations={entry.citations} onOpen={handleOpenInspector} />
                        </article>
                      ))}</div>
                    ))}
                    {timelineData.events.length === 0 && timelineData.undated.length === 0 && <p className="empty-subtext">No supported date mentions found. Upload evidence containing explicit dates to populate the timeline.</p>}
                  </>}
                </section>

                <section className="detail-card" aria-label="Investigation report">
                  <div className="detail-card-header">
                    <div><h2>Investigation Report</h2><p className="section-subtext">Case details, evidence hashes and integrity checks, timeline, AI observations, interpretations, questions and cited excerpts.</p></div>
                    <button className="btn-primary" onClick={handleExportReport} disabled={reportLoading || analysisLoading || uploadProgress !== null}>
                      {reportLoading ? 'Preparing Report…' : 'Download Case Report'}
                    </button>
                  </div>
                  <p className="section-subtext">Open the downloaded HTML report to print or save as PDF. Export checks integrity and does not contact Gemini.</p>
                  {!analysisData && <p className="alert-banner info">Generate Case Analysis first to include AI findings. Without it, the report clearly marks those sections as unavailable.</p>}
                  {reportError && <div className="alert-banner error" role="alert">{reportError}</div>}
                </section>

                {/* Evidence Section (Phase 2 Upload & Registry) */}
                <div className="detail-card evidence-section">
                  <div className="evidence-section-header">
                    <div>
                      <h2>Case Evidence Records</h2>
                      <p className="section-subtext">Original text evidence preservation and line-level index</p>
                    </div>

                    <div className="evidence-upload-controls">
                      <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileUpload}
                        accept=".txt,text/plain"
                        multiple
                        style={{ display: 'none' }}
                        id="evidence-file-input"
                      />
                      <label htmlFor="evidence-file-input" className="btn-primary upload-label">
                        + Ingest TXT Evidence
                      </label>
                    </div>
                  </div>

                  {/* Upload Progress & Results Notification */}
                  {uploadProgress && (
                    <div className="alert-banner info">{uploadProgress}</div>
                  )}
                  {uploadResults.length > 0 && (
                    <div className="upload-results-panel">
                      <div className="results-header">
                        <span>Ingestion Results ({uploadResults.length} file{uploadResults.length > 1 ? 's' : ''})</span>
                        <button className="btn-text" onClick={() => setUploadResults([])}>Dismiss</button>
                      </div>
                      <div className="results-list">
                        {uploadResults.map((r, i) => (
                          <div key={i} className={`result-row ${r.status}`}>
                            <span className="result-name">{r.name}</span>
                            <span className="result-msg">{r.message}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {evidenceError && <div className="alert-banner error">{evidenceError}</div>}

                  {/* Evidence Table */}
                  {evidenceLoading ? (
                    <div className="loading-state">Loading evidence records...</div>
                  ) : evidenceFiles.length === 0 ? (
                    <div className="empty-card evidence-empty">
                      <div className="evidence-empty-icon">&#128196;</div>
                      <h3>No Evidence Ingested for this Case</h3>
                      <p>Upload text files (.txt, max 5 MB per file). Original file bytes will be cryptographically preserved, hashed with SHA-256, and indexed line-by-line.</p>
                      <label htmlFor="evidence-file-input" className="btn-primary upload-label">
                        Ingest First File
                      </label>
                    </div>
                  ) : (
                    <div className="table-wrapper">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Evidence File</th>
                            <th>Size</th>
                            <th>SHA-256 Hash</th>
                            <th>Lines</th>
                            <th>Uploaded (local time)</th>
                            <th>Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {evidenceFiles.map((ev) => (
                            <tr key={ev.id}>
                              <td className="case-title-cell font-bold">{ev.original_filename}</td>
                              <td>{(ev.file_size / 1024).toFixed(1)} KB</td>
                              <td className="mono-cell">
                                <span title={ev.sha256_hash}>
                                  {ev.sha256_hash.substring(0, 16)}...
                                </span>
                              </td>
                              <td>{ev.line_count.toLocaleString()}</td>
                              <td>{formatTimestamp(ev.uploaded_at)}</td>
                              <td>
                                <button className="btn-table-action" onClick={() => handleOpenInspector(ev)}>
                                  Inspect Evidence
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        )}

        {/* EVIDENCE INSPECTOR MODAL */}
        {inspectedFile && (
          <div className="modal-overlay" onClick={closeInspector}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <div>
                  <div className="inspector-meta-tag">Evidence Inspector</div>
                  <h2 className="modal-title">{inspectedFile.original_filename}</h2>
                </div>
                <button className="btn-close" onClick={closeInspector}>&times;</button>
              </div>

              {/* Inspector Meta Ribbon */}
              <div className="inspector-ribbon">
                <div className="ribbon-item">
                  <span className="ribbon-label">SHA-256:</span>
                  <span className="ribbon-val mono-val">{inspectedFile.sha256_hash}</span>
                  <button className="btn-copy" onClick={() => handleCopyHash(inspectedFile.sha256_hash)}>
                    {copySuccess ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <div className="ribbon-item">
                  <span className="ribbon-label">Encoding:</span>
                  <span className="ribbon-val">{inspectedFile.encoding || 'utf-8'}</span>
                </div>
                <div className="ribbon-item">
                  <span className="ribbon-label">Lines:</span>
                  <span className="ribbon-val">
                    {inspectedFile.line_count ? inspectedFile.line_count.toLocaleString() : inspectedLines.length}
                  </span>
                </div>
                {inspectedFile.file_size > 0 && (
                  <div className="ribbon-item">
                    <span className="ribbon-label">Size:</span>
                    <span className="ribbon-val">{inspectedFile.file_size} bytes</span>
                  </div>
                )}
                <div className="ribbon-item verify-btn-container">
                  <button
                    className="btn-secondary btn-verify"
                    onClick={() => handleVerifyIntegrity(inspectedFile.id)}
                    disabled={verifyStatus === 'verifying'}
                  >
                    {verifyStatus === 'verifying' ? 'Verifying...' : 'Verify Cryptographic Integrity'}
                  </button>
                </div>
              </div>

              {/* Integrity Status Callout */}
              {verifyStatus && verifyStatus !== 'verifying' && (
                <div className={`verification-banner ${verifyStatus.verification_status}`}>
                  <div className="verify-icon">
                    {verifyStatus.verification_status === 'verified' && '✓'}
                    {verifyStatus.verification_status === 'corrupted' && '⚠'}
                    {verifyStatus.verification_status === 'missing_file' && '✕'}
                  </div>
                  <div>
                    <div className="verify-title">
                      {verifyStatus.verification_status === 'verified' && 'Cryptographic Integrity Confirmed'}
                      {verifyStatus.verification_status === 'corrupted' && 'CRITICAL: Hash Mismatch Detected!'}
                      {verifyStatus.verification_status === 'missing_file' && 'Evidence File Missing'}
                    </div>
                    <div className="verify-detail">{verifyStatus.message}</div>
                    {verifyStatus.computed_hash && (
                      <div className="verify-hashes">
                        <div>Stored Hash: <code>{verifyStatus.stored_hash}</code></div>
                        <div>Computed Hash: <code>{verifyStatus.computed_hash}</code></div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Line Content Viewer */}
              {inspectorNotice && (
                <div className="alert-banner warning" role="status">{inspectorNotice}</div>
              )}
              <div className="evidence-viewer-container">
                {linesLoading ? (
                  <div className="loading-state">Loading indexed evidence lines...</div>
                ) : linesError ? (
                  <div className="alert-banner error">
                    {linesError}{' '}
                    <button className="btn-secondary" onClick={() => handleInspectorPageChange(inspectorPage)}>
                      Retry Page
                    </button>
                  </div>
                ) : (
                  <div className="line-table-wrapper">
                    <table className="line-table">
                      <tbody>
                        {inspectedLines.map((line) => {
                          const isTarget = targetLineNumber === line.line_number;
                          return (
                            <tr
                              key={line.id}
                              ref={(el) => (lineRefs.current[line.line_number] = el)}
                              className={`line-row ${isTarget ? 'targeted-line' : ''}`}
                            >
                              <td className="line-num">{line.line_number}</td>
                              <td className="line-text">
                                {activeSearchQuery && isTarget ? (
                                  <HighlightMatch text={line.content || '\u00A0'} query={activeSearchQuery} />
                                ) : (
                                  line.content || '\u00A0'
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {inspectedFile.line_count > INSPECTOR_PAGE_SIZE && (
                <nav className="modal-footer" aria-label="Evidence line pages">
                  <button
                    className="btn-secondary"
                    disabled={linesLoading || inspectorPage <= 1}
                    onClick={() => handleInspectorPageChange(inspectorPage - 1)}
                  >
                    &larr; Previous
                  </button>
                  <span className="page-indicator" aria-live="polite">
                    Page {inspectorPage} of {Math.ceil(inspectedFile.line_count / INSPECTOR_PAGE_SIZE)}
                    {inspectedLines.length > 0 && (
                      <> · Lines {inspectedLines[0].line_number}–{inspectedLines[inspectedLines.length - 1].line_number} of {inspectedFile.line_count}</>
                    )}
                  </span>
                  <button
                    className="btn-secondary"
                    disabled={linesLoading || inspectorPage >= Math.ceil(inspectedFile.line_count / INSPECTOR_PAGE_SIZE)}
                    onClick={() => handleInspectorPageChange(inspectorPage + 1)}
                  >
                    Next &rarr;
                  </button>
                </nav>
              )}
              <div className="modal-footer">
                <span className="evidence-footer-hint">Exact byte-level original stored on backend filesystem under case custody.</span>
                <button className="btn-secondary" onClick={closeInspector}>Close</button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
