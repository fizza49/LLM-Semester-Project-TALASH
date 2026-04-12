// ── TALASH · CS417 · Milestone 1 · app.js ──────────────────────

// ── STATE ─────────────────────────────────────────────────────────
const state = {
  files: [],       // { name, size, status, data }
  candidates: [],  // parsed candidate objects
};

// ── DOM REFS ──────────────────────────────────────────────────────
const dropZone       = document.getElementById('drop-zone');
const fileInput      = document.getElementById('file-input');
const fileItems      = document.getElementById('file-items');
const processBtn     = document.getElementById('process-btn');
const cvCountEl      = document.getElementById('cv-count');
const extractCountEl = document.getElementById('extract-count');
const candidatesBody = document.getElementById('candidates-body');
const candidateSelect= document.getElementById('candidate-select');
const tableSelect    = document.getElementById('table-select');
const extractionWrap = document.getElementById('extraction-table-wrap');
const toast          = document.getElementById('toast');
const sectionTitle   = document.getElementById('section-title');

// ── NAV ───────────────────────────────────────────────────────────
const sectionTitles = {
  upload:       'CV Upload & Ingestion',
  candidates:   'Candidate Registry',
  extraction:   'Structured Extraction Output',
  architecture: 'System Architecture',
};

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', e => {
    e.preventDefault();
    const sec = item.dataset.section;
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    item.classList.add('active');
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.getElementById('section-' + sec).classList.add('active');
    sectionTitle.textContent = sectionTitles[sec] || '';
  });
});

// ── DRAG & DROP ───────────────────────────────────────────────────
dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));

dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  handleFiles(e.dataTransfer.files);
});

dropZone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', () => handleFiles(fileInput.files));

function handleFiles(fileList) {
  Array.from(fileList).forEach(file => {
    if (!file.name.endsWith('.pdf')) {
      showToast('Only PDF files are supported.', 'error');
      return;
    }
    if (state.files.find(f => f.name === file.name)) return; // skip duplicates
    state.files.push({ name: file.name, size: file.size, status: 'queued', raw: file });
  });
  renderFileList();
  updateStats();
}

function renderFileList() {
  if (state.files.length === 0) {
    fileItems.innerHTML = '<div class="empty-state">No files uploaded yet.</div>';
    processBtn.disabled = true;
    return;
  }

  fileItems.innerHTML = state.files.map((f, i) => `
    <div class="file-item" id="file-item-${i}">
      <div class="file-info">
        <span class="file-icon">◈</span>
        <div>
          <div class="file-name">${f.name}</div>
          <div class="file-size">${formatSize(f.size)}</div>
        </div>
      </div>
      <span class="file-status ${f.status}">${f.status}</span>
    </div>
  `).join('');

  const allDone = state.files.every(f => f.status === 'done');
  const anyQueued = state.files.some(f => f.status === 'queued');
  processBtn.disabled = !anyQueued;
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ── PROCESS CVs ──────────────────────────────────────────────────
processBtn.addEventListener('click', async () => {
  const queued = state.files.filter(f => f.status === 'queued');
  if (!queued.length) return;

  processBtn.disabled = true;
  showToast('Processing CVs…', 'success');

  for (const file of queued) {
    setFileStatus(file.name, 'processing');
    try {
      const formData = new FormData();
      formData.append('cv', file.raw);

      const res = await fetch('/upload', { method: 'POST', body: formData });
      const data = await res.json();

      if (data.error) throw new Error(data.error);

      setFileStatus(file.name, 'done');
      file.data = data;
      state.candidates.push(data);
      addCandidateToSelect(data);
      renderCandidatesTable();
      extractCountEl.textContent = state.candidates.length;
    } catch (err) {
      setFileStatus(file.name, 'error');
      showToast('Error processing ' + file.name, 'error');
    }
  }

  updateStats();
  showToast('Processing complete!', 'success');
});

function setFileStatus(name, status) {
  const file = state.files.find(f => f.name === name);
  if (file) file.status = status;
  renderFileList();
}

function updateStats() {
  cvCountEl.textContent = state.files.length;
  extractCountEl.textContent = state.candidates.length;
}

// ── CANDIDATES TABLE ──────────────────────────────────────────────
function renderCandidatesTable() {
  if (!state.candidates.length) {
    candidatesBody.innerHTML = '<tr><td colspan="6" class="empty-row">No candidates yet. Upload and process CVs first.</td></tr>';
    return;
  }

  candidatesBody.innerHTML = state.candidates.map((c, i) => {
    const edu = c.education?.[0] || {};
    return `
      <tr>
        <td>${i + 1}</td>
        <td>${c.name || '—'}</td>
        <td>${c.applied_for || '—'}</td>
        <td>${edu.degree || '—'}</td>
        <td>${edu.university || '—'}</td>
        <td><span class="badge badge-green">Extracted</span></td>
      </tr>
    `;
  }).join('');
}

// ── EXTRACTION TABLE ──────────────────────────────────────────────
function addCandidateToSelect(candidate) {
  const opt = document.createElement('option');
  opt.value = state.candidates.length - 1;
  opt.textContent = candidate.name || 'Candidate ' + state.candidates.length;
  candidateSelect.appendChild(opt);
}

candidateSelect.addEventListener('change', renderExtractionTable);
tableSelect.addEventListener('change', renderExtractionTable);

function renderExtractionTable() {
  const idx = candidateSelect.value;
  const table = tableSelect.value;

  if (idx === '') {
    extractionWrap.innerHTML = '<div class="empty-state">Select a candidate to view extracted data.</div>';
    return;
  }

  const candidate = state.candidates[parseInt(idx)];
  const data = candidate?.[table];

  if (!data || !data.length) {
    extractionWrap.innerHTML = `<div class="empty-state">No ${table} data found for this candidate.</div>`;
    return;
  }

  const headers = Object.keys(data[0]);
  extractionWrap.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>${headers.map(h => `<th>${h.replace(/_/g, ' ')}</th>`).join('')}</tr>
      </thead>
      <tbody>
        ${data.map(row => `
          <tr>${headers.map(h => `<td>${row[h] ?? '—'}</td>`).join('')}</tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

// ── EXPORT ────────────────────────────────────────────────────────
document.getElementById('export-csv-btn').addEventListener('click', () => {
  const idx = candidateSelect.value;
  const table = tableSelect.value;
  if (idx === '') { showToast('Select a candidate first.', 'error'); return; }

  const candidate = state.candidates[parseInt(idx)];
  const data = candidate?.[table];
  if (!data || !data.length) { showToast('No data to export.', 'error'); return; }

  const headers = Object.keys(data[0]);
  const rows = data.map(r => headers.map(h => `"${r[h] ?? ''}"`).join(','));
  const csv = [headers.join(','), ...rows].join('\n');

  downloadText(csv, `${candidate.name}_${table}.csv`, 'text/csv');
  showToast('CSV exported!', 'success');
});

document.getElementById('export-excel-btn').addEventListener('click', () => {
  window.location.href = '/export/excel';
  showToast('Downloading Excel…', 'success');
});

function downloadText(content, filename, type) {
  const blob = new Blob([content], { type });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

// ── TOAST ─────────────────────────────────────────────────────────
let toastTimer;
function showToast(msg, type = '') {
  toast.textContent = msg;
  toast.className = 'toast show ' + type;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3000);
}
