"""
TALASH - CS417 Milestone 3
Preprocessing module: PDF ingestion, structured extraction, Excel + JSON + MongoDB
"""

import json
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

import pdfplumber
from dotenv import load_dotenv

from common import PREPROCESS_DIR, app_paths, upsert_many, write_json, write_workbook

load_dotenv()


SYSTEM_PROMPT = """
You are an expert CV parser for the TALASH Smart HR Recruitment System (CS417 project).
Your job is to extract structured information from one university faculty/academic CV.

You MUST return ONLY a valid JSON object. Do not include markdown, code fences, or explanations.

Return this exact JSON structure:
{
  "personal": {
    "name": "full name",
    "dob": "date of birth or null",
    "nationality": "nationality or null",
    "marital_status": "Married/Single/etc or null",
    "current_salary": "amount or null",
    "expected_salary": "amount or null",
    "present_employment": "current job or Unemployed",
    "applied_for": "exact post/position mentioned"
  },
  "education": [
    {
      "degree": "exact degree name",
      "specialization": "field/major",
      "grade_cgpa": "numeric value as string",
      "grade_type": "CGPA/Percentage",
      "passing_year": "year as string",
      "institution": "full institution name",
      "level": "SSC/HSSC/Bachelor/Master/MPhil/PhD/Other"
    }
  ],
  "experience": [
    {
      "role": "job title",
      "organization": "employer",
      "location": "city/country",
      "start_date": "Mon-YYYY or null",
      "end_date": "Mon-YYYY or Present",
      "duration_months": "estimated integer or null"
    }
  ],
  "publications": [
    {
      "title": "paper title",
      "first_author": "name",
      "co_authors": "comma-separated names",
      "venue": "journal or conference name",
      "venue_type": "Journal/Conference/Book",
      "impact_factor": "number as string or null",
      "volume": "vol number or null",
      "pages": "page range or null",
      "year": "year as string",
      "candidate_is_first_author": true
    }
  ],
  "awards": [
    {
      "type": "Scholarship/Award/Membership/etc",
      "detail": "full description"
    }
  ],
  "supervision": [
    {
      "student_name": "student name",
      "degree_level": "MS/PhD",
      "role": "Main Supervisor/Co-Supervisor",
      "graduation_year": "year or null"
    }
  ],
  "books": [
    {
      "title": "book title",
      "authors": "comma-separated authors",
      "isbn": "isbn or null",
      "publisher": "publisher name or null",
      "year": "year as string or null",
      "link": "online link or null"
    }
  ],
  "patents": [
    {
      "title": "patent title",
      "patent_number": "number or null",
      "filing_date": "date or null",
      "inventors": "comma-separated inventors",
      "country": "country of filing or null",
      "link": "verification link or null"
    }
  ],
  "references": [
    {
      "name": "referee name",
      "designation": "title",
      "organization": "institution",
      "email": "email or null",
      "phone": "phone or null"
    }
  ],
  "skills": ["list of skills"],
  "missing_fields": ["list any important fields that are absent or unclear in the CV"]
}

Rules:
- Extract only what is explicitly present in this single CV.
- Do not assume the PDF contains multiple candidates.
- If a field is missing, use null or an empty list as appropriate.
- If supervision, books, or patents are not mentioned, return empty lists.
- Return JSON only.
""".strip()


EDUCATION_LEVEL_RANK = {
    "ssc": 1,
    "matric": 1,
    "o level": 1,
    "hssc": 2,
    "intermediate": 2,
    "fsc": 2,
    "a level": 2,
    "bachelor": 3,
    "bs": 3,
    "bsc": 3,
    "be": 3,
    "master": 4,
    "ms": 4,
    "msc": 4,
    "mba": 4,
    "mphil": 5,
    "phd": 6,
    "doctorate": 6,
}


def call_gemini(prompt: str) -> str:
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set.")

    model_name = os.getenv("TALASH_GEMINI_MODEL", "gemini-2.5-flash").strip()
    timeout_seconds = int(os.getenv("TALASH_GEMINI_TIMEOUT_SECONDS", "75").strip() or "75")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=SYSTEM_PROMPT,
        generation_config={"temperature": 0.1, "response_mime_type": "application/json"},
    )
    response = model.generate_content(prompt, request_options={"timeout": timeout_seconds})
    return (getattr(response, "text", "") or "").strip()


def extract_json_block(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    if raw.startswith("{") and raw.endswith("}"):
        return raw
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start:end + 1]
    return raw


