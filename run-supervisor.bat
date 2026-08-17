@echo off
REM Launch the Workspace v0 Supervisor (Streamlit).
REM `streamlit` is not on PATH here, so we invoke it as a module via `python -m`.
REM Run from the project root so supervisor/app.py and its sys.path inserts resolve.
setlocal
cd /d "%~dp0"
echo Starting supervisor on http://localhost:8501 ...
python -m streamlit run supervisor/app.py
endlocal