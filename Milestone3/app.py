"""
TALASH Flask application.
"""

import csv
import io
import json
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file

from common import CV_DIR, DATA_DIR, EDUCATION_DIR, PREPROCESS_DIR, PROFESSIONAL_DIR, RESEARCH_DIR, UPLOAD_DIR, read_json, write_json, write_workbook
from education_analysis import process_preprocessed_json as run_education_analysis
from preprocess import build_preprocess_workbook_rows, run_pipeline as run_preprocess
from professional_analysis import process_preprocessed_json as run_professional_analysis
from research_paper import process_preprocessed_json as run_research_analysis

load_dotenv()

app = Flask(__name__)


RESEARCH_STRENGTH_SCORES = {
    "None": 0,
    "Emerging": 45,
    "Moderate": 72,
    "Strong": 92,
}


def get_preprocess_json_path() -> Path:
    return PREPROCESS_DIR / "TALASH_Candidates.json"


def get_preprocess_excel_path() -> Path:
    return PREPROCESS_DIR / "TALASH_Candidates.xlsx"


def load_json_if_exists(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def as_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_candidate_rankings(candidates):
    ranked = []
    for candidate in candidates:
        education_score = as_float(candidate.get("education_analysis", {}).get("education_score"))
        skill_score = as_float(candidate.get("skill_alignment_summary", {}).get("skill_alignment_score"))
        experience_years = as_float(candidate.get("professional_analysis", {}).get("total_experience_years"))
        total_publications = as_float(candidate.get("research_analysis", {}).get("total_publications"))
        research_strength = candidate.get("research_analysis", {}).get("research_strength", "None")
        missing_count = as_float(candidate.get("missing_detail", {}).get("missing_count"))

        experience_score = min(experience_years * 8, 100)
        publication_score = min(total_publications * 8, 100)
        research_score = RESEARCH_STRENGTH_SCORES.get(str(research_strength), 0)
        penalty = min(missing_count * 2, 15)

        composite_score = round(
            (education_score * 0.28)
            + (skill_score * 0.24)
            + (research_score * 0.20)
            + (publication_score * 0.16)
            + (experience_score * 0.12)
            - penalty,
            2,
        )
        composite_score = max(composite_score, 0.0)
        ranked.append(
            {
                **candidate,
                "composite_ranking": {
                    "score": composite_score,
                    "education_score": education_score,
                    "skill_alignment_score": skill_score,
                    "research_strength_score": research_score,
                    "publication_score": round(publication_score, 2),
                    "experience_score": round(experience_score, 2),
                    "missing_penalty": round(penalty, 2),
                    "weights": {
                        "education": 0.28,
                        "skills": 0.24,
                        "research_strength": 0.20,
                        "publications": 0.16,
                        "experience": 0.12,
                    },
                },
            }
        )

    ranked.sort(key=lambda item: item.get("composite_ranking", {}).get("score", 0), reverse=True)
    for index, candidate in enumerate(ranked, start=1):
        candidate["composite_ranking"]["rank"] = index
    return ranked


def load_preprocessed_candidates():
    json_path = get_preprocess_json_path()
    if not json_path.exists():
        return []
    data = read_json(json_path)
    return data if isinstance(data, list) else []


def merge_candidates(existing, new_items):
    merged = {}
    for item in existing:
        if isinstance(item, dict) and item.get("_source_file"):
            merged[item["_source_file"]] = item
    for item in new_items:
        if isinstance(item, dict) and item.get("_source_file"):
            merged[item["_source_file"]] = item
    return list(merged.values())


def get_highest_education(candidate):
    education = candidate.get("education", [])
    if not education:
        return {}
    rank_map = {
        "ssc": 1, "matric": 1, "hssc": 2, "fsc": 2, "intermediate": 2,
        "bachelor": 3, "bs": 3, "bsc": 3, "be": 3,
        "master": 4, "ms": 4, "msc": 4, "mba": 4,
        "mphil": 5, "phd": 6,
    }

    def rank(item):
        level = str(item.get("level", "") or "").lower()
        degree = str(item.get("degree", "") or "").lower()
        for key, value in rank_map.items():
            if key in level or key in degree:
                return value
        return 0

    return max(education, key=rank)


def flatten_candidate_for_ui(candidate, index):
    personal = candidate.get("personal", {})
    highest = get_highest_education(candidate)
    return {
        "id": index,
        "source_file": candidate.get("_source_file", ""),
        "name": personal.get("name", candidate.get("_source_file", "Unknown")),
        "applied_for": personal.get("applied_for", "-"),
        "present_employment": personal.get("present_employment", "-"),
        "nationality": personal.get("nationality", "-"),
        "highest_degree": highest.get("degree", "-") if isinstance(highest, dict) else "-",
        "highest_level": highest.get("level", "-") if isinstance(highest, dict) else "-",
        "university": highest.get("institution", "-") if isinstance(highest, dict) else "-",
        "status": "Processed",
        "personal": personal,
        "education": candidate.get("education", []),
        "experience": candidate.get("experience", []),
        "skills": candidate.get("skills", []),
        "publications": candidate.get("publications", []),
        "awards": candidate.get("awards", []),
        "supervision": candidate.get("supervision", []),
        "books": candidate.get("books", []),
        "patents": candidate.get("patents", []),
        "references": candidate.get("references", []),
        "missing_fields": candidate.get("missing_fields", []),
    }


def outputs_manifest():
    modules = {
        "preprocess": PREPROCESS_DIR,
        "education": EDUCATION_DIR,
        "professional": PROFESSIONAL_DIR,
        "research": RESEARCH_DIR,
    }
    manifest = {}
    for module, folder in modules.items():
        items = []
        for path in sorted(folder.iterdir(), key=lambda item: item.name.lower()):
            if path.is_file():
                items.append({"name": path.name, "url": f"/download/{module}/{path.name}"})
        manifest[module] = items
    return manifest


def build_chart_payload():
    chart_names = {
        "education": [
            "highest_degree_distribution.png",
            "education_score_distribution.png",
            "top10_normalized_marks.png",
            "education_gap_pie.png",
            "institution_quality_distribution.png",
            "marks_trend_distribution.png",
        ],
        "research": [
            "top_publications.png",
            "publication_type_distribution.png",
            "authorship_role_distribution.png",
            "yearly_publication_trend.png",
            "research_strength_distribution.png",
            "collaboration_network_size.png",
            "research_focus_distribution.png",
        ],
    }
    payload = {}
    for module, names in chart_names.items():
        payload[module] = [f"/download/{module}/{name}" for name in names if (globals()[f"{module.upper()}_DIR"] / name).exists()]
    return payload


def build_dashboard_payload():
    candidates = load_preprocessed_candidates()
    education_payload = load_json_if_exists(EDUCATION_DIR / "education_extracted.json", {"analysis": []})
    professional_payload = load_json_if_exists(
        PROFESSIONAL_DIR / "professional_analysis.json",
        {
            "professional_analysis": [],
            "missing_info_detailed": [],
            "candidate_summaries": [],
            "drafted_emails": [],
            "skill_alignment_summary": [],
            "skill_alignment_details": [],
        },
    )
    research_payload = load_json_if_exists(
        RESEARCH_DIR / "research_analysis.json",
        {
            "analysis": [],
            "publications": [],
            "authorship_roles": [],
            "collaboration_analysis": [],
            "topic_analysis": [],
            "supervision_records": [],
            "supervision_summary": [],
            "books_analysis": [],
            "books_summary": [],
            "patents_analysis": [],
            "patents_summary": [],
        },
    )

    edu_by_source = {row["source_file"]: row for row in education_payload.get("analysis", [])}
    prof_by_source = {row["source_file"]: row for row in professional_payload.get("professional_analysis", [])}
    missing_by_source = {row["source_file"]: row for row in professional_payload.get("missing_info_detailed", [])}
    email_by_source = {row["source_file"]: row for row in professional_payload.get("drafted_emails", [])}
    summary_by_source = {row["source_file"]: row for row in professional_payload.get("candidate_summaries", [])}
    skill_summary_by_source = {row["source_file"]: row for row in professional_payload.get("skill_alignment_summary", [])}
    skill_details_by_source = {}
    for row in professional_payload.get("skill_alignment_details", []):
        skill_details_by_source.setdefault(row["source_file"], []).append(row)
    research_by_source = {row["source_file"]: row for row in research_payload.get("analysis", [])}
    collaboration_by_source = {row["source_file"]: row for row in research_payload.get("collaboration_analysis", [])}
    topic_by_source = {row["source_file"]: row for row in research_payload.get("topic_analysis", [])}
    supervision_summary_by_source = {row["source_file"]: row for row in research_payload.get("supervision_summary", [])}
    books_summary_by_source = {row["source_file"]: row for row in research_payload.get("books_summary", [])}
    patents_summary_by_source = {row["source_file"]: row for row in research_payload.get("patents_summary", [])}

    merged = []
    for idx, candidate in enumerate(candidates, start=1):
        base = flatten_candidate_for_ui(candidate, idx)
        source = candidate.get("_source_file")
        base["education_analysis"] = edu_by_source.get(source, {})
        base["professional_analysis"] = prof_by_source.get(source, {})
        base["missing_detail"] = missing_by_source.get(source, {})
        base["drafted_email"] = email_by_source.get(source, {})
        base["candidate_summary"] = summary_by_source.get(source, {})
        base["skill_alignment_summary"] = skill_summary_by_source.get(source, {})
        base["skill_alignment_details"] = skill_details_by_source.get(source, [])
        base["research_analysis"] = research_by_source.get(source, {})
        base["collaboration_analysis"] = collaboration_by_source.get(source, {})
        base["topic_analysis"] = topic_by_source.get(source, {})
        base["supervision_summary"] = supervision_summary_by_source.get(source, {})
        base["books_summary"] = books_summary_by_source.get(source, {})
        base["patents_summary"] = patents_summary_by_source.get(source, {})
        merged.append(base)

    merged = compute_candidate_rankings(merged)
    research_papers = research_payload.get("publications", [])

    return {
        "candidates": merged,
        "research_papers": research_papers,
        "authorship_roles": research_payload.get("authorship_roles", []),
        "collaboration_analysis": research_payload.get("collaboration_analysis", []),
        "topic_analysis": research_payload.get("topic_analysis", []),
        "supervision_records": research_payload.get("supervision_records", []),
        "books_analysis": research_payload.get("books_analysis", []),
        "patents_analysis": research_payload.get("patents_analysis", []),
        "skill_alignment_details": professional_payload.get("skill_alignment_details", []),
        "charts": build_chart_payload(),
        "outputs": outputs_manifest(),
        "system_flags": {
            "groq_configured": professional_payload.get("meta", {}).get("groq_configured", False),
            "groq_model": professional_payload.get("meta", {}).get("groq_model", ""),
            "configured_venue_entries": len(load_json_if_exists(DATA_DIR / "venue_rankings.json", [])),
            "verified_publication_rows": sum(1 for row in research_papers if row.get("verification_mode") == "Configured"),
            "heuristic_publication_rows": sum(1 for row in research_papers if row.get("verification_mode") == "Heuristic"),
        },
    }


def save_combined_preprocess_outputs(candidates):
    json_path = write_json(candidates, PREPROCESS_DIR / "TALASH_Candidates.json")
    excel_path = write_workbook(build_preprocess_workbook_rows(candidates), PREPROCESS_DIR / "TALASH_Candidates.xlsx")
    return str(json_path), str(excel_path)


def build_master_export_sheets():
    candidates = load_preprocessed_candidates()
    preprocess_sheets = build_preprocess_workbook_rows(candidates) if candidates else {}
    dashboard = build_dashboard_payload()
    merged_candidates = dashboard.get("candidates", [])

    candidate_overview = []
    for row in merged_candidates:
        candidate_overview.append(
            {
                "candidate_name": row.get("name"),
                "source_file": row.get("source_file"),
                "applied_for": row.get("applied_for"),
                "present_employment": row.get("present_employment"),
                "nationality": row.get("nationality"),
                "highest_degree": row.get("highest_degree"),
                "university": row.get("university"),
                "education_score": row.get("education_analysis", {}).get("education_score"),
                "composite_rank": row.get("composite_ranking", {}).get("rank"),
                "composite_score": row.get("composite_ranking", {}).get("score"),
                "institution_quality": row.get("education_analysis", {}).get("institution_quality_label"),
                "experience_years": row.get("professional_analysis", {}).get("total_experience_years"),
                "career_progression": row.get("professional_analysis", {}).get("career_progression"),
                "skill_alignment_score": row.get("skill_alignment_summary", {}).get("skill_alignment_score"),
                "skill_alignment_label": row.get("skill_alignment_summary", {}).get("skill_alignment_label"),
                "research_strength": row.get("research_analysis", {}).get("research_strength"),
                "total_publications": row.get("research_analysis", {}).get("total_publications"),
                "dominant_topic": row.get("topic_analysis", {}).get("dominant_topic"),
                "topic_diversity_score": row.get("topic_analysis", {}).get("topic_diversity_score"),
                "unique_coauthors": row.get("collaboration_analysis", {}).get("unique_coauthors"),
                "missing_count": row.get("missing_detail", {}).get("missing_count"),
                "critical_missing": row.get("missing_detail", {}).get("critical_count"),
                "supervised_students": row.get("supervision_summary", {}).get("supervised_students_count"),
                "books_count": row.get("books_summary", {}).get("books_count"),
                "patent_count": row.get("patents_summary", {}).get("patent_count"),
            }
        )

    education_payload = load_json_if_exists(EDUCATION_DIR / "education_extracted.json", {"analysis": [], "candidates": []})
    professional_payload = load_json_if_exists(PROFESSIONAL_DIR / "professional_analysis.json", {})
    research_payload = load_json_if_exists(RESEARCH_DIR / "research_analysis.json", {})

    return {
        "Candidate Overview": candidate_overview,
        "Personal Info": preprocess_sheets.get("Personal Info", []),
        "Education Records": preprocess_sheets.get("Education", []),
        "Experience Records": preprocess_sheets.get("Experience", []),
        "Publications": preprocess_sheets.get("Publications", []),
        "Awards": preprocess_sheets.get("Awards", []),
        "Supervision Raw": preprocess_sheets.get("Supervision", []),
        "Books Raw": preprocess_sheets.get("Books", []),
        "Patents Raw": preprocess_sheets.get("Patents", []),
        "References": preprocess_sheets.get("References", []),
        "Skills Raw": preprocess_sheets.get("Skills", []),
        "Missing Raw": preprocess_sheets.get("Missing Info", []),
        "Education Analysis": education_payload.get("analysis", []),
        "Professional Analysis": professional_payload.get("professional_analysis", []),
        "Missing Details": professional_payload.get("missing_info_detailed", []),
        "Drafted Emails": professional_payload.get("drafted_emails", []),
        "Candidate Summaries": professional_payload.get("candidate_summaries", []),
        "Skill Summary": professional_payload.get("skill_alignment_summary", []),
        "Skill Detail": professional_payload.get("skill_alignment_details", []),
        "Research Analysis": research_payload.get("analysis", []),
        "Authorship Roles": research_payload.get("authorship_roles", []),
        "Collaboration": research_payload.get("collaboration_analysis", []),
        "Topic Analysis": research_payload.get("topic_analysis", []),
        "Supervision Analysis": research_payload.get("supervision_records", []),
        "Books Analysis": research_payload.get("books_analysis", []),
        "Patents Analysis": research_payload.get("patents_analysis", []),
    }


def run_all_modules(input_pdf_path: Path):
    latest_dir = PREPROCESS_DIR / "_latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    preprocess_result = run_preprocess(str(input_pdf_path), str(latest_dir), save_to_mongo=True)
    existing_candidates = load_preprocessed_candidates()
    combined_candidates = merge_candidates(existing_candidates, preprocess_result["candidates"])
    combined_json_path, combined_excel_path = save_combined_preprocess_outputs(combined_candidates)

    preprocess_json = combined_json_path
    education_result = run_education_analysis(preprocess_json, str(EDUCATION_DIR), save_to_mongo=True)
    professional_result = run_professional_analysis(preprocess_json, str(PROFESSIONAL_DIR), save_to_mongo=True)
    research_result = run_research_analysis(preprocess_json, str(RESEARCH_DIR), save_to_mongo=True)
    return {
        "preprocess": {**preprocess_result, "candidates": combined_candidates, "json_path": combined_json_path, "excel_path": combined_excel_path},
        "education": education_result,
        "professional": professional_result,
        "research": research_result,
    }


def run_all_modules_for_folder(input_folder: Path):
    preprocess_result = run_preprocess(str(input_folder), str(PREPROCESS_DIR / "_latest"), save_to_mongo=True)
    combined_candidates = merge_candidates(load_preprocessed_candidates(), preprocess_result["candidates"])
    combined_json_path, combined_excel_path = save_combined_preprocess_outputs(combined_candidates)
    education_result = run_education_analysis(combined_json_path, str(EDUCATION_DIR), save_to_mongo=True)
    professional_result = run_professional_analysis(combined_json_path, str(PROFESSIONAL_DIR), save_to_mongo=True)
    research_result = run_research_analysis(combined_json_path, str(RESEARCH_DIR), save_to_mongo=True)
    return {
        "preprocess": {**preprocess_result, "candidates": combined_candidates, "json_path": combined_json_path, "excel_path": combined_excel_path},
        "education": education_result,
        "professional": professional_result,
        "research": research_result,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_route():
    if "cv" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["cv"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    pdf_path = UPLOAD_DIR / Path(file.filename).name
    file.save(pdf_path)

    try:
        results = run_all_modules(pdf_path)
        dashboard = build_dashboard_payload()
    except PermissionError:
        return jsonify({"error": "Please close the output files and try again"}), 409
    except Exception as exc:
        return jsonify({"error": f"Processing failed: {exc}"}), 500

    latest_candidate = None
    if results.get("preprocess", {}).get("candidates"):
        latest_candidate = next(
            (
                row for row in results["preprocess"]["candidates"]
                if row.get("_source_file") == pdf_path.name
            ),
            results["preprocess"]["candidates"][-1],
        )
    warning = None
    if latest_candidate and latest_candidate.get("missing_fields"):
        if "LLM extraction failed" in latest_candidate.get("missing_fields", []):
            warning = "CV uploaded, but AI extraction failed for this file. The record was saved with fallback empty fields."
        elif "No text extracted" in latest_candidate.get("missing_fields", []):
            warning = "CV uploaded, but no readable text could be extracted from the PDF."

    return jsonify({"message": "Processing completed", "warning": warning, "dashboard": dashboard, "outputs": results})


@app.route("/api/dashboard-data")
def dashboard_data():
    return jsonify(build_dashboard_payload())


@app.route("/run/folder", methods=["POST"])
def run_folder_route():
    try:
        results = run_all_modules_for_folder(CV_DIR)
        dashboard = build_dashboard_payload()
    except Exception as exc:
        return jsonify({"error": f"Folder processing failed: {exc}"}), 500
    return jsonify({"message": f"Processed folder {CV_DIR.name}", "dashboard": dashboard, "outputs": results})


@app.route("/run/preprocess", methods=["POST"])
def run_preprocess_route():
    if "cv" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["cv"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    pdf_path = UPLOAD_DIR / Path(file.filename).name
    file.save(pdf_path)
    try:
        result = run_preprocess(str(pdf_path), str(PREPROCESS_DIR), save_to_mongo=True)
    except Exception as exc:
        return jsonify({"error": f"Preprocessing failed: {exc}"}), 500
    return jsonify({"message": "Preprocessing completed", "candidate_count": len(result["candidates"]), "excel_file": result["excel_path"], "json_file": result["json_path"]})


@app.route("/run/education", methods=["POST"])
def run_education_route():
    json_path = get_preprocess_json_path()
    if not json_path.exists():
        return jsonify({"error": "Run preprocessing first. TALASH_Candidates.json not found."}), 400
    try:
        result = run_education_analysis(str(json_path), str(EDUCATION_DIR), save_to_mongo=True)
    except Exception as exc:
        return jsonify({"error": f"Education analysis failed: {exc}"}), 500
    return jsonify({"message": "Education analysis completed", "excel_file": result["excel_path"], "json_file": result["json_path"]})


@app.route("/run/professional", methods=["POST"])
def run_professional_route():
    json_path = get_preprocess_json_path()
    if not json_path.exists():
        return jsonify({"error": "Run preprocessing first. TALASH_Candidates.json not found."}), 400
    try:
        result = run_professional_analysis(str(json_path), str(PROFESSIONAL_DIR), save_to_mongo=True)
    except Exception as exc:
        return jsonify({"error": f"Professional analysis failed: {exc}"}), 500
    return jsonify({
        "message": "Professional analysis completed",
        "excel_file": result["excel_path"],
        "json_file": result["json_path"],
        "summary_csv": result["summary_csv"],
        "summary_excel": result["summary_excel"],
        "missing_csv": result["missing_csv"],
        "email_csv": result["email_csv"],
        "skill_summary_csv": result["skill_summary_csv"],
        "skill_detail_csv": result["skill_detail_csv"],
    })


@app.route("/run/research", methods=["POST"])
def run_research_route():
    json_path = get_preprocess_json_path()
    if not json_path.exists():
        return jsonify({"error": "Run preprocessing first. TALASH_Candidates.json not found."}), 400
    try:
        result = run_research_analysis(str(json_path), str(RESEARCH_DIR), save_to_mongo=True)
    except Exception as exc:
        return jsonify({"error": f"Research analysis failed: {exc}"}), 500
    return jsonify({
        "message": "Research analysis completed",
        "excel_file": result["excel_path"],
        "json_file": result["json_path"],
        "dashboard_file": result["dashboard_path"],
        "chart_files": result["chart_files"],
    })


@app.route("/export/excel")
def export_excel():
    candidates = load_preprocessed_candidates()
    if not candidates:
        return jsonify({"error": "Run processing first. Excel file not found."}), 400
    export_path = write_workbook(build_master_export_sheets(), PREPROCESS_DIR / "TALASH_Master_Export.xlsx")
    return send_file(export_path, as_attachment=True, download_name=export_path.name)


@app.route("/export/csv")
def export_csv():
    rows = build_master_export_sheets().get("Candidate Overview", [])
    if not rows:
        return jsonify({"error": "Run processing first. No candidates found."}), 400
    stream = io.StringIO()
    writer = csv.writer(stream)
    headers = list(rows[0].keys())
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(header, "") for header in headers])
    bytes_io = io.BytesIO(stream.getvalue().encode("utf-8-sig"))
    bytes_io.seek(0)
    return send_file(bytes_io, mimetype="text/csv", as_attachment=True, download_name="TALASH_Master_Export.csv")


@app.route("/download/<module>/<path:filename>")
def download_module_file(module: str, filename: str):
    folders = {"preprocess": PREPROCESS_DIR, "education": EDUCATION_DIR, "professional": PROFESSIONAL_DIR, "research": RESEARCH_DIR}
    base = folders.get(module)
    if not base:
        return jsonify({"error": "Unknown module"}), 404
    target = base / filename
    if not target.exists():
        return jsonify({"error": "File not found"}), 404
    as_attachment = target.suffix.lower() != ".html"
    return send_file(target, as_attachment=as_attachment, download_name=target.name)


@app.route("/outputs")
def list_outputs():
    return jsonify(outputs_manifest())


if __name__ == "__main__":
    app.run(debug=True)
