# TALASH – CS417 Milestone 1

## Setup & Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your google api key 
```bash
$env:GEMINI_API_KEY="your_actual_api_key_here"
$env:TALASH_LLM="gemini"
```
# CLI (processes all CVs in cv_folder/)
```bash
python preprocess.py
```


### 3. Run the app
```bash
python app.py
```

### 4. Open in browser
```
http://127.0.0.1:5000
```

---

## Project Structure

```
talash_app/
├── app.py                  ← Flask backend
├── requirements.txt
├── uploads/                ← Uploaded CVs saved here
├── templates/
│   └── index.html          ← Main HTML page
└── static/
    ├── css/
    │   └── style.css       ← All styling
    └── js/
        └── app.js          ← Frontend logic
```

---

## How It Works

1. User uploads a PDF CV via the web UI
2. Flask saves it and extracts text using `pdfplumber`
3. Text is sent to Claude API with a structured prompt
4. Claude returns JSON: name, education, experience, skills, publications
5. Frontend displays data in tables; user can switch between categories and export CSV
