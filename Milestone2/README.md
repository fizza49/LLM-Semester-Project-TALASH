# TALASH – CS417 Milestone 2

## Setup & Run


### 1. Run the app
```bash
python app.py
```

### 2. Open in browser
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
3. Text is sent to Gemni API with a structured prompt
4. Gemni returns JSON: name, education, experience, skills, publications
5. Frontend displays data in tables; user can switch between categories and export CSV
