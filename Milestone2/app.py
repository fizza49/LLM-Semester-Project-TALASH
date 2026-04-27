"""
TALASH - CS417 Milestone 1
Flask backend for preprocessing + education + professional + research pipeline
"""

import csv
import io
import json
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file

from common import EDUCATION_DIR, PREPROCESS_DIR, PROFESSIONAL_DIR, RESEARCH_DIR, UPLOAD_DIR, read_json, write_json, write_workbook
from education_analysis import process_preprocessed_json as run_education_analysis
from preprocess import build_preprocess_workbook_rows, run_pipeline as run_preprocess
from professional_analysis import process_preprocessed_json as run_professional_analysis
from research_paper import process_preprocessed_json as run_research_analysis

load_dotenv()

app = Flask(__name__)


def get_preprocess_json_path() -> Path:
    return PREPROCESS_DIR / "TALASH_Candidates.json"


def get_preprocess_excel_path() -> Path:
    return PREPROCESS_DIR / "TALASH_Candidates.xlsx"


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


def load_json_if_exists(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


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
        "name": personal.get("name", candidate.get("_source_file", "Unknown")),
        "applied_for": personal.get("applied_for", "—"),
        "highest_degree": highest.get("degree", "—") if isinstance(highest, dict) else "—",
        "university": highest.get("institution", "—") if isinstance(highest, dict) else "—",
        "status": "Processed",
        "education": candidate.get("education", []),
        "experience": candidate.get("experience", []),
        "skills": candidate.get("skills", []),
        "publications": candidate.get("publications", []),
        "awards": candidate.get("awards", []),
        "references": candidate.get("references", []),
        "missing_fields": candidate.get("missing_fields", []),
    }


def build_dashboard_payload():
    candidates = load_preprocessed_candidates()
    education_payload = load_json_if_exists(EDUCATION_DIR / "education_extracted.json", {"analysis": []})
    professional_payload = load_json_if_exists(PROFESSIONAL_DIR / "professional_analysis.json", {"professional_analysis": [], "missing_info_detailed": [], "candidate_summaries": [], "drafted_emails": []})
    research_payload = load_json_if_exists(RESEARCH_DIR / "research_analysis.json", {"analysis": []})

    edu_by_source = {row["source_file"]: row for row in education_payload.get("analysis", [])}
    prof_by_source = {row["source_file"]: row for row in professional_payload.get("professional_analysis", [])}
    missing_by_source = {row["source_file"]: row for row in professional_payload.get("missing_info_detailed", [])}
    email_by_source = {row["source_file"]: row for row in professional_payload.get("drafted_emails", [])}
    summary_by_source = {row["source_file"]: row for row in professional_payload.get("candidate_summaries", [])}
    research_by_source = {row["source_file"]: row for row in research_payload.get("analysis", [])}

    merged = []
    for idx, candidate in enumerate(candidates, start=1):
        base = flatten_candidate_for_ui(candidate, idx)
        source = candidate.get("_source_file")
        base["education_analysis"] = edu_by_source.get(source, {})
        base["professional_analysis"] = prof_by_source.get(source, {})
        base["missing_detail"] = missing_by_source.get(source, {})
        base["drafted_email"] = email_by_source.get(source, {})
        base["candidate_summary"] = summary_by_source.get(source, {})
        base["research_analysis"] = research_by_source.get(source, {})
        merged.append(base)
    return merged


def build_chart_payload():
    return {
        "education": [
            f"/download/education/{name}"
            for name in [
                "highest_degree_distribution.png",
                "education_score_distribution.png",
                "top10_normalized_marks.png",
                "education_gap_pie.png",
            ]
            if (EDUCATION_DIR / name).exists()
        ],
        "research": [
            f"/download/research/{name}"
            for name in [
                "top_publications.png",
                "research_strength_distribution.png",
                "publications_vs_impact.png",
                "publication_type_distribution.png",
            ]
            if (RESEARCH_DIR / name).exists()
        ],
    }


