const state = {
  files: [],
  candidates: [],
};

const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const fileItems = document.getElementById('file-items');
const processBtn = document.getElementById('process-btn');
const cvCountEl = document.getElementById('cv-count');
const extractCountEl = document.getElementById('extract-count');
const candidatesBody = document.getElementById('candidates-body');
const candidateSelect = document.getElementById('candidate-select');
const analysisCandidateSelect = document.getElementById('analysis-candidate-select');
const summaryCandidateSelect = document.getElementById('summary-candidate-select');
const tableSelect = document.getElementById('table-select');
const extractionWrap = document.getElementById('extraction-table-wrap');
const analysisWrap = document.getElementById('analysis-table-wrap');
const summaryWrap = document.getElementById('summary-wrap');
const emailWrap = document.getElementById('email-wrap');
const chartGrid = document.getElementById('chart-grid');
const toast = document.getElementById('toast');
const sectionTitle = document.getElementById('section-title');

const sectionTitles = {
  upload: 'CV Upload & Ingestion',
  candidates: 'Candidate Registry',
  extraction: 'Structured Extraction Output',
  analysis: 'Analysis Dashboard',
  summary: 'Candidate Summaries',
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
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      showToast('Only PDF files are supported.', 'error');
      return;
    }
    if (state.files.find(f => f.name === file.name)) return;
    state.files.push({ name: file.name, size: file.size, status: 'queued', raw: file });
  });
  renderFileList();
  updateStats();
}