def extract_text_from_pdf(pdf_path: Path) -> List[Dict[str, object]]:
    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            pages.append({"page_no": page_no, "text": (page.extract_text() or "").strip()})
    return pages


def extract_text_from_zip_pdf(pdf_path: Path) -> List[Dict[str, object]]:
    pages = []
    with zipfile.ZipFile(str(pdf_path), "r") as archive:
        txt_files = sorted(
            [name for name in archive.namelist() if name.lower().endswith(".txt")],
            key=lambda name: int(re.sub(r"\D", "", Path(name).stem) or 0),
        )
        for idx, name in enumerate(txt_files, start=1):
            with archive.open(name) as file_obj:
                pages.append({"page_no": idx, "text": file_obj.read().decode("utf-8", errors="replace").strip()})
    return pages


def load_pages(pdf_path: Path) -> List[Dict[str, object]]:
    try:
        return extract_text_from_zip_pdf(pdf_path)
    except zipfile.BadZipFile:
        return extract_text_from_pdf(pdf_path)
    except Exception:
        return extract_text_from_pdf(pdf_path)


def extract_text_from_cv(cv_path: str) -> str:
    pages = load_pages(Path(cv_path))
    return "\n\n".join(f"[Page {p['page_no']}]\n{p['text']}" for p in pages if p.get("text")).strip()


def collect_cv_files(input_path: Path) -> List[Path]:
    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.glob("*.pdf"))
    raise FileNotFoundError(f"Input path not found: {input_path}")


def empty_record(source_file: str, reason: str) -> Dict[str, object]:
    return {
        "_source_file": source_file,
        "personal": {
            "name": Path(source_file).stem,
            "dob": None,
            "nationality": None,
            "marital_status": None,
            "current_salary": None,
            "expected_salary": None,
            "present_employment": None,
            "applied_for": None,
        },
        "education": [],
        "experience": [],
        "publications": [],
        "awards": [],
        "supervision": [],
        "books": [],
        "patents": [],
        "references": [],
        "skills": [],
        "missing_fields": [reason],
    }


def normalize_candidate(data: Dict[str, object], source_file: str) -> Dict[str, object]:
    personal = data.get("personal", {}) if isinstance(data.get("personal"), dict) else {}
    normalized = {
        "_source_file": source_file,
        "personal": {
            "name": personal.get("name") or Path(source_file).stem,
            "dob": personal.get("dob"),
            "nationality": personal.get("nationality"),
            "marital_status": personal.get("marital_status"),
            "current_salary": personal.get("current_salary"),
            "expected_salary": personal.get("expected_salary"),
            "present_employment": personal.get("present_employment"),
            "applied_for": personal.get("applied_for"),
        },
        "education": data.get("education", []) if isinstance(data.get("education"), list) else [],
        "experience": data.get("experience", []) if isinstance(data.get("experience"), list) else [],
        "publications": data.get("publications", []) if isinstance(data.get("publications"), list) else [],
        "awards": data.get("awards", []) if isinstance(data.get("awards"), list) else [],
        "supervision": data.get("supervision", []) if isinstance(data.get("supervision"), list) else [],
        "books": data.get("books", []) if isinstance(data.get("books"), list) else [],
        "patents": data.get("patents", []) if isinstance(data.get("patents"), list) else [],
        "references": data.get("references", []) if isinstance(data.get("references"), list) else [],
        "skills": data.get("skills", []) if isinstance(data.get("skills"), list) else [],
        "missing_fields": data.get("missing_fields", []) if isinstance(data.get("missing_fields"), list) else [],
    }
    for exp in normalized["experience"]:
        if isinstance(exp, dict) and isinstance(exp.get("duration_months"), str) and exp["duration_months"].isdigit():
            exp["duration_months"] = int(exp["duration_months"])
    return normalized


def parse_cv_with_llm(cv_text: str, filename: str) -> Dict[str, object]:
    try:
        raw = call_gemini(f"Source file: {filename}\n\nExtract candidate information from this CV text:\n\n{cv_text}")
        return normalize_candidate(json.loads(extract_json_block(raw)), filename)
    except Exception as exc:
        print(f"  [!] Failed on {filename}: {exc}")
        return empty_record(filename, "LLM extraction failed")


def education_rank(entry: Dict[str, object]) -> int:
    level = str(entry.get("level", "") or "").lower()
    degree = str(entry.get("degree", "") or "").lower()
    for key, rank in EDUCATION_LEVEL_RANK.items():
        if key in level or key in degree:
            return rank
    return 0


