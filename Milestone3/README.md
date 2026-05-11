# TALASH - CS417 Milestone 3

TALASH is a faculty hiring intelligence dashboard that parses academic CVs and produces:

- structured extraction from PDF CVs
- education scoring and institution-quality enrichment
- professional timeline analysis and missing-info follow-up emails
- research-paper verification, authorship analytics, and topic analysis
- composite candidate ranking for shortlist support

## Demo-Ready Features

- Gemini-backed CV extraction
- Groq-backed candidate summaries and follow-up emails
- configured venue verification from `data/venue_rankings.json`
- configured institution-quality enrichment from `data/institution_rankings.json`
- composite ranking based on education, skills, research strength, publications, and experience

## Setup

### 1. Python

Use Python `3.12` or newer.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure `.env`

Add the following keys before running the app:

```env
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here
MONGODB_URI=your_mongodb_connection_string
MONGODB_DB=TALASH
TALASH_GEMINI_MODEL=gemini-3.1-flash-lite-preview
TALASH_GROQ_MODEL=llama-3.3-70b-versatile
```

`GROQ_API_KEY` is required if you want AI-generated candidate summaries and drafted emails. If it is missing, TALASH now shows template fallback instead of failing silently.

### 4. Run the app

```bash
python app.py
```

### 5. Open in browser

```text
http://127.0.0.1:5000
```

## Verification Data

- `data/venue_rankings.json` contains configured venue entries used for demo-time verification labels.
- `data/institution_rankings.json` contains configured institution entries used by the education module.
- If a venue or institution is not found in these files, TALASH falls back to heuristic labeling.

## Composite Ranking

The dashboard now computes a composite candidate score using:

- `education_score`
- `skill_alignment_score`
- `research_strength`
- `total_publications`
- `total_experience_years`

Candidates are sorted by this score and displayed with rank numbers in the UI and exports.

## Journal Verification Note

For the current milestone submission, venue verification is performed from the configured local reference database in `data/venue_rankings.json`, with heuristic fallback when a venue is missing. For a production deployment, this should be extended with broader synchronized data from Clarivate WoS, Scopus, and CORE.
