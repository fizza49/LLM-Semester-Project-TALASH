"""
TALASH - CS417 Milestone 1
Research/publication analysis: JSON in, Excel + JSON + MongoDB out
"""

import html
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv

from common import RESEARCH_DIR, read_json, upsert_many, write_json, write_workbook

load_dotenv()


def normalize_preprocessed_candidate(candidate: Dict[str, object]) -> Dict[str, object]:
    personal = candidate.get("personal", {}) if isinstance(candidate.get("personal"), dict) else {}
    return {
        "source_file": candidate.get("_source_file", "unknown.pdf"),
        "candidate_name": personal.get("name") or candidate.get("_source_file", "Unknown"),
        "applied_for": personal.get("applied_for"),
        "publications": candidate.get("publications", []) if isinstance(candidate.get("publications"), list) else [],
    }


def build_publication_rows(candidate: Dict[str, object]) -> List[Dict[str, object]]:
    rows = []
    for row in candidate.get("publications", []):
        rows.append(
            {
                "source_file": candidate["source_file"],
                "candidate_name": candidate["candidate_name"],
                "applied_for": candidate.get("applied_for"),
                "title": row.get("title"),
                "first_author": row.get("first_author"),
                "co_authors": row.get("co_authors"),
                "venue": row.get("venue"),
                "venue_type": row.get("venue_type"),
                "impact_factor": row.get("impact_factor"),
                "volume": row.get("volume"),
                "pages": row.get("pages"),
                "year": row.get("year"),
                "candidate_is_first_author": "Yes" if row.get("candidate_is_first_author") else "No",
            }
        )
    return rows


def analyze_candidate(candidate: Dict[str, object]) -> Dict[str, object]:
    publications = candidate.get("publications", [])
    journal_count = sum(1 for row in publications if str(row.get("venue_type", "")).lower() == "journal")
    conference_count = sum(1 for row in publications if str(row.get("venue_type", "")).lower() == "conference")
    first_author_count = sum(1 for row in publications if row.get("candidate_is_first_author"))
    impact_values = []
    for row in publications:
        value = row.get("impact_factor")
        try:
            if value not in (None, ""):
                impact_values.append(float(value))
        except Exception:
            continue

    return {
        "source_file": candidate["source_file"],
        "candidate_name": candidate["candidate_name"],
        "applied_for": candidate.get("applied_for"),
        "total_publications": len(publications),
        "journal_publications": journal_count,
        "conference_publications": conference_count,
        "first_author_publications": first_author_count,
        "avg_impact_factor": round(sum(impact_values) / len(impact_values), 2) if impact_values else 0.0,
        "research_strength": (
            "Strong" if len(publications) >= 10 else
            "Moderate" if len(publications) >= 4 else
            "Emerging" if len(publications) >= 1 else
            "None"
        ),
    }


def create_charts(publication_rows: List[Dict[str, object]], analysis_rows: List[Dict[str, object]], output_dir: Path) -> List[str]:
    chart_files = []

    analysis_df = pd.DataFrame(analysis_rows)
    pub_df = pd.DataFrame(publication_rows)

    if not analysis_df.empty:
        plt.style.use("ggplot")

        plt.figure(figsize=(8, 5))
        top_candidates = analysis_df.sort_values("total_publications", ascending=False).head(10)
        plt.barh(top_candidates["candidate_name"], top_candidates["total_publications"], color="#2F5D8A")
        plt.gca().invert_yaxis()
        plt.title("Top Candidates by Publications")
        plt.xlabel("Total Publications")
        plt.tight_layout()
        file1 = output_dir / "top_publications.png"
        plt.savefig(file1, dpi=200)
        plt.close()
        chart_files.append(file1.name)

        plt.figure(figsize=(7, 5))
        strength_counts = analysis_df["research_strength"].value_counts()
        strength_counts.plot(kind="bar", color="#2A9D8F")
        plt.title("Research Strength Distribution")
        plt.xlabel("Strength")
        plt.ylabel("Candidates")
        plt.tight_layout()
        file2 = output_dir / "research_strength_distribution.png"
        plt.savefig(file2, dpi=200)
        plt.close()
        chart_files.append(file2.name)

        plt.figure(figsize=(7, 5))
        plt.scatter(
            analysis_df["total_publications"],
            analysis_df["avg_impact_factor"],
            color="#E76F51",
            alpha=0.8,
        )
        plt.title("Publications vs Average Impact Factor")
        plt.xlabel("Total Publications")
        plt.ylabel("Average Impact Factor")
        plt.tight_layout()
        file3 = output_dir / "publications_vs_impact.png"
        plt.savefig(file3, dpi=200)
        plt.close()
        chart_files.append(file3.name)

    if not pub_df.empty:
        plt.figure(figsize=(7, 5))
        type_counts = pub_df["venue_type"].fillna("Unknown").value_counts()
        plt.pie(type_counts, labels=type_counts.index, autopct="%1.1f%%")
        plt.title("Publication Type Distribution")
        plt.tight_layout()
        file4 = output_dir / "publication_type_distribution.png"
        plt.savefig(file4, dpi=200)
        plt.close()
        chart_files.append(file4.name)

    return chart_files


