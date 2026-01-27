import io
import os
import textwrap
import streamlit as st
import pandas as pd
from typing import Tuple, Dict
import plotly.express as px
import plotly.graph_objects as go

# Assuming these modules exist in your src folder based on the imports
from src.parse import parse_vtu_results
from src.analytics import (
    compute_student_status,
    compute_subject_statistics,
    compute_overall_metrics,
    build_excel_summary,
    build_pdf_summary,
    compute_sgpa,
)
from src.ocr import is_scanned, extract_text_from_pdf

def check_dependencies():
    """Checks for optional dependencies and warns the user if missing."""
    missing = []
    try:
        import pytesseract
    except ImportError:
        missing.append("pytesseract")
    try:
        import pdf2image
    except ImportError:
        missing.append("pdf2image")
    try:
        import cv2
    except ImportError:
        missing.append("opencv-python-headless")
    
    if missing:
        st.error(f"❌ **Missing Dependencies**: {', '.join(missing)}")
        st.info("It looks like Streamlit Cloud is still installing packages. Please wait a minute and **Reboot the App** from the Streamlit menu (bottom right).")
        st.stop()

# Run dependency check immediately
check_dependencies()

def _show_header() -> bool:
    st.set_page_config(
        page_title="VTU Results Analyzer",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Theme toggle in the sidebar
    st.sidebar.markdown("## 🎨 Appearance")
    dark_mode = st.sidebar.checkbox("🌙 Dark Mode", value=True, help="Toggle between dark and light themes")

    # -------------------------------------------------------------------------
    #  🎨 PRO UI/UX CSS INJECTION
    # -------------------------------------------------------------------------
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400&display=swap');

        :root {
            /* Palette: Modern Slate & Indigo */
            --bg-dark: #0f172a;
            --surface-dark: #1e293b;
            --surface-light: #334155;
            --border-color: #334155;
            
            --primary-gradient: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            
            --success-color: #10b981;
            --warning-color: #f59e0b;
            --danger-color: #ef4444;
            --info-color: #3b82f6;
        }

        /* 1. Global Reset & Typography */
        .stApp {
            font-family: 'Inter', sans-serif !important;
            background-color: var(--bg-dark);
        }
        h1, h2, h3, h4, h5, h6 {
            color: var(--text-primary) !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em;
        }
        p, label, span, li {
            color: var(--text-secondary) !important;
        }
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 4rem !important;
            max-width: 1200px !important;
        }

        /* 2. Header Section */
        .hero-header {
            text-align: center;
            padding: 3rem 1rem;
            margin-bottom: 3rem;
            background: radial-gradient(circle at center, rgba(59, 130, 246, 0.15) 0%, rgba(15, 23, 42, 0) 70%);
            border-bottom: 1px solid var(--border-color);
        }
        .hero-title {
            font-size: 3.5rem !important;
            background: var(--primary-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem !important;
            filter: drop-shadow(0 0 20px rgba(59, 130, 246, 0.3));
        }
        .hero-subtitle {
            font-size: 1.2rem !important;
            color: var(--text-secondary);
            font-weight: 400;
        }

        /* 3. Cards (KPIs & Info) */
        .stat-card {
            background: var(--surface-dark);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            text-align: center;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
            border-color: #6366f1;
        }
        .stat-label {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }
        .stat-value {
            font-size: 2.2rem;
            font-weight: 800;
            color: var(--text-primary);
        }

        /* 4. Buttons (Custom Overrides) */
        .stButton button {
            background: var(--surface-light) !important;
            color: var(--text-primary) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 8px !important;
            padding: 0.6rem 1.2rem !important;
            font-weight: 500 !important;
            transition: all 0.2s ease-in-out !important;
            width: 100%;
        }
        .stButton button:hover {
            background: var(--primary-gradient) !important;
            border-color: transparent !important;
            color: white !important;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
        }

        .stDownloadButton button {
            background: transparent !important;
            border: 1px solid var(--info-color) !important;
            color: var(--info-color) !important;
            border-radius: 8px !important;
            transition: all 0.2s ease !important;
        }
        .stDownloadButton button:hover {
            background: var(--info-color) !important;
            color: white !important;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }

        /* 5. Inputs & Filters */
        .stFileUploader {
            border: 2px dashed var(--border-color);
            border-radius: 16px;
            padding: 2rem;
            background: rgba(30, 41, 59, 0.5);
        }
        .stFileUploader:hover {
            border-color: #6366f1;
            background: rgba(30, 41, 59, 0.8);
        }
        div[data-baseweb="select"] > div {
            background-color: var(--surface-dark) !important;
            border-color: var(--border-color) !important;
            border-radius: 8px !important;
            color: var(--text-primary) !important;
        }
        
        /* 6. Tabs & Utilities */
        .stTabs [data-baseweb="tab-list"] {
            gap: 1rem;
            border-bottom: 1px solid var(--border-color);
        }
        .stTabs [data-baseweb="tab"] {
            background-color: transparent !important;
            border-radius: 6px 6px 0 0 !important;
            color: var(--text-secondary) !important;
            padding: 0.5rem 1rem !important;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            color: #6366f1 !important;
            border-bottom: 2px solid #6366f1 !important;
        }
        .section-divider {
            margin: 3rem 0;
            border-top: 1px solid var(--border-color);
        }
        
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="hero-header fade-in">
            <h1 class="hero-title">VTU Results Analytics</h1>
            <p class="hero-subtitle">Advanced Performance Intelligence for Departments</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return dark_mode


def _default_config() -> Dict:
    return {
        "min_total": 40,
        "min_external": 35,
        "result_col": "Result",
        "total_col": "Total",
        "external_col": "External",
        "rollno_col": "USN",
        "name_col": "Name",
        "subject_code_col": "Subject Code",
        "subject_name_col": "Subject Name",
        "semester_col": "Semester",
    }


def _aggregate_uploads(files) -> pd.DataFrame:
    frames = []
    for f in files:
        file_name = getattr(f, 'name', 'file')
        try:
            if file_name.lower().endswith('.pdf'):
                f.seek(0)
                file_bytes = f.read()
                f.seek(0)
                if is_scanned(file_bytes):
                    with st.status(f"🔍 Processing Scanned PDF: {file_name}...", expanded=False) as status:
                        st.write("Detecting layout & text layers...")
                        st.write("Applying OCR engine...")
                        parsed_df = parse_vtu_results(f)
                        status.update(label=f"✅ OCR Completed: {file_name}", state="complete", expanded=False)
                        frames.append(parsed_df)
                else:
                    frames.append(parse_vtu_results(f))
            else:
                frames.append(parse_vtu_results(f))
        except Exception as exc:
            st.warning(f"Skipped {file_name}: {exc}")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def main():
    dark_mode = _show_header()
    config = _default_config()

    # --- 1. Upload Section ---
    col1, col2 = st.columns([1, 4])
    with col2:
        st.markdown("### 📤 Import Data")
        uploaded = st.file_uploader(
            "Drag & drop result files (CSV, Excel, PDF)",
            type=["csv", "xls", "xlsx", "pdf"],
            accept_multiple_files=True,
            label_visibility="collapsed"
        )
    with col1:
        st.markdown("### ℹ️ Help")
        st.markdown("""
        <div style="font-size: 0.9rem; color: #94a3b8;">
        Upload your raw VTU result files.
        <br><br>
        ✅ <strong>CSV / Excel</strong><br>
        ✅ <strong>Digital PDFs</strong><br>
        ✅ <strong>Scanned PDFs</strong>
        </div>
        """, unsafe_allow_html=True)
        # Sample data download
        sample_file_path = "data/sample_vtu_results.csv"
        if os.path.exists(sample_file_path):
            with open(sample_file_path, "rb") as f:
                st.download_button(
                    label="Download Sample Data",
                    data=f.read(),
                    file_name="sample_vtu_results.csv",
                    mime="text/csv",
                    help="Test the app with this file"
                )

    if not uploaded:
        st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
        
        # --- FOOTER: CREDIT CARD DESIGN (Small & Centered) ---
        st.markdown(
            textwrap.dedent("""
            <div style="
                max-width: 420px;
                margin: 4rem auto 2rem auto;
                padding: 1.5rem;
                background: linear-gradient(135deg, rgba(30, 41, 59, 0.4), rgba(15, 23, 42, 0.6));
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
                backdrop-filter: blur(12px);
                font-family: 'Inter', sans-serif;
                position: relative;
                overflow: hidden;
            ">
                <div style="
                    position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
                    background: radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 60%);
                    pointer-events: none;
                "></div>

                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem; position: relative;">
                    <div>
                        <div style="color: #64748b; font-size: 0.65rem; letter-spacing: 2px; text-transform: uppercase; font-weight: 600;">PROJECT TEAM</div>
                        <div style="color: #f1f5f9; font-weight: 700; font-size: 1.1rem; margin-top: 0.2rem; letter-spacing: -0.5px;">VTU Analytics</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="color: #38bdf8; font-size: 0.65rem; font-weight: 700; letter-spacing: 1px;">GUIDE</div>
                        <div style="color: #cbd5e1; font-size: 0.8rem; margin-top: 0.1rem;">Raghavendra G S</div>
                    </div>
                </div>

                <div style="margin-bottom: 1.5rem; position: relative;">
                    <div style="color: #64748b; font-size: 0.6rem; margin-bottom: 0.5rem; font-weight: 600;">CONTRIBUTORS</div>
                    <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                        <span style="background: rgba(56, 189, 248, 0.1); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.2); font-size: 0.75rem; color: #bae6fd; font-family: 'JetBrains Mono', monospace;">Aditya K S</span>
                        <span style="background: rgba(56, 189, 248, 0.1); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.2); font-size: 0.75rem; color: #bae6fd; font-family: 'JetBrains Mono', monospace;">Amith S</span>
                        <span style="background: rgba(56, 189, 248, 0.1); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.2); font-size: 0.75rem; color: #bae6fd; font-family: 'JetBrains Mono', monospace;">Prajanth</span>
                        <span style="background: rgba(56, 189, 248, 0.1); padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.2); font-size: 0.75rem; color: #bae6fd; font-family: 'JetBrains Mono', monospace;">Preetham</span>
                    </div>
                </div>

                <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 0.8rem; position: relative;">
                     <div style="font-size: 0.65rem; color: #94a3b8; font-weight: 500;">
                        SMVITM • CSE DEPT • 2025
                     </div>
                     <div style="width: 30px; height: 20px; background: linear-gradient(135deg, #fbbf24, #d97706); border-radius: 4px; opacity: 0.8;"></div>
                </div>
            </div>
            """),
            unsafe_allow_html=True
        )
        return

    df = _aggregate_uploads(uploaded)
    if df.empty:
        st.error("No readable data extracted. Please check your files.")
        return

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # --- 2. Filter Section ---
    st.markdown("### 🛠️ Data Filters")
    with st.container():
        col1, col2, col3 = st.columns(3)
        
        with col1:
            subject_codes = sorted(df[config["subject_code_col"]].dropna().unique()) if config["subject_code_col"] in df.columns else []
            sel_codes = st.multiselect("Subjects", options=subject_codes, default=subject_codes)

        with col2:
            semesters = sorted(df[config["semester_col"]].dropna().unique()) if config["semester_col"] in df.columns else []
            sel_sem = st.multiselect("Semesters", options=semesters, default=semesters)

        with col3:
            sections = sorted(df["Section"].dropna().unique()) if "Section" in df.columns else []
            sel_section = st.multiselect("Sections", options=sections, default=sections)

    # Apply filters
    filtered = df.copy()
    if sel_codes:
        filtered = filtered[filtered[config["subject_code_col"]].isin(sel_codes)]
    if sel_sem:
        filtered = filtered[filtered[config["semester_col"]].isin(sel_sem)]
    if "Section" in filtered.columns and sel_section:
        filtered = filtered[filtered["Section"].isin(sel_section)]

    # --- Data Processing ---
    per_student = compute_student_status(
        df=filtered,
        rollno_col=config["rollno_col"],
        name_col=config["name_col"],
        result_col=config["result_col"],
        total_col=config["total_col"],
        external_col=config["external_col"],
        min_total=config["min_total"],
        min_external=config["min_external"],
    )
    
    # Exclude Absent students from analytics
    analysis_students = per_student[per_student["Status"] != "ABSENT"].copy()
    
    # Subject Stats
    per_subject = compute_subject_statistics(
        df=filtered,
        subject_code_col=config["subject_code_col"],
        subject_name_col=config["subject_name_col"],
        result_col=config["result_col"],
        total_col=config["total_col"],
        external_col=config["external_col"],
        min_total=config["min_total"],
        min_external=config["min_external"],
    )

    # Section Subject Stats (if Section exists)
    if "Section" in filtered.columns:
        section_subject_stats = (
            filtered.groupby([config["subject_code_col"], config["subject_name_col"], "Section"])
            .agg(
                Total=("USN", "count"),
                Absent=("Result", lambda x: (x.astype(str).str.upper() == "A").sum()),
                Passed=("Result", lambda x: x.astype(str).str.upper().str.contains(r"PASS|PASSED|^P$").sum())
            ).reset_index()
        )
        section_subject_stats["Appeared"] = section_subject_stats["Total"] - section_subject_stats["Absent"]
        section_subject_stats["Failed"] = section_subject_stats["Appeared"] - section_subject_stats["Passed"]
        section_subject_stats["Pass%"] = (
            section_subject_stats["Passed"] / section_subject_stats["Appeared"].replace(0, pd.NA) * 100
        ).fillna(0).round(2)
    else:
        section_subject_stats = pd.DataFrame()

    # --- 3. Dashboard KPI Section ---
    st.markdown("<br>", unsafe_allow_html=True)
    
    total_st = per_student['USN'].dropna().unique().shape[0]
    backlogs = analysis_students[analysis_students["Status"] == "FAIL"].shape[0]
    pass_pct = (analysis_students["Status"] == "PASS").mean() * 100 if not analysis_students.empty else 0
    
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">👥 Total Students</div>
            <div class="stat-value" style="color: #3b82f6;">{total_st}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">⚠️ With Backlogs</div>
            <div class="stat-value" style="color: #ef4444;">{backlogs}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">✅ Pass Percentage</div>
            <div class="stat-value" style="color: #10b981;">{pass_pct:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # --- 4. Charts & Detailed Stats ---
    col_chart, col_toppers = st.columns([1, 1])

    with col_chart:
        st.markdown("#### 🍩 Pass/Fail Distribution")
        
        # Prepare Pie Data (Exclude Absent)
        pie_df = per_student[per_student['Status'] != 'ABSENT']
        status_counts = pie_df['Status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        
        fig = go.Figure(go.Pie(
            labels=status_counts["Status"],
            values=status_counts["Count"],
            hole=0.6,
            marker=dict(colors=['#10b981', '#ef4444']), # Green, Red
            textinfo="label+percent",
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8"),
            showlegend=False,
            margin=dict(t=20, b=20, l=20, r=20)
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_toppers:
        st.markdown("#### 🏅 Quick Statistics")
        st.markdown(f"""
        <div style="background: var(--surface-dark); padding: 1.5rem; border-radius: 12px; border: 1px solid var(--border-color);">
            <div style="display:flex; justify-content:space-between; margin-bottom:1rem; padding-bottom:1rem; border-bottom:1px solid var(--border-color);">
                <span>Passing Students</span>
                <span style="color:#10b981; font-weight:700;">{status_counts[status_counts['Status']=='PASS']['Count'].sum() if not status_counts.empty else 0}</span>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span>Failing Students</span>
                <span style="color:#ef4444; font-weight:700;">{status_counts[status_counts['Status']=='FAIL']['Count'].sum() if not status_counts.empty else 0}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 5. Tabs for Detailed Data ---
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📚 Subject Stats", "👥 Students", "🏷 Section Stats"])

    with tab1:
        st.markdown("##### Full Result Matrix")
        st.dataframe(per_student, use_container_width=True, height=400)

    with tab2:
        st.markdown("##### Subject-wise Performance")
        st.dataframe(per_subject, use_container_width=True)

    with tab3:
        st.markdown("##### Student Search")
        search = st.text_input("Enter USN or Name", placeholder="Search...")
        if search:
            res = per_student[per_student['USN'].str.contains(search, case=False, na=False) | 
                              per_student['Name'].str.contains(search, case=False, na=False)]
            st.dataframe(res, use_container_width=True)
        else:
            st.info("Type above to search specific student records.")

    with tab4:
        if not section_subject_stats.empty:
            st.markdown("##### Section-wise Breakdown")
            st.dataframe(section_subject_stats, use_container_width=True)
        else:
            st.warning("No Section data found in the uploaded files.")

    st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)

    # --- 6. Export Section (Redesigned) ---
    st.markdown("### 💾 Export Reports")
    st.markdown("Download comprehensive reports for your records.")
    
    # Row 1: Main Summaries
    c1, c2, c3 = st.columns(3)
    
    with c1:
        excel_data = build_excel_summary(filtered, per_student, per_subject)
        st.download_button(
            "📊 Full Excel Summary",
            data=excel_data,
            file_name="Full_Analysis_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Contains Analysis, Student Results, and Subject Stats"
        )
    
    with c2:
        pdf_data = build_pdf_summary(per_student, per_subject, {"total_students": total_st, "students_with_backlogs": backlogs, "overall_pass_percentage": pass_pct})
        st.download_button(
            "📄 Official PDF Report",
            data=pdf_data,
            file_name="Result_Summary.pdf",
            mime="application/pdf",
            help="Print-ready PDF report"
        )
        
    with c3:
        failed_usns = per_student[per_student["Status"] == "FAIL"]["USN"]
        failed_df = filtered[filtered["USN"].isin(failed_usns)][["USN", "Name", "Subject Code", "Result"]]
        st.download_button(
            "❌ Failed List (CSV)",
            data=failed_df.to_csv(index=False).encode(),
            file_name="Failed_Students.csv",
            mime="text/csv"
        )

    # Row 2: Advanced Exports
    with st.expander("🔽 Advanced Export Options"):
        ac1, ac2, ac3 = st.columns(3)
        
        with ac1:
            # Section Summary (One sheet per section)
            if "Section" in per_student.columns:
                try:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        unique_sections = sorted(per_student["Section"].dropna().unique())
                        for sec in unique_sections:
                            sec_df = per_student[per_student["Section"] == sec]
                            safe_name = f"Sec_{sec}"[:31].replace(':','')
                            sec_df.to_excel(writer, sheet_name=safe_name, index=False)
                    output.seek(0)
                    st.download_button("📑 Section Student Lists", data=output, file_name="Section_Students.xlsx", mime="application/vnd.ms-excel")
                except: st.error("Error generating report")
            else: st.caption("No Section Data")

        with ac2:
            # Section Subject Stats
            if "Section" in filtered.columns:
                try:
                    output_stats = io.BytesIO()
                    with pd.ExcelWriter(output_stats, engine='xlsxwriter') as writer:
                        unique_sections = sorted(filtered["Section"].dropna().unique())
                        for sec in unique_sections:
                            sec_data = filtered[filtered["Section"] == sec]
                            stats = sec_data.groupby([config["subject_code_col"], config["subject_name_col"]]).agg(
                                Total=('USN', 'count'),
                                Absent=('Result', lambda x: (x.astype(str).str.upper() == 'A').sum()),
                                Passed=('Result', lambda x: x.astype(str).str.upper().str.contains(r'PASS|PASSED|^P$').sum())
                            ).reset_index()
                            stats['Appeared'] = stats['Total'] - stats['Absent']
                            stats['Failed'] = stats['Appeared'] - stats['Passed']
                            stats['Pass%'] = (stats['Passed'] / stats['Appeared'].replace(0, pd.NA) * 100).fillna(0).round(2)
                            safe_name = f"Sec_{sec}"[:31].replace(':','')
                            stats.to_excel(writer, sheet_name=safe_name, index=False)
                    output_stats.seek(0)
                    st.download_button("📊 Section Subject Stats", data=output_stats, file_name="Section_Subject_Stats.xlsx", mime="application/vnd.ms-excel")
                except: st.error("Error generating report")
            else: st.caption("No Section Data")

        with ac3:
            # Broadsheet Matrix
            if "Section" in filtered.columns:
                try:
                    output_matrix = io.BytesIO()
                    with pd.ExcelWriter(output_matrix, engine='xlsxwriter') as writer:
                        unique_sections = sorted(filtered["Section"].dropna().unique())
                        for sec in unique_sections:
                            sec_raw = filtered[filtered["Section"] == sec]
                            pivot_df = sec_raw.pivot_table(
                                index=['USN', 'Name'], 
                                columns=config['subject_code_col'], 
                                values=[config['total_col'], config['result_col']],
                                aggfunc='first'
                            )
                            # Flatten columns
                            pivot_df = pivot_df.swaplevel(0, 1, axis=1).sort_index(axis=1)
                            pivot_df.columns = [f"{c[0]}_{c[1]}" for c in pivot_df.columns]
                            safe_name = f"Matrix_{sec}"[:31].replace(':','')
                            pivot_df.to_excel(writer, sheet_name=safe_name)
                    output_matrix.seek(0)
                    st.download_button("📉 Result Matrix (Broadsheet)", data=output_matrix, file_name="Result_Matrix.xlsx", mime="application/vnd.ms-excel")
                except: st.error("Error generating report")
            else: st.caption("No Section Data")

    # --- Footer (Visible on Analysis Page as well) ---
    st.markdown("<div style='margin-top: 5rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        textwrap.dedent("""
        <div style="
            text-align: center;
            padding: 2rem;
            margin-top: 4rem;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            color: #94a3b8;
            font-size: 0.8rem;
        ">
            <p style="margin-bottom: 0.5rem;">© 2025 - 2026 VTU Result Analyser</p>
            <p style="font-size: 0.75rem; color: #64748b;">Department of CSE, SMVITM</p>
        </div>
        """),
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
