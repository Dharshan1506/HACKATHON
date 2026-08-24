# PackSure AI – Legal Metrology Compliance Checker

PackSure AI is an AI-powered and deterministic rule-based pre-market compliance engine that automatically audits packaged commodity labels under the **Legal Metrology Act, 2009** and the **Legal Metrology (Packaged Commodities) Rules, 2011 (PCR 2011)**.

---

## ⚡ Quick Start: Run Everything in ONE File in VS Code

You can run the entire frontend, backend, OCR, AI extraction, rules engine, database, and PDF generator in a **single Python file**:

### Method 1: In VS Code Terminal
```bash
py packsure_app.py
```

### Method 2: Press F5 in VS Code
- Open [`packsure_app.py`](file:///d:/HACKATHON/packsure_app.py) in VS Code.
- Press **F5** (or click **Run & Debug** -> select **"⚡ Run PackSure AI (Single File App)"**).
- The application starts on `http://localhost:8000` and automatically opens your default web browser!

### Method 3: Double-Click Launcher
- Double-click [`start_single_file.bat`](file:///d:/HACKATHON/start_single_file.bat).

---

## 🔄 Complete 10-Step Connected Pipeline

```
[1. Upload] ──> [2. OCR & OpenCV] ──> [3. AI Extraction] ──> [4. Category Detection]
                                                                      │
[8. Results Dashboard] <── [7. Risk Priority] <── [6. Scoring] <── [5. Rules Engine]
        │
        ├──> [9. Official PDF Audit Certificate Export]
        └──> [10. Audit History & SQLite Database Search]
```

1. **Upload**: Drag-and-drop or select any packaging image (PNG, JPG, JPEG, WEBP).
2. **OCR Engine**: Authentic text detection using PaddleOCR (DBNet + CRNN) & EasyOCR with OpenCV bilateral filtering and adaptive thresholding.
3. **AI Structured Extraction**: Extracts 10 mandatory declarations without hallucination:
   - Commodity Name, Brand, Net Quantity, MRP, Unit Sale Price (USP), Mfg Date, Expiry Date, Manufacturer Address, Country of Origin, Consumer Care contacts.
4. **Category Detection**: Classifies commodity into `Food`, `Cosmetics`, `Household`, `Consumer Goods`, `Imported Goods`, `Other` with instant manual override.
5. **Rule-Based Engine**: Configurable deterministic rule checks against statutory clauses (`Rule 6(1)(a)-(h)`, `Rule 7`, `Rule 2(m)`). Returns `PASS`, `FAIL`, `WARNING`, `MANUAL REVIEW`.
6. **Deterministic Compliance Score**: Computes exact percentage score:
   $$\text{Score} = \frac{\text{Passed Rule Weight}}{\text{Total Applicable Rule Weight}} \times 100$$
   Mapped to 4 statutory tiers:
   - **90–100%**: `COMPLIANT`
   - **70–89%**: `MOSTLY COMPLIANT`
   - **40–69%**: `NEEDS REVIEW`
   - **0–39%**: `HIGH RISK`
7. **Risk Prioritization**: Classifies issues into `CRITICAL`, `HIGH`, `MEDIUM`, and `LOW`. Strictly sorts checks from highest to lowest priority.
8. **Final Results Dashboard**: High-resolution image thumbnail + lightbox zoom, deterministic score badge, statutory recommendations checklist, and live field editor for instant re-calculation.
9. **PDF Report Generation**: Downloadable 2-page Audit Certificate with ReportLab including embedded image, OCR diagnostic, score formula, violation breakdown, recommendations, and legal disclaimer.
10. **Audit History & Search**: Persistent SQLite database storing full audit trails queryable by report code, product name, and compliance status.

---

## 🧪 Automated Test Suite

Run the full end-to-end audit test:
```bash
py test_complete_workflow.py
```

Run individual unit test suites:
```bash
py test_rules_engine.py       # Tests rules, mathematical scoring, and prioritization
py test_pdf_generation.py     # Tests ReportLab PDF layout and all 9 required sections
py test_category_detection.py # Tests commodity classification
py verify_api_compliance.py   # Tests live REST API scan endpoint
```

---

## 📁 Repository Structure

```
├── packsure_app.py             # ⚡ ALL-IN-ONE SINGLE FILE (Backend + Frontend + OCR + Rules + PDF)
├── start_single_file.bat       # Single-click Windows launcher for all-in-one app
├── run_all.py                  # Dual-process launcher (FastAPI + Vite React frontend)
├── start.bat                   # Dual-process launcher batch script
├── test_label.png              # Authentic product label sample
├── test_complete_workflow.py   # Master 10-step end-to-end pipeline test
├── test_rules_engine.py        # Legal Metrology rules test suite
├── test_pdf_generation.py      # PDF report generator test suite
│
├── backend/                    # Modular Python Backend
│   ├── app/
│   │   ├── ocr/                # PaddleOCR + OpenCV image preprocessing
│   │   ├── ai/                 # NLP declaration extraction & category detection
│   │   ├── compliance/         # Legal Metrology PCR 2011 rules engine
│   │   ├── reports/            # ReportLab PDF certificate generator
│   │   ├── database/           # SQLite / SQLAlchemy models
│   │   └── api/                # FastAPI REST router
│   ├── rules_config.json       # Configurable Legal Metrology rules
│   └── requirements.txt        # Python dependencies
│
└── frontend/                   # Modern React + Vite + Tailwind Frontend
    ├── src/
    │   ├── pages/              # ScanProduct, ViewReports, Home pages
    │   ├── components/         # Navbar, ReportCard, Lightbox modals
    │   └── services/           # Axios API clients
    └── package.json
```

---

## ⚖️ Statutory Reference
- **The Legal Metrology Act, 2009 (Act No. 1 of 2010)**
- **The Legal Metrology (Packaged Commodities) Rules, 2011 (G.S.R. 202(E) as amended)**
- **Legal Metrology (Packaged Commodities) Amendment Rules, 2021 (Unit Sale Price & Standard Units)**
