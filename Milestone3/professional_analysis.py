"""
TALASH professional analysis:
- experience timeline analysis
- missing information analysis
- drafted follow-up emails
- candidate summaries
"""

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from dotenv import load_dotenv

from common import PROFESSIONAL_DIR, read_json, upsert_many, write_json, write_workbook

load_dotenv()


DATE_FORMATS = [
    "%Y",
    "%m/%Y",
    "%B %Y",
    "%b %Y",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%m-%Y",
    "%Y-%m",
    "%b-%Y",
    "%B-%Y",
]

SENIORITY_KEYWORDS = {
    5: ["director", "head", "vp", "vice president", "chief", "dean", "rector", "principal"],
    4: ["senior", "lead", "manager", "supervisor", "professor", "associate professor", "assistant professor"],
    3: ["engineer", "developer", "analyst", "researcher", "lecturer", "coordinator", "consultant"],
    2: ["junior", "associate", "assistant", "technician"],
    1: ["intern", "trainee", "graduate", "student"],
}

REQUIRED_PERSONAL = ["name", "dob", "nationality", "applied_for"]
REQUIRED_EXP_FIELDS = ["start_date", "end_date"]

EMAIL_SYSTEM = (
    "You are the HR coordinator for TALASH (Talent Acquisition and Learning Automation "
    "for Smart Hiring) at SEECS, NUST. Write professional, polite, concise emails in "
    "plain text. No markdown. No bullet symbols. Use numbered lists only. "
    "Address the candidate by name. Keep tone warm but formal."
)

SUMMARY_SYSTEM = (
    "You are a senior HR analyst for TALASH (Talent Acquisition and Learning Automation "
    "for Smart Hiring) at SEECS, NUST. Write concise, factual, third-person candidate "
    "summaries (150-200 words) suitable for a hiring committee. Mention the highest "
    "qualification, total experience, career trajectory, notable roles, research profile, "
    "and any significant gaps or data completeness issues. No markdown. Plain text only."
)

SKILL_TAXONOMY = {
    "machine learning": ["machine learning", "ml", "classification", "prediction", "random forest"],
    "deep learning": ["deep learning", "neural network", "cnn", "lstm", "transformer"],
    "computer vision": ["computer vision", "image", "video", "detection", "segmentation", "vision"],
    "nlp": ["nlp", "natural language", "text mining", "language model", "llm"],
    "data analysis": ["data analysis", "analytics", "statistics", "visualization", "dashboard"],
    "signal processing": ["signal processing", "filter", "spectral", "wavelet"],
    "embedded systems": ["embedded", "microcontroller", "iot", "iiot", "tinyml"],
    "power systems": ["power", "energy", "electrical", "grid", "turbine"],
    "teaching": ["lecturer", "assistant professor", "associate professor", "professor", "teaching", "curriculum"],
    "research": ["research", "publication", "journal", "conference", "supervision"],
    "management": ["manager", "head", "director", "lead", "coordinator", "supervisor"],
    "software development": ["developer", "software", "python", "java", "web", "flask", "api"],
}


def safe_text(value, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text and text.lower() not in {"nan", "none", "null"} else fallback


def looks_like_placeholder(value: str) -> bool:
    normalized = safe_text(value).lower()
    return normalized.startswith("your_") or normalized.endswith("_here") or "placeholder" in normalized


def parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    text = safe_text(value)
    if not text:
        return None
    if re.match(r"^(present|current|ongoing|till\s*date|to\s*date|now)$", text, re.I):
        return datetime.now()
    match = re.search(r"\b(19|20)\d{2}\b", text)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    if match:
        try:
            return datetime(int(match.group()), 1, 1)
        except ValueError:
            return None
    return None


def parse_year(value: str) -> Optional[int]:
    parsed = parse_date(value)
    return parsed.year if parsed else None


def normalize_preprocessed_candidate(candidate: Dict[str, object]) -> Dict[str, object]:
    personal = candidate.get("personal", {}) if isinstance(candidate.get("personal"), dict) else {}
    return {
        "source_file": candidate.get("_source_file", "unknown.pdf"),
        "candidate_name": safe_text(personal.get("name"), candidate.get("_source_file", "Unknown")),
        "applied_for": safe_text(personal.get("applied_for")),
        "present_employment": safe_text(personal.get("present_employment")),
        "personal": personal,
        "education": candidate.get("education", []) if isinstance(candidate.get("education"), list) else [],
        "experience": candidate.get("experience", []) if isinstance(candidate.get("experience"), list) else [],
        "publications": candidate.get("publications", []) if isinstance(candidate.get("publications"), list) else [],
        "supervision": candidate.get("supervision", []) if isinstance(candidate.get("supervision"), list) else [],
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
                    "title": safe_text(row.get("role"), "Unknown"),
                    "organization": safe_text(row.get("organization"), "Unknown"),
                    "location": safe_text(row.get("location"), "Unknown"),
                    "raw_start": row.get("start_date"),
                    "raw_end": row.get("end_date"),
                }
            )
    timeline.sort(key=lambda item: item["start"])
    return timeline


