import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// Exercise the actual component handlers without JSX or a browser dependency.
// Hooks retain state across explicit renders; fetch deliberately ignores aborts.
const source = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8').replace(/\r\n/g, '\n');
const start = source.indexOf('function App() {') + 'function App() {'.length;
const end = source.indexOf('\n  return (\n    <div className="app-container">', start);
assert.ok(start > 0 && end > start, 'App handler boundary must remain identifiable');
const body = source.slice(start, end);
const names = [...body.matchAll(/const \[([^\]]+)\] = useState\(/g)]
  .map(match => match[1].split(',')[0].trim()).filter(Boolean);
const handlers = ['navigateToCase', 'fetchCaseDetail', 'fetchEvidenceList', 'fetchEntities',
  'executeEvidenceSearch', 'handleTriggerAnalysis', 'handleOpenInspector',
  'handleVerifyIntegrity', 'handleSaveEdit', 'handleFileUpload', 'handleCreateCase',
  'handleClearEvidenceSearch', 'handleCopyHash', 'fetchStats', 'fetchCases',
  'fetchTimeline', 'handleSendChat', 'clearChat', 'handleExportReport', 'setChatInput', 'apiError', 'formatTimestamp'];
// Optional exports let these tests demonstrate failures against the old checkpoint too.
const component = new Function('useState', 'useEffect', 'useRef', 'fetch', 'setTimeout',
  'clearTimeout', 'AbortController', 'navigator', 'document', 'URL', body + '\nreturn { state: {' + names.join(',') +
  '}, ' + handlers.join(',') + ', navigateToView: typeof navigateToView === "function" ? navigateToView : null,' +
  'closeInspector: typeof closeInspector === "function" ? closeInspector : null,' +
  'handleInspectorPageChange: typeof handleInspectorPageChange === "function" ? handleInspectorPageChange : null,' +
  'lineRefs };');

function harness() {
  const states = [], refs = [], requests = [], timers = new Map(), downloads = [], revoked = [];
  let cursor = 0, refCursor = 0, timerId = 0, effects = [];
  const useState = initial => {
    const index = cursor++;
    if (!(index in states)) states[index] = initial;
    return [states[index], value => { states[index] = typeof value === 'function' ? value(states[index]) : value; }];
  };
  const useRef = initial => { const index = refCursor++; return refs[index] ||= { current: initial }; };
  const fetch = (url, options = {}) => new Promise((resolve, reject) => requests.push({ url, options, resolve, reject, done: false }));
  const render = () => {
    cursor = 0; refCursor = 0; effects = [];
    return component(useState, effect => effects.push(effect), useRef, fetch,
      fn => { timers.set(++timerId, fn); return timerId; }, id => timers.delete(id),
      AbortController, { clipboard: { writeText: async () => {} } },
      { body: { appendChild() {} }, createElement: () => ({ click() { downloads.push({ href: this.href, download: this.download }); }, remove() {} }) },
      { createObjectURL: () => 'blob:synthetic-report', revokeObjectURL: url => revoked.push(url) });
  };
  const current = () => requests.findLast(request => !request.done);
  const finish = (request, data, mode = 'success') => {
    assert.ok(request, 'Expected an outstanding request'); request.done = true;
    if (mode === 'network') request.reject(new Error('synthetic network failure'));
    else request.resolve({ ok: mode !== 'http', status: mode === 'http' ? 503 : 200, blob: async () => new Blob([String(data)]),
      json: async () => { if (mode === 'json') throw new Error('synthetic parse failure'); return data; } });
  };
  const select = id => { render().navigateToCase(id); return render(); };
  const unmount = () => {
    const lifecycle = effects.find(effect => effect.toString().includes('invalidateRequests'));
    assert.ok(lifecycle, 'Request cleanup must be registered'); lifecycle()();
  };
  const mountInspectorLines = () => {
    const ui = render(); let scrolledLine = null;
    for (const line of ui.state.inspectedLines) {
      ui.lineRefs.current[line.line_number] = { scrollIntoView: () => { scrolledLine = line.line_number; } };
    }
    const scrollEffect = effects.find(effect => effect.toString().includes('scrollIntoView'));
    assert.ok(scrollEffect); scrollEffect();
    // Evaluate the actual JSX row-selection expression rather than a test copy.
    const expression = source.match(/const isTarget = ([^;]+);/)[1];
    const isTarget = new Function('targetLineNumber', 'line', 'return ' + expression);
    return { scrolledLine, highlightedLines: ui.state.inspectedLines.filter(line => isTarget(ui.state.targetLineNumber, line)).map(line => line.line_number) };
  };
  return { render, select, current, finish, requests, timers, unmount, mountInspectorLines, downloads, revoked };
}
const event = { preventDefault() {} };
const tick = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
const operations = [
  { name: 'details', start: ui => ui.fetchCaseDetail(ui.state.selectedCaseId), loading: 'caseLoading', error: 'caseError', value: 'currentCase', data: id => ({ id, title: 'Case ' + id, status: 'Open' }) },
  { name: 'evidence', start: ui => ui.fetchEvidenceList(ui.state.selectedCaseId), loading: 'evidenceLoading', error: 'evidenceError', value: 'evidenceFiles', data: id => [{ id, case_id: id }] },
  { name: 'entities', start: ui => ui.fetchEntities(ui.state.selectedCaseId), loading: 'entitiesLoading', error: 'entitiesError', value: 'entitiesData', data: id => ({ case_id: id, entities: [], category_counts: {} }) },
  { name: 'search', start: ui => ui.executeEvidenceSearch('Alpha'), loading: 'searchLoading', error: 'searchError', value: 'searchResults', data: id => ({ case_id: id, results: [] }) },
  { name: 'analysis', start: ui => ui.handleTriggerAnalysis(), loading: 'analysisLoading', error: 'analysisError', value: 'analysisData', data: id => ({ case_id: id, summary: [] }) },
  { name: 'edit', start: ui => ui.handleSaveEdit(event), loading: 'editSaving', error: 'editError', value: 'currentCase', data: id => ({ id, title: 'Edited ' + id, status: 'Open' }) },
];