def save_combined_preprocess_outputs(candidates):
    json_path = write_json(candidates, PREPROCESS_DIR / "TALASH_Candidates.json")
    excel_path = write_workbook(build_preprocess_workbook_rows(candidates), PREPROCESS_DIR / "TALASH_Candidates.xlsx")
    return str(json_path), str(excel_path)


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
        "preprocess": {
            **preprocess_result,
            "candidates": combined_candidates,
            "json_path": combined_json_path,
            "excel_path": combined_excel_path,
        },
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
        candidates = load_preprocessed_candidates()
    except PermissionError:
        return jsonify({"error": "Please close the output files and try again"}), 409
    except Exception as exc:
        return jsonify({"error": f"Processing failed: {exc}"}), 500

    ui_candidates = [flatten_candidate_for_ui(candidate, idx) for idx, candidate in enumerate(candidates, start=1)]
    return jsonify(
        {
            "message": "Processing completed",
            "candidate_count": len(ui_candidates),
            "candidates": ui_candidates,
            "outputs": {
                "preprocess_excel": results["preprocess"]["excel_path"],
                "preprocess_json": results["preprocess"]["json_path"],
                "education_excel": results["education"]["excel_path"],
                "professional_excel": results["professional"]["excel_path"],
                "research_excel": results["research"]["excel_path"],
                "research_dashboard": results["research"]["dashboard_path"],
            },
        }
    )


@app.route("/api/dashboard-data")
def dashboard_data():
    return jsonify({"candidates": build_dashboard_payload(), "charts": build_chart_payload()})


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

    return jsonify(
        {
            "message": "Preprocessing completed",
            "candidate_count": len(result["candidates"]),
            "excel_file": result["excel_path"],
            "json_file": result["json_path"],
        }
    )


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
    excel_path = get_preprocess_excel_path()
    if not excel_path.exists():
        return jsonify({"error": "Run processing first. Excel file not found."}), 400
    return send_file(excel_path, as_attachment=True, download_name=excel_path.name)


@app.route("/export/csv")
def export_csv():
    candidates = load_preprocessed_candidates()
    if not candidates:
        return jsonify({"error": "Run processing first. No candidates found."}), 400
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["name", "applied_for", "highest_degree", "university", "source_file"])
    for candidate in candidates:
        personal = candidate.get("personal", {})
        highest = get_highest_education(candidate)
        writer.writerow([
            personal.get("name", ""),
            personal.get("applied_for", ""),
            highest.get("degree", "") if isinstance(highest, dict) else "",
            highest.get("institution", "") if isinstance(highest, dict) else "",
            candidate.get("_source_file", ""),
        ])
    bytes_io = io.BytesIO(stream.getvalue().encode("utf-8-sig"))
    bytes_io.seek(0)
    return send_file(bytes_io, mimetype="text/csv", as_attachment=True, download_name="TALASH_Candidates.csv")


@app.route("/download/<module>/<path:filename>")
def download_module_file(module: str, filename: str):
    folders = {
        "preprocess": PREPROCESS_DIR,
        "education": EDUCATION_DIR,
        "professional": PROFESSIONAL_DIR,
        "research": RESEARCH_DIR,
    }
    base = folders.get(module)
    if not base:
        return jsonify({"error": "Unknown module"}), 404
    target = base / filename
    if not target.exists():
        return jsonify({"error": "File not found"}), 404
    return send_file(target, as_attachment=True, download_name=target.name)


@app.route("/outputs")
def list_outputs():
    response = {}
    for name, folder in {
        "preprocess": PREPROCESS_DIR,
        "education": EDUCATION_DIR,
        "professional": PROFESSIONAL_DIR,
        "research": RESEARCH_DIR,
    }.items():
        response[name] = sorted(item.name for item in folder.iterdir() if item.is_file())
    return jsonify(response)


if __name__ == "__main__":
    app.run(debug=True)
