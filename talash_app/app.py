"""
TALASH - CS417 Milestone 1
Flask backend: CV upload + preprocessing module integration
"""

import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from preprocess import (
    collect_candidate_sections,
    parse_candidate_text,
    save_json,
    write_excel,
)


app = Flask(__name__)
UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

LLM = "GEMINI"
HAS_KEY = bool(os.environ.get("GEMINI_API_KEY"))

processed_candidates = []


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_cv():
    if "cv" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["cv"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    save_path = UPLOAD_FOLDER / Path(file.filename).name
    file.save(save_path)

    try:
        sections = collect_candidate_sections(save_path)
    except Exception as exc:
        return jsonify({"error": f"Could not read PDF: {exc}"}), 422

    if not sections:
        return jsonify({"error": "Could not extract text from this PDF"}), 422

    parsed = []
    for section in sections:
        candidate = parse_candidate_text(
            section["text"],
            section["source_file"],
            section["pages"],
        )
        processed_candidates.append(candidate)
        parsed.append(flatten_for_ui(candidate))

    return jsonify(
        {
            "message": f"Processed {len(parsed)} candidate(s)",
            "count": len(parsed),
            "candidates": parsed,
        }
    )


@app.route("/export/excel")
def export_excel():
    if not processed_candidates:
        return jsonify({"error": "No data to export"}), 400

    out = UPLOAD_FOLDER / "TALASH_Candidates.xlsx"
    try:
        write_excel(processed_candidates, out)
    except PermissionError:
        return jsonify({"error": "Please close TALASH_Candidates.xlsx and try again"}), 409

    return send_file(str(out), as_attachment=True, download_name="TALASH_Candidates.xlsx")


@app.route("/export/json")
def export_json():
    if not processed_candidates:
        return jsonify({"error": "No data to export"}), 400

    out = UPLOAD_FOLDER / "TALASH_Candidates.json"
    try:
        save_json(processed_candidates, out)
    except PermissionError:
        return jsonify({"error": "Please close TALASH_Candidates.json and try again"}), 409

    return send_file(str(out), as_attachment=True, download_name="TALASH_Candidates.json")


@app.route("/clear", methods=["POST"])
def clear_data():
    processed_candidates.clear()
    return jsonify({"message": "Processed candidates cleared"})


def flatten_for_ui(data):
    personal = data.get("personal", {})
    education = data.get("education", [])
    experience = data.get("experience", [])
    publications = data.get("publications", [])
    awards = data.get("awards", [])
    references = data.get("references", [])

    return {
        "source_file": data.get("_source_file", ""),
        "page_range": data.get("_page_range", ""),
        "name": personal.get("name", data.get("_source_file", "Unknown")),
        "applied_for": personal.get("applied_for", "—"),
        "present_employment": personal.get("present_employment", "—"),
        "education": [
            {
                "degree": item.get("degree", "—"),
                "specialization": item.get("specialization", "—"),
                "institution": item.get("institution", "—"),
                "grade_cgpa": item.get("grade_cgpa", "—"),
                "grade_type": item.get("grade_type", "—"),
                "level": item.get("level", "—"),
                "passing_year": item.get("passing_year", "—"),
            }
            for item in education
        ],
        "experience": [
            {
                "role": item.get("role", "—"),
                "organization": item.get("organization", "—"),
                "location": item.get("location", "—"),
                "start_date": item.get("start_date", "—"),
                "end_date": item.get("end_date", "—"),
                "duration_months": item.get("duration_months", "—"),
            }
            for item in experience
        ],
        "publications": [
            {
                "title": item.get("title", "—"),
                "venue": item.get("venue", "—"),
                "type": item.get("venue_type", "—"),
                "impact_factor": item.get("impact_factor", "—"),
                "year": item.get("year", "—"),
                "candidate_is_first_author": "Yes" if item.get("candidate_is_first_author") else "No",
            }
            for item in publications
        ],
        "awards": [
            {
                "type": item.get("type", "—"),
                "detail": item.get("detail", "—"),
            }
            for item in awards
        ],
        "references": [
            {
                "name": item.get("name", "—"),
                "designation": item.get("designation", "—"),
                "organization": item.get("organization", "—"),
                "email": item.get("email", "—"),
                "phone": item.get("phone", "—"),
            }
            for item in references
        ],
        "skills": data.get("skills", []),
        "missing_fields": data.get("missing_fields", []),
    }


if __name__ == "__main__":
    print("=" * 55)
    print("  TALASH - CS417 Milestone 1")
    print(f"  LLM backend  : {LLM}")
    print(f"  API key set  : {'Yes' if HAS_KEY else 'No (set GEMINI_API_KEY)'}")
    print("  Running at   : http://127.0.0.1:5000")
    print("=" * 55)
    app.run(debug=True)
