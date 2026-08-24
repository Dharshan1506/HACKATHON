@echo off
title PackSure AI - All-in-One Legal Metrology Compliance Checker
cls
echo ======================================================================
echo   PACKSURE AI - ALL-IN-ONE LEGAL METROLOGY COMPLIANCE CHECKER
echo ======================================================================
echo   [1] Full FastAPI Backend Server
echo   [2] Embedded SQLite Database
echo   [3] Authentic OCR Engine (PaddleOCR / EasyOCR + OpenCV)
echo   [4] AI Information Extraction (NLP & Structured JSON)
echo   [5] Category Classification (Food, Cosmetics, Household, etc.)
echo   [6] Legal Metrology Rules Engine (PCR 2011)
echo   [7] Deterministic Compliance Score & 4-Tier Scale
echo   [8] Risk Violation Prioritization (CRITICAL, HIGH, MED, LOW)
echo   [9] Interactive Results Dashboard & Live Correction Form
echo   [10] Official PDF Report Generation & Audit History
echo ======================================================================
echo   Starting application on http://localhost:8000 ...
echo ======================================================================
py packsure_app.py
pause