function renderFileList() {
  if (!state.files.length) {
    fileItems.innerHTML = '<div class="empty-state">No files uploaded yet.</div>';
    processBtn.disabled = true;
    return;
  }
  fileItems.innerHTML = state.files.map((f, i) => `
    <div class="file-item">
      <div class="file-info">
        <span class="file-icon">PDF</span>
        <div>
          <div class="file-name">${f.name}</div>
          <div class="file-size">${formatSize(f.size)}</div>
        </div>
      </div>
      <span class="file-status ${f.status}">${f.status}</span>
    </div>
  `).join('');
  processBtn.disabled = !state.files.some(f => f.status === 'queued');
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

processBtn.addEventListener('click', async () => {
  const queued = state.files.filter(f => f.status === 'queued');
  if (!queued.length) return;

  processBtn.disabled = true;
  showToast('Processing CVs...', 'success');

  for (const file of queued) {
    setFileStatus(file.name, 'processing');
    try {
      const formData = new FormData();
      formData.append('cv', file.raw);
      const res = await fetch('/upload', { method: 'POST', body: formData });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || 'Processing failed');

      file.data = data.candidates || [];
      setFileStatus(file.name, 'done');
      await refreshDashboardData();
      showToast(`${file.name} processed successfully.`, 'success');
    } catch (err) {
      console.error(err);
      setFileStatus(file.name, 'error');
      showToast(`Error processing ${file.name}`, 'error');
    }
  }
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

async function refreshDashboardData() {
  const res = await fetch('/api/dashboard-data');
  const data = await res.json();
  state.candidates = Array.isArray(data.candidates) ? data.candidates : [];
  state.charts = data.charts || { education: [], research: [] };
  updateStats();
  renderCandidatesTable();
  populateCandidateSelects();
  renderExtractionTable();
  renderAnalysisTable();
  renderSummary();
  renderCharts();
}

function populateCandidateSelects() {
  const selects = [candidateSelect, analysisCandidateSelect, summaryCandidateSelect];
  selects.forEach(select => {
    const currentValue = select.value;
    select.innerHTML = '<option value="">Select a candidate</option>';
    state.candidates.forEach((candidate, index) => {
      const opt = document.createElement('option');
      opt.value = index;
      opt.textContent = candidate.name || `Candidate ${index + 1}`;
      select.appendChild(opt);
    });
    select.value = currentValue;
  });
}

function renderCandidatesTable() {
  if (!state.candidates.length) {
    candidatesBody.innerHTML = '<tr><td colspan="6" class="empty-row">No candidates yet. Upload and process CVs first.</td></tr>';
    return;
  }
  candidatesBody.innerHTML = state.candidates.map((c, i) => `
    <tr>
      <td>${i + 1}</td>
      <td>${c.name || '—'}</td>
      <td>${c.applied_for || '—'}</td>
      <td>${c.highest_degree || '—'}</td>
      <td>${c.university || '—'}</td>
      <td><span class="badge badge-green">${c.status || 'Processed'}</span></td>
    </tr>
  `).join('');
}

candidateSelect.addEventListener('change', renderExtractionTable);
tableSelect.addEventListener('change', renderExtractionTable);
analysisCandidateSelect.addEventListener('change', renderAnalysisTable);
summaryCandidateSelect.addEventListener('change', renderSummary);

function renderExtractionTable() {
  const idx = candidateSelect.value;
  const table = tableSelect.value;
  if (idx === '') {
    extractionWrap.innerHTML = '<div class="empty-state">Select a candidate to view extracted data.</div>';
    return;
  }
  const candidate = state.candidates[parseInt(idx, 10)];
  let data = candidate?.[table];
  if (table === 'skills' && Array.isArray(data)) data = data.map(skill => ({ skill }));
  if (!data || !data.length) {
    extractionWrap.innerHTML = `<div class="empty-state">No ${table} data found for this candidate.</div>`;
    return;
  }
  renderTable(extractionWrap, data);
}

function renderAnalysisTable() {
  const idx = analysisCandidateSelect.value;
  if (idx === '') {
    analysisWrap.innerHTML = '<div class="empty-state">Select a candidate to view education and professional analysis.</div>';
    return;
  }
  const candidate = state.candidates[parseInt(idx, 10)];
  const edu = candidate.education_analysis || {};
  const prof = candidate.professional_analysis || {};
  const missing = candidate.missing_detail || {};
  const research = candidate.research_analysis || {};

  const rows = [
    { metric: 'Education Score', value: edu.education_score ?? '—' },
    { metric: 'Education Strength', value: edu.education_strength ?? '—' },
    { metric: 'Highest Degree Rank', value: edu.highest_degree_rank ?? '—' },
    { metric: 'Average Normalized Marks', value: edu.avg_normalized_marks ?? '—' },
    { metric: 'Educational Gap', value: edu.education_gap_flag ?? '—' },
    { metric: 'Educational Gap Detail', value: edu.education_gap_detail ?? '—' },
    { metric: 'Gap Justified', value: edu.gap_justification_flag ?? '—' },
    { metric: 'Specialization Consistency', value: edu.specialization_consistency ?? '—' },
    { metric: 'Marks Trend', value: edu.marks_trend ?? '—' },
    { metric: 'Total Experience Years', value: prof.total_experience_years ?? '—' },
    { metric: 'Longest Tenure Years', value: prof.longest_tenure_years ?? '—' },
    { metric: 'Employment Gap', value: prof.professional_gap_flag ?? '—' },
    { metric: 'Employment Gap Detail', value: prof.professional_gap_detail ?? '—' },
    { metric: 'Overlap Detail', value: prof.overlap_detail ?? '—' },
    { metric: 'Career Progression', value: prof.career_progression ?? '—' },
    { metric: 'Missing Detail', value: missing.missing_info_items ?? '—' },
    { metric: 'Research Strength', value: research.research_strength ?? '—' },
    { metric: 'Total Publications', value: research.total_publications ?? '—' },
  ];
  renderTable(analysisWrap, rows);
}

function renderSummary() {
  const idx = summaryCandidateSelect.value;
  if (idx === '') {
    summaryWrap.innerHTML = '<div class="empty-state">Select a candidate to view summary.</div>';
    return;
  }
  const candidate = state.candidates[parseInt(idx, 10)];
  const summary = candidate.candidate_summary?.candidate_summary || 'No summary available.';
  const email = candidate.drafted_email?.draft_email || 'No drafted email available.';
  summaryWrap.innerHTML = `
    <div class="file-item">
      <div class="file-info" style="display:block">
        <div class="file-name">${candidate.name || 'Candidate'}</div>
        <div class="upload-sub" style="margin-top:10px; white-space:normal;">${summary}</div>
      </div>
    </div>
  `;
  emailWrap.innerHTML = `
    <div class="file-item">
      <div class="file-info" style="display:block">
        <div class="file-name">Drafted Email</div>
        <pre style="white-space:pre-wrap; margin:10px 0 0 0; font-family:inherit;">${email}</pre>
      </div>
    </div>
  `;
}

function renderCharts() {
  const educationCharts = (state.charts && state.charts.education) || [];
  const researchCharts = (state.charts && state.charts.research) || [];
  const allCharts = [...educationCharts, ...researchCharts];
  if (!allCharts.length) {
    chartGrid.innerHTML = '<div class="empty-state">No charts available yet. Process CVs first.</div>';
    return;
  }
  chartGrid.innerHTML = allCharts.map(url => `
    <div class="arch-card">
      <img src="${url}?t=${Date.now()}" alt="chart" style="width:100%; border-radius:10px;" />
    </div>
  `).join('');
}

function renderTable(container, rows) {
  const headers = Object.keys(rows[0]);
  container.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>${headers.map(h => `<th>${h.replace(/_/g, ' ')}</th>`).join('')}</tr>
      </thead>
      <tbody>
        ${rows.map(row => `<tr>${headers.map(h => `<td>${row[h] ?? '—'}</td>`).join('')}</tr>`).join('')}
      </tbody>
    </table>
  `;
}

document.getElementById('export-csv-btn').addEventListener('click', () => {
  window.location.href = '/export/csv';
  showToast('Downloading CSV...', 'success');
});

document.getElementById('export-excel-btn').addEventListener('click', () => {
  window.location.href = '/export/excel';
  showToast('Downloading Excel...', 'success');
});

let toastTimer;
function showToast(msg, type = '') {
  toast.textContent = msg;
  toast.className = 'toast show ' + type;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3000);
}

refreshDashboardData();
