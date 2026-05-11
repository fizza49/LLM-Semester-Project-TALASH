"""
TALASH education analysis:
- degree normalization
- marks normalization
- progression and gap analysis
- institution quality enrichment
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv

from common import DATA_DIR, EDUCATION_DIR, read_json, read_json_if_exists, upsert_many, write_json, write_workbook

load_dotenv()


LEVEL_RANK = {
    "SSC": 1,
    "HSSC": 2,
    "BACHELOR": 3,
    "MASTER": 4,
    "MPHIL": 5,
    "PHD": 6,
    "OTHER": 0,
}

LEVEL_ALIASES = {
    "doctorate": "PHD",
    "phd": "PHD",
    "mphil": "MPHIL",
    "m phil": "MPHIL",
    "master": "MASTER",
    "msc": "MASTER",
    "ms": "MASTER",
    "mba": "MASTER",
    "bachelor": "BACHELOR",
    "bsc": "BACHELOR",
    "bs": "BACHELOR",
    "be": "BACHELOR",
    "hssc": "HSSC",
    "fsc": "HSSC",
    "intermediate": "HSSC",
    "a level": "HSSC",
    "ssc": "SSC",
    "matric": "SSC",
    "o level": "SSC",
}

EXPECTED_GAP_BUFFER = {
    ("SSC", "HSSC"): 1,
    ("HSSC", "BACHELOR"): 1,
    ("HSSC", "MASTER"): 2,
    ("BACHELOR", "MASTER"): 2,
    ("MASTER", "MPHIL"): 1,
    ("MASTER", "PHD"): 2,
    ("MPHIL", "PHD"): 1,
}

INSTITUTION_HINTS = {
    "nust": {"label": "Excellent", "score": 95},
    "lums": {"label": "Excellent", "score": 94},
    "comsats": {"label": "Strong", "score": 88},
    "uet": {"label": "Strong", "score": 84},
    "giki": {"label": "Strong", "score": 89},
    "fast": {"label": "Strong", "score": 87},
    "air university": {"label": "Strong", "score": 82},
    "iiu": {"label": "Moderate", "score": 74},
    "international islamic university": {"label": "Moderate", "score": 74},
    "university of": {"label": "Moderate", "score": 70},
    "board": {"label": "Board/School", "score": 55},
    "bise": {"label": "Board/School", "score": 55},
}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def detect_level(level: str, degree: str) -> str:
    level_text = re.sub(r"[^a-z0-9]+", " ", clean_text(level).lower())
    degree_text = re.sub(r"[^a-z0-9]+", " ", clean_text(degree).lower())
    for key, mapped in sorted(LEVEL_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = rf"\b{re.escape(key)}\b"
        if re.search(pattern, level_text) or re.search(pattern, degree_text):
            return mapped
    return "OTHER"


def normalize_grade(grade_value: str, grade_type: str) -> Optional[float]:
    if not grade_value:
        return None
    match = re.search(r"\d+(?:\.\d+)?", str(grade_value))
    if not match:
        return None
    value = float(match.group())
    gtype = clean_text(grade_type).lower()
    if "cgpa" in gtype or value <= 5:
        scale = 4.0 if value <= 4.0 else 5.0
        return round((value / scale) * 100, 2)
    if "percent" in gtype or value > 5:
        return round(min(value, 100.0), 2)
    return None


def parse_year(value: str) -> Optional[int]:
    if not value:
        return None
    match = re.search(r"(19|20)\d{2}", str(value))
    return int(match.group()) if match else None


def normalize_institution_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_text(name).lower()).strip()


def load_institution_rankings():
    ranking_data = read_json_if_exists(DATA_DIR / "institution_rankings.json", {})
    if isinstance(ranking_data, list):
        normalized = {}
        for item in ranking_data:
            aliases = item.get("aliases", []) if isinstance(item, dict) else []
            for alias in aliases:
                normalized[normalize_institution_name(alias)] = item
        return normalized
    if isinstance(ranking_data, dict):
        return {normalize_institution_name(key): value for key, value in ranking_data.items()}
    return {}


INSTITUTION_RANKINGS = load_institution_rankings()


def assess_institution_quality(institution: str) -> Dict[str, object]:
    normalized = normalize_institution_name(institution)
    if not normalized:
        return {
            "institution_quality_label": "Unknown",
            "institution_quality_score": 0,
            "qs_rank": None,
            "the_rank": None,
            "ranking_status": "Unavailable",
        }

    for key, item in INSTITUTION_RANKINGS.items():
        if key and (key in normalized or normalized in key):
            qs_rank = item.get("qs_rank")
            the_rank = item.get("the_rank")
            raw_score = item.get("score")
            if raw_score is None:
                rank_values = [value for value in [qs_rank, the_rank] if isinstance(value, int)]
                if rank_values:
                    best_rank = min(rank_values)
                    raw_score = max(40, 100 - min(best_rank, 600) / 10)
                else:
                    raw_score = 70
            score = round(float(raw_score), 2)
            label = item.get("label") or ("Excellent" if score >= 90 else "Strong" if score >= 80 else "Moderate" if score >= 65 else "Developing")
            return {
                "institution_quality_label": label,
                "institution_quality_score": score,
                "qs_rank": qs_rank,
                "the_rank": the_rank,
                "ranking_status": "Verified",
            }

    for token, info in INSTITUTION_HINTS.items():
        if token in normalized:
            return {
                "institution_quality_label": info["label"],
                "institution_quality_score": info["score"],
                "qs_rank": None,
                "the_rank": None,
                "ranking_status": "Heuristic",
            }

    return {
        "institution_quality_label": "Unverified",
        "institution_quality_score": 60,
        "qs_rank": None,
        "the_rank": None,
        "ranking_status": "Unavailable",
    }


def normalize_preprocessed_candidate(candidate: Dict[str, object]) -> Dict[str, object]:
    personal = candidate.get("personal", {}) if isinstance(candidate.get("personal"), dict) else {}
    education = candidate.get("education", []) if isinstance(candidate.get("education"), list) else []
    experience = candidate.get("experience", []) if isinstance(candidate.get("experience"), list) else []
    cleaned = []
    for row in education:
        if not isinstance(row, dict):
            continue
        institution = row.get("institution")
        ranking = assess_institution_quality(institution)
        cleaned.append(
            {
                "level": detect_level(row.get("level", ""), row.get("degree", "")),
                "degree": row.get("degree"),
                "specialization": row.get("specialization"),
                "institution": institution,
                "grade_value": row.get("grade_cgpa") or row.get("grade_value"),
                "grade_type": row.get("grade_type"),
                "start_year": row.get("start_year"),
                "end_year": row.get("end_year") or row.get("passing_year"),
                "passing_year": row.get("passing_year"),
                **ranking,
            }
        )
    return {
        "source_file": candidate.get("_source_file", "unknown.pdf"),
        "candidate_name": personal.get("name") or candidate.get("_source_file", "Unknown"),
        "applied_for": personal.get("applied_for"),
        "education": cleaned,
        "experience": experience,
    }


def estimate_program_duration(level: str, degree: str) -> int:
    degree_lower = clean_text(degree).lower()
    if level in {"SSC", "HSSC"}:
        return 2
    if level == "BACHELOR":
        if "bsc" in degree_lower and "engineering" not in degree_lower and "bs" not in degree_lower:
            return 2
        return 4
    if level in {"MASTER", "MPHIL"}:
        return 2
    if level == "PHD":
        return 4
    return 2


def parse_experience_periods(candidate: Dict[str, object]) -> List[Dict[str, Optional[int]]]:
    periods = []
    for row in candidate.get("experience", []):
        if not isinstance(row, dict):
            continue
        periods.append({"role": row.get("role"), "start_year": parse_year(row.get("start_date")), "end_year": parse_year(row.get("end_date"))})
    return [period for period in periods if period.get("start_year") or period.get("end_year")]


def calculate_gap_analysis(candidate: Dict[str, object]) -> Dict[str, object]:
    rows = []
    for row in candidate.get("education", []):
        level = row.get("level", "OTHER")
        degree = row.get("degree", "")
        start_year = parse_year(row.get("start_year"))
        end_year = parse_year(row.get("end_year")) or parse_year(row.get("passing_year"))
        duration = estimate_program_duration(level, degree)
        if end_year is None and start_year is not None:
            end_year = start_year + duration
        if start_year is None and end_year is not None:
            start_year = end_year - duration
        if start_year is None and end_year is None:
            continue
        rows.append({"level": level, "degree": degree, "start_year": start_year, "end_year": end_year})

    rows.sort(key=lambda item: (item["start_year"] if item["start_year"] is not None else 9999, item["end_year"] if item["end_year"] is not None else 9999))
    experience_periods = parse_experience_periods(candidate)
    total_gap_years = 0
    unexplained_gap_years = 0
    unexplained = []
    justified = []
    for current, nxt in zip(rows, rows[1:]):
        if current["end_year"] is None or nxt["start_year"] is None:
            continue
        raw_gap = nxt["start_year"] - current["end_year"]
        allowed = EXPECTED_GAP_BUFFER.get((current["level"], nxt["level"]), 1)
        effective_gap = max(raw_gap - allowed, 0)
        if effective_gap <= 0:
            continue
        total_gap_years += effective_gap
        gap_start = current["end_year"]
        gap_end = nxt["start_year"]
        covered = False
        for period in experience_periods:
            start = period.get("start_year")
            end = period.get("end_year") or start
            if start is None:
                continue
            if start < gap_end and end > gap_start:
                covered = True
                justified.append(f"{current['level']} to {nxt['level']}: {effective_gap} year(s) justified by {period.get('role') or 'experience'}")
                break
        if not covered:
            unexplained_gap_years += effective_gap
            unexplained.append(f"{current['level']} to {nxt['level']}: {effective_gap} year(s)")
    detail_parts = []
    if unexplained:
        detail_parts.append("Unexplained gaps: " + "; ".join(unexplained))
    if justified:
        detail_parts.append("Justified gaps: " + "; ".join(justified))
    return {
        "education_gap_years": total_gap_years,
        "unexplained_gap_years": unexplained_gap_years,
        "education_gap_flag": "Yes" if total_gap_years > 0 else "No",
        "gap_justification_flag": "Yes" if justified else "No",
        "education_gap_detail": " | ".join(detail_parts) if detail_parts else "No significant gap detected",
    }


def analyze_specialization_consistency(education_rows: List[Dict[str, object]]) -> Dict[str, str]:
    higher = []
    for row in education_rows:
        if row.get("level") in {"BACHELOR", "MASTER", "MPHIL", "PHD"}:
            spec = clean_text(row.get("specialization")).lower()
            if spec:
                higher.append(spec)
    if len(higher) <= 1:
        return {"specialization_consistency": "Consistent", "specialization_track": ", ".join(higher) if higher else "Not available"}
    tokens = [set(re.findall(r"[a-z]+", spec)) for spec in higher]
    overlap = set.intersection(*tokens) if all(tokens) else set()
    return {"specialization_consistency": "Consistent" if overlap else "Mixed", "specialization_track": " -> ".join(higher)}


def analyze_marks_trend(education_rows: List[Dict[str, object]]) -> str:
    scored = []
    for row in education_rows:
        score = row.get("normalized_marks")
        if score is None:
            continue
        scored.append((LEVEL_RANK.get(row.get("level", "OTHER"), 0), score))
    scored.sort(key=lambda item: item[0])
    if len(scored) < 2:
        return "Insufficient data"
    delta = scored[-1][1] - scored[0][1]
    if delta >= 5:
        return "Improving"
    if delta <= -5:
        return "Declining"
    return "Stable"


def analyze_candidate(candidate: Dict[str, object]) -> Dict[str, object]:
    education = candidate.get("education", [])
    if not education:
        return {
            "source_file": candidate["source_file"],
            "candidate_name": candidate["candidate_name"],
            "applied_for": candidate.get("applied_for"),
            "highest_degree": "None",
            "highest_degree_rank": 0,
            "avg_normalized_marks": 0.0,
            "education_gap_years": 0,
            "unexplained_gap_years": 0,
            "education_gap_flag": "Yes",
            "gap_justification_flag": "No",
            "education_gap_detail": "No education data extracted",
            "specialization_consistency": "Not available",
            "specialization_track": "Not available",
            "marks_trend": "Insufficient data",
            "education_score": 0.0,
            "education_strength": "Weak",
            "avg_institution_quality_score": 0.0,
            "institution_quality_label": "Unknown",
            "best_qs_rank": None,
            "best_the_rank": None,
        }

    highest_rank = 0
    highest_degree = "OTHER"
    marks = []
    quality_scores = []
    qs_ranks = []
    the_ranks = []
    quality_labels = []
    for row in education:
        level = row.get("level", "OTHER")
        rank = LEVEL_RANK.get(level, 0)
        if rank > highest_rank:
            highest_rank = rank
            highest_degree = level
        normalized = normalize_grade(row.get("grade_value"), row.get("grade_type"))
        row["normalized_marks"] = normalized
        if normalized is not None:
            marks.append(normalized)
        quality_scores.append(float(row.get("institution_quality_score", 0) or 0))
        if isinstance(row.get("qs_rank"), int):
            qs_ranks.append(row["qs_rank"])
        if isinstance(row.get("the_rank"), int):
            the_ranks.append(row["the_rank"])
        quality_labels.append(row.get("institution_quality_label", "Unknown"))

    avg_marks = round(sum(marks) / len(marks), 2) if marks else 0.0
    avg_institution_quality = round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else 0.0
    gap_info = calculate_gap_analysis(candidate)
    specialization = analyze_specialization_consistency(education)
    marks_trend = analyze_marks_trend(education)

    degree_score = min((highest_rank / 6) * 35, 35)
    marks_score = min((avg_marks / 100) * 35, 35)
    continuity_bonus = 0 if gap_info["unexplained_gap_years"] > 0 else 12
    consistency_bonus = 8 if specialization["specialization_consistency"] == "Consistent" else 3
    institution_bonus = min((avg_institution_quality / 100) * 10, 10)
    education_score = round(min(degree_score + marks_score + continuity_bonus + consistency_bonus + institution_bonus, 100), 2)

    if education_score >= 82:
        strength = "Very Strong"
    elif education_score >= 68:
        strength = "Strong"
    elif education_score >= 52:
        strength = "Moderate"
    else:
        strength = "Weak"

    institution_quality_label = max(set(quality_labels), key=quality_labels.count) if quality_labels else "Unknown"

    return {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "applied_for": candidate.get("applied_for"),
        "highest_degree": highest_degree,
        "highest_degree_rank": highest_rank,
        "avg_normalized_marks": avg_marks,
        "education_gap_years": gap_info["education_gap_years"],
        "unexplained_gap_years": gap_info["unexplained_gap_years"],
        "education_gap_flag": gap_info["education_gap_flag"],
        "gap_justification_flag": gap_info["gap_justification_flag"],
        "education_gap_detail": gap_info["education_gap_detail"],
        "specialization_consistency": specialization["specialization_consistency"],
        "specialization_track": specialization["specialization_track"],
        "marks_trend": marks_trend,
        "education_score": education_score,
        "education_strength": strength,
        "avg_institution_quality_score": avg_institution_quality,
        "institution_quality_label": institution_quality_label,
        "best_qs_rank": min(qs_ranks) if qs_ranks else None,
        "best_the_rank": min(the_ranks) if the_ranks else None,
    }


def build_education_rows(candidate: Dict[str, object]) -> List[Dict[str, object]]:
    rows = []
    for row in candidate.get("education", []):
        rows.append(
            {
                "source_file": candidate["source_file"],
                "candidate_name": candidate["candidate_name"],
                "applied_for": candidate.get("applied_for"),
                "level": row.get("level"),
                "degree": row.get("degree"),
                "specialization": row.get("specialization"),
                "institution": row.get("institution"),
                "grade_value": row.get("grade_value"),
                "grade_type": row.get("grade_type"),
                "normalized_marks": row.get("normalized_marks"),
                "start_year": row.get("start_year"),
                "end_year": row.get("end_year"),
                "passing_year": row.get("passing_year"),
                "institution_quality_label": row.get("institution_quality_label"),
                "institution_quality_score": row.get("institution_quality_score"),
                "qs_rank": row.get("qs_rank"),
                "the_rank": row.get("the_rank"),
                "ranking_status": row.get("ranking_status"),
            }
        )
    return rows


def create_charts(analysis_rows: List[Dict[str, object]], output_dir: Path) -> None:
    if not analysis_rows:
        return
    analysis_df = pd.DataFrame(analysis_rows)
    plt.style.use("ggplot")

    degree_counts = analysis_df["highest_degree"].value_counts().sort_index()
    plt.figure(figsize=(8, 5))
    degree_counts.plot(kind="bar", color="#2F5D8A")
    plt.title("Highest Degree Distribution")
    plt.tight_layout()
    plt.savefig(output_dir / "highest_degree_distribution.png", dpi=200)
    plt.close()

    plt.figure(figsize=(8, 5))
    analysis_df["education_score"].plot(kind="hist", bins=10, color="#2A9D8F", edgecolor="black")
    plt.title("Education Score Distribution")
    plt.tight_layout()
    plt.savefig(output_dir / "education_score_distribution.png", dpi=200)
    plt.close()

    top_marks = analysis_df.sort_values("avg_normalized_marks", ascending=False).head(10)
    plt.figure(figsize=(10, 6))
    plt.barh(top_marks["candidate_name"], top_marks["avg_normalized_marks"], color="#E76F51")
    plt.gca().invert_yaxis()
    plt.title("Top 10 Candidates by Normalized Marks")
    plt.tight_layout()
    plt.savefig(output_dir / "top10_normalized_marks.png", dpi=200)
    plt.close()

    gap_counts = analysis_df["education_gap_flag"].value_counts()
    plt.figure(figsize=(6, 6))
    plt.pie(gap_counts, labels=gap_counts.index, autopct="%1.1f%%", colors=["#264653", "#F4A261"])
    plt.title("Educational Gap Detection")
    plt.tight_layout()
    plt.savefig(output_dir / "education_gap_pie.png", dpi=200)
    plt.close()

    quality_counts = analysis_df["institution_quality_label"].fillna("Unknown").value_counts()
    plt.figure(figsize=(8, 5))
    quality_counts.plot(kind="bar", color="#6B8E23")
    plt.title("Institution Quality Distribution")
    plt.tight_layout()
    plt.savefig(output_dir / "institution_quality_distribution.png", dpi=200)
    plt.close()

    trend_counts = analysis_df["marks_trend"].fillna("Unknown").value_counts()
    plt.figure(figsize=(8, 5))
    trend_counts.plot(kind="bar", color="#8A5CF6")
    plt.title("Marks Trend Distribution")
    plt.tight_layout()
    plt.savefig(output_dir / "marks_trend_distribution.png", dpi=200)
    plt.close()


def save_to_mongodb(analysis_rows: List[Dict[str, object]]) -> int:
    return upsert_many("education_analysis", analysis_rows, ["source_file", "candidate_name"])


def process_preprocessed_json(input_json: str, output_folder: Optional[str] = None, save_to_mongo: bool = True) -> Dict[str, object]:
    input_path = Path(input_json)
    output_dir = Path(output_folder) if output_folder else EDUCATION_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_candidates = read_json(input_path)
    if not isinstance(raw_candidates, list):
        raise ValueError("Preprocessed JSON must contain a list of candidates.")

    candidates = []
    education_rows = []
    analysis_rows = []
    for raw_candidate in raw_candidates:
        candidate = normalize_preprocessed_candidate(raw_candidate)
        analysis = analyze_candidate(candidate)
        candidates.append(candidate)
        education_rows.extend(build_education_rows(candidate))
        analysis_rows.append(analysis)

    json_path = write_json({"candidates": candidates, "analysis": analysis_rows}, output_dir / "education_extracted.json")
    excel_path = write_workbook({"Education Records": education_rows, "Education Analysis": analysis_rows}, output_dir / "education_analysis.xlsx")
    create_charts(analysis_rows, output_dir)
    mongo_count = save_to_mongodb(analysis_rows) if save_to_mongo and analysis_rows else 0
    return {
        "candidates": candidates,
        "education_rows": education_rows,
        "analysis_rows": analysis_rows,
        "json_path": str(json_path),
        "excel_path": str(excel_path),
        "output_dir": str(output_dir),
        "mongo_written": mongo_count,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:\n  python education_analysis.py <preprocessed_json> [output_dir]\n")
        sys.exit(1)
    result = process_preprocessed_json(sys.argv[1], sys.argv[2] if len(sys.argv) >= 3 else None)
    print(f"JSON saved  : {result['json_path']}")
    print(f"Excel saved : {result['excel_path']}")
    if result["mongo_written"]:
        print(f"Mongo saved : {result['mongo_written']} document(s)")


if __name__ == "__main__":
    main()
