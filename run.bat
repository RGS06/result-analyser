@echo off
echo Starting VTU Results Analyzer...
echo.
echo The application will open in your default web browser.
echo If it doesn't open automatically, go to: http://localhost:8501
echo.
echo Press Ctrl+C to stop the application.
echo.
streamlit run app.py --server.port 8501
pause