def detect_professional_gaps(timeline: List[Dict[str, object]]) -> List[Dict[str, object]]:
    gaps = []
    for previous, current in zip(timeline, timeline[1:]):
        gap_days = (current["start"] - previous["end"]).days
        if gap_days > 180:
            gaps.append(
                {
                    "after_role": previous["title"],
                    "before_role": current["title"],
                    "gap_months": round(gap_days / 30.44, 1),
                    "from": previous["end"].strftime("%Y-%m"),
                    "to": current["start"].strftime("%Y-%m"),
                }
            )
    return gaps


def detect_overlaps(timeline: List[Dict[str, object]]) -> List[Dict[str, object]]:
    overlaps = []
    for idx in range(len(timeline)):
        for jdx in range(idx + 1, len(timeline)):
            left = timeline[idx]
            right = timeline[jdx]
            overlap_days = (min(left["end"], right["end"]) - max(left["start"], right["start"])).days
            if overlap_days > 30:
                overlaps.append(
                    {
                        "role_a": left["title"],
                        "org_a": left["organization"],
                        "role_b": right["title"],
                        "org_b": right["organization"],
                        "overlap_months": round(overlap_days / 30.44, 1),
                    }
                )
    return overlaps


def detect_edu_job_overlaps(timeline: List[Dict[str, object]], education_rows: List[Dict[str, object]]) -> List[str]:
    issues = []
    full_time_degrees = ["phd", "ms", "msc", "mphil", "bs", "bsc", "be", "beng", "bachelor", "master"]
    for edu_row in education_rows:
        degree = safe_text(edu_row.get("degree")).lower()
        if not any(token in degree for token in full_time_degrees):
            continue
        end_year = parse_year(edu_row.get("passing_year") or edu_row.get("end_year"))
        if not end_year:
            continue
        years_back = 4 if any(token in degree for token in ["bs", "bsc", "be", "beng", "bachelor"]) else 2
        edu_start = datetime(end_year - years_back, 1, 1)
        edu_end = datetime(end_year, 12, 31)
        for job in timeline:
            overlap_days = (min(job["end"], edu_end) - max(job["start"], edu_start)).days
            if overlap_days > 180:
                issues.append(f"{job['title']} at {job['organization']} overlaps with {safe_text(edu_row.get('degree'), 'degree')} (~{end_year})")
    return issues


def seniority_level(job_title: str) -> int:
    title = safe_text(job_title).lower()
    for level in sorted(SENIORITY_KEYWORDS, reverse=True):
        if any(keyword in title for keyword in SENIORITY_KEYWORDS[level]):
            return level
    return 2


def career_progression_label(timeline: List[Dict[str, object]]) -> str:
    if len(timeline) < 2:
        return "Insufficient Data"
    levels = [seniority_level(item["title"]) for item in timeline]
    count = len(levels)
    xs = list(range(count))
    x_mean = sum(xs) / count
    y_mean = sum(levels) / count
    numerator = sum((xs[idx] - x_mean) * (levels[idx] - y_mean) for idx in range(count))
    denominator = sum((xs[idx] - x_mean) ** 2 for idx in range(count))
    slope = numerator / denominator if denominator else 0
    if slope > 0.1:
        return "Upward"
    if slope < -0.1:
        return "Downward"
    return "Lateral"


def total_experience_years(timeline: List[Dict[str, object]]) -> float:
    if not timeline:
        return 0.0
    earliest = min(item["start"] for item in timeline)
    latest = max(item["end"] for item in timeline)
    return round((latest - earliest).days / 365.25, 2)