for (const operation of operations) {
  for (const mode of ['success', 'http', 'network', 'json']) {
    test(`${operation.name}: old ${mode} and finally cannot affect a newer case request`, async () => {
      const h = harness(); const old = operation.start(h.select(101)); const requestA = h.current();
      const fresh = operation.start(h.select(202)); const requestB = h.current();
      const before = h.render().state;
      h.finish(requestA, mode === 'http' ? { detail: 'old failure' } : operation.data(101), mode); await old;
      const after = h.render().state;
      assert.equal(after.selectedCaseId, 202);
      assert.equal(after[operation.loading], true, 'Old finally must not clear current loading');
      assert.deepEqual(after[operation.value], before[operation.value], 'Old success must not replace current data');
      assert.equal(after[operation.error], before[operation.error], 'Old error must not replace current error');
      if (operation.name === 'details') assert.equal(h.requests.length, 2, 'Old details must not launch follow-up requests');
      h.finish(requestB, operation.data(202)); await fresh;
      assert.deepEqual(h.render().state[operation.value], operation.data(202));
      assert.equal(h.render().state[operation.loading], false);
      assert.equal(requestA.options.signal?.aborted, true);
    });
  }
  test(`${operation.name}: reversed completion in the same case keeps the latest request`, async () => {
    const h = harness(); const ui = h.select(101);
    const old = operation.start(ui); const requestA = h.current();
    const fresh = operation.start(h.render()); const requestB = h.current();
    h.finish(requestB, operation.data(202)); await fresh;
    h.finish(requestA, operation.data(101)); await old;
    assert.deepEqual(h.render().state[operation.value], operation.data(202));
    assert.equal(h.render().state[operation.loading], false);
  });
  test(`${operation.name}: current errors still render and reset loading`, async () => {
    const h = harness(); const pending = operation.start(h.select(101));
    h.finish(h.current(), { detail: 'current failure' }, 'http'); await pending;
    assert.ok(h.render().state[operation.error]);
    assert.equal(h.render().state[operation.loading], false);
  });
}