def get_highest_education(education: List[Dict[str, object]]) -> Dict[str, object]:
    return max(education, key=education_rank) if education else {}


def build_preprocess_workbook_rows(all_candidates: List[Dict[str, object]]) -> Dict[str, List[dict]]:
    summary_rows = []
    personal_rows = []
    education_rows = []
    experience_rows = []
    publications_rows = []
    awards_rows = []
    supervision_rows = []
    books_rows = []
    patents_rows = []
    references_rows = []
    skills_rows = []
    missing_rows = []

    for idx, candidate in enumerate(all_candidates, start=1):
        personal = candidate.get("personal", {})
        education = candidate.get("education", [])
        experience = candidate.get("experience", [])
        publications = candidate.get("publications", [])
        highest = get_highest_education(education)
        total_months = sum(
            item.get("duration_months", 0)
            for item in experience
            if isinstance(item, dict) and isinstance(item.get("duration_months"), int)
        )

        summary_rows.append(
            {
                "#": idx,
                "name": personal.get("name", "—"),
                "applied_for": personal.get("applied_for", "—"),
                "highest_degree": highest.get("degree", "—") if isinstance(highest, dict) else "—",
                "specialization": highest.get("specialization", "—") if isinstance(highest, dict) else "—",
                "institution": highest.get("institution", "—") if isinstance(highest, dict) else "—",
                "cgpa_percent": highest.get("grade_cgpa", "—") if isinstance(highest, dict) else "—",
                "total_publications": len(publications),
                "years_experience": round(total_months / 12, 1) if total_months else "—",
                "present_employment": personal.get("present_employment", "—"),
                "source_file": candidate.get("_source_file", ""),
                "missing_fields": "; ".join(candidate.get("missing_fields", [])) if candidate.get("missing_fields") else "None",
            }
        )

        personal_rows.append(
            {
                "#": idx,
                "source_file": candidate.get("_source_file", ""),
                "name": personal.get("name", "—"),
                "date_of_birth": personal.get("dob", "—"),
                "nationality": personal.get("nationality", "—"),
                "marital_status": personal.get("marital_status", "—"),
                "current_salary": personal.get("current_salary", "—"),
                "expected_salary": personal.get("expected_salary", "—"),
                "present_employment": personal.get("present_employment", "—"),
                "applied_for": personal.get("applied_for", "—"),
            }
        )

        for item in education:
            education_rows.append(
                {
                    "candidate_name": personal.get("name", "—"),
                    "source_file": candidate.get("_source_file", ""),
                    "level": item.get("level", "—"),
                    "degree": item.get("degree", "—"),
                    "specialization": item.get("specialization", "—"),
                    "grade_cgpa": item.get("grade_cgpa", "—"),
                    "grade_type": item.get("grade_type", "—"),
                    "passing_year": item.get("passing_year", "—"),
                    "institution": item.get("institution", "—"),
                }
            )

        for item in experience:
            experience_rows.append(
                {
                    "candidate_name": personal.get("name", "—"),
                    "source_file": candidate.get("_source_file", ""),
                    "role": item.get("role", "—"),
                    "organization": item.get("organization", "—"),
                    "location": item.get("location", "—"),
                    "start_date": item.get("start_date", "—"),
                    "end_date": item.get("end_date", "—"),
                    "duration_months": item.get("duration_months", "—"),
                }
            )

        for item in publications:
            publications_rows.append(
                {
                    "candidate_name": personal.get("name", "—"),
                    "source_file": candidate.get("_source_file", ""),
                    "title": item.get("title", "—"),
                    "first_author": item.get("first_author", "—"),
                    "co_authors": item.get("co_authors", "—"),
                    "venue": item.get("venue", "—"),
                    "venue_type": item.get("venue_type", "—"),
                    "impact_factor": item.get("impact_factor", "—"),
                    "volume": item.get("volume", "—"),
                    "pages": item.get("pages", "—"),
                    "year": item.get("year", "—"),
                    "candidate_is_first_author": "Yes" if item.get("candidate_is_first_author") else "No",
                }
            )

        for item in candidate.get("awards", []):
            awards_rows.append(
                {
                    "candidate_name": personal.get("name", "—"),
                    "source_file": candidate.get("_source_file", ""),
                    "type": item.get("type", "—"),
                    "detail": item.get("detail", "—"),
                }
            )

        for item in candidate.get("supervision", []):
            supervision_rows.append(
                {
                    "candidate_name": personal.get("name", "-"),
                    "source_file": candidate.get("_source_file", ""),
                    "student_name": item.get("student_name", "-"),
                    "degree_level": item.get("degree_level", "-"),
                    "role": item.get("role", "-"),
                    "graduation_year": item.get("graduation_year", "-"),
                }
            )

        for item in candidate.get("books", []):
            books_rows.append(
                {
                    "candidate_name": personal.get("name", "-"),
                    "source_file": candidate.get("_source_file", ""),
                    "title": item.get("title", "-"),
                    "authors": item.get("authors", "-"),
                    "isbn": item.get("isbn", "-"),
                    "publisher": item.get("publisher", "-"),
                    "year": item.get("year", "-"),
                    "link": item.get("link", "-"),
                }
            )

        for item in candidate.get("patents", []):
            patents_rows.append(
                {
                    "candidate_name": personal.get("name", "-"),
                    "source_file": candidate.get("_source_file", ""),
                    "title": item.get("title", "-"),
                    "patent_number": item.get("patent_number", "-"),
                    "filing_date": item.get("filing_date", "-"),
                    "inventors": item.get("inventors", "-"),
                    "country": item.get("country", "-"),
                    "link": item.get("link", "-"),
                }
            )

        for item in candidate.get("references", []):
            references_rows.append(
                {
                    "candidate_name": personal.get("name", "—"),
                    "source_file": candidate.get("_source_file", ""),
                    "name": item.get("name", "—"),
                    "designation": item.get("designation", "—"),
                    "organization": item.get("organization", "—"),
                    "email": item.get("email", "—"),
                    "phone": item.get("phone", "—"),
                }
            )

        for skill in candidate.get("skills", []):
            skills_rows.append(
                {
                    "candidate_name": personal.get("name", "—"),
                    "source_file": candidate.get("_source_file", ""),
                    "skill": skill,
                }
            )

        missing_rows.append(
            {
                "candidate_name": personal.get("name", "—"),
                "source_file": candidate.get("_source_file", ""),
                "missing_fields": "; ".join(candidate.get("missing_fields", [])) if candidate.get("missing_fields") else "None",
            }
        )

    return {
        "Summary": summary_rows,
        "Personal Info": personal_rows,
        "Education": education_rows,
        "Experience": experience_rows,
        "Publications": publications_rows,
        "Awards": awards_rows,
        "Supervision": supervision_rows,
        "Books": books_rows,
        "Patents": patents_rows,
        "References": references_rows,
        "Skills": skills_rows,
        "Missing Info": missing_rows,
    }


