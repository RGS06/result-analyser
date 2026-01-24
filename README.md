
<div align="center">

# 🎓 VTU Result Analyser
### Automated Pass/Fail Analytics Dashboard for Departments

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![Plotly](https://img.shields.io/badge/Plotly-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)](https://plotly.com/)



A powerful, modern web application designed to automate the processing and analysis of VTU result files. Transform raw PDF/Excel data into actionable insights, visual dashboards, and comprehensive reports in seconds.

[View Demo](https://vtu-result-analyser.streamlit.app) · [Report Bug](https://github.com/yourusername/vtu-result-analyser/issues) · [Request Feature](https://github.com/yourusername/vtu-result-analyser/issues)

</div>

---

## ✨ Key Features

*   **📄 Universal Support:** Seamlessly process extracted PDF, Excel (.xlsx), and CSV result files.
*   **📊 Instant Analytics:** Automatically calculates:
    *   Overall Pass Percentage.
    *   Subject-wise Performance.
    *   Failure & Backlog Counts.
    *   Topper Lists.
*   **🎨 Dynamic Dashboard:** Interactive charts and KPI cards tailored with a premium, responsive UI.
*   **📥 Smart Exports:**
    *   **Excel:** Comprehensive multi-sheet reports.
    *   **PDF:** Professional summary reports ready for printing.
    *   **CSV:** Raw data extracts for further processing.
*   **🔍 Deep Dive:** Individual student performance tracking with "Traffic Light" status indicators (Pass/Fail/Average).

## 🛠️ Tech Stack

This project is built using a robust Python stack for data science and web development:

*   **Frontend:** [Streamlit](https://streamlit.io/) for the interactive web interface.
*   **Data Processing:** `Pandas` and `NumPy` for high-performance data manipulation.
*   **Visualization:** `Plotly` for interactive graphs and `Altair` for charts.
*   **PDF Extraction:** `Camelot`, `Tabula-py`, `PDFPlumber`, and `PDF2Image` for extracting tables from complex result PDFs.

## 🚀 Getting Started

### Prerequisites

Ensure you have the following installed:
*   Python 3.10+
*   **Java Runtime Environment (JRE)** (Required for Tabula)
*   **Ghostscript** (Required for Camelot)
*   **Poppler** (Required for PDF2Image)

### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/yourusername/vtu-result-analyser.git
    cd vtu-result-analyser/miniproject
    ```

2.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the application**
    ```bash
    streamlit run app.py
    ```

## 🐳 Docker Support

Deploy anywhere easily using the included Docker configuration.

```bash
# Build the image
docker build -t vtu-analyser .

# Run the container
docker run -p 8501:8501 vtu-analyser
```

## 📁 Usage Guide

1.  **Upload:** Drag and drop your result file (PDF, Excel, or CSV) into the upload zone.
2.  **Filter:** Use the sidebar or top filters to select specific Semesters or Subject Codes.
3.  **Analyze:**
    *   **Dashboard:** View high-level KPIs and pass/fail distribution charts.
    *   **Student Status:** Check individual student results with pass/fail indicators.
    *   **Subject Stats:** See which subjects students found most difficult.
4.  **Export:** Click the download buttons at the bottom to get your reports.

## 🤝 Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

## 👨‍🎓 Student Contributors

A special thanks to the student contributors who helped make this project possible:

| USN | Name |
|:---:|:---|
| 4MW24CS400 | Aditya K Shenava |
| 4MW24CS401 | Amith Suvarna |
| 4MW24CS403 | Prajanth |
| 4MW24CS404 | Preetham |