for (const mode of ['success', 'http', 'network', 'json']) {
  test(`Inspector: old ${mode} cannot affect the newly opened file`, async () => {
    const h = harness(); h.select(101);
    const old = h.render().handleOpenInspector({ id: 11, case_id: 101, original_filename: 'A.txt' }, 1); const requestA = h.current();
    const fresh = h.render().handleOpenInspector({ id: 22, case_id: 101, original_filename: 'B.txt' }, 2); const requestB = h.current();
    h.finish(requestA, { total_lines: 1, lines: [{ evidence_file_id: 11, line_number: 1 }] }, mode); await old;
    assert.equal(h.render().state.inspectedFile.id, 22);
    assert.deepEqual(h.render().state.inspectedLines, []);
    assert.equal(h.render().state.linesError, null);
    assert.equal(h.render().state.linesLoading, true);
    h.finish(requestB, { total_lines: 2, lines: [{ evidence_file_id: 22, line_number: 2 }] }); await fresh;
    assert.equal(h.render().state.inspectedLines[0].evidence_file_id, 22);
    assert.equal(h.render().state.targetLineNumber, 2);
    assert.equal(requestA.options.signal?.aborted, true);
    assert.ok(requestB.url.endsWith('/lines?page=1&page_size=2000'), 'Pagination stays unchanged');
  });
}
test('Inspector: reversed completion and verification remain tied to the current file', async () => {
  const h = harness(); h.select(101);
  const old = h.render().handleOpenInspector({ id: 11, case_id: 101 }, 1); const a = h.current();
  const verification = h.render().handleVerifyIntegrity(11); const verify = h.current();
  const fresh = h.render().handleOpenInspector({ id: 22, case_id: 101 }, 2); const b = h.current();
  h.finish(b, { total_lines: 2, lines: [{ evidence_file_id: 22, line_number: 2 }] }); await fresh;
  h.finish(a, { total_lines: 1, lines: [{ evidence_file_id: 11, line_number: 1 }] }); await old;
  h.finish(verify, { evidence_id: 11, verification_status: 'verified' }); await verification;
  assert.equal(h.render().state.inspectedFile.id, 22);
  assert.equal(h.render().state.inspectedLines[0].evidence_file_id, 22);
  assert.equal(h.render().state.verifyStatus, null);
});
test('Inspector close invalidates pending line and integrity responses', async () => {
  const h = harness(); h.select(101);
  const opening = h.render().handleOpenInspector({ id: 11, case_id: 101 }, 1); const lines = h.current();
  const verifying = h.render().handleVerifyIntegrity(11); const verify = h.current();
  assert.ok(h.render().closeInspector); h.render().closeInspector();
  h.finish(lines, { total_lines: 1, lines: [{ evidence_file_id: 11 }] }); await opening;
  h.finish(verify, { evidence_id: 11 }); await verifying;
  assert.equal(h.render().state.inspectedFile, null);
  assert.deepEqual(h.render().state.inspectedLines, []);
  assert.equal(h.render().state.verifyStatus, null);
});
test('Leaving the case view invalidates analysis and returning to the same case does not revive it', async () => {
  const h = harness(); const old = h.select(101).handleTriggerAnalysis(); const a = h.current();
  assert.ok(h.render().navigateToView); h.render().navigateToView('dashboard'); h.select(101);
  h.finish(a, { case_id: 101, summary: ['stale'] }); await old;
  assert.equal(h.render().state.analysisData, null);
  assert.equal(h.render().state.analysisLoading, false);
});
test('Clearing a search invalidates its pending response', async () => {
  const h = harness(); const pending = h.select(101).executeEvidenceSearch('Alpha'); const a = h.current();
  h.render().handleClearEvidenceSearch(); h.finish(a, { results: ['stale'] }); await pending;
  assert.equal(h.render().state.searchResults, null); assert.equal(h.render().state.searchLoading, false);
});
test('Uploads stop scheduling files and cannot refresh a different case after navigation', async () => {
  const h = harness(); h.select(101);
  const files = [new File(['A'], 'A.txt'), new File(['B'], 'B.txt')];
  const uploading = h.render().handleFileUpload({ target: { files } }); const a = h.current();
  h.select(202); h.finish(a, { line_count: 1, sha256_hash: 'a'.repeat(64) }); await tick();
  // Drain the pre-fix second upload so the reproduction fails rather than hangs.
  if (h.current()) h.finish(h.current(), { line_count: 1, sha256_hash: 'b'.repeat(64) });
  await uploading;
  assert.equal(h.requests.length, 1); assert.deepEqual(h.render().state.uploadResults, []);
  assert.equal(h.render().state.uploadProgress, null);
});
test('Stale case creation cannot navigate away from a newer selection', async () => {
  const h = harness(); const creating = h.render().handleCreateCase(event); const a = h.current();
  h.select(202); h.finish(a, { id: 303 }); await creating;
  assert.equal(h.render().state.selectedCaseId, 202); assert.equal(h.render().state.newCaseSubmitting, false);
});
test('Normal case creation uses the same case-navigation reset path', async () => {
  const h = harness(); const creating = h.render().handleCreateCase(event); h.finish(h.current(), { id: 303 }); await creating;
  assert.equal(h.render().state.selectedCaseId, 303); assert.equal(h.render().state.currentView, 'case-detail');
  assert.equal(h.render().state.newCaseSubmitting, false);
});
test('Current analysis timeout is still reported and loading resets', async () => {
  const h = harness(); const pending = h.select(101).handleTriggerAnalysis(); const request = h.current();
  for (const fn of h.timers.values()) fn();
  const error = new Error('aborted'); error.name = 'AbortError'; request.reject(error); await pending;
  assert.match(h.render().state.analysisError, /75 seconds/); assert.equal(h.render().state.analysisLoading, false);
  await tick();
});

