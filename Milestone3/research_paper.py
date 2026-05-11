"""
TALASH research analysis:
- publication records and venue verification
- authorship analytics
- topic variability and collaboration patterns
- supervision/books/patents analysis
"""

import html
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv

from common import DATA_DIR, RESEARCH_DIR, read_json, read_json_if_exists, upsert_many, write_json, write_workbook

load_dotenv()


VENUE_HINTS = {
    "ieee": {"publisher": "IEEE", "wos_indexed": "Likely", "scopus_indexed": "Likely", "legitimacy_status": "Recognized"},
    "acm": {"publisher": "ACM", "wos_indexed": "Likely", "scopus_indexed": "Likely", "legitimacy_status": "Recognized"},
    "springer": {"publisher": "Springer", "wos_indexed": "Possible", "scopus_indexed": "Likely", "legitimacy_status": "Recognized"},
    "elsevier": {"publisher": "Elsevier", "wos_indexed": "Possible", "scopus_indexed": "Likely", "legitimacy_status": "Recognized"},
    "scientific reports": {"publisher": "Nature", "wos_indexed": "Yes", "scopus_indexed": "Yes", "legitimacy_status": "Recognized"},
    "journal": {"publisher": "Journal", "wos_indexed": "Unknown", "scopus_indexed": "Unknown", "legitimacy_status": "Needs verification"},
    "conference": {"publisher": "Conference", "wos_indexed": "Unknown", "scopus_indexed": "Unknown", "legitimacy_status": "Needs verification"},
}

TOPIC_KEYWORDS = {
    "computer vision": ["vision", "image", "video", "detection", "segmentation", "human action"],
    "machine learning": ["learning", "classification", "random forest", "prediction", "feature"],
    "deep learning": ["deep learning", "neural", "cnn", "lstm", "network"],
    "power systems": ["power", "energy", "grid", "turbine", "electrical"],
    "signal processing": ["signal", "spectral", "wavelet", "filter"],
    "biomedical": ["ecg", "biomedical", "cancer", "depression", "suicide"],
    "embedded systems": ["embedded", "iot", "iiot", "tinyml"],
    "software/web": ["software", "web", "dashboard", "api", "system"],
}


