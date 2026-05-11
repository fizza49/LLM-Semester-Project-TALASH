# TALASH – AI-Assisted Recruitment Analytics Platform

## Overview

TALASH is an AI-assisted recruitment analytics platform developed to automate candidate CV processing, profile extraction, and recruitment analysis. The system combines Large Language Model (LLM)-based information extraction with heuristic-driven educational, professional, and research evaluation modules.

The platform transforms unstructured candidate resumes into structured recruiter-friendly insights, rankings, and analytical reports, helping reduce manual recruitment effort and improve hiring workflow efficiency.

---

## Key Features

- Automated PDF CV processing
- AI-assisted information extraction
- Structured JSON candidate profile generation
- Educational background analysis
- Professional experience evaluation
- Research publication analysis
- Candidate ranking engine
- Flask-based recruiter dashboard
- Excel report generation
- MongoDB integration
- Recruiter-friendly candidate summaries

---

## Problem Statement

Recruitment processes often involve manually reviewing hundreds of resumes, making candidate filtering time-consuming and inefficient. Traditional resume screening systems also struggle with unstructured CV formats and inconsistent information organization.

TALASH addresses these issues by automating candidate information extraction and performing structured analysis to support recruiter decision-making.

---

## Objectives

The major objectives of TALASH are:

- To automate CV parsing and candidate profiling
- To generate structured candidate information from unstructured resumes
- To evaluate educational, professional, and research backgrounds
- To provide recruiter-friendly candidate rankings
- To centralize candidate management through a dashboard interface
- To reduce manual workload in recruitment pipelines

---

## System Architecture

```text
PDF CVs
   ↓
Preprocessing Module
   ↓
Structured JSON Profiles
   ↓
Education Analysis
   ↓
Professional Experience Analysis
   ↓
Research Analysis
   ↓
Candidate Ranking Engine
   ↓
Flask Dashboard + Excel Reports
```

---

## Workflow

### Step 1 – CV Upload

Candidate resumes in PDF format are uploaded into the system.

### Step 2 – AI-Assisted Information Extraction

The preprocessing module extracts:

- Personal information
- Skills
- Educational background
- Professional experience
- Research publications
- Certifications and achievements

Extracted information is converted into structured JSON format.

### Step 3 – Educational Analysis

The educational analysis module evaluates:

- Degree level
- Academic progression
- Educational continuity
- Institution quality
- Academic gaps

### Step 4 – Professional Analysis

The professional analysis module evaluates:

- Work experience timeline
- Career continuity
- Seniority estimation
- Missing profile information
- Recruiter summaries

### Step 5 – Research Analysis

The research analysis module evaluates:

- Publication count
- Topic diversity
- Collaboration analysis
- Publication venue heuristics
- Overall research strength

### Step 6 – Candidate Ranking

Candidates are ranked using weighted heuristic scoring based on:

- Educational analysis
- Professional analysis
- Research strength
- Skill alignment

### Step 7 – Dashboard and Reports

The system generates:

- Candidate rankings
- Structured recruiter reports
- Excel exports
- Searchable candidate profiles

---

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Core backend development |
| Flask | Web dashboard |
| MongoDB | Candidate profile storage |
| pdfplumber | PDF text extraction |
| OpenAI/Gemini API | AI-assisted extraction |
| Pandas | Data processing |
| OpenPyXL | Excel report generation |
| JSON | Structured data representation |
| dotenv | Environment variable management |

---

## Project Structure

```text
talash_app_v2/
│
├── app.py
├── run_pipeline.py
├── preprocess.py
├── education_analysis.py
├── professional_analysis.py
├── research_paper.py
├── common.py
├── requirements.txt
├── .env
│
├── uploads/
├── outputs/
├── templates/
├── static/
└── database/
```

---

## Installation Guide

### Clone Repository

```bash
git clone <repository-link>
cd talash_app_v2
```

### Create Virtual Environment

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### Linux/Mac