for (const operation of operations) {
  test(`${operation.name}: navigation while JSON decoding is pending cannot update the new case`, async () => {
    const h = harness(); const old = operation.start(h.select(101)); const a = h.current();
    let finishJSON;
    a.done = true;
    a.resolve({ ok: true, status: 200, json: () => new Promise(resolve => { finishJSON = resolve; }) });
    await tick(); assert.ok(finishJSON);
    h.select(202); const before = h.render().state;
    finishJSON(operation.data(101)); await old;
    assert.deepEqual(h.render().state, before);
  });
}
for (const mode of ['http', 'network', 'json']) {
  test(`Integrity verification: stale ${mode} cannot affect another file`, async () => {
    const h = harness(); h.select(101);
    const opening = h.render().handleOpenInspector({ id: 11, case_id: 101 }, 1);
    h.finish(h.current(), { total_lines: 1, lines: [] }); await opening;
    const verifying = h.render().handleVerifyIntegrity(11); const a = h.current();
    const next = h.render().handleOpenInspector({ id: 22, case_id: 101 }, 1); const b = h.current();
    h.finish(a, { detail: 'old verification failure' }, mode); await verifying;
    assert.equal(h.render().state.verifyStatus, null);
    h.finish(b, { total_lines: 1, lines: [{ evidence_file_id: 22 }] }); await next;
    assert.equal(h.render().state.inspectedLines[0].evidence_file_id, 22);
  });
  test(`Upload: stale ${mode} cannot publish results or restart processing`, async () => {
    const h = harness(); h.select(101);
    const pending = h.render().handleFileUpload({ target: { files: [new File(['A'], 'A.txt')] } }); const a = h.current();
    h.select(202); h.finish(a, { detail: 'old failure' }, mode); await pending;
    assert.deepEqual(h.render().state.uploadResults, []); assert.equal(h.render().state.uploadProgress, null);
    assert.equal(h.requests.length, 1);
  });
}
test('Normal upload publishes results and refreshes only its own case', async () => {
  const h = harness(); h.select(101);
  const pending = h.render().handleFileUpload({ target: { files: [new File(['A'], 'A.txt')] } });
  h.finish(h.current(), { line_count: 1, sha256_hash: 'a'.repeat(64) }); await pending;
  assert.equal(h.render().state.uploadResults[0].status, 'success');
  assert.deepEqual(h.requests.slice(1).map(request => request.url), [
    '/api/cases/101/evidence', '/api/cases/101/entities?page=1&page_size=50', '/api/cases/101/timeline',
  ]);
});
test('Normal verification still displays its result', async () => {
  const h = harness(); h.select(101);
  const opening = h.render().handleOpenInspector({ id: 11, case_id: 101 }, 1);
  h.finish(h.current(), { total_lines: 1, lines: [] }); await opening;
  const verifying = h.render().handleVerifyIntegrity(11);
  h.finish(h.current(), { evidence_id: 11, verification_status: 'verified' }); await verifying;
  assert.equal(h.render().state.verifyStatus.evidence_id, 11);
});
test('Selecting the same case again preserves an active request and displayed case', async () => {
  const h = harness(); const pending = h.select(101).fetchCaseDetail(101); const a = h.current();
  h.select(101); assert.equal(a.options.signal.aborted, false);
  h.finish(a, { id: 101, title: 'A', status: 'Open' }); await pending;
  assert.equal(h.render().state.currentCase.id, 101);
});
test('Unmount invalidates pending analysis even if abort is ignored', async () => {
  const h = harness(); const pending = h.select(101).handleTriggerAnalysis(); const a = h.current();
  h.unmount(); const before = h.render().state;
  h.finish(a, { case_id: 101 }); await pending;
  assert.deepEqual(h.render().state, before); assert.equal(a.options.signal.aborted, true);
});
test('Old clipboard timer cannot clear a newer file copy indicator', async () => {
  const h = harness(); h.select(101);
  await h.render().handleCopyHash('first'); const oldTimer = [...h.timers.values()][0];
  const opening = h.render().handleOpenInspector({ id: 22, case_id: 101 }, 1);
  await h.render().handleCopyHash('second'); oldTimer();
  assert.equal(h.render().state.copySuccess, true);
  h.finish(h.current(), { total_lines: 1, lines: [] }); await opening;
});
for (const method of ['fetchStats', 'fetchCases']) {
  test(`${method}: navigation also discards stale global-list responses`, async () => {
    const h = harness(); const pending = h.render()[method](); const a = h.current();
    h.select(101); const before = h.render().state;
    h.finish(a, method === 'fetchStats' ? { total_cases: 999 } : [{ id: 999 }]); await pending;
    assert.deepEqual(h.render().state, before);
  });
}

// Synthetic responses follow the existing backend contract and contain one page.
const bigFile = { id: 11, case_id: 101, original_filename: 'large.txt', line_count: 5005, sha256_hash: 'a'.repeat(64) };
function pageResponse(page, total = 5005, fileId = 11) {
  const first = (page - 1) * 2000 + 1;
  return { page, page_size: 2000, total_lines: total,
    lines: Array.from({ length: Math.max(0, Math.min(2000, total - first + 1)) }, (_, index) => ({
      id: first + index, evidence_file_id: fileId, line_number: first + index, content: 'Synthetic line ' + (first + index),
    })) };
}
const requestedPage = request => Number(new URL(request.url, 'http://synthetic.invalid').searchParams.get('page'));
async function openBigFile(h) {
  h.select(101); const pending = h.render().handleOpenInspector(bigFile);
  h.finish(h.current(), pageResponse(1)); await pending;
}