def save_to_mongodb(all_candidates: List[Dict[str, object]]) -> int:
    return upsert_many("preprocessed_candidates", all_candidates, ["_source_file"])


def run_pipeline(input_path: str, output_dir: Optional[str] = None, save_to_mongo: bool = True) -> Dict[str, object]:
    target = Path(input_path)
    out_dir = Path(output_dir) if output_dir else PREPROCESS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    cv_files = collect_cv_files(target)
    if not cv_files:
        raise RuntimeError("No PDF files found.")

    all_candidates = []
    for idx, pdf_file in enumerate(cv_files, start=1):
        print(f"[{idx}/{len(cv_files)}] Processing {pdf_file.name}")
        text = extract_text_from_cv(str(pdf_file))
        if not text:
            all_candidates.append(empty_record(pdf_file.name, "No text extracted"))
            continue
        candidate = parse_cv_with_llm(text, pdf_file.name)
        all_candidates.append(candidate)

    json_path = write_json(all_candidates, out_dir / "TALASH_Candidates.json")
    excel_path = write_workbook(build_preprocess_workbook_rows(all_candidates), out_dir / "TALASH_Candidates.xlsx")
    mongo_count = save_to_mongodb(all_candidates) if save_to_mongo and all_candidates else 0

    return {
        "candidates": all_candidates,
        "json_path": str(json_path),
        "excel_path": str(excel_path),
        "mongo_written": mongo_count,
        "output_dir": str(out_dir),
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:\n  python preprocess.py <input_pdf_or_folder> [output_dir]\n")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) >= 3 else None
    result = run_pipeline(input_path, output_dir)
    print(f"JSON saved  : {result['json_path']}")
    print(f"Excel saved : {result['excel_path']}")
    if result["mongo_written"]:
        print(f"Mongo saved : {result['mongo_written']} document(s)")


if __name__ == "__main__":
    main()
