const state = {
  files: [],
  candidates: [],
  researchPapers: [],
  authorshipRoles: [],
  collaborationAnalysis: [],
  topicAnalysis: [],
  supervisionRecords: [],
  booksAnalysis: [],
  patentsAnalysis: [],
  skillAlignmentDetails: [],
  charts: { education: [], research: [] },
  outputs: {},
  systemFlags: {},
};

const fileInput = document.getElementById("file-input");
const dropZone = document.getElementById("drop-zone");
const fileItems = document.getElementById("file-items");
const processBtn = document.getElementById("process-btn");
const processFolderBtn = document.getElementById("process-folder-btn");
const toast = document.getElementById("toast");

const cvCountEl = document.getElementById("cv-count");
const candidateCountEl = document.getElementById("candidate-count");
const paperCountEl = document.getElementById("paper-count");
const kpiGrid = document.getElementById("kpi-grid");
const chartGrid = document.getElementById("chart-grid");
const outputsGrid = document.getElementById("outputs-grid");

const candidatesBody = document.getElementById("candidates-body");
const candidateSearch = document.getElementById("candidate-search");
const progressionFilter = document.getElementById("progression-filter");
const researchFilter = document.getElementById("research-filter");

const candidateSelect = document.getElementById("candidate-select");
const analysisCandidateSelect = document.getElementById("analysis-candidate-select");
const summaryCandidateSelect = document.getElementById("summary-candidate-select");
const tableSelect = document.getElementById("table-select");
const extractionWrap = document.getElementById("extraction-wrap");
const analysisWrap = document.getElementById("analysis-wrap");
const analysisSidecard = document.getElementById("analysis-sidecard");
const summaryWrap = document.getElementById("summary-wrap");
const emailWrap = document.getElementById("email-wrap");

const papersBody = document.getElementById("papers-body");
const paperSearch = document.getElementById("paper-search");
const paperTypeFilter = document.getElementById("paper-type-filter");
const paperRoleFilter = document.getElementById("paper-role-filter");
const authorshipBody = document.getElementById("authorship-body");

const candidateModal = document.getElementById("candidate-modal");
const modalContent = document.getElementById("modal-content");
const modalClose = document.getElementById("modal-close");

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    const panel = button.dataset.panel;
    document.querySelectorAll(".panel").forEach((item) => item.classList.remove("active"));
    document.getElementById(`panel-${panel}`).classList.add("active");
  });
});

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("dragover");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("dragover");
  handleFiles(event.dataTransfer.files);
});
fileInput.addEventListener("change", () => handleFiles(fileInput.files));

function handleFiles(fileList) {
  Array.from(fileList).forEach((file) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showToast("Only PDF files are supported.", "error");
      return;
    }
    if (state.files.some((item) => item.name === file.name)) {
      return;
    }
    state.files.push({ name: file.name, size: file.size, status: "queued", raw: file });
  });
  renderQueue();
  updateTopStats();
}

