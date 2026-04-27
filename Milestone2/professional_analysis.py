"""
TALASH - CS417 Milestone 1
Professional profile analysis, missing details, and candidate summaries.
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv

from common import PROFESSIONAL_DIR, read_json, upsert_many, write_json, write_workbook

load_dotenv()


DATE_FORMATS = [
    "%b-%Y",
    "%B-%Y",
    "%b %Y",
    "%B %Y",
    "%m/%Y",
    "%Y-%m",
    "%Y",
]

SENIORITY_KEYWORDS = {
    5: ["director", "head", "vice president", "vp", "chief", "dean", "principal"],
    4: ["senior", "lead", "manager", "professor", "associate professor", "assistant professor"],
    3: ["engineer", "developer", "analyst", "researcher", "lecturer", "consultant", "coordinator"],
    2: ["assistant", "associate", "technician"],
    1: ["intern", "trainee", "student"],
}


def parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if re.match(r"^(present|current|ongoing|now)$", text, re.I):
        return datetime.now()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    match = re.search(r"(19|20)\d{2}", text)
    if match:
        return datetime(int(match.group()), 1, 1)
    return None


def normalize_preprocessed_candidate(candidate: Dict[str, object]) -> Dict[str, object]:
    personal = candidate.get("personal", {}) if isinstance(candidate.get("personal"), dict) else {}
    return {
        "source_file": candidate.get("_source_file", "unknown.pdf"),
        "candidate_name": personal.get("name") or candidate.get("_source_file", "Unknown"),
        "applied_for": personal.get("applied_for"),
        "present_employment": personal.get("present_employment"),
        "personal": personal,
        "education": candidate.get("education", []) if isinstance(candidate.get("education"), list) else [],
        "experience": candidate.get("experience", []) if isinstance(candidate.get("experience"), list) else [],
        "publications": candidate.get("publications", []) if isinstance(candidate.get("publications"), list) else [],
        "skills": candidate.get("skills", []) if isinstance(candidate.get("skills"), list) else [],
        "missing_fields": candidate.get("missing_fields", []) if isinstance(candidate.get("missing_fields"), list) else [],
    }


def build_timeline(experience_rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    timeline = []
    for row in experience_rows:
        start = parse_date(row.get("start_date"))
        end = parse_date(row.get("end_date"))
        if start:
            timeline.append(
                {
                    "start": start,
                    "end": end or datetime.now(),
                    "role": row.get("role") or "Unknown",
                    "organization": row.get("organization") or "Unknown",
                    "location": row.get("location") or "Unknown",
                }
            )
    timeline.sort(key=lambda item: item["start"])
    return timeline


def detect_professional_gaps(timeline: List[Dict[str, object]]) -> List[str]:
    gaps = []
    for previous, current in zip(timeline, timeline[1:]):
        gap_days = (current["start"] - previous["end"]).days
        if gap_days > 180:
            gaps.append(f"{previous['role']} -> {current['role']}: {round(gap_days / 30.44, 1)} months")
    return gaps


def detect_overlaps(timeline: List[Dict[str, object]]) -> List[str]:
    overlaps = []
    for idx in range(len(timeline)):
        for jdx in range(idx + 1, len(timeline)):
            left = timeline[idx]
            right = timeline[jdx]
            overlap_days = (min(left["end"], right["end"]) - max(left["start"], right["start"])).days
            if overlap_days > 30:
                overlaps.append(f"{left['role']} with {right['role']}: {round(overlap_days / 30.44, 1)} months")
    return overlaps


def seniority_level(job_title: str) -> int:
    title = (job_title or "").lower()
    for level in sorted(SENIORITY_KEYWORDS, reverse=True):
        if any(keyword in title for keyword in SENIORITY_KEYWORDS[level]):
            return level
    return 2


def career_progression_label(timeline: List[Dict[str, object]]) -> str:
    if len(timeline) < 2:
        return "Insufficient data"
    levels = [seniority_level(item["role"]) for item in timeline]
    if levels[-1] > levels[0]:
        return "Upward"
    if levels[-1] < levels[0]:
        return "Declining"
    return "Stable"


def total_experience_years(timeline: List[Dict[str, object]]) -> float:
    if not timeline:
        return 0.0
    total_days = sum(max((item["end"] - item["start"]).days, 0) for item in timeline)
    return round(total_days / 365.25, 2)


def longest_tenure_years(timeline: List[Dict[str, object]]) -> float:
    if not timeline:
        return 0.0
    return round(max((item["end"] - item["start"]).days for item in timeline) / 365.25, 2)


def detect_missing_fields_detailed(candidate: Dict[str, object]) -> Dict[str, object]:
    personal = candidate.get("personal", {})
    education = candidate.get("education", [])
    experience = candidate.get("experience", [])
    publications = candidate.get("publications", [])
    skills = candidate.get("skills", [])

    missing = []
    if not personal.get("dob"):
        missing.append("date of birth")
    if not personal.get("nationality"):
        missing.append("nationality")
    if not personal.get("applied_for"):
        missing.append("applied for position")
    if not any(str(row.get("level", "")).lower().find("ssc") >= 0 for row in education):
        missing.append("SSC record")
    if not any(str(row.get("level", "")).lower().find("hssc") >= 0 for row in education):
        missing.append("HSSC record")
    if not experience:
        missing.append("professional experience")
    if not publications:
        missing.append("publications")
    if not skills:
        missing.append("skills")

    return {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "missing_info_flag": "Yes" if missing else "No",
        "missing_info_items": "; ".join(missing) if missing else "None",
    }


def draft_missing_info_email(candidate: Dict[str, object], missing: Dict[str, object]) -> Dict[str, object]:
    name = candidate["candidate_name"]
    items = missing.get("missing_info_items", "None")
    if items == "None":
        body = (
            f"Subject: TALASH profile update for {name}\n\n"
            f"Dear {name},\n\n"
            "Thank you for submitting your profile to TALASH. Your CV has been processed successfully and no major missing information was detected at this stage.\n\n"
            "Best regards,\nTALASH Recruitment Team"
        )
    else:
        body = (
            f"Subject: Additional information required for {name}\n\n"
            f"Dear {name},\n\n"
            "Thank you for applying through TALASH. During automated review of your CV, we found a few items that are missing or unclear.\n\n"
            f"Please share the following details if available: {items}.\n\n"
            "This will help us complete your profile evaluation more accurately.\n\n"
            "Best regards,\nTALASH Recruitment Team"
        )
    return {
        "source_file": candidate["source_file"],
        "candidate_name": name,
        "draft_email": body,
    }


def generate_candidate_summary(candidate: Dict[str, object], prof: Dict[str, object], missing: Dict[str, object]) -> Dict[str, object]:
    education = candidate.get("education", [])
    highest = education[0].get("degree") if education else "no recorded highest qualification"
    summary = (
        f"{candidate['candidate_name']} applied for {candidate.get('applied_for') or 'an unspecified role'}. "
        f"The profile reports {prof['total_experience_years']} years of experience with career progression marked as "
        f"{prof['career_progression']}. The longest single tenure is {prof['longest_tenure_years']} years. "
        f"Highest recorded qualification is {highest}. Professional gap status is {prof['professional_gap_flag']}"
        f" and overlap status is {prof['overlap_flag']}. Missing information: {missing['missing_info_items']}."
    )
    return {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "candidate_summary": summary,
    }


def analyze_candidate(candidate: Dict[str, object]) -> Dict[str, object]:
    timeline = build_timeline(candidate.get("experience", []))
    gaps = detect_professional_gaps(timeline)
    overlaps = detect_overlaps(timeline)

    return {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "applied_for": candidate.get("applied_for"),
        "present_employment": candidate.get("present_employment"),
        "total_experience_years": total_experience_years(timeline),
        "longest_tenure_years": longest_tenure_years(timeline),
        "professional_gap_flag": "Yes" if gaps else "No",
        "professional_gap_detail": "; ".join(gaps) if gaps else "No significant professional gap detected",
        "overlap_flag": "Yes" if overlaps else "No",
        "overlap_detail": "; ".join(overlaps) if overlaps else "No major overlap detected",
        "career_progression": career_progression_label(timeline),
        "experience_record_count": len(candidate.get("experience", [])),
    }


def build_experience_rows(candidate: Dict[str, object]) -> List[Dict[str, object]]:
    rows = []
    for row in candidate.get("experience", []):
        rows.append(
            {
                "source_file": candidate["source_file"],
                "candidate_name": candidate["candidate_name"],
                "applied_for": candidate.get("applied_for"),
                "role": row.get("role"),
                "organization": row.get("organization"),
                "location": row.get("location"),
                "start_date": row.get("start_date"),
                "end_date": row.get("end_date"),
                "duration_months": row.get("duration_months"),
            }
        )
    return rows


def save_csv(rows: List[Dict[str, object]], path: Path) -> Path:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def save_to_mongodb(rows: List[Dict[str, object]]) -> int:
    return upsert_many("professional_analysis", rows, ["source_file", "candidate_name"])


def process_preprocessed_json(input_json: str, output_folder: Optional[str] = None, save_to_mongo: bool = True) -> Dict[str, object]:
    input_path = Path(input_json)
    output_dir = Path(output_folder) if output_folder else PROFESSIONAL_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_candidates = read_json(input_path)
    if not isinstance(raw_candidates, list):
        raise ValueError("Preprocessed JSON must contain a list of candidates.")

    candidates = [normalize_preprocessed_candidate(item) for item in raw_candidates]
    experience_rows = []
    analysis_rows = []
    missing_rows = []
    email_rows = []
    summary_rows = []

    for candidate in candidates:
        experience_rows.extend(build_experience_rows(candidate))
        prof = analyze_candidate(candidate)
        missing = detect_missing_fields_detailed(candidate)
        email = draft_missing_info_email(candidate, missing)
        summary = generate_candidate_summary(candidate, prof, missing)
        analysis_rows.append(prof)
        missing_rows.append(missing)
        email_rows.append(email)
        summary_rows.append(summary)

    json_path = write_json(
        {
            "experience_rows": experience_rows,
            "professional_analysis": analysis_rows,
            "missing_info_detailed": missing_rows,
            "drafted_emails": email_rows,
            "candidate_summaries": summary_rows,
        },
        output_dir / "professional_analysis.json",
    )
    excel_path = write_workbook(
        {
            "Experience Records": experience_rows,
            "Professional Analysis": analysis_rows,
            "Missing Details": missing_rows,
            "Drafted Emails": email_rows,
            "Candidate Summaries": summary_rows,
        },
        output_dir / "professional_analysis.xlsx",
    )
    summary_csv = save_csv(summary_rows, output_dir / "candidate_summaries.csv")
    summary_excel = write_workbook({"Candidate Summaries": summary_rows}, output_dir / "candidate_summaries.xlsx")
    missing_csv = save_csv(missing_rows, output_dir / "missing_info_detailed.csv")
    email_csv = save_csv(email_rows, output_dir / "drafted_emails.csv")
    mongo_count = save_to_mongodb(analysis_rows) if save_to_mongo and analysis_rows else 0

    return {
        "experience_rows": experience_rows,
        "analysis_rows": analysis_rows,
        "missing_rows": missing_rows,
        "email_rows": email_rows,
        "summary_rows": summary_rows,
        "json_path": str(json_path),
        "excel_path": str(excel_path),
        "summary_csv": str(summary_csv),
        "summary_excel": str(summary_excel),
        "missing_csv": str(missing_csv),
        "email_csv": str(email_csv),
        "output_dir": str(output_dir),
        "mongo_written": mongo_count,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:\n  python professional_analysis.py <preprocessed_json> [output_dir]\n")
        sys.exit(1)
    result = process_preprocessed_json(sys.argv[1], sys.argv[2] if len(sys.argv) >= 3 else None)
    print(f"JSON saved  : {result['json_path']}")
    print(f"Excel saved : {result['excel_path']}")
    print(f"Summary CSV : {result['summary_csv']}")
    print(f"Summary XLSX: {result['summary_excel']}")
    print(f"Email CSV   : {result['email_csv']}")
    if result["mongo_written"]:
        print(f"Mongo saved : {result['mongo_written']} document(s)")


if __name__ == "__main__":
    main()