def safe_text(value, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text and text.lower() not in {"nan", "none", "null"} else fallback


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", safe_text(name).lower()).strip()


def load_venue_rankings():
    ranking_data = read_json_if_exists(DATA_DIR / "venue_rankings.json", {})
    if isinstance(ranking_data, dict):
        return {normalize_name(key): value for key, value in ranking_data.items()}
    if isinstance(ranking_data, list):
        mapped = {}
        for item in ranking_data:
            aliases = item.get("aliases", []) if isinstance(item, dict) else []
            for alias in aliases:
                mapped[normalize_name(alias)] = item
        return mapped
    return {}


VENUE_RANKINGS = load_venue_rankings()


def normalize_preprocessed_candidate(candidate: Dict[str, object]) -> Dict[str, object]:
    personal = candidate.get("personal", {}) if isinstance(candidate.get("personal"), dict) else {}
    return {
        "source_file": candidate.get("_source_file", "unknown.pdf"),
        "candidate_name": safe_text(personal.get("name"), candidate.get("_source_file", "Unknown")),
        "applied_for": safe_text(personal.get("applied_for")),
        "publications": candidate.get("publications", []) if isinstance(candidate.get("publications"), list) else [],
        "supervision": candidate.get("supervision", []) if isinstance(candidate.get("supervision"), list) else [],
        "books": candidate.get("books", []) if isinstance(candidate.get("books"), list) else [],
        "patents": candidate.get("patents", []) if isinstance(candidate.get("patents"), list) else [],
    }


def parse_authors(publication: Dict[str, object]) -> List[str]:
    authors = []
    first_author = safe_text(publication.get("first_author"))
    if first_author:
        authors.append(first_author)
    co_authors = safe_text(publication.get("co_authors"))
    if co_authors:
        authors.extend([part.strip() for part in re.split(r";|,|\band\b", co_authors) if part.strip()])
    cleaned = []
    seen = set()
    for author in authors:
        lowered = author.lower()
        if lowered not in seen:
            seen.add(lowered)
            cleaned.append(author)
    return cleaned


def detect_authorship_role(candidate_name: str, authors: List[str]) -> Tuple[str, int]:
    if not authors:
        return "Unknown", -1
    candidate_tokens = set(normalize_name(candidate_name).split())
    match_index = -1
    for index, author in enumerate(authors):
        author_tokens = set(normalize_name(author).split())
        if candidate_tokens & author_tokens:
            match_index = index
            break
    if match_index == -1:
        return "Unknown", -1
    if match_index == 0:
        return "First Author", match_index
    if match_index == 1:
        return "Second Author", match_index
    if match_index == len(authors) - 1 and len(authors) > 2:
        return "Last Author", match_index
    return "Co-Author", match_index


def verify_venue(venue: str, venue_type: str) -> Dict[str, object]:
    normalized = normalize_name(venue)
    if normalized in VENUE_RANKINGS:
        info = VENUE_RANKINGS[normalized]
        return {
            "publisher": info.get("publisher", "Unknown"),
            "wos_indexed": info.get("wos_indexed", "Unknown"),
            "scopus_indexed": info.get("scopus_indexed", "Unknown"),
            "quartile": info.get("quartile", "Unknown"),
            "core_rank": info.get("core_rank", "Unknown"),
            "legitimacy_status": info.get("legitimacy_status", "Verified"),
            "verification_mode": "Configured",
            "verification_source": info.get("verification_source", "Configured venue database"),
            "verification_note": info.get("verification_note", ""),
        }
    for token, info in VENUE_HINTS.items():
        if token in normalized:
            return {
                "publisher": info.get("publisher", "Unknown"),
                "wos_indexed": info.get("wos_indexed", "Unknown"),
                "scopus_indexed": info.get("scopus_indexed", "Unknown"),
                "quartile": "Unknown",
                "core_rank": "Unknown" if safe_text(venue_type).lower() != "conference" else "Unverified",
                "legitimacy_status": info.get("legitimacy_status", "Needs verification"),
                "verification_mode": "Heuristic",
                "verification_source": "Keyword heuristic",
                "verification_note": "Publisher/token matched, but no configured database entry was found.",
            }
    return {
        "publisher": "Unknown",
        "wos_indexed": "Unknown",
        "scopus_indexed": "Unknown",
        "quartile": "Unknown",
        "core_rank": "Unknown",
        "legitimacy_status": "Needs verification",
        "verification_mode": "Unavailable",
        "verification_source": "No configured match",
        "verification_note": "Add this venue to data/venue_rankings.json for explicit verification.",
    }


def detect_topics(title: str, venue: str) -> List[str]:
    text = f"{safe_text(title)} {safe_text(venue)}".lower()
    matches = [topic for topic, keywords in TOPIC_KEYWORDS.items() if any(keyword in text for keyword in keywords)]
    return matches or ["general"]


def venue_quality_score(verification: Dict[str, object], venue_type: str) -> float:
    score = 45.0
    if verification.get("legitimacy_status") == "Recognized":
        score += 18
    if verification.get("wos_indexed") in {"Yes", "Likely"}:
        score += 12
    if verification.get("scopus_indexed") in {"Yes", "Likely"}:
        score += 12
    quartile = safe_text(verification.get("quartile"))
    if quartile == "Q1":
        score += 12
    elif quartile == "Q2":
        score += 8
    elif quartile == "Q3":
        score += 5
    elif quartile == "Q4":
        score += 2
    if safe_text(venue_type).lower() == "conference" and safe_text(verification.get("core_rank")) in {"A*", "A"}:
        score += 12
    return round(min(score, 100), 2)


def build_publication_rows(candidate: Dict[str, object]) -> List[Dict[str, object]]:
    rows = []
    for row in candidate.get("publications", []):
        authors = parse_authors(row)
        role, position = detect_authorship_role(candidate["candidate_name"], authors)
        verification = verify_venue(row.get("venue"), row.get("venue_type"))
        topics = detect_topics(row.get("title"), row.get("venue"))
        rows.append(
            {
                "source_file": candidate["source_file"],
                "candidate_name": candidate["candidate_name"],
                "applied_for": candidate.get("applied_for"),
                "title": row.get("title"),
                "first_author": row.get("first_author"),
                "co_authors": row.get("co_authors"),
                "authors": ", ".join(authors),
                "author_list_parsed": "; ".join(authors),
                "venue": row.get("venue"),
                "venue_type": row.get("venue_type"),
                "impact_factor": row.get("impact_factor"),
                "volume": row.get("volume"),
                "pages": row.get("pages"),
                "year": row.get("year"),
                "candidate_is_first_author": "Yes" if row.get("candidate_is_first_author") else "No",
                "authorship_role": role,
                "author_position": position,
                "co_author_count": max(len(authors) - 1, 0),
                "publisher": verification["publisher"],
                "wos_indexed": verification["wos_indexed"],
                "scopus_indexed": verification["scopus_indexed"],
                "quartile": verification["quartile"],
                "core_rank": verification["core_rank"],
                "legitimacy_status": verification["legitimacy_status"],
                "verification_mode": verification["verification_mode"],
                "verification_source": verification["verification_source"],
                "verification_note": verification["verification_note"],
                "venue_quality_score": venue_quality_score(verification, row.get("venue_type")),
                "topic_tags": ", ".join(topics),
            }
        )
    return rows


def authorship_rows_from_publications(publication_rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    return [
        {
            "source_file": row["source_file"],
            "candidate_name": row["candidate_name"],
            "title": row["title"],
            "year": row["year"],
            "publication_type": row["venue_type"],
            "venue": row["venue"],
            "authorship_role": row["authorship_role"],
            "author_position": row["author_position"],
            "co_author_count": row["co_author_count"],
            "publisher": row["publisher"],
            "venue_quality_score": row["venue_quality_score"],
        }
        for row in publication_rows
    ]


def build_collaboration_summary(candidate: Dict[str, object], publication_rows: List[Dict[str, object]]) -> Dict[str, object]:
    coauthor_counter = Counter()
    team_sizes = []
    for row in publication_rows:
        authors = [author.strip() for author in safe_text(row.get("author_list_parsed")).split(";") if author.strip()]
        normalized_candidate = normalize_name(candidate["candidate_name"])
        collaborators = [author for author in authors if normalize_name(author) != normalized_candidate]
        team_sizes.append(len(collaborators))
        for collaborator in collaborators:
            coauthor_counter[collaborator] += 1
    recurring = {name: count for name, count in coauthor_counter.items() if count > 1}
    recurring_papers = sum(1 for row in publication_rows if int(row.get("co_author_count") or 0) > 0)
    total_papers = len(publication_rows)
    recurring_ratio = round(recurring_papers / total_papers * 100, 2) if total_papers else 0.0
    unique_coauthors = len(coauthor_counter)
    diversity_score = round(unique_coauthors / total_papers, 2) if total_papers else 0.0
    return {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "unique_coauthors": unique_coauthors,
        "average_coauthors_per_paper": round(sum(team_sizes) / total_papers, 2) if total_papers else 0.0,
        "recurring_collaborator_count": len(recurring),
        "recurring_collaboration_ratio": recurring_ratio,
        "top_collaborators": "; ".join(f"{name} ({count})" for name, count in coauthor_counter.most_common(5)) or "None",
        "collaboration_diversity_score": diversity_score,
    }


def build_topic_summary(candidate: Dict[str, object], publication_rows: List[Dict[str, object]]) -> Dict[str, object]:
    topic_counter = Counter()
    yearly_topic_counter = Counter()
    for row in publication_rows:
        topics = [topic.strip() for topic in safe_text(row.get("topic_tags")).split(",") if topic.strip()]
        year = safe_text(row.get("year"), "Unknown")
        for topic in topics:
            topic_counter[topic] += 1
            yearly_topic_counter[(year, topic)] += 1
    total = sum(topic_counter.values())
    dominant_topic, dominant_count = topic_counter.most_common(1)[0] if topic_counter else ("Unknown", 0)
    if total and dominant_count / total >= 0.55:
        focus = "Focused"
    elif total:
        focus = "Interdisciplinary"
    else:
        focus = "No publications"
    return {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "dominant_topic": dominant_topic,
        "dominant_topic_share": round(dominant_count / total * 100, 2) if total else 0.0,
        "topic_diversity_score": round(len(topic_counter) / max(len(publication_rows), 1), 2) if publication_rows else 0.0,
        "research_focus_type": focus,
        "topic_distribution": "; ".join(f"{topic} ({count})" for topic, count in topic_counter.most_common()) or "None",
    }


def build_supervision_rows(candidate: Dict[str, object], publication_rows: List[Dict[str, object]]) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    rows = []
    student_names = []
    main_count = 0
    co_count = 0
    publication_links = 0
    for item in candidate.get("supervision", []):
        student_name = safe_text(item.get("student_name"))
        role = safe_text(item.get("role"))
        if role.lower().startswith("main"):
            main_count += 1
        elif role:
            co_count += 1
        if student_name:
            student_names.append(student_name)
        linked_titles = []
        for row in publication_rows:
            authors_blob = safe_text(row.get("authors")).lower()
            if student_name and normalize_name(student_name) and normalize_name(student_name) in normalize_name(authors_blob):
                publication_links += 1
                linked_titles.append(safe_text(row.get("title")))
        rows.append(
            {
                "source_file": candidate["source_file"],
                "candidate_name": candidate["candidate_name"],
                "student_name": student_name,
                "degree_level": item.get("degree_level"),
                "role": role,
                "graduation_year": item.get("graduation_year"),
                "linked_publications": "; ".join(linked_titles) or "None",
            }
        )
    summary = {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "main_supervision_count": main_count,
        "co_supervision_count": co_count,
        "supervised_students_count": len(student_names),
        "student_publication_links": publication_links,
    }
    return rows, summary


def build_book_rows(candidate: Dict[str, object]) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    rows = []
    sole = 0
    lead = 0
    co = 0
    for item in candidate.get("books", []):
        authors = [author.strip() for author in re.split(r";|,|\band\b", safe_text(item.get("authors"))) if author.strip()]
        role = "Unknown"
        if len(authors) == 1:
            role = "Sole author"
            sole += 1
        elif authors and normalize_name(authors[0]) == normalize_name(candidate["candidate_name"]):
            role = "Lead author"
            lead += 1
        elif authors:
            role = "Co-author"
            co += 1
        publisher = safe_text(item.get("publisher"))
        credibility = "Recognized" if any(token in publisher.lower() for token in ["springer", "wiley", "oxford", "cambridge", "pearson", "crc"]) else ("Provided" if publisher else "Unknown")
        rows.append(
            {
                "source_file": candidate["source_file"],
                "candidate_name": candidate["candidate_name"],
                "title": item.get("title"),
                "authors": item.get("authors"),
                "isbn": item.get("isbn"),
                "publisher": publisher,
                "year": item.get("year"),
                "link": item.get("link"),
                "authorship_role": role,
                "publisher_credibility": credibility,
            }
        )
    summary = {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "books_count": len(rows),
        "sole_authored_books": sole,
        "lead_authored_books": lead,
        "co_authored_books": co,
    }
    return rows, summary


def build_patent_rows(candidate: Dict[str, object]) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    rows = []
    lead = 0
    co = 0
    for item in candidate.get("patents", []):
        inventors = [name.strip() for name in re.split(r";|,|\band\b", safe_text(item.get("inventors"))) if name.strip()]
        role = "Unknown"
        if inventors and normalize_name(inventors[0]) == normalize_name(candidate["candidate_name"]):
            role = "Lead inventor"
            lead += 1
        elif inventors:
            role = "Co-inventor"
            co += 1
        rows.append(
            {
                "source_file": candidate["source_file"],
                "candidate_name": candidate["candidate_name"],
                "title": item.get("title"),
                "patent_number": item.get("patent_number"),
                "filing_date": item.get("filing_date"),
                "inventors": item.get("inventors"),
                "country": item.get("country"),
                "link": item.get("link"),
                "inventor_role": role,
                "verification_available": "Yes" if safe_text(item.get("link")) else "No",
            }
        )
    summary = {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "patent_count": len(rows),
        "lead_inventor_patents": lead,
        "co_inventor_patents": co,
    }
    return rows, summary


def analyze_candidate(
    candidate: Dict[str, object],
    publication_rows: List[Dict[str, object]],
    collaboration_summary: Dict[str, object],
    topic_summary: Dict[str, object],
    supervision_summary: Dict[str, object],
    book_summary: Dict[str, object],
    patent_summary: Dict[str, object],
) -> Dict[str, object]:
    journals = sum(1 for row in publication_rows if safe_text(row.get("venue_type")).lower() == "journal")
    conferences = sum(1 for row in publication_rows if safe_text(row.get("venue_type")).lower() == "conference")
    first_author = sum(1 for row in publication_rows if row.get("authorship_role") == "First Author")
    co_author = sum(1 for row in publication_rows if row.get("authorship_role") in {"Co-Author", "Second Author", "Last Author"})
    impact_values = []
    years = []
    venues = set()
    quality_scores = []
    for row in publication_rows:
        try:
            if safe_text(row.get("impact_factor")):
                impact_values.append(float(row["impact_factor"]))
        except Exception:
            pass
        try:
            if safe_text(row.get("year")):
                years.append(int(float(row["year"])))
        except Exception:
            pass
        if safe_text(row.get("venue")):
            venues.add(safe_text(row.get("venue")))
        quality_scores.append(float(row.get("venue_quality_score") or 0))
    total = len(publication_rows)
    if total >= 10:
        strength = "Strong"
    elif total >= 4:
        strength = "Moderate"
    elif total >= 1:
        strength = "Emerging"
    else:
        strength = "None"
    span = ""
    if years:
        span = f"{min(years)}-{max(years)}" if min(years) != max(years) else str(years[0])
    return {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "applied_for": candidate.get("applied_for"),
        "total_publications": total,
        "journal_publications": journals,
        "conference_publications": conferences,
        "first_author_publications": first_author,
        "corresponding_publications": 0,
        "co_author_publications": co_author,
        "unknown_role_publications": total - first_author - co_author,
        "publication_span": span,
        "unique_venues": len(venues),
        "papers_with_doi": 0,
        "avg_impact_factor": round(sum(impact_values) / len(impact_values), 2) if impact_values else 0.0,
        "avg_venue_quality_score": round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else 0.0,
        "research_strength": strength,
        "research_active": "Yes" if total > 0 else "No",
        "average_coauthors_per_paper": collaboration_summary["average_coauthors_per_paper"],
        "recurring_collaboration_ratio": collaboration_summary["recurring_collaboration_ratio"],
        "dominant_topic": topic_summary["dominant_topic"],
        "dominant_topic_share": topic_summary["dominant_topic_share"],
        "topic_diversity_score": topic_summary["topic_diversity_score"],
        "research_focus_type": topic_summary["research_focus_type"],
        "supervised_students_count": supervision_summary["supervised_students_count"],
        "books_count": book_summary["books_count"],
        "patent_count": patent_summary["patent_count"],
    }


def create_charts(
    publication_rows: List[Dict[str, object]],
    analysis_rows: List[Dict[str, object]],
    collaboration_rows: List[Dict[str, object]],
    topic_rows: List[Dict[str, object]],
    output_dir: Path,
) -> List[str]:
    chart_files = []
    analysis_df = pd.DataFrame(analysis_rows)
    pub_df = pd.DataFrame(publication_rows)
    collab_df = pd.DataFrame(collaboration_rows)
    topic_df = pd.DataFrame(topic_rows)
    if analysis_df.empty:
        return chart_files

    plt.style.use("ggplot")

    top_candidates = analysis_df.sort_values("total_publications", ascending=False).head(15)
    if not top_candidates.empty and top_candidates["total_publications"].sum() > 0:
        plt.figure(figsize=(10, 5))
        plt.bar(top_candidates["candidate_name"].str[:24], top_candidates["total_publications"], color="#2563EB")
        plt.xticks(rotation=40, ha="right")
        plt.title("Top Candidates by Total Publications")
        plt.tight_layout()
        path = output_dir / "top_publications.png"
        plt.savefig(path, dpi=180)
        plt.close()
        chart_files.append(path.name)

    if not pub_df.empty:
        type_counts = pub_df["venue_type"].fillna("Unknown").value_counts()
        plt.figure(figsize=(8, 5))
        plt.pie(type_counts.values, labels=type_counts.index, autopct="%1.1f%%")
        plt.title("Publication Type Distribution")
        plt.tight_layout()
        path = output_dir / "publication_type_distribution.png"
        plt.savefig(path, dpi=180)
        plt.close()
        chart_files.append(path.name)

        role_counts = pub_df["authorship_role"].fillna("Unknown").value_counts()
        plt.figure(figsize=(8, 5))
        plt.barh(role_counts.index, role_counts.values, color="#10B981")
        plt.gca().invert_yaxis()
        plt.title("Authorship Role Distribution")
        plt.tight_layout()
        path = output_dir / "authorship_role_distribution.png"
        plt.savefig(path, dpi=180)
        plt.close()
        chart_files.append(path.name)

        year_counts = pd.to_numeric(pub_df["year"], errors="coerce").dropna().astype(int).value_counts().sort_index()
        if not year_counts.empty:
            plt.figure(figsize=(10, 4))
            plt.plot(year_counts.index, year_counts.values, "o-", color="#7C3AED", linewidth=2)
            plt.fill_between(year_counts.index, year_counts.values, color="#7C3AED", alpha=0.2)
            plt.title("Publications per Year")
            plt.tight_layout()
            path = output_dir / "yearly_publication_trend.png"
            plt.savefig(path, dpi=180)
            plt.close()
            chart_files.append(path.name)

    plt.figure(figsize=(8, 5))
    analysis_df["research_strength"].value_counts().plot(kind="bar", color="#F59E0B")
    plt.title("Research Strength Distribution")
    plt.tight_layout()
    path = output_dir / "research_strength_distribution.png"
    plt.savefig(path, dpi=180)
    plt.close()
    chart_files.append(path.name)

    if not collab_df.empty:
        plt.figure(figsize=(8, 5))
        top_collab = collab_df.sort_values("unique_coauthors", ascending=False).head(10)
        plt.barh(top_collab["candidate_name"], top_collab["unique_coauthors"], color="#00B4D8")
        plt.gca().invert_yaxis()
        plt.title("Collaboration Network Size")
        plt.tight_layout()
        path = output_dir / "collaboration_network_size.png"
        plt.savefig(path, dpi=180)
        plt.close()
        chart_files.append(path.name)

    if not topic_df.empty:
        plt.figure(figsize=(8, 5))
        focus_counts = topic_df["research_focus_type"].value_counts()
        focus_counts.plot(kind="bar", color="#E76F51")
        plt.title("Research Focus Type")
        plt.tight_layout()
        path = output_dir / "research_focus_distribution.png"
        plt.savefig(path, dpi=180)
        plt.close()
        chart_files.append(path.name)

    return chart_files


def generate_dashboard_html(
    analysis_rows: List[Dict[str, object]],
    publication_rows: List[Dict[str, object]],
    authorship_rows: List[Dict[str, object]],
    collaboration_rows: List[Dict[str, object]],
    topic_rows: List[Dict[str, object]],
    chart_files: List[str],
    output_dir: Path,
) -> Path:
    cards = []
    collaboration_lookup = {row["source_file"]: row for row in collaboration_rows}
    topic_lookup = {row["source_file"]: row for row in topic_rows}
    for row in sorted(analysis_rows, key=lambda item: item.get("total_publications", 0), reverse=True):
        collab = collaboration_lookup.get(row["source_file"], {})
        topic = topic_lookup.get(row["source_file"], {})
        cards.append(
            f"""
            <div class="card">
              <h3>{html.escape(str(row.get('candidate_name', 'Unknown')))}</h3>
              <p><strong>Applied for:</strong> {html.escape(str(row.get('applied_for', '-')))}</p>
              <p><strong>Total publications:</strong> {row.get('total_publications', 0)}</p>
              <p><strong>Research strength:</strong> {html.escape(str(row.get('research_strength', '-')))}</p>
              <p><strong>Dominant topic:</strong> {html.escape(str(topic.get('dominant_topic', '-')))}</p>
              <p><strong>Unique co-authors:</strong> {collab.get('unique_coauthors', 0)}</p>
            </div>
            """
        )
    charts_html = "\n".join(f'<div class="chart-card"><img src="{html.escape(name)}" alt="{html.escape(name)}"></div>' for name in chart_files)
    paper_rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(safe_text(row.get('candidate_name')))}</td>
          <td>{html.escape(safe_text(row.get('title')))}</td>
          <td>{html.escape(safe_text(row.get('venue')))}</td>
          <td>{html.escape(safe_text(row.get('quartile')))}</td>
          <td>{html.escape(safe_text(row.get('authorship_role')))}</td>
          <td>{html.escape(safe_text(row.get('topic_tags')))}</td>
        </tr>
        """
        for row in publication_rows
    )
    author_rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(safe_text(row.get('candidate_name')))}</td>
          <td>{html.escape(safe_text(row.get('title')))}</td>
          <td>{html.escape(safe_text(row.get('authorship_role')))}</td>
          <td>{html.escape(safe_text(row.get('author_position')))}</td>
          <td>{html.escape(safe_text(row.get('venue_quality_score')))}</td>
        </tr>
        """
        for row in authorship_rows
    )
    html_text = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TALASH Research Dashboard</title>
  <style>
    body {{ font-family: Segoe UI, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }}
    header {{ padding: 24px 32px; border-bottom: 1px solid #334155; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); }}
    h1 {{ margin: 0; font-size: 28px; }}
    p {{ color: #94a3b8; }}
    main {{ padding: 28px 32px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
    .card, .chart-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 14px; padding: 18px; }}
    img {{ width: 100%; border-radius: 12px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; background: #1e293b; border: 1px solid #334155; border-radius: 12px; overflow: hidden; }}
    th, td {{ padding: 12px; border-bottom: 1px solid #334155; text-align: left; }}
    th {{ background: #263348; color: #94a3b8; }}
    section {{ margin-top: 28px; }}
  </style>
</head>
<body>
  <header>
    <h1>TALASH Research Dashboard</h1>
    <p>Research papers, venue verification, authorship analytics, topic variability, and collaboration insights.</p>
  </header>
  <main>
    <section>
      <h2>Charts</h2>
      <div class="grid">{charts_html}</div>
    </section>
    <section>
      <h2>Candidate Profiles</h2>
      <div class="grid">{''.join(cards)}</div>
    </section>
    <section>
      <h2>Research Papers</h2>
      <table>
        <thead><tr><th>Candidate</th><th>Title</th><th>Venue</th><th>Quartile</th><th>Role</th><th>Topics</th></tr></thead>
        <tbody>{paper_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Authorship</h2>
      <table>
        <thead><tr><th>Candidate</th><th>Paper</th><th>Role</th><th>Position</th><th>Quality Score</th></tr></thead>
        <tbody>{author_rows}</tbody>
      </table>
    </section>
  </main>
</body>
</html>"""
    path = output_dir / "dashboard.html"
    path.write_text(html_text, encoding="utf-8")
    return path


def save_to_mongodb(rows: List[Dict[str, object]]) -> int:
    return upsert_many("research_analysis", rows, ["source_file", "candidate_name"])


def process_preprocessed_json(input_json: str, output_folder: Optional[str] = None, save_to_mongo: bool = True) -> Dict[str, object]:
    input_path = Path(input_json)
    output_dir = Path(output_folder) if output_folder else RESEARCH_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_candidates = read_json(input_path)
    if not isinstance(raw_candidates, list):
        raise ValueError("Preprocessed JSON must contain a list of candidates.")

    candidates = [normalize_preprocessed_candidate(item) for item in raw_candidates]
    publication_rows = []
    authorship_rows = []
    collaboration_rows = []
    topic_rows = []
    supervision_rows = []
    supervision_summary_rows = []
    book_rows = []
    book_summary_rows = []
    patent_rows = []
    patent_summary_rows = []
    analysis_rows = []

    for candidate in candidates:
        candidate_publications = build_publication_rows(candidate)
        candidate_authorship = authorship_rows_from_publications(candidate_publications)
        collaboration_summary = build_collaboration_summary(candidate, candidate_publications)
        topic_summary = build_topic_summary(candidate, candidate_publications)
        candidate_supervision_rows, supervision_summary = build_supervision_rows(candidate, candidate_publications)
        candidate_book_rows, book_summary = build_book_rows(candidate)
        candidate_patent_rows, patent_summary = build_patent_rows(candidate)

        publication_rows.extend(candidate_publications)
        authorship_rows.extend(candidate_authorship)
        collaboration_rows.append(collaboration_summary)
        topic_rows.append(topic_summary)
        supervision_rows.extend(candidate_supervision_rows)
        supervision_summary_rows.append(supervision_summary)
        book_rows.extend(candidate_book_rows)
        book_summary_rows.append(book_summary)
        patent_rows.extend(candidate_patent_rows)
        patent_summary_rows.append(patent_summary)
        analysis_rows.append(
            analyze_candidate(
                candidate,
                candidate_publications,
                collaboration_summary,
                topic_summary,
                supervision_summary,
                book_summary,
                patent_summary,
            )
        )

    chart_files = create_charts(publication_rows, analysis_rows, collaboration_rows, topic_rows, output_dir)
    dashboard_path = generate_dashboard_html(analysis_rows, publication_rows, authorship_rows, collaboration_rows, topic_rows, chart_files, output_dir)
    json_path = write_json(
        {
            "publications": publication_rows,
            "analysis": analysis_rows,
            "authorship_roles": authorship_rows,
            "collaboration_analysis": collaboration_rows,
            "topic_analysis": topic_rows,
            "supervision_records": supervision_rows,
            "supervision_summary": supervision_summary_rows,
            "books_analysis": book_rows,
            "books_summary": book_summary_rows,
            "patents_analysis": patent_rows,
            "patents_summary": patent_summary_rows,
        },
        output_dir / "research_analysis.json",
    )
    excel_path = write_workbook(
        {
            "Publication Records": publication_rows,
            "Research Analysis": analysis_rows,
            "Authorship Roles": authorship_rows,
            "Collaboration": collaboration_rows,
            "Topics": topic_rows,
            "Supervision": supervision_rows,
            "Book Analysis": book_rows,
            "Patent Analysis": patent_rows,
        },
        output_dir / "research_analysis.xlsx",
    )
    mongo_count = save_to_mongodb(analysis_rows) if save_to_mongo and analysis_rows else 0
    return {
        "publication_rows": publication_rows,
        "analysis_rows": analysis_rows,
        "authorship_rows": authorship_rows,
        "collaboration_rows": collaboration_rows,
        "topic_rows": topic_rows,
        "supervision_rows": supervision_rows,
        "book_rows": book_rows,
        "patent_rows": patent_rows,
        "json_path": str(json_path),
        "excel_path": str(excel_path),
        "dashboard_path": str(dashboard_path),
        "chart_files": chart_files,
        "output_dir": str(output_dir),
        "mongo_written": mongo_count,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:\n  python research_paper.py <preprocessed_json> [output_dir]\n")
        sys.exit(1)
    result = process_preprocessed_json(sys.argv[1], sys.argv[2] if len(sys.argv) >= 3 else None)
    print(f"JSON saved  : {result['json_path']}")
    print(f"Excel saved : {result['excel_path']}")
    print(f"Dashboard   : {result['dashboard_path']}")
    if result["mongo_written"]:
        print(f"Mongo saved : {result['mongo_written']} document(s)")


if __name__ == "__main__":
    main()