for (const [target, page] of [[null, 1], [9, 1], [2000, 1], [2001, 2], [2501, 2], [5005, 3]]) {
  test(`Inspector pagination: target ${target ?? 'none'} loads page ${page} and selects its exact line`, async () => {
    const h = harness(); h.select(101);
    const pending = h.render().handleOpenInspector(bigFile, target); const request = h.current();
    assert.equal(requestedPage(request), page);
    h.finish(request, pageResponse(page)); await pending;
    const ui = h.render();
    assert.equal(ui.state.inspectorPage, page);
    assert.equal(ui.state.inspectedFile.id, 11);
    assert.equal(ui.state.inspectedFile.line_count, 5005);
    assert.equal(ui.state.inspectedLines[0].line_number, (page - 1) * 2000 + 1);
    assert.ok(ui.state.inspectedLines.length <= 2000);
    assert.equal(ui.state.linesError, null);
    const mounted = h.mountInspectorLines();
    assert.equal(mounted.scrolledLine, target);
    assert.deepEqual(mounted.highlightedLines, target === null ? [] : [target]);
  });
}
test('Inspector pagination: a small file defaults to page 1 and keeps metadata', async () => {
  const h = harness(); h.select(101);
  const file = { ...bigFile, line_count: 17, encoding: 'utf-8', file_size: 100 };
  const list = h.render().fetchEvidenceList(101); h.finish(h.current(), [file]); await list;
  const opening = h.render().handleOpenInspector({ evidence_file_id: 11, original_filename: 'large.txt' });
  assert.equal(requestedPage(h.current()), 1); h.finish(h.current(), pageResponse(1, 17)); await opening;
  assert.equal(h.render().state.inspectedLines.length, 17);
  assert.equal(h.render().state.inspectedFile.sha256_hash, file.sha256_hash);
  assert.equal(h.render().state.inspectedFile.encoding, 'utf-8');
  assert.equal(h.render().state.inspectorNotice, null);
});
test('Inspector pagination: first, middle and last pages retain integrity and citation selection', async () => {
  const h = harness(); await openBigFile(h);
  const verifying = h.render().handleVerifyIntegrity(11);
  h.finish(h.current(), { evidence_id: 11, verification_status: 'verified' }); await verifying;
  for (const page of [2, 3, 1]) {
    assert.ok(h.render().handleInspectorPageChange);
    const pending = h.render().handleInspectorPageChange(page);
    assert.equal(h.render().state.linesLoading, true);
    assert.deepEqual(h.render().state.inspectedLines, []);
    assert.equal(requestedPage(h.current()), page);
    h.finish(h.current(), pageResponse(page)); await pending;
    assert.equal(h.render().state.inspectorPage, page);
    assert.equal(h.render().state.inspectedLines.at(-1).line_number, page === 3 ? 5005 : page * 2000);
    assert.equal(h.render().state.verifyStatus.verification_status, 'verified');
  }
});
for (const target of [0, -1, 1.5, '9', true, Infinity, NaN, Number.MAX_SAFE_INTEGER + 1]) {
  test(`Inspector pagination: invalid target ${String(target)} opens first page with a notice`, async () => {
    const h = harness(); h.select(101);
    const pending = h.render().handleOpenInspector(bigFile, target);
    assert.equal(requestedPage(h.current()), 1);
    h.finish(h.current(), pageResponse(1)); await pending;
    assert.equal(h.render().state.targetLineNumber, null);
    assert.ok(h.render().state.inspectorNotice);
    assert.equal(h.render().state.linesError, null);
  });
}
for (const [target, page] of [[18, 1], [2501, 2]]) {
  test(`Inspector pagination: target ${target} beyond the server total falls back safely`, async () => {
    const h = harness(); h.select(101);
    const pending = h.render().handleOpenInspector({ evidence_file_id: 11, original_filename: 'small.txt' }, target);
    assert.equal(requestedPage(h.current()), page);
    h.finish(h.current(), pageResponse(page, 17)); await tick();
    if (page !== 1) {
      assert.equal(h.requests.length, 2); assert.equal(requestedPage(h.current()), 1);
      h.finish(h.current(), pageResponse(1, 17));
    }
    await pending;
    assert.equal(h.render().state.inspectorPage, 1);
    assert.equal(h.render().state.inspectedFile.line_count, 17);
    assert.equal(h.render().state.targetLineNumber, null);
    assert.ok(h.render().state.inspectorNotice);
    assert.equal(h.render().state.inspectedLines.length, 17);
  });
}
test('Inspector pagination: zero indexed lines do not trigger a fallback loop', async () => {
  const h = harness(); h.select(101);
  const pending = h.render().handleOpenInspector({ id: 11, case_id: 101, line_count: 0 }, 1);
  h.finish(h.current(), pageResponse(1, 0)); await pending;
  assert.equal(h.requests.length, 1); assert.equal(h.render().state.inspectorPage, 1);
  assert.equal(h.render().state.inspectedFile.line_count, 0);
  assert.deepEqual(h.render().state.inspectedLines, []);
  assert.equal(h.render().state.targetLineNumber, null);
});
for (const mode of ['success', 'http', 'network', 'json']) {
  test(`Inspector pagination: stale page ${mode} and finally cannot affect a newer page`, async () => {
    const h = harness(); await openBigFile(h);
    const old = h.render().handleInspectorPageChange(2); const a = h.current();
    const fresh = h.render().handleInspectorPageChange(3); const b = h.current();
    h.finish(a, pageResponse(2), mode); await old;
    assert.equal(h.render().state.inspectorPage, 3); assert.equal(h.render().state.linesLoading, true);
    assert.equal(h.render().state.linesError, null); assert.deepEqual(h.render().state.inspectedLines, []);
    h.finish(b, pageResponse(3)); await fresh;
    assert.equal(h.render().state.inspectedLines[0].line_number, 4001);
    assert.equal(a.options.signal.aborted, true);
  });
}
test('Inspector pagination: reversed completion preserves the last requested page', async () => {
  const h = harness(); await openBigFile(h);
  const old = h.render().handleInspectorPageChange(2); const a = h.current();
  const fresh = h.render().handleInspectorPageChange(3); const b = h.current();
  h.finish(b, pageResponse(3)); await fresh; h.finish(a, pageResponse(2)); await old;
  assert.equal(h.render().state.inspectorPage, 3);
  assert.equal(h.render().state.inspectedLines[0].line_number, 4001);
});
test('Inspector pagination: switching files invalidates a pending page', async () => {
  const h = harness(); await openBigFile(h);
  const old = h.render().handleInspectorPageChange(2); const a = h.current();
  const fresh = h.render().handleOpenInspector({ id: 22, case_id: 101, original_filename: 'B.txt', line_count: 17 }, 9);
  h.finish(h.current(), pageResponse(1, 17, 22)); await fresh;
  h.finish(a, pageResponse(2)); await old;
  assert.equal(h.render().state.inspectedFile.id, 22);
  assert.equal(h.render().state.inspectedLines[0].evidence_file_id, 22);
  assert.equal(h.render().state.inspectorPage, 1);
  assert.equal(h.mountInspectorLines().scrolledLine, 9);
});
test('Inspector pagination: closing during a pending page prevents late updates', async () => {
  const h = harness(); await openBigFile(h);
  const pending = h.render().handleInspectorPageChange(2); const a = h.current(); h.render().closeInspector();
  h.finish(a, pageResponse(2)); await pending;
  assert.equal(h.render().state.inspectedFile, null); assert.equal(h.render().state.inspectorPage, 1);
  assert.equal(h.render().state.linesLoading, false); assert.deepEqual(h.render().state.inspectedLines, []);
});
test('Inspector pagination: switching cases invalidates a pending page', async () => {
  const h = harness(); await openBigFile(h);
  const pending = h.render().handleInspectorPageChange(2); const a = h.current(); h.select(202);
  h.finish(a, pageResponse(2)); await pending;
  assert.equal(h.render().state.selectedCaseId, 202); assert.equal(h.render().state.inspectedFile, null);
  assert.deepEqual(h.render().state.inspectedLines, []);
});
for (const mode of ['http', 'network', 'json']) {
  test(`Inspector pagination: current page ${mode} errors reset loading and can be retried`, async () => {
    const h = harness(); await openBigFile(h);
    const pending = h.render().handleInspectorPageChange(2); h.finish(h.current(), { detail: 'failure' }, mode); await pending;
    assert.equal(h.render().state.linesLoading, false); assert.ok(h.render().state.linesError);
    assert.deepEqual(h.render().state.inspectedLines, []);
    const retry = h.render().handleInspectorPageChange(2); h.finish(h.current(), pageResponse(2)); await retry;
    assert.equal(h.render().state.linesError, null); assert.equal(h.render().state.inspectedLines[0].line_number, 2001);
  });
}
test('Inspector pagination: invalid page numbers do not fetch or discard the current page', async () => {
  const h = harness(); await openBigFile(h); const count = h.requests.length;
  for (const page of [0, -1, 4, 1.5, '2', NaN]) await h.render().handleInspectorPageChange(page);
  assert.equal(h.requests.length, count); assert.equal(h.render().state.inspectorPage, 1);
  assert.equal(h.render().state.inspectedLines[0].line_number, 1); assert.ok(h.render().state.inspectorNotice);
});
for (const origin of ['search', 'analysis']) {
  test(`Inspector pagination: ${origin} citation wiring opens and scrolls to line 2501`, async () => {
    const h = harness(); h.select(101); let opening;
    if (origin === 'search') {
      const pending = h.render().executeEvidenceSearch('Synthetic');
      h.finish(h.current(), { results: [{ case_id: 101, evidence_file_id: 11, original_filename: 'large.txt', line_number: 2501 }] }); await pending;
      const expression = source.match(/handleOpenInspector\(item, item\.line_number\)/)[0];
      opening = new Function('handleOpenInspector', 'item', 'return ' + expression)(h.render().handleOpenInspector, h.render().state.searchResults.results[0]);
    } else {
      const pending = h.render().handleTriggerAnalysis();
      h.finish(h.current(), { case_id: 101, summary: [{ citations: [{ evidence_file_id: 11, original_filename: 'large.txt', start_line: 2501, end_line: 2502 }] }] }); await pending;
      const expression = source.match(/handleOpenInspector\(cit, cit\.start_line\)/)[0];
      opening = new Function('handleOpenInspector', 'cit', 'return ' + expression)(h.render().handleOpenInspector, h.render().state.analysisData.summary[0].citations[0]);
    }
    assert.equal(requestedPage(h.current()), 2); h.finish(h.current(), pageResponse(2)); await opening;
    assert.deepEqual(h.mountInspectorLines(), { scrolledLine: 2501, highlightedLines: [2501] });
  });
}