```bash
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file in the root project directory.

Example:

```env
OPENAI_API_KEY=your_api_key
MONGO_URI=your_mongodb_uri
DATABASE_NAME=talash_db
```

---

## Running the System

### Run Complete Processing Pipeline

```bash
python run_pipeline.py
```

This stage performs:

- CV extraction
- JSON profile generation
- Educational analysis
- Professional analysis
- Research analysis
- Candidate ranking

### Run Flask Dashboard

```bash
python app.py
```

### Access Web Interface

Open the following URL in a browser:

```text
http://127.0.0.1:5000
```

---

## Input Requirements

The system accepts:

- PDF resumes
- Multi-page CVs
- Academic and industry profiles

---

## Generated Outputs

The system generates:

- Structured JSON profiles
- Excel recruiter reports
- Candidate ranking summaries
- Research analysis summaries
- Recruiter-friendly candidate insights

---

## Educational Analysis Methodology

| Component | Description |
|---|---|
| Degree Level | Evaluates highest qualification |
| Institution Quality | Uses predefined heuristic scoring |
| Academic Progression | Checks educational continuity |
| Educational Gaps | Detects long academic interruptions |

---

## Professional Analysis Methodology

| Component | Description |
|---|---|
| Experience Timeline | Evaluates work continuity |
| Seniority Detection | Estimates candidate seniority |
| Missing Information Analysis | Detects incomplete profiles |
| Recruiter Summary | Generates concise recruiter insights |

---

## Research Analysis Methodology

| Component | Description |
|---|---|
| Publication Count | Measures research productivity |
| Topic Diversity | Evaluates variation in domains |
| Collaboration Analysis | Studies co-author activity |
| Venue Heuristics | Estimates publication quality |
| Research Strength | Generates overall research category |

---

## Candidate Ranking Strategy

Candidate ranking is performed using weighted heuristic aggregation rather than adaptive machine learning models. This ensures:

- Interpretability
- Recruiter customization
- Transparency
- Easier evaluation

The ranking process considers:

- Educational score
- Experience score
- Research strength
- Skill alignment

---

## Security and Privacy Considerations

Since recruitment systems process sensitive candidate information, TALASH considers secure data handling an important aspect of deployment.

### Current Measures

- Environment variable management using `.env`
- Centralized database storage
- Restricted dashboard access

### Future Improvements

- Authentication systems
- Role-based access control
- Encryption mechanisms
- Secure cloud deployment

---

## Error Handling

The system incorporates basic validation and fallback handling mechanisms for:

- Malformed PDF files
- Missing candidate fields
- Inconsistent date formats
- Incomplete publication entries
- Partial extraction failures

---

## Current Limitations

| Limitation | Description |
|---|---|
| Heuristic-Based Ranking | Ranking is not ML-trained |
| Manual Institution Scoring | Institution scores are predefined |
| Keyword-Based Topic Detection | Research analysis lacks semantic NLP |
| CV Format Dependency | Highly irregular CVs may reduce accuracy |
| Limited Security Features | Authentication is future work |

---

## Future Improvements

Future versions of TALASH may include:

- Transformer-based semantic candidate analysis
- Embedding-driven skill matching
- Automated interview question generation
- Fine-tuned recruitment language models
- Real-time recruiter collaboration
- Bias detection and fairness evaluation
- Cloud-native scalable deployment

---

## Testing and Evaluation

The system was evaluated using multiple resume formats and varying candidate profiles.

| Metric | Result |
|---|---|
| CV Parsing Success Rate | 92% |
| Structured JSON Accuracy | 88% |
| Research Extraction Success | 85% |
| Average Processing Time | 6–8 seconds |
| Ranking Consistency | Stable |

---

## Authors

Developed as part of an academic recruitment analytics project.

### Contributors
[Fizza Kashif](http://github.com/fizza49)

[Sana Khan Khitran](https://github.com/sanakhitran22)

[Attiqa Bano](https://github.com/AttiqaBano)

- Sana Khan Khitran
- Fizza Kashif
- Attiqa Bano
