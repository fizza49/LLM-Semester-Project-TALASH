"""
Run TALASH preprocessing, education, professional, and research modules in sequence.
"""

import sys
from pathlib import Path

from common import EDUCATION_DIR, PREPROCESS_DIR, PROFESSIONAL_DIR, RESEARCH_DIR
from education_analysis import process_preprocessed_json as run_education_analysis
from preprocess import run_pipeline as run_preprocess
from professional_analysis import process_preprocessed_json as run_professional_analysis
from research_paper import process_preprocessed_json as run_research_analysis


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:\n  python run_pipeline.py <input_pdf_or_folder>\n")
        sys.exit(1)

    input_path = sys.argv[1]

    print("Step 1: Preprocessing")
    preprocess_result = run_preprocess(input_path, str(PREPROCESS_DIR), save_to_mongo=True)

    print("\nStep 2: Education analysis")
    education_result = run_education_analysis(preprocess_result["json_path"], str(EDUCATION_DIR), save_to_mongo=True)

    print("\nStep 3: Professional analysis")
    professional_result = run_professional_analysis(preprocess_result["json_path"], str(PROFESSIONAL_DIR), save_to_mongo=True)

    print("\nStep 4: Research analysis")
    research_result = run_research_analysis(preprocess_result["json_path"], str(RESEARCH_DIR), save_to_mongo=True)

    print("\nPipeline completed successfully.")
    print(f"Preprocess output   : {Path(preprocess_result['output_dir']).resolve()}")
    print(f"Education output    : {Path(education_result['output_dir']).resolve()}")
    print(f"Professional output : {Path(professional_result['output_dir']).resolve()}")
    print(f"Research output     : {Path(research_result['output_dir']).resolve()}")


if __name__ == "__main__":
    main()