test('Inspector pagination: navigation during page JSON decoding ignores old content', async () => {
  const h = harness(); await openBigFile(h);
  const old = h.render().handleInspectorPageChange(2); const a = h.current(); let finishJSON;
  a.done = true; a.resolve({ ok: true, json: () => new Promise(resolve => { finishJSON = resolve; }) });
  await tick(); assert.ok(finishJSON);
  const fresh = h.render().handleInspectorPageChange(3); const b = h.current();
  h.finish(b, pageResponse(3)); await fresh; finishJSON(pageResponse(2)); await old;
  assert.equal(h.render().state.inspectorPage, 3);
  assert.equal(h.render().state.inspectedLines[0].line_number, 4001);
});
test('Inspector pagination: a fallback response cannot overwrite a newly opened file', async () => {
  const h = harness(); h.select(101);
  const old = h.render().handleOpenInspector({ id: 11, case_id: 101 }, 2501);
  h.finish(h.current(), pageResponse(2, 17)); await tick(); const fallback = h.current();
  assert.equal(requestedPage(fallback), 1);
  const fresh = h.render().handleOpenInspector({ id: 22, case_id: 101 }, 9);
  h.finish(h.current(), pageResponse(1, 17, 22)); await fresh;
  h.finish(fallback, pageResponse(1, 17)); await old;
  assert.equal(h.render().state.inspectedFile.id, 22);
  assert.equal(h.render().state.inspectedLines[0].evidence_file_id, 22);
  assert.equal(h.render().state.inspectorNotice, null);
});
test('Inspector pagination: returning to the citation page restores highlighting and scrolling', async () => {
  const h = harness(); h.select(101);
  const opening = h.render().handleOpenInspector(bigFile, 2501);
  h.finish(h.current(), pageResponse(2)); await opening;
  assert.deepEqual(h.mountInspectorLines(), { scrolledLine: 2501, highlightedLines: [2501] });
  const away = h.render().handleInspectorPageChange(1); h.finish(h.current(), pageResponse(1)); await away;
  assert.deepEqual(h.mountInspectorLines(), { scrolledLine: null, highlightedLines: [] });
  const back = h.render().handleInspectorPageChange(2); h.finish(h.current(), pageResponse(2)); await back;
  assert.deepEqual(h.mountInspectorLines(), { scrolledLine: 2501, highlightedLines: [2501] });
});
test('Inspector pagination: a distant citation with unknown metadata can retry its current page', async () => {
  const h = harness(); h.select(101);
  const opening = h.render().handleOpenInspector({ evidence_file_id: 11, original_filename: 'large.txt' }, 2501);
  h.finish(h.current(), { detail: 'Temporary failure' }, 'http'); await opening;
  assert.equal(h.render().state.inspectedFile.line_count, 0);
  const retry = h.render().handleInspectorPageChange(2);
  assert.equal(requestedPage(h.current()), 2); h.finish(h.current(), pageResponse(2)); await retry;
  assert.equal(h.render().state.inspectedFile.line_count, 5005);
  assert.equal(h.render().state.linesError, null); assert.equal(h.mountInspectorLines().scrolledLine, 2501);
});
test('Inspector pagination: explicit foreign-case file metadata cannot open an Inspector', async () => {
  const h = harness(); h.select(101);
  await h.render().handleOpenInspector({ id: 22, case_id: 202 }, 2501);
  assert.equal(h.requests.length, 0); assert.equal(h.render().state.inspectedFile, null);
});