def generate_dashboard_html(publication_rows: List[Dict[str, object]], analysis_rows: List[Dict[str, object]], chart_files: List[str], output_dir: Path) -> Path:
    cards = []
    for row in sorted(analysis_rows, key=lambda item: item.get("total_publications", 0), reverse=True):
        cards.append(
            f"""
            <div class="card">
              <h3>{html.escape(str(row.get('candidate_name', 'Unknown')))}</h3>
              <p><strong>Applied For:</strong> {html.escape(str(row.get('applied_for', '—')))}</p>
              <p><strong>Total Publications:</strong> {row.get('total_publications', 0)}</p>
              <p><strong>Journal Publications:</strong> {row.get('journal_publications', 0)}</p>
              <p><strong>Conference Publications:</strong> {row.get('conference_publications', 0)}</p>
              <p><strong>First Author Publications:</strong> {row.get('first_author_publications', 0)}</p>
              <p><strong>Average Impact Factor:</strong> {row.get('avg_impact_factor', 0)}</p>
              <p><strong>Research Strength:</strong> {html.escape(str(row.get('research_strength', '—')))}</p>
            </div>
            """
        )

    charts_html = "\n".join(
        f'<div class="chart-card"><img src="{html.escape(name)}" alt="{html.escape(name)}"></div>'
        for name in chart_files
    )

    table_rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(str(row.get('candidate_name', '')))}</td>
          <td>{html.escape(str(row.get('title', '')))}</td>
          <td>{html.escape(str(row.get('venue', '')))}</td>
          <td>{html.escape(str(row.get('venue_type', '')))}</td>
          <td>{html.escape(str(row.get('year', '')))}</td>
          <td>{html.escape(str(row.get('candidate_is_first_author', '')))}</td>
        </tr>
        """
        for row in publication_rows
    )

    html_text = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TALASH Research Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; background: #f6f8fc; color: #1a1a2e; }}
    h1, h2 {{ margin-bottom: 8px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    .card, .chart-card {{ background: white; border-radius: 12px; padding: 16px; box-shadow: 0 8px 24px rgba(0,0,0,0.08); }}
    img {{ width: 100%; border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; margin-top: 16px; }}
    th, td {{ padding: 10px; border: 1px solid #d9deea; text-align: left; }}
    th {{ background: #1a1a2e; color: white; }}
  </style>
</head>
<body>
  <h1>TALASH Research Dashboard</h1>
  <p>Standalone research analysis dashboard generated from candidate publication data.</p>

  <h2>Charts</h2>
  <div class="grid">{charts_html}</div>

  <h2>Candidate Research Profiles</h2>
  <div class="grid">{''.join(cards)}</div>

  <h2>Publication Table</h2>
  <table>
    <thead>
      <tr>
        <th>Candidate</th>
        <th>Title</th>
        <th>Venue</th>
        <th>Type</th>
        <th>Year</th>
        <th>First Author</th>
      </tr>
    </thead>
    <tbody>{table_rows}</tbody>
  </table>
</body>
</html>
"""
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
    analysis_rows = []
    for candidate in candidates:
        publication_rows.extend(build_publication_rows(candidate))
        analysis_rows.append(analyze_candidate(candidate))

    chart_files = create_charts(publication_rows, analysis_rows, output_dir)
    dashboard_path = generate_dashboard_html(publication_rows, analysis_rows, chart_files, output_dir)
    json_path = write_json({"publications": publication_rows, "analysis": analysis_rows}, output_dir / "research_analysis.json")
    excel_path = write_workbook(
        {
            "Publication Records": publication_rows,
            "Research Analysis": analysis_rows,
        },
        output_dir / "research_analysis.xlsx",
    )
    mongo_count = save_to_mongodb(analysis_rows) if save_to_mongo and analysis_rows else 0

    return {
        "publication_rows": publication_rows,
        "analysis_rows": analysis_rows,
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