function renderQueue() {
  if (!state.files.length) {
    fileItems.innerHTML = '<div class="empty-state">No files uploaded yet.</div>';
    processBtn.disabled = true;
    return;
  }
  fileItems.innerHTML = state.files.map((file) => `
    <div class="queue-item">
      <div>
        <div class="queue-name">${escapeHtml(file.name)}</div>
        <div class="queue-meta">${formatSize(file.size)}</div>
      </div>
      <span class="status-pill ${file.status}">${file.status}</span>
    </div>
  `).join("");
  processBtn.disabled = !state.files.some((file) => file.status === "queued");
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function updateTopStats() {
  cvCountEl.textContent = state.files.length;
  candidateCountEl.textContent = state.candidates.length;
  paperCountEl.textContent = state.researchPapers.length;
}

processBtn.addEventListener("click", async () => {
  const queued = state.files.filter((file) => file.status === "queued");
  if (!queued.length) return;
  processBtn.disabled = true;
  showToast("Processing queued CVs...", "success");

  for (const file of queued) {
    setFileStatus(file.name, "processing");
    try {
      const formData = new FormData();
      formData.append("cv", file.raw);
      const response = await fetch("/upload", { method: "POST", body: formData });
      const payload = await response.json();
      if (!response.ok || payload.error) {
        throw new Error(payload.error || "Processing failed");
      }
      setFileStatus(file.name, "done");
      await refreshDashboardData();
      if (payload.warning) {
        showToast(payload.warning, "error");
      } else {
        showToast(`${file.name} processed successfully.`, "success");
      }
    } catch (error) {
      console.error(error);
      setFileStatus(file.name, "error");
      showToast(error.message ? `Error processing ${file.name}: ${error.message}` : `Error processing ${file.name}`, "error");
    }
  }
});

function setFileStatus(name, status) {
  const record = state.files.find((file) => file.name === name);
  if (record) record.status = status;
  renderQueue();
}

async function refreshDashboardData() {
  const response = await fetch("/api/dashboard-data");
  const payload = await response.json();
  state.candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
  state.researchPapers = Array.isArray(payload.research_papers) ? payload.research_papers : [];
  state.authorshipRoles = Array.isArray(payload.authorship_roles) ? payload.authorship_roles : [];
  state.collaborationAnalysis = Array.isArray(payload.collaboration_analysis) ? payload.collaboration_analysis : [];
  state.topicAnalysis = Array.isArray(payload.topic_analysis) ? payload.topic_analysis : [];
  state.supervisionRecords = Array.isArray(payload.supervision_records) ? payload.supervision_records : [];
  state.booksAnalysis = Array.isArray(payload.books_analysis) ? payload.books_analysis : [];
  state.patentsAnalysis = Array.isArray(payload.patents_analysis) ? payload.patents_analysis : [];
  state.skillAlignmentDetails = Array.isArray(payload.skill_alignment_details) ? payload.skill_alignment_details : [];
  state.charts = payload.charts || { education: [], research: [] };
  state.outputs = payload.outputs || {};
  state.systemFlags = payload.system_flags || {};
  updateTopStats();
  populateCandidateSelects();
  renderOverview();
  renderCandidatesTable();
  renderExtractionTable();
  renderAnalysisTable();
  renderSummary();
  renderResearchTable();
  renderAuthorshipTable();
}

function populateCandidateSelects() {
  const selects = [candidateSelect, analysisCandidateSelect, summaryCandidateSelect];
  selects.forEach((select) => {
    const previous = select.value;
    select.innerHTML = '<option value="">Select a candidate</option>';
    state.candidates.forEach((candidate, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = candidate.name || `Candidate ${index + 1}`;
      select.appendChild(option);
    });
    select.value = previous;
  });
}

function renderOverview() {
  const candidateCount = state.candidates.length;
  const missingCandidates = state.candidates.filter((candidate) => (candidate.missing_detail?.missing_count || 0) > 0).length;
  const activeResearchers = state.candidates.filter((candidate) => (candidate.research_analysis?.research_active || "No") === "Yes").length;
  const totalPublications = state.researchPapers.length;
  const verifiedVenueCount = state.researchPapers.filter((paper) => (paper.verification_mode || "") === "Configured").length;
  const topComposite = state.candidates.length ? state.candidates[0].composite_ranking?.score ?? "-" : "-";
  const groqStatus = state.systemFlags?.groq_configured ? "Ready" : "Missing";

  const kpis = [
    { label: "Candidates processed", value: candidateCount },
    { label: "Research-active candidates", value: activeResearchers },
    { label: "Candidates with missing items", value: missingCandidates },
    { label: "Publication records", value: totalPublications },
    { label: "Configured venue verifications", value: verifiedVenueCount },
    { label: "Top composite score", value: topComposite },
    { label: "Groq summaries", value: groqStatus },
  ];

  kpiGrid.innerHTML = kpis.map((kpi) => `
    <div class="kpi-card">
      <div class="kpi-value">${escapeHtml(String(kpi.value))}</div>
      <span class="kpi-label">${escapeHtml(kpi.label)}</span>
    </div>
  `).join("");

  const chartUrls = [...(state.charts.education || []), ...(state.charts.research || [])];
  chartGrid.innerHTML = chartUrls.length
    ? chartUrls.map((url) => `<div class="chart-card"><img src="${url}?t=${Date.now()}" alt="chart" /></div>`).join("")
    : '<div class="empty-state">No charts available yet. Process CVs first.</div>';

  outputsGrid.innerHTML = Object.entries(state.outputs).map(([module, files]) => `
    <div class="output-module">
      <h4>${escapeHtml(module)}</h4>
      <div class="output-list">
        ${(files || []).length ? files.map((file) => `<a href="${file.url}" target="_blank">${escapeHtml(file.name)}</a>`).join("") : '<span class="empty-state">No files yet.</span>'}
      </div>
    </div>
  `).join("");
}

function filteredCandidates() {
  const search = candidateSearch.value.trim().toLowerCase();
  const progression = progressionFilter.value;
  const research = researchFilter.value;
  return state.candidates.filter((candidate) => {
    const haystack = [
      candidate.name,
      candidate.applied_for,
      candidate.highest_degree,
      candidate.university,
    ].join(" ").toLowerCase();
    const progressionMatch = !progression || (candidate.professional_analysis?.career_progression || "") === progression;
    const researchMatch = !research || (candidate.research_analysis?.research_active || "No") === research;
    const searchMatch = !search || haystack.includes(search);
    return progressionMatch && researchMatch && searchMatch;
  });
}

function renderCandidatesTable() {
  const rows = filteredCandidates();
  if (!rows.length) {
    candidatesBody.innerHTML = '<tr><td colspan="10" class="empty-row">No candidates match the current filters.</td></tr>';
    return;
  }
  candidatesBody.innerHTML = rows.map((candidate) => `
    <tr>
      <td>#${escapeHtml(String(candidate.composite_ranking?.rank ?? "-"))}</td>
      <td>${escapeHtml(candidate.name || "-")}</td>
      <td>${escapeHtml(candidate.applied_for || "-")}</td>
      <td>${escapeHtml(candidate.highest_degree || "-")}</td>
      <td>${escapeHtml(String(candidate.composite_ranking?.score ?? "-"))}</td>
      <td>${escapeHtml(String(candidate.professional_analysis?.total_experience_years ?? "-"))}</td>
      <td>${escapeHtml(candidate.professional_analysis?.career_progression || "-")}</td>
      <td>${escapeHtml(String(candidate.research_analysis?.total_publications ?? 0))}</td>
      <td>${escapeHtml(String(candidate.missing_detail?.missing_count ?? 0))}</td>
      <td><button class="table-action" data-source="${escapeHtml(candidate.source_file)}">Details</button></td>
    </tr>
  `).join("");
  candidatesBody.querySelectorAll(".table-action").forEach((button) => {
    button.addEventListener("click", () => openCandidateModal(button.dataset.source));
  });
}

function renderExtractionTable() {
  const index = candidateSelect.value;
  const tableName = tableSelect.value;
  if (index === "") {
    extractionWrap.innerHTML = '<div class="empty-state">Select a candidate to inspect extracted data.</div>';
    return;
  }
  const candidate = state.candidates[Number(index)];
  let rows = candidate?.[tableName];
  if (tableName === "skills" && Array.isArray(rows)) {
    rows = rows.map((skill) => ({ skill }));
  }
  if (!rows || !rows.length) {
    extractionWrap.innerHTML = `<div class="empty-state">No ${escapeHtml(tableName)} data found for this candidate.</div>`;
    return;
  }
  renderGenericTable(extractionWrap, rows);
}

function renderAnalysisTable() {
  const index = analysisCandidateSelect.value;
  if (index === "") {
    analysisWrap.innerHTML = '<div class="empty-state">Select a candidate to view analytics.</div>';
    analysisSidecard.innerHTML = '<div class="empty-state">Candidate-specific flags and notes appear here.</div>';
    return;
  }
  const candidate = state.candidates[Number(index)];
  const education = candidate.education_analysis || {};
  const professional = candidate.professional_analysis || {};
  const missing = candidate.missing_detail || {};
  const research = candidate.research_analysis || {};
  const rows = [
    { metric: "Composite rank", value: candidate.composite_ranking?.rank ?? "-" },
    { metric: "Composite score", value: candidate.composite_ranking?.score ?? "-" },
    { metric: "Education score", value: education.education_score ?? "-" },
    { metric: "Education strength", value: education.education_strength ?? "-" },
    { metric: "Highest degree rank", value: education.highest_degree_rank ?? "-" },
    { metric: "Average normalized marks", value: education.avg_normalized_marks ?? "-" },
    { metric: "Institution quality", value: education.institution_quality_label ?? "-" },
    { metric: "Institution quality score", value: education.avg_institution_quality_score ?? "-" },
    { metric: "Educational gap flag", value: education.education_gap_flag ?? "-" },
    { metric: "Educational gap detail", value: education.education_gap_detail ?? "-" },
    { metric: "Gap justified", value: education.gap_justification_flag ?? "-" },
    { metric: "Specialization consistency", value: education.specialization_consistency ?? "-" },
    { metric: "Marks trend", value: education.marks_trend ?? "-" },
    { metric: "Total roles", value: professional.total_roles ?? "-" },
    { metric: "Experience years", value: professional.total_experience_years ?? "-" },
    { metric: "Career progression", value: professional.career_progression ?? "-" },
    { metric: "Gap count", value: professional.gap_count ?? "-" },
    { metric: "Professional gap detail", value: professional.professional_gap_detail ?? "-" },
    { metric: "Job overlaps", value: professional.job_overlaps ?? "-" },
    { metric: "Education-job overlaps", value: professional.edu_job_overlaps ?? "-" },
    { metric: "Timeline consistent", value: professional.timeline_consistent ?? "-" },
    { metric: "Research strength", value: research.research_strength ?? "-" },
    { metric: "Total publications", value: research.total_publications ?? 0 },
    { metric: "Dominant topic", value: candidate.topic_analysis?.dominant_topic ?? research.dominant_topic ?? "-" },
    { metric: "Topic diversity score", value: candidate.topic_analysis?.topic_diversity_score ?? research.topic_diversity_score ?? "-" },
    { metric: "Average co-authors per paper", value: research.average_coauthors_per_paper ?? "-" },
    { metric: "Skill alignment score", value: candidate.skill_alignment_summary?.skill_alignment_score ?? "-" },
    { metric: "Skill alignment label", value: candidate.skill_alignment_summary?.skill_alignment_label ?? "-" },
    { metric: "Missing items", value: missing.missing_count ?? 0 },
  ];
  renderGenericTable(analysisWrap, rows);

  analysisSidecard.innerHTML = `
    <h3>${escapeHtml(candidate.name || "Candidate")}</h3>
    <div class="insight-list">
      <div class="insight-row"><strong>Longest tenure:</strong><br>${escapeHtml(professional.longest_tenure_role || "-")} (${escapeHtml(String(professional.longest_tenure_years ?? "-"))} yrs)</div>
      <div class="insight-row"><strong>Composite ranking:</strong><br>Rank #${escapeHtml(String(candidate.composite_ranking?.rank ?? "-"))} | Score ${escapeHtml(String(candidate.composite_ranking?.score ?? "-"))}</div>
      <div class="insight-row"><strong>Notes:</strong><br>${escapeHtml(professional.notes || "-")}</div>
      <div class="insight-row"><strong>Missing fields:</strong><br>${escapeHtml(missing.missing_fields || "None")}</div>
      <div class="insight-row"><strong>Severity counts:</strong><br>Critical ${escapeHtml(String(missing.critical_count ?? 0))} | High ${escapeHtml(String(missing.high_count ?? 0))} | Medium ${escapeHtml(String(missing.medium_count ?? 0))} | Low ${escapeHtml(String(missing.low_count ?? 0))}</div>
      <div class="insight-row"><strong>Skill alignment:</strong><br>${escapeHtml(candidate.skill_alignment_summary?.skill_alignment_label || "-")} (${escapeHtml(String(candidate.skill_alignment_summary?.skill_alignment_score ?? "-"))})</div>
      <div class="insight-row"><strong>Collaboration:</strong><br>Unique co-authors ${escapeHtml(String(candidate.collaboration_analysis?.unique_coauthors ?? 0))} | Recurring ratio ${escapeHtml(String(candidate.collaboration_analysis?.recurring_collaboration_ratio ?? 0))}%</div>
      <div class="insight-row"><strong>Research assets:</strong><br>Supervision ${escapeHtml(String(candidate.supervision_summary?.supervised_students_count ?? 0))} | Books ${escapeHtml(String(candidate.books_summary?.books_count ?? 0))} | Patents ${escapeHtml(String(candidate.patents_summary?.patent_count ?? 0))}</div>
    </div>
  `;
}

function filteredResearchPapers() {
  const search = paperSearch.value.trim().toLowerCase();
  const type = paperTypeFilter.value;
  const role = paperRoleFilter.value;
  return state.researchPapers.filter((paper) => {
    const haystack = [paper.candidate_name, paper.title, paper.venue].join(" ").toLowerCase();
    const searchMatch = !search || haystack.includes(search);
    const typeMatch = !type || (paper.venue_type || "") === type;
    const roleMatch = !role || (paper.authorship_role || "") === role;
    return searchMatch && typeMatch && roleMatch;
  });
}

function renderResearchTable() {
  const rows = filteredResearchPapers();
  if (!rows.length) {
    papersBody.innerHTML = '<tr><td colspan="6" class="empty-row">No research papers match the current filters.</td></tr>';
    return;
  }
  papersBody.innerHTML = rows.map((paper) => `
    <tr>
      <td>${escapeHtml(paper.candidate_name || "-")}</td>
      <td>${escapeHtml(paper.title || "-")}</td>
      <td>${escapeHtml(paper.venue || "-")}</td>
      <td>${escapeHtml((paper.quartile && paper.quartile !== "Unknown") ? paper.quartile : (paper.venue_type || "-"))}<br><span class="queue-meta">${escapeHtml(paper.verification_mode || "-")}</span></td>
      <td>${escapeHtml(paper.authorship_role || "-")}</td>
      <td>${escapeHtml(String(paper.year || "-"))}<br><span class="queue-meta">${escapeHtml(paper.verification_source || paper.topic_tags || "-")}</span></td>
    </tr>
  `).join("");
}

function renderAuthorshipTable() {
  if (!state.authorshipRoles.length) {
    authorshipBody.innerHTML = '<tr><td colspan="5" class="empty-row">No authorship records available yet.</td></tr>';
    return;
  }
  authorshipBody.innerHTML = state.authorshipRoles.map((row) => `
    <tr>
      <td>${escapeHtml(row.candidate_name || "-")}</td>
      <td>${escapeHtml(row.title || "-")}</td>
      <td>${escapeHtml(row.authorship_role || "-")}</td>
      <td>${escapeHtml(String(row.author_position ?? "-"))}</td>
      <td>${escapeHtml(String(row.co_author_count ?? 0))}<br><span class="queue-meta">Quality ${escapeHtml(String(row.venue_quality_score ?? "-"))}</span></td>
    </tr>
  `).join("");
}

function renderSummary() {
  const index = summaryCandidateSelect.value;
  if (index === "") {
    summaryWrap.innerHTML = '<div class="empty-state">Select a candidate to view summary.</div>';
    emailWrap.innerHTML = '<div class="empty-state">Select a candidate to view drafted email.</div>';
    return;
  }
  const candidate = state.candidates[Number(index)];
  const summary = candidate.candidate_summary?.candidate_summary || "No summary available.";
  const email = candidate.drafted_email?.draft_email || "No drafted email available.";
  summaryWrap.innerHTML = `
    <h3>${escapeHtml(candidate.name || "Candidate")} Summary</h3>
    <div class="insight-row"><strong>Summary mode:</strong> ${escapeHtml(candidate.candidate_summary?.generation_mode || "Template")}</div>
    <div class="summary-copy">${escapeHtml(summary)}</div>
    <div class="insight-list" style="margin-top:16px;">
      <div class="insight-row"><strong>Skill alignment</strong><br>${escapeHtml(candidate.skill_alignment_summary?.skill_alignment_label || "-")} (${escapeHtml(String(candidate.skill_alignment_summary?.skill_alignment_score ?? "-"))})</div>
      <div class="insight-row"><strong>Top collaborators</strong><br>${escapeHtml(candidate.collaboration_analysis?.top_collaborators || "None")}</div>
      <div class="insight-row"><strong>Topic distribution</strong><br>${escapeHtml(candidate.topic_analysis?.topic_distribution || "None")}</div>
    </div>
  `;
  emailWrap.innerHTML = `
    <h3>Drafted Follow-up Email</h3>
    <div class="insight-row"><strong>Email mode:</strong> ${escapeHtml(candidate.drafted_email?.generation_mode || "Template")}</div>
    <div class="email-copy">${escapeHtml(email)}</div>
  `;
}

function renderGenericTable(container, rows) {
  const headers = Object.keys(rows[0]);
  container.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>${headers.map((header) => `<th>${escapeHtml(header.replaceAll("_", " "))}</th>`).join("")}</tr>
      </thead>
      <tbody>
        ${rows.map((row) => `<tr>${headers.map((header) => `<td>${escapeHtml(String(row[header] ?? "-"))}</td>`).join("")}</tr>`).join("")}
      </tbody>
    </table>
  `;
}

function openCandidateModal(sourceFile) {
  const candidate = state.candidates.find((item) => item.source_file === sourceFile);
  if (!candidate) return;
  modalContent.innerHTML = `
    <h2>${escapeHtml(candidate.name || "Candidate")}</h2>
    <p class="hero-copy">${escapeHtml(candidate.applied_for || "-")}</p>
    <div class="detail-grid">
      <div class="detail-box"><div class="detail-label">Highest degree</div><div class="detail-value">${escapeHtml(candidate.highest_degree || "-")}</div></div>
      <div class="detail-box"><div class="detail-label">Composite rank</div><div class="detail-value">#${escapeHtml(String(candidate.composite_ranking?.rank ?? "-"))}</div></div>
      <div class="detail-box"><div class="detail-label">Composite score</div><div class="detail-value">${escapeHtml(String(candidate.composite_ranking?.score ?? "-"))}</div></div>
      <div class="detail-box"><div class="detail-label">University</div><div class="detail-value">${escapeHtml(candidate.university || "-")}</div></div>
      <div class="detail-box"><div class="detail-label">Experience years</div><div class="detail-value">${escapeHtml(String(candidate.professional_analysis?.total_experience_years ?? "-"))}</div></div>
      <div class="detail-box"><div class="detail-label">Career progression</div><div class="detail-value">${escapeHtml(candidate.professional_analysis?.career_progression || "-")}</div></div>
      <div class="detail-box"><div class="detail-label">Research papers</div><div class="detail-value">${escapeHtml(String(candidate.research_analysis?.total_publications ?? 0))}</div></div>
      <div class="detail-box"><div class="detail-label">Missing items</div><div class="detail-value">${escapeHtml(String(candidate.missing_detail?.missing_count ?? 0))}</div></div>
      <div class="detail-box"><div class="detail-label">Supervision records</div><div class="detail-value">${escapeHtml(String(candidate.supervision?.length ?? 0))}</div></div>
      <div class="detail-box"><div class="detail-label">Books</div><div class="detail-value">${escapeHtml(String(candidate.books?.length ?? 0))}</div></div>
      <div class="detail-box"><div class="detail-label">Patents</div><div class="detail-value">${escapeHtml(String(candidate.patents?.length ?? 0))}</div></div>
      <div class="detail-box"><div class="detail-label">Skill alignment</div><div class="detail-value">${escapeHtml(candidate.skill_alignment_summary?.skill_alignment_label || "-")} (${escapeHtml(String(candidate.skill_alignment_summary?.skill_alignment_score ?? "-"))})</div></div>
      <div class="detail-box"><div class="detail-label">Dominant topic</div><div class="detail-value">${escapeHtml(candidate.topic_analysis?.dominant_topic || "-")}</div></div>
    </div>
    <div class="summary-card">
      <h3>Committee Summary</h3>
      <div class="summary-copy">${escapeHtml(candidate.candidate_summary?.candidate_summary || "No summary available.")}</div>
    </div>
    <div class="summary-card" style="margin-top:16px;">
      <h3>Skill Evidence</h3>
      <div class="summary-copy">${escapeHtml((candidate.skill_alignment_details || []).map((row) => `${row.claimed_skill}: ${row.evidence_strength}`).join(" | ") || "No skill evidence available.")}</div>
    </div>
  `;
  candidateModal.classList.add("open");
}

modalClose.addEventListener("click", () => candidateModal.classList.remove("open"));
candidateModal.addEventListener("click", (event) => {
  if (event.target === candidateModal) {
    candidateModal.classList.remove("open");
  }
});

candidateSearch.addEventListener("input", renderCandidatesTable);
progressionFilter.addEventListener("change", renderCandidatesTable);
researchFilter.addEventListener("change", renderCandidatesTable);
candidateSelect.addEventListener("change", renderExtractionTable);
tableSelect.addEventListener("change", renderExtractionTable);
analysisCandidateSelect.addEventListener("change", renderAnalysisTable);
summaryCandidateSelect.addEventListener("change", renderSummary);
paperSearch.addEventListener("input", renderResearchTable);
paperTypeFilter.addEventListener("change", renderResearchTable);
paperRoleFilter.addEventListener("change", renderResearchTable);

document.getElementById("export-csv-btn").addEventListener("click", () => {
  window.location.href = "/export/csv";
  showToast("Downloading CSV...", "success");
});

document.getElementById("export-excel-btn").addEventListener("click", () => {
  window.location.href = "/export/excel";
  showToast("Downloading Excel...", "success");
});

processFolderBtn.addEventListener("click", async () => {
  processFolderBtn.disabled = true;
  showToast("Processing cv_folder...", "success");
  try {
    const response = await fetch("/run/folder", { method: "POST" });
    const payload = await response.json();
    if (!response.ok || payload.error) {
      throw new Error(payload.error || "Folder processing failed");
    }
    await refreshDashboardData();
    showToast("cv_folder processed successfully.", "success");
  } catch (error) {
    console.error(error);
    showToast("Error processing cv_folder.", "error");
  } finally {
    processFolderBtn.disabled = false;
  }
});

let toastTimer;
function showToast(message, type = "") {
  toast.textContent = message;
  toast.className = `toast show ${type}`.trim();
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.classList.remove("show");
  }, 3200);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

refreshDashboardData().catch((error) => {
  console.error(error);
  showToast("Failed to load dashboard data.", "error");
});