const chatReply = caseId => ({ case_id: caseId, answer_status: 'grounded', message: 'Cited answer',
  summary: [{ statement: 'Documented transfer', citations: [{ evidence_file_id: 11, start_line: 2501, end_line: 2501 }] }],
  documented_observations: [], possible_interpretations: [], unresolved_questions: [], warnings: [] });
function ask(h, question = 'What does the evidence say?') {
  h.render().setChatInput(question); return h.render().handleSendChat(event);
}
for (const mode of ['success', 'http', 'network', 'json']) {
  test(`Case chat: stale ${mode} cannot cross a case switch or clear current loading`, async () => {
    const h = harness(); h.select(101); const old = ask(h); const a = h.current();
    h.select(202); const fresh = ask(h, 'Question for B'); const b = h.current();
    h.finish(a, chatReply(101), mode); await old;
    assert.equal(h.render().state.chatLoading, true); assert.equal(h.render().state.chatError, null);
    assert.equal(h.render().state.chatMessages.length, 1); assert.equal(h.render().state.chatMessages[0].case_id, 202);
    assert.equal(h.render().state.chatMessages[0].answer, undefined);
    h.finish(b, chatReply(202)); await fresh;
    assert.equal(h.render().state.chatMessages[0].answer.case_id, 202);
    assert.equal(h.render().state.chatLoading, false); assert.equal(a.options.signal.aborted, true);
  });
}
test('Case chat: history includes only prior completed questions from this case and clears on navigation', async () => {
  const h = harness(); h.select(101);
  const first = ask(h, 'First question'); h.finish(h.current(), chatReply(101)); await first;
  const second = ask(h, 'Follow-up'); const b = h.current();
  assert.deepEqual(JSON.parse(b.options.body).history, [{ case_id: 101, question: 'First question' }]);
  h.finish(b, chatReply(101)); await second;
  h.select(202); assert.deepEqual(h.render().state.chatMessages, []);
  const next = ask(h, 'New case question'); assert.deepEqual(JSON.parse(h.current().options.body).history, []);
  h.finish(h.current(), chatReply(202)); await next;
});
test('Case chat: clearing an active conversation prevents late answers', async () => {
  const h = harness(); h.select(101); const pending = ask(h); const a = h.current();
  h.render().clearChat(); h.finish(a, chatReply(101)); await pending;
  assert.deepEqual(h.render().state.chatMessages, []); assert.equal(h.render().state.chatLoading, false);
});
test('Case chat: reversed requests remove superseded pending turns and retain the newest answer', async () => {
  const h = harness(); h.select(101); const old = ask(h, 'Old'); const a = h.current();
  const fresh = ask(h, 'New'); const b = h.current();
  h.finish(b, chatReply(101)); await fresh; h.finish(a, chatReply(101)); await old;
  assert.equal(h.render().state.chatMessages.length, 1); assert.equal(h.render().state.chatMessages[0].question, 'New');
});
test('Case chat: timeout is visible and resets loading', async () => {
  const h = harness(); h.select(101); const pending = ask(h); const a = h.current();
  for (const fn of h.timers.values()) fn(); const error = new Error('aborted'); error.name = 'AbortError'; a.reject(error); await pending;
  assert.match(h.render().state.chatError, /75 seconds/); assert.equal(h.render().state.chatLoading, false);
});
test('Case chat: unsupported responses are retained as explicit no-answer notices', async () => {
  const h = harness(); h.select(101); const pending = ask(h);
  const answer = { ...chatReply(101), summary: [], answer_status: 'insufficient_evidence', message: 'Evidence does not support an answer.' };
  h.finish(h.current(), answer); await pending;
  assert.equal(h.render().state.chatMessages[0].answer.answer_status, 'insufficient_evidence');
});
for (const mode of ['success', 'http', 'network', 'json']) {
  test(`Timeline: stale ${mode} cannot replace another case timeline`, async () => {
    const h = harness(); h.select(101); const old = h.render().fetchTimeline(101); const a = h.current();
    h.select(202); const fresh = h.render().fetchTimeline(202); const b = h.current();
    h.finish(a, { case_id: 101, events: [], undated: [] }, mode); await old;
    assert.equal(h.render().state.timelineLoading, true); assert.equal(h.render().state.timelineData, null);
    assert.equal(h.render().state.timelineError, null);
    h.finish(b, { case_id: 202, events: [], undated: [] }); await fresh;
    assert.equal(h.render().state.timelineData.case_id, 202); assert.equal(h.render().state.timelineLoading, false);
  });
}
test('Timeline: reverse completion in one case retains the newest response', async () => {
  const h = harness(); h.select(101); const old = h.render().fetchTimeline(101); const a = h.current();
  const fresh = h.render().fetchTimeline(101); const b = h.current();
  h.finish(b, { case_id: 101, events: ['new'], undated: [] }); await fresh;
  h.finish(a, { case_id: 101, events: ['old'], undated: [] }); await old;
  assert.deepEqual(h.render().state.timelineData.events, ['new']);
});
for (const mode of ['success', 'http', 'network']) {
  test(`Report: stale ${mode} cannot download or set errors in a different case`, async () => {
    const h = harness(); h.select(101); const old = h.render().handleExportReport(); const a = h.current();
    h.select(202); const fresh = h.render().handleExportReport(); const b = h.current();
    h.finish(a, { detail: 'old failure' }, mode); await old;
    assert.equal(h.downloads.length, 0); assert.equal(h.render().state.reportLoading, true);
    assert.equal(h.render().state.reportError, null);
    h.finish(b, '<html>Report B</html>'); await fresh;
    assert.equal(h.downloads.length, 1); assert.equal(h.downloads[0].download, 'ChronicleAI-case-202.html');
    assert.equal(h.render().state.reportLoading, false);
  });
}
test('Report: exports the current analysis snapshot and revokes its browser URL', async () => {
  const h = harness(); h.select(101);
  const analysis = h.render().handleTriggerAnalysis(); const snapshot = { ...chatReply(101), evidence_scope: { file_count: 1, line_count: 1, total_characters: 10 } };
  h.finish(h.current(), snapshot); await analysis;
  const exporting = h.render().handleExportReport(); assert.deepEqual(JSON.parse(h.current().options.body).analysis, snapshot);
  h.finish(h.current(), '<html>Report</html>'); await exporting;
  assert.equal(h.downloads[0].href, 'blob:synthetic-report');
  for (const fn of h.timers.values()) fn(); assert.deepEqual(h.revoked, ['blob:synthetic-report']);
});
test('Upload: new evidence invalidates previous analysis and conversation answers', async () => {
  const h = harness(); h.select(101); const chat = ask(h); h.finish(h.current(), chatReply(101)); await chat;
  const analysis = h.render().handleTriggerAnalysis(); h.finish(h.current(), chatReply(101)); await analysis;
  const upload = h.render().handleFileUpload({ target: { files: [new File(['new'], 'new.txt')] } });
  h.finish(h.current(), { line_count: 1, sha256_hash: 'a'.repeat(64) }); await upload;
  assert.equal(h.render().state.analysisData, null); assert.deepEqual(h.render().state.chatMessages, []);
  assert.ok(h.requests.some(request => request.url.endsWith('/101/timeline')));
});
test('API validation messages are always safe strings for React rendering', () => {
  const ui = harness().render();
  assert.equal(ui.apiError([{ msg: 'Title too long', input: {} }], 'fallback'), 'Title too long');
  assert.equal(ui.apiError({ unexpected: 'object' }, 'fallback'), 'fallback');
  assert.equal(ui.apiError([null, 7, {}], 'fallback'), 'fallback');
});
test('Case creation safely renders FastAPI validation-error arrays', async () => {
  const h = harness(); const pending = h.render().handleCreateCase(event);
  h.finish(h.current(), { detail: [{ msg: 'Title too long' }] }, 'http'); await pending;
  assert.equal(h.render().state.newCaseError, 'Title too long');
});
test('Case editing safely renders FastAPI validation-error arrays', async () => {
  const h = harness(); h.select(101); const pending = h.render().handleSaveEdit(event);
  h.finish(h.current(), { detail: [{ msg: 'Title too long' }] }, 'http'); await pending;
  assert.equal(h.render().state.editError, 'Title too long');
});
test('Naive UTC timestamps and explicitly zoned timestamps represent the same local instant', () => {
  const ui = harness().render();
  assert.equal(ui.formatTimestamp('2026-10-12T10:00:00'), ui.formatTimestamp('2026-10-12T10:00:00Z'));
});