def longest_tenure(timeline: List[Dict[str, object]]) -> Tuple[str, float]:
    if not timeline:
        return "", 0.0
    best_duration = -1
    best_label = ""
    for item in timeline:
        years = round((item["end"] - item["start"]).days / 365.25, 2)
        if years > best_duration:
            best_duration = years
            best_label = f"{item['title']} at {item['organization']}"
    return best_label, max(best_duration, 0.0)


def detect_missing_fields_detailed(candidate: Dict[str, object]) -> Dict[str, object]:
    personal = candidate.get("personal", {})
    education = candidate.get("education", [])
    experience = candidate.get("experience", [])
    skills = candidate.get("skills", [])
    publications = candidate.get("publications", [])
    supervision = candidate.get("supervision", [])
    missing_items = []

    for field in REQUIRED_PERSONAL:
        value = personal.get(field) if isinstance(personal, dict) else None
        if not safe_text(value):
            label = field.replace("_", " ").title()
            severity = "Critical" if field == "name" else "High"
            missing_items.append({"section": "Personal Info", "field": label, "severity": severity})

    if not education:
        missing_items.append({"section": "Education", "field": "All education records", "severity": "Critical"})
    else:
        for edu in education:
            degree = safe_text(edu.get("degree"), "degree")
            if not safe_text(edu.get("grade_cgpa") or edu.get("grade_value")):
                missing_items.append({"section": "Education", "field": f"Marks/CGPA for {degree}", "severity": "High"})
            if not safe_text(edu.get("passing_year") or edu.get("end_year")):
                missing_items.append({"section": "Education", "field": f"Passing year for {degree}", "severity": "High"})

    if not experience:
        missing_items.append({"section": "Experience", "field": "All experience records", "severity": "Medium"})
    else:
        for exp in experience:
            role = safe_text(exp.get("role"), "position")
            for field in REQUIRED_EXP_FIELDS:
                if not safe_text(exp.get(field)):
                    label = "Start date" if field == "start_date" else "End date"
                    missing_items.append({"section": "Experience", "field": f"{label} for '{role}'", "severity": "Medium"})

    if not skills:
        missing_items.append({"section": "Skills", "field": "Skills list", "severity": "Medium"})
    if not publications:
        missing_items.append({"section": "Research", "field": "Publication history", "severity": "Low"})
    if not supervision:
        missing_items.append(
            {
                "section": "Supervision",
                "field": "Supervised student names, degree levels, and graduation years",
                "severity": "Medium",
            }
        )

    counts = {
        "Critical": sum(1 for item in missing_items if item["severity"] == "Critical"),
        "High": sum(1 for item in missing_items if item["severity"] == "High"),
        "Medium": sum(1 for item in missing_items if item["severity"] == "Medium"),
        "Low": sum(1 for item in missing_items if item["severity"] == "Low"),
    }
    missing_text = " | ".join(f"[{item['section']}] {item['field']}" for item in missing_items)

    return {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "missing_info_flag": "Yes" if missing_items else "No",
        "missing_count": len(missing_items),
        "critical_count": counts["Critical"],
        "high_count": counts["High"],
        "medium_count": counts["Medium"],
        "low_count": counts["Low"],
        "missing_info_items": "; ".join(item["field"] for item in missing_items) if missing_items else "None",
        "missing_fields": missing_text if missing_items else "None",
        "missing_items": missing_items,
    }


def groq_ready() -> bool:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    return bool(api_key) and not looks_like_placeholder(api_key)


def call_groq_with_retry(prompt: str, system: str, max_tokens: int = 1024, max_retries: int = 3) -> Optional[str]:
    try:
        from groq import Groq
    except Exception:
        return None

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or looks_like_placeholder(api_key):
        return None

    client = Groq(api_key=api_key)
    model = os.getenv("TALASH_GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    delay = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return safe_text(response.choices[0].message.content)
        except Exception as exc:
            error_text = str(exc).lower()
            if any(token in error_text for token in ["429", "503", "rate"]) and attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            return None
    return None


def template_email(candidate_name: str, missing_items: List[Dict[str, str]]) -> str:
    items = "\n".join(f"{idx + 1}. [{item['section']}] {item['field']}" for idx, item in enumerate(missing_items))
    return (
        "Subject: Additional Information Required - Your TALASH Application\n\n"
        f"Dear {candidate_name},\n\n"
        "Thank you for submitting your CV through the TALASH Smart HR Recruitment System.\n\n"
        "Our automated review has identified the following missing or incomplete information:\n\n"
        f"{items}\n\n"
        "Please reply with the above details within 5 working days so your application can be fully evaluated.\n\n"
        "Best regards,\n"
        "TALASH Recruitment Team\n"
        "Faculty of Computing, SEECS, NUST"
    )


def draft_missing_info_email(candidate: Dict[str, object], missing: Dict[str, object]) -> Dict[str, object]:
    missing_items = missing.get("missing_items", [])
    generation_mode = "Template"
    if not missing_items:
        body = (
            f"Subject: TALASH profile update for {candidate['candidate_name']}\n\n"
            f"Dear {candidate['candidate_name']},\n\n"
            "Thank you for submitting your profile to TALASH. Your CV has been processed successfully and "
            "no major missing information was detected at this stage.\n\n"
            "Best regards,\n"
            "TALASH Recruitment Team"
        )
    else:
        items_text = "\n".join(
            f"{idx + 1}. [{item['section']}] {item['field']} (Severity: {item['severity']})"
            for idx, item in enumerate(missing_items)
        )
        prompt = (
            f"Candidate name: {candidate['candidate_name']}\n"
            f"The following information is missing from their CV:\n{items_text}\n\n"
            "Write a professional email requesting this missing information. "
            "Include a subject line at the top starting with 'Subject: '. "
            "Mention each missing item by section and field. "
            "If supervision information is missing, explicitly ask for supervised student names, degree levels, "
            "supervision role (main/co-supervisor), and graduation years. "
            "Close by asking them to reply within 5 working days."
        )
        generated = call_groq_with_retry(prompt, EMAIL_SYSTEM, max_tokens=1024)
        if generated:
            body = generated
            generation_mode = "AI"
        else:
            body = template_email(candidate["candidate_name"], missing_items)

    return {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "draft_email": body,
        "generation_mode": generation_mode,
    }


def template_summary(candidate: Dict[str, object], prof: Dict[str, object], research_overview: Dict[str, object], missing: Dict[str, object], skill_summary: Dict[str, object]) -> str:
    highest = "No recorded qualification"
    if candidate.get("education"):
        highest = safe_text(candidate["education"][0].get("degree"), highest)
    notes = safe_text(prof.get("notes"), "No major issues identified.")
    return (
        f"{candidate['candidate_name']} is being considered for {candidate.get('applied_for') or 'an unspecified role'}. "
        f"The profile shows {prof.get('total_experience_years', 0)} years of experience across {prof.get('total_roles', 0)} recorded roles, "
        f"with {prof.get('career_progression', 'Insufficient Data').lower()} career progression. "
        f"The longest tenure was {prof.get('longest_tenure_role', 'not available')} "
        f"for {prof.get('longest_tenure_years', 0)} years. Highest qualification recorded is {highest}. "
        f"The candidate has {research_overview.get('total_publications', 0)} listed publication(s), "
        f"including {research_overview.get('first_author_publications', 0)} first-author paper(s). "
        f"Claimed skill alignment is {skill_summary.get('skill_alignment_label', 'unknown')} "
        f"with a score of {skill_summary.get('skill_alignment_score', 0)}. "
        f"Missing-information count is {missing.get('missing_count', 0)}. Notes: {notes}"
    )


def generate_candidate_summary(candidate: Dict[str, object], prof: Dict[str, object], missing: Dict[str, object], research_overview: Dict[str, object], skill_summary: Dict[str, object]) -> Dict[str, object]:
    edu_text = "\n".join(
        f"- {safe_text(row.get('degree'), '?')} from {safe_text(row.get('institution'), '?')} ({safe_text(row.get('passing_year'), '?')})"
        for row in candidate.get("education", [])
    ) or "- No education records"
    exp_text = "\n".join(
        f"- {safe_text(row.get('role'), '?')} at {safe_text(row.get('organization'), '?')} ({safe_text(row.get('start_date'), '?')} - {safe_text(row.get('end_date'), '?')})"
        for row in candidate.get("experience", [])
    ) or "- No experience records"
    prompt = (
        f"Candidate: {candidate['candidate_name']}\n"
        f"Applied for: {candidate.get('applied_for') or 'N/A'}\n"
        f"Nationality: {safe_text(candidate.get('personal', {}).get('nationality'), 'N/A')}\n\n"
        f"Education:\n{edu_text}\n\n"
        f"Experience:\n{exp_text}\n\n"
        f"Professional Analysis:\n"
        f"Total years: {prof.get('total_experience_years', 0)}\n"
        f"Career progression: {prof.get('career_progression', 'N/A')}\n"
        f"Gaps: {prof.get('professional_gaps', 'None')}\n"
        f"Overlaps: {prof.get('job_overlaps', 'None')}\n"
        f"Timeline consistent: {prof.get('timeline_consistent', False)}\n\n"
        f"Research:\n"
        f"Total publications: {research_overview.get('total_publications', 0)}\n"
        f"First-author publications: {research_overview.get('first_author_publications', 0)}\n"
        f"Research strength: {research_overview.get('research_strength', 'N/A')}\n\n"
        f"Skill Alignment:\n"
        f"Alignment score: {skill_summary.get('skill_alignment_score', 0)}\n"
        f"Alignment label: {skill_summary.get('skill_alignment_label', 'N/A')}\n"
        f"Strongly evidenced skills: {skill_summary.get('strong_skill_count', 0)}\n\n"
        f"Missing Information: {missing.get('missing_fields', 'None')}\n\n"
        "Write a 150-200 word third-person summary for the hiring committee."
    )
    summary = call_groq_with_retry(prompt, SUMMARY_SYSTEM, max_tokens=512)
    generation_mode = "AI"
    if not summary:
        summary = template_summary(candidate, prof, research_overview, missing, skill_summary)
        generation_mode = "Template"
    return {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "total_experience_years": prof.get("total_experience_years", 0),
        "career_progression": prof.get("career_progression", "N/A"),
        "gap_count": prof.get("gap_count", 0),
        "missing_fields_count": missing.get("missing_count", 0),
        "skill_alignment_score": skill_summary.get("skill_alignment_score", 0),
        "skill_alignment_label": skill_summary.get("skill_alignment_label", "N/A"),
        "candidate_summary": summary,
        "generation_mode": generation_mode,
    }


def analyze_candidate(candidate: Dict[str, object]) -> Dict[str, object]:
    timeline = build_timeline(candidate.get("experience", []))
    if not timeline:
        return {
            "source_file": candidate["source_file"],
            "candidate_name": candidate["candidate_name"],
            "applied_for": candidate.get("applied_for"),
            "present_employment": candidate.get("present_employment"),
            "total_roles": 0,
            "total_experience_years": 0,
            "career_progression": "No Experience",
            "professional_gaps": "",
            "gap_count": 0,
            "professional_gap_flag": "No",
            "professional_gap_detail": "No experience records found",
            "job_overlaps": "",
            "overlap_flag": "No",
            "overlap_detail": "No experience records found",
            "edu_job_overlaps": "",
            "longest_tenure_role": "",
            "longest_tenure_years": 0,
            "timeline_consistent": False,
            "notes": "No experience records found",
            "experience_record_count": len(candidate.get("experience", [])),
        }

    gaps = detect_professional_gaps(timeline)
    overlaps = detect_overlaps(timeline)
    edu_job_overlaps = detect_edu_job_overlaps(timeline, candidate.get("education", []))
    longest_role, longest_years = longest_tenure(timeline)
    missing_dates = sum(
        1
        for row in candidate.get("experience", [])
        if not safe_text(row.get("start_date")) or not safe_text(row.get("end_date"))
    )
    notes = []
    if missing_dates:
        notes.append(f"{missing_dates} role(s) missing start/end dates")
    if gaps:
        notes.append(f"{len(gaps)} employment gap(s) detected")
    if overlaps:
        notes.append(f"{len(overlaps)} job overlap(s) detected")
    if edu_job_overlaps:
        notes.append("Education-job overlap detected")

    gap_strings = [f"{gap['gap_months']}mo after '{gap['after_role']}' ({gap['from']} - {gap['to']})" for gap in gaps]
    overlap_strings = [f"{ov['role_a']} & {ov['role_b']} overlapped {ov['overlap_months']}mo" for ov in overlaps]
    consistent = missing_dates == 0 and not overlaps

    return {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "applied_for": candidate.get("applied_for"),
        "present_employment": candidate.get("present_employment"),
        "total_roles": len(timeline),
        "total_experience_years": total_experience_years(timeline),
        "career_progression": career_progression_label(timeline),
        "professional_gaps": " | ".join(gap_strings),
        "gap_count": len(gaps),
        "professional_gap_flag": "Yes" if gaps else "No",
        "professional_gap_detail": "; ".join(
            f"{gap['after_role']} -> {gap['before_role']}: {gap['gap_months']} months" for gap in gaps
        ) if gaps else "No significant professional gap detected",
        "job_overlaps": " | ".join(overlap_strings),
        "overlap_flag": "Yes" if overlaps else "No",
        "overlap_detail": "; ".join(
            f"{ov['role_a']} with {ov['role_b']}: {ov['overlap_months']} months" for ov in overlaps
        ) if overlaps else "No major overlap detected",
        "edu_job_overlaps": " | ".join(edu_job_overlaps),
        "longest_tenure_role": longest_role,
        "longest_tenure_years": longest_years,
        "timeline_consistent": consistent,
        "notes": "; ".join(notes) if notes else "Clean timeline",
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


def build_research_overview(candidate: Dict[str, object]) -> Dict[str, object]:
    publications = candidate.get("publications", [])
    first_author_count = sum(1 for row in publications if row.get("candidate_is_first_author"))
    journal_count = sum(1 for row in publications if safe_text(row.get("venue_type")).lower() == "journal")
    conference_count = sum(1 for row in publications if safe_text(row.get("venue_type")).lower() == "conference")
    if len(publications) >= 10:
        strength = "Strong"
    elif len(publications) >= 4:
        strength = "Moderate"
    elif len(publications) >= 1:
        strength = "Emerging"
    else:
        strength = "None"
    return {
        "total_publications": len(publications),
        "first_author_publications": first_author_count,
        "journal_publications": journal_count,
        "conference_publications": conference_count,
        "research_strength": strength,
    }


def canonical_skill_label(skill_name: str) -> str:
    lowered = safe_text(skill_name).lower()
    for canonical, keywords in SKILL_TAXONOMY.items():
        if lowered == canonical or any(keyword in lowered for keyword in keywords):
            return canonical
    return lowered


def evidence_text(candidate: Dict[str, object]) -> str:
    parts = [candidate.get("applied_for", "")]
    parts.extend(
        " ".join(
            [
                safe_text(row.get("role")),
                safe_text(row.get("organization")),
                safe_text(row.get("location")),
            ]
        )
        for row in candidate.get("experience", [])
    )
    parts.extend(
        " ".join(
            [
                safe_text(row.get("title")),
                safe_text(row.get("venue")),
                safe_text(row.get("co_authors")),
            ]
        )
        for row in candidate.get("publications", [])
    )
    parts.extend(
        " ".join(
            [
                safe_text(row.get("degree")),
                safe_text(row.get("specialization")),
            ]
        )
        for row in candidate.get("education", [])
    )
    return " ".join(parts).lower()


def evaluate_skill_alignment(candidate: Dict[str, object]) -> Dict[str, object]:
    claimed_skills = [safe_text(skill) for skill in candidate.get("skills", []) if safe_text(skill)]
    text = evidence_text(candidate)
    aligned = []
    strong = 0
    partial = 0
    weak = 0
    unsupported = 0
    for skill in claimed_skills:
        canonical = canonical_skill_label(skill)
        keywords = SKILL_TAXONOMY.get(canonical, [canonical])
        match_count = sum(1 for keyword in keywords if keyword and keyword in text)
        if match_count >= 3:
            strength = "Strongly evidenced"
            strong += 1
        elif match_count >= 1:
            strength = "Partially evidenced"
            partial += 1
        elif len(skill.split()) > 1:
            strength = "Weakly evidenced"
            weak += 1
        else:
            strength = "Unsupported"
            unsupported += 1
        aligned.append(
            {
                "source_file": candidate["source_file"],
                "candidate_name": candidate["candidate_name"],
                "claimed_skill": skill,
                "canonical_skill": canonical,
                "evidence_strength": strength,
                "matched_keywords": ", ".join([keyword for keyword in keywords if keyword in text][:5]) or "None",
            }
        )

    score = 0.0
    total = len(claimed_skills)
    if total:
        score = round(((strong * 1.0) + (partial * 0.65) + (weak * 0.35)) / total * 100, 2)
    if score >= 80:
        label = "High alignment"
    elif score >= 55:
        label = "Moderate alignment"
    elif score > 0:
        label = "Low alignment"
    else:
        label = "No evidence"
    return {
        "summary": {
            "source_file": candidate["source_file"],
            "candidate_name": candidate["candidate_name"],
            "claimed_skill_count": total,
            "strong_skill_count": strong,
            "partial_skill_count": partial,
            "weak_skill_count": weak,
            "unsupported_skill_count": unsupported,
            "skill_alignment_score": score,
            "skill_alignment_label": label,
        },
        "details": aligned,
    }


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
    skill_alignment_rows = []
    skill_alignment_summary_rows = []

    for candidate in candidates:
        experience_rows.extend(build_experience_rows(candidate))
        professional_row = analyze_candidate(candidate)
        missing_row = detect_missing_fields_detailed(candidate)
        research_overview = build_research_overview(candidate)
        skill_alignment = evaluate_skill_alignment(candidate)
        email_row = draft_missing_info_email(candidate, missing_row)
        summary_row = generate_candidate_summary(candidate, professional_row, missing_row, research_overview, skill_alignment["summary"])
        analysis_rows.append(professional_row)
        missing_rows.append(missing_row)
        email_rows.append(email_row)
        summary_rows.append(summary_row)
        skill_alignment_summary_rows.append(skill_alignment["summary"])
        skill_alignment_rows.extend(skill_alignment["details"])

    json_path = write_json(
        {
            "meta": {
                "groq_configured": groq_ready(),
                "groq_model": os.getenv("TALASH_GROQ_MODEL", "llama-3.3-70b-versatile").strip(),
            },
            "experience_rows": experience_rows,
            "professional_analysis": analysis_rows,
            "missing_info_detailed": missing_rows,
            "drafted_emails": email_rows,
            "candidate_summaries": summary_rows,
            "skill_alignment_summary": skill_alignment_summary_rows,
            "skill_alignment_details": skill_alignment_rows,
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
            "Skill Alignment Summary": skill_alignment_summary_rows,
            "Skill Alignment Detail": skill_alignment_rows,
        },
        output_dir / "professional_analysis.xlsx",
    )
    summary_csv = save_csv(summary_rows, output_dir / "candidate_summaries.csv")
    summary_excel = write_workbook({"Candidate Summaries": summary_rows}, output_dir / "candidate_summaries.xlsx")
    missing_csv = save_csv(missing_rows, output_dir / "missing_info_detailed.csv")
    email_csv = save_csv(email_rows, output_dir / "drafted_emails.csv")
    skill_summary_csv = save_csv(skill_alignment_summary_rows, output_dir / "skill_alignment_summary.csv")
    skill_detail_csv = save_csv(skill_alignment_rows, output_dir / "skill_alignment_details.csv")
    mongo_count = save_to_mongodb(analysis_rows) if save_to_mongo and analysis_rows else 0

    return {
        "experience_rows": experience_rows,
        "analysis_rows": analysis_rows,
        "missing_rows": missing_rows,
        "email_rows": email_rows,
        "summary_rows": summary_rows,
        "skill_alignment_rows": skill_alignment_rows,
        "skill_alignment_summary_rows": skill_alignment_summary_rows,
        "json_path": str(json_path),
        "excel_path": str(excel_path),
        "summary_csv": str(summary_csv),
        "summary_excel": str(summary_excel),
        "missing_csv": str(missing_csv),
        "email_csv": str(email_csv),
        "skill_summary_csv": str(skill_summary_csv),
        "skill_detail_csv": str(skill_detail_csv),
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
    print(f"Skill CSV   : {result['skill_summary_csv']}")
    if result["mongo_written"]:
        print(f"Mongo saved : {result['mongo_written']} document(s)")


if __name__ == "__main__":
    main()
