import io
import os
import textwrap

def check_dependencies():
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
        import streamlit as st
        st.error(f"❌ **Missing Dependencies**: {', '.join(missing)}")
        st.info("It looks like Streamlit Cloud is still installing packages. Please wait a minute and **Reboot the App** from the Streamlit menu (bottom right).")
        st.stop()

check_dependencies()

from typing import Tuple, Dict

import streamlit as st
import pandas as pd

from src.parse import parse_vtu_results
from src.analytics import (
    compute_student_status,
    compute_subject_statistics,
    compute_overall_metrics,
    build_excel_summary,
    build_pdf_summary,
    compute_sgpa,
)
# plotly.graph_objects is used for the pie chart; avoid unused imports


def _show_header() -> bool:
    st.set_page_config(
        page_title="VTU Results Analyzer",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Theme toggle in the sidebar
    st.sidebar.markdown("## Theme")
    dark_mode = st.sidebar.checkbox("🌙 Dark mode", value=False, help="Enable dark theme for the app")

    # Enhanced global styles with modern design and theme variables
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        :root {
            /* Core Colors - High Contrast Modern Dark Theme */
            --bg-color: #0f172a;           /* Slate 900 */
            --card-color: #1e293b;         /* Slate 800 */
            --text-color: #f8fafc;         /* Slate 50 */
            --text-muted: #94a3b8;         /* Slate 400 */
            --primary: #38bdf8;            /* Sky 400 */
            --secondary: #818cf8;          /* Indigo 400 */
            --success: #22c55e;            /* Green 500 */
            --danger: #ef4444;             /* Red 500 */
            --border-color: #334155;       /* Slate 700 */
            
            /* Gradients */
            --header-gradient: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
            --card-gradient: linear-gradient(145deg, #1e293b, #0f172a);
        }

        /* Base App Styling */
        .stApp {
            background-color: var(--bg-color) !important;
            font-family: 'Inter', sans-serif !important;
        }

        /* Text Visibility - Ensure EVERYTHING is visible */
        h1, h2, h3, h4, h5, h6, p, label, span, div {
            color: var(--text-color) !important;
        }
        .stMarkdown p {
            color: var(--text-muted) !important;
        }

        /* Main Header */
        .header-container {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 2rem;
            text-align: center;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .header-title {
            font-size: 2.5rem !important;
            font-weight: 800 !important;
            background: var(--header-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent !important;
            background-clip: text;
            margin-bottom: 0.5rem;
        }
        .header-subtitle {
            font-size: 1.1rem !important;
            color: var(--text-muted) !important;
            -webkit-text-fill-color: var(--text-muted) !important;
        }

        /* Info Cards (KPIs) */
        .kpi-card {
            background: var(--card-color);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            transition: all 0.2s ease;
        }
        .kpi-card:hover {
            transform: translateY(-4px);
            border-color: var(--primary);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2);
        }
        .kpi-label {
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted) !important;
            margin-bottom: 0.5rem;
        }
        .kpi-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-color) !important;
        }
        .kpi-value.pass { color: var(--success) !important; }
        .kpi-value.fail { color: var(--danger) !important; }
        .kpi-value.total { color: var(--primary) !important; }

        /* Widget Containers (Sidebar, Selectboxes) */
        .stSelectbox > div > div {
            background-color: var(--card-color) !important;
            color: var(--text-color) !important;
            border-color: var(--border-color) !important;
        }
        .stMultiSelect > div > div {
            background-color: var(--card-color) !important;
            border-color: var(--border-color) !important;
        }
        
        /* Expander Styling */
        .streamlit-expanderHeader {
            background-color: var(--card-color) !important;
            border: 1px solid var(--border-color) !important;
            color: var(--text-color) !important;
            border-radius: 8px !important;
        }
        
        /* Dataframes & Tables */
        .stDataFrame {
            background-color: var(--card-color) !important;
            border: 1px solid var(--border-color);
            border-radius: 8px;
        }
        [data-testid="stTable"] {
            background-color: var(--card-color) !important;
            color: var(--text-color) !important;
        }

        /* Buttons - Modern Standard */
        .stButton > button, .stDownloadButton > button {
            background: var(--card-color) !important;
            color: var(--text-color) !important;
            border: 1px solid var(--border-color) !important;
            border-radius: 8px !important;
            transition: all 0.2s;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            border-color: var(--primary) !important;
            color: var(--primary) !important;
            background: #1e293b !important;
        }

        /* File Uploader */
        [data-testid="stFileUploader"] {
            padding: 2rem;
            border-radius: 12px;
            border: 2px dashed var(--border-color);
            background: rgba(30, 41, 59, 0.4);
        }
        [data-testid="stFileUploader"] small {
            color: var(--text-muted) !important;
        }
        [data-testid="stFileUploader"] button {
            background: var(--primary) !important;
            color: #0f172a !important; /* Dark text on bright button */
            font-weight: 600 !important;
            border: none !important;
        }
        
        /* Highlighting specific elements */
        .highlight-container {
            background: var(--card-color);
            border-left: 4px solid var(--primary);
            padding: 1rem;
            border-radius: 0 8px 8px 0;
            margin-bottom: 1rem;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab"] {
            color: var(--text-muted) !important;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            color: var(--primary) !important;
            border-bottom-color: var(--primary) !important;
        }
        
        /* Scrollbars */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #475569; }
        
        /* Remove Default Footer */
        footer { visibility: hidden; }
        #MainMenu { visibility: hidden; }
        
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <script>
        // Apply data-theme attribute based on Python-side toggle
        (function() {{
            try {{
                var dark = {str(dark_mode).lower()};
                if (dark) {{
                    document.documentElement.setAttribute('data-theme', 'dark');
                }} else {{
                    document.documentElement.removeAttribute('data-theme');
                }}
            }} catch (e) {{ console.error(e); }}
        }})();
        </script>
        """,
        unsafe_allow_html=True,
    )

    # Custom header with enhanced design
    st.markdown(
        """
        <div class="header-container fade-in">
            <div class="header-title">🎓 VTU Results Analyzer</div>
            <div class="header-subtitle">Department Dashboard for Automated Pass/Fail Analytics</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return dark_mode

    # Sample data download with better styling
    sample_file_path = "data/sample_vtu_results.csv"
    if os.path.exists(sample_file_path):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with open(sample_file_path, "rb") as f:
                st.download_button(
                    label="📥 Download Sample Data (CSV)",
                    data=f.read(),
                    file_name="sample_vtu_results.csv",
                    mime="text/csv",
                    help="Download sample VTU results data to test the analyzer"
                )
    else:
        st.info("💡 **Getting Started:** Upload your VTU results files (CSV, Excel, or PDF) to begin analysis.")


def _default_config() -> Dict:
    # Fixed configuration (settings menu removed)
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
                # Check for scanned PDF to provide user feedback
                f.seek(0)
                file_bytes = f.read()
                f.seek(0)
                from src.ocr import is_scanned
                if is_scanned(file_bytes):
                    with st.status(f"🔍 Analyzing scanned PDF: {file_name}...", expanded=False) as status:
                        st.write("Detecting layout...")
                        st.write("Performing OCR extraction (this may take a moment)...")
                        parsed_df = parse_vtu_results(f)
                        status.update(label=f"✅ Finished OCR for {file_name}", state="complete", expanded=False)
                        frames.append(parsed_df)
                else:
                    frames.append(parse_vtu_results(f))
            else:
                frames.append(parse_vtu_results(f))
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Skipped {file_name}: {exc}")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def main():
    dark_mode = _show_header()
    config = _default_config()

    # Enhanced file uploader section
    st.markdown("### 📤 Upload Your Results")
    uploaded = st.file_uploader(
        "Choose VTU results file(s) (CSV, Excel, or PDF)",
        type=["csv", "xls", "xlsx", "pdf"],
        accept_multiple_files=True,
        help="Upload one or more VTU result files. Supports CSV, Excel (.xls/.xlsx), and PDF formats."
    )

    # Enhanced PDF help section
    if uploaded:
        pdf_files = [f for f in uploaded if getattr(f, 'name', '').lower().endswith('.pdf')]
        if pdf_files:
            with st.expander("📄 PDF Processing Tips", expanded=False):
                st.markdown("""
                **Our advanced PDF engine now features:**
                - **Automatic Scanned Detection**: Detects if your PDF is text-based or a scanned image.
                - **Integrated OCR**: Automatically uses Tesseract OCR for handwriting or poor scans.
                - **Regex Reconstruction**: Robustly handles imperfect text capture from any source.
                - **Pro Tip**: If processing is slow, it's likely performing high-precision OCR for scanned pages.
                """)

    if not uploaded:
        # Enhanced welcome section
        st.markdown(
            """
            <div style="text-align: center; padding: 3rem 2rem; background: #1e293b; border-radius: 16px; margin: 2rem 0; border: 1px solid #334155; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                <div style="font-size: 4rem; margin-bottom: 1rem;">📊</div>
                <h3 style="color: #f8fafc; margin-bottom: 1rem;">Ready to Analyze VTU Results?</h3>
                <p style="color: #94a3b8; font-size: 1.1rem; margin-bottom: 2rem;">
                    Upload your VTU result files above to get instant insights on student performance,
                    pass/fail distributions, and subject-wise analytics.
                </p>
                <div style="display: flex; justify-content: center; gap: 1rem; flex-wrap: wrap;">
                    <div style="background: #0f172a; padding: 1rem; border-radius: 8px; border-left: 4px solid #38bdf8; color: #e2e8f0;">
                        <strong style="color: #38bdf8;">Supported Formats:</strong> CSV, Excel, PDF
                    </div>
                    <div style="background: #0f172a; padding: 1rem; border-radius: 8px; border-left: 4px solid #22c55e; color: #e2e8f0;">
                        <strong style="color: #22c55e;">Features:</strong> Automated analysis, visual dashboards, exports
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    df = _aggregate_uploads(uploaded)
    # Preserve original extracted columns for debug display
    original_columns = list(df.columns) if not df.empty else []
    if df.empty:
        st.warning("No readable data found in uploaded files.")
        return

    # Enhanced filters section
    with st.expander("🔍 Filter & Customize Analysis", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            subject_codes = sorted(df[config["subject_code_col"]].dropna().unique()) if config["subject_code_col"] in df.columns else []
            sel_codes = st.multiselect(
                "📚 Select Subject Codes",
                options=subject_codes,
                default=subject_codes,
                help="Choose specific subjects to analyze"
            )

        with col2:
            semesters = sorted(df[config["semester_col"]].dropna().unique()) if config["semester_col"] in df.columns else []
            sel_sem = st.multiselect(
                "📅 Select Semesters",
                options=semesters,
                default=semesters,
                help="Choose specific semesters to analyze"
            )

    filtered = df.copy()
    # Apply filters only when the user has selected specific values
    if sel_codes:
        filtered = filtered[filtered[config["subject_code_col"]].isin(sel_codes)]
    if sel_sem:
        filtered = filtered[filtered[config["semester_col"]].isin(sel_sem)]

    st.markdown("<br><br>", unsafe_allow_html=True)

    # Enhanced data preview and debug info
    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown("### 📋 Data Preview")
        with st.expander("View Raw Data (First 50 rows)", expanded=False):
            st.dataframe(filtered.head(50), use_container_width=True)

    with col2:
        with st.expander("🔍 Debug Info", expanded=False):
            st.markdown("**Extracted Columns:**")
            st.code("\n".join(original_columns), language="text")
            st.markdown(f"**Total Columns:** {len(original_columns)}")
            st.markdown(f"**Filtered Columns:** {len(filtered.columns)}")
            
            # Show Raw OCR text if PDF was uploaded
            if uploaded:
                st.markdown("---")
                st.markdown("**Raw OCR/PDF Text:**")
                from src.ocr import extract_text_from_pdf
                for f in uploaded:
                    if f.name.lower().endswith('.pdf'):
                        f.seek(0)
                        raw_txt = extract_text_from_pdf(f.read())
                        st.text_area(f"Text from {f.name}", raw_txt, height=200)

    # Compute analytics
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

    # --- SGPA & Credit Configuration ---
    st.sidebar.markdown("### ⚙️ SGPA Config")
    with st.sidebar.expander("📝 Subject Credits", expanded=False):
        st.info("Assign credits to subjects for SGPA calculation.")
        unique_subjects = sorted(filtered[config["subject_code_col"]].unique())
        # Default credit DataFrame
        credit_df = pd.DataFrame({"Subject Code": unique_subjects, "Credit": [4] * len(unique_subjects)})
        
        # Helper dict to store session credits if needed, for now just use editor
        edited_credits = st.data_editor(
            credit_df,
            column_config={
                "Credit": st.column_config.NumberColumn("Credit", min_value=0, max_value=10, step=1)
            },
            hide_index=True,
            use_container_width=True,
            key="credit_editor"
        )
        # Convert to dictionary
        credit_map = dict(zip(edited_credits["Subject Code"], edited_credits["Credit"]))

    # Compute SGPA
    per_student = compute_sgpa(
        per_student=per_student,
        df=filtered,
        subject_credits=credit_map,
        subject_code_col=config["subject_code_col"],
        total_col=config["total_col"],
        result_col=config["result_col"]
    )

    st.markdown("<br><br>", unsafe_allow_html=True)

    # --- Toppers Section ---
    st.markdown("### 🏆 Class Toppers")
    
    # Sort by SGPA DESC, then SubjectsPassed DESC
    toppers = per_student.sort_values(by=["SGPA", "SubjectsPassed"], ascending=[False, False]).head(3)
    
    if not toppers.empty:
        col1, col2, col3 = st.columns(3)
        medals = ["🥇", "🥈", "🥉"]
        colors = ["#f59e0b", "#94a3b8", "#b45309"] # Gold, Silver, Bronze styling
        
        for idx, (i, student) in enumerate(toppers.iterrows()):
            if idx < 3:
                medal = medals[idx]
                border_color = colors[idx]
                with [col1, col2, col3][idx]:
                    st.markdown(
                        textwrap.dedent(f"""
                        <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid {border_color}; border-radius: 12px; padding: 1.5rem; text-align: center; position: relative; overflow: hidden;">
                            <div style="font-size: 3rem; margin-bottom: 0.5rem;">{medal}</div>
                            <h3 style="color: #f8fafc; margin: 0; font-size: 1.2rem;">{student[config['name_col']]}</h3>
                            <div style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 1rem;">{student[config['rollno_col']]}</div>
                            <div style="background: rgba(255,255,255,0.05); padding: 0.5rem; border-radius: 6px;">
                                <div style="font-size: 0.8rem; color: #cbd5e1; text-transform: uppercase; letter-spacing: 1px;">SGPA</div>
                                <div style="font-size: 2rem; font-weight: 800; color: {border_color};">{student['SGPA']}</div>
                            </div>
                        </div>
                        """),
                        unsafe_allow_html=True
                    )
    else:
        st.info("No students found to rank.")

    st.markdown("<br><br>", unsafe_allow_html=True)

    # --- SGPA Distribution and Stats ---
    # col1: Histogram, col2: Summary Stats already exists below, so we can insert a chart section here
    
    st.markdown("### 📊 SGPA Analytics")
    colA, colB = st.columns([2, 1])
    
    with colA:
        import plotly.express as px
        # Filter valid SGPAs (e.g., > 0)
        valid_sgpa = per_student[per_student['SGPA'] > 0]
        if not valid_sgpa.empty:
            fig_hist = px.histogram(
                valid_sgpa, 
                x="SGPA", 
                nbins=20, 
                title="SGPA Distribution",
                color_discrete_sequence=["#38bdf8"]
            )
            fig_hist.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#cbd5e1",
                xaxis_title="SGPA",
                yaxis_title="Count of Students",
                margin=dict(t=40, l=20, r=20, b=20)
            )
            fig_hist.update_traces(marker_line_color="#1e293b", marker_line_width=1.5)
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.warning("No valid SGPA data to display distribution.")

    with colB:
        # Quick stats table for SGPA
        if not valid_sgpa.empty:
            avg_sgpa = valid_sgpa['SGPA'].mean()
            max_sgpa = valid_sgpa['SGPA'].max()
            min_sgpa = valid_sgpa['SGPA'].min()
            
            st.markdown(
                textwrap.dedent(f"""
                <div style="background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155;">
                    <h4 style="color: #f8fafc; margin-top: 0; margin-bottom: 1.5rem;">📈 Performance Stats</h4>
                    <div style="margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid #334155;">
                        <span style="color: #94a3b8; font-size: 0.9rem; display: block;">Average SGPA</span>
                        <span style="color: #38bdf8; font-size: 1.8rem; font-weight: 700; display: block;">{avg_sgpa:.2f}</span>
                    </div>
                    <div style="margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid #334155;">
                        <span style="color: #94a3b8; font-size: 0.9rem; display: block;">Highest SGPA</span>
                        <span style="color: #22c55e; font-size: 1.8rem; font-weight: 700; display: block;">{max_sgpa:.2f}</span>
                    </div>
                    <div>
                        <span style="color: #94a3b8; font-size: 0.9rem; display: block;">Lowest SGPA</span>
                        <span style="color: #ef4444; font-size: 1.8rem; font-weight: 700; display: block;">{min_sgpa:.2f}</span>
                    </div>
                </div>
                """),
                unsafe_allow_html=True
            )

    st.markdown("<br><br>", unsafe_allow_html=True)

    # --- Subject-wise Toppers ---
    st.markdown("### 🏅 Subject-wise Performance")
    
    # Get list of subjects
    available_subjects = sorted(filtered[config["subject_code_col"]].dropna().unique()) if config["subject_code_col"] in filtered.columns else []
    
    if available_subjects:
        selected_subject = st.selectbox("Select Subject to View Toppers", available_subjects)
        
        # Filter for this subject
        subj_df = filtered[filtered[config["subject_code_col"]] == selected_subject].copy()
        
        # Ensure Total is numeric
        if config["total_col"] in subj_df.columns:
            subj_df[config["total_col"]] = pd.to_numeric(subj_df[config["total_col"]], errors='coerce').fillna(0)
            
            # Sort by Total DESC
            subj_toppers = subj_df.sort_values(by=config["total_col"], ascending=False)
            
            if not subj_toppers.empty:
                col_top, col_list = st.columns([1, 2])
                
                with col_top:
                    # #1 Topper
                    topper = subj_toppers.iloc[0]
                    name_val = topper.get(config['name_col'], 'Unknown')
                    usn_val = topper.get(config['rollno_col'], 'Unknown')
                    score_val = int(topper.get(config['total_col'], 0))
                    
                    st.markdown(
                        textwrap.dedent(f"""
                        <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid #f59e0b; border-radius: 12px; padding: 2rem; text-align: center; margin-bottom: 1rem;">
                            <div style="color: #f59e0b; font-size: 1rem; font-weight: 700; letter-spacing: 2px; margin-bottom: 1rem;">SUBJECT TOPPER</div>
                            <div style="font-size: 4rem; margin-bottom: 1rem; text-shadow: 0 4px 20px rgba(245, 158, 11, 0.5);">🥇</div>
                            <h3 style="color: #f8fafc; margin: 0; font-size: 1.4rem; margin-bottom: 0.5rem;">{name_val}</h3>
                            <div style="color: #94a3b8; font-size: 1rem; margin-bottom: 1.5rem;">{usn_val}</div>
                            <div style="display: inline-block; background: rgba(245, 158, 11, 0.15); padding: 0.8rem 2rem; border-radius: 50px; border: 1px solid #f59e0b;">
                                <span style="color: #cbd5e1; margin-right: 0.5rem; font-size: 0.9rem;">SCORE</span>
                                <span style="color: #f59e0b; font-weight: 800; font-size: 1.5rem;">{score_val}</span>
                            </div>
                        </div>
                        """),
                        unsafe_allow_html=True
                    )
                
                with col_list:
                    # Top 10 Table
                    st.markdown("#### 🔝 Top 10 Students")
                    cols_to_show = [c for c in [config['rollno_col'], config['name_col'], config['total_col'], config['result_col']] if c in subj_toppers.columns]
                    top_10 = subj_toppers.head(10)[cols_to_show].reset_index(drop=True)
                    top_10.index = top_10.index + 1 # Rank 1-10
                    st.dataframe(top_10, use_container_width=True)
        else:
            st.warning(f"Column '{config['total_col']}' not found in data.")
    else:
        st.info("No subjects found.")

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

    # Fix total students: count unique, non-empty USNs
    total_students = per_student['USN'].dropna().astype(str).str.strip().replace('', pd.NA).dropna().nunique() if 'USN' in per_student.columns else 0

    overall = compute_overall_metrics(per_student)

    # Enhanced summary dashboard
    avg_pass_pct = per_subject['Pass%'].mean() if not per_subject.empty and 'Pass%' in per_subject.columns else 0.0
    avg_appeared = per_subject['Appeared'].mean() if not per_subject.empty and 'Appeared' in per_subject.columns else 0.0

    st.markdown("<br><hr><br>", unsafe_allow_html=True)
    st.markdown("### 📊 Analysis Dashboard")

    # KPI Cards in a responsive grid
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            textwrap.dedent(f"""
            <div class="kpi-card">
                <div class="kpi-label">👥 Total Students</div>
                <div class="kpi-value total">{total_students}</div>
            </div>
            """),
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            textwrap.dedent(f"""
            <div class="kpi-card">
                <div class="kpi-label">⚠️ Students with Backlogs</div>
                <div class="kpi-value fail">{overall['students_with_backlogs']}</div>
            </div>
            """),
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            textwrap.dedent(f"""
            <div class="kpi-card">
                <div class="kpi-label">✅ Overall Pass %</div>
                <div class="kpi-value pass">{overall['overall_pass_percentage']:.1f}%</div>
            </div>
            """),
            unsafe_allow_html=True,
        )

    # Enhanced insights section
    with st.expander("📈 Detailed Insights", expanded=True):
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 12px; padding: 1.5rem; border-left: 4px solid #38bdf8; border: 1px solid #334155;">
                <h4 style="color: #f8fafc; margin-bottom: 1rem;">📋 Summary Report</h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
                    <div style="background: #0f172a; padding: 1rem; border-radius: 8px; border: 1px solid #334155; color: #cbd5e1;">
                        <strong style="color: #38bdf8;">Total Students Analyzed:</strong> {total_students}
                    </div>
                    <div style="background: #0f172a; padding: 1rem; border-radius: 8px; border: 1px solid #334155; color: #cbd5e1;">
                        <strong style="color: #ef4444;">Students with Backlogs:</strong> {overall['students_with_backlogs']}
                    </div>
                    <div style="background: #0f172a; padding: 1rem; border-radius: 8px; border: 1px solid #334155; color: #cbd5e1;">
                        <strong style="color: #22c55e;">Overall Pass Rate:</strong> {overall['overall_pass_percentage']:.1f}%
                    </div>
                    <div style="background: #0f172a; padding: 1rem; border-radius: 8px; border: 1px solid #334155; color: #cbd5e1;">
                        <strong style="color: #818cf8;">Avg Subject Pass Rate:</strong> {avg_pass_pct:.1f}%
                    </div>
                </div>
                <div style="margin-top: 1rem; padding: 1rem; background: rgba(15, 23, 42, 0.5); border-radius: 8px; color: #94a3b8;">
                    <strong style="color: #e2e8f0;">Analysis Overview:</strong><br>
                    Out of <strong>{total_students}</strong> students analyzed, <strong>{overall['students_with_backlogs']}</strong> have at least one backlog.
                    The overall pass percentage stands at <strong>{overall['overall_pass_percentage']:.1f}%</strong>.
                    Subjects show an average pass rate of <strong>{avg_pass_pct:.1f}%</strong> with <strong>{avg_appeared:.1f}</strong> students per subject on average.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Enhanced result distribution visualization
    st.markdown("### 📈 Result Distribution")

    # Clean and prepare data for pie chart
    pie_df = per_student.copy()
    pie_df = pie_df[pie_df['USN'].notnull() & (pie_df['USN'].astype(str).str.strip() != '')]
    pie_df = pie_df[pie_df['Status'].notnull() & (pie_df['Status'].astype(str).str.strip() != '')]

    # Always show both PASS and FAIL, even if one is zero
    status_order = ['PASS', 'FAIL']
    status_counts = pie_df['Status'].value_counts().reindex(status_order, fill_value=0).reset_index()
    status_counts.columns = ['Status', 'Count']
    total = status_counts['Count'].sum()
    status_counts['Percent'] = status_counts['Count'] / total * 100 if total else 0

    col1, col2 = st.columns([2, 1])

    with col1:
        import plotly.graph_objects as go
        pie_colors = ["#10b981" if s == "PASS" else "#ef4444" for s in status_counts["Status"]]
        fig = go.Figure(
            go.Pie(
                labels=status_counts["Status"],
                values=status_counts["Count"],
                hole=0.6,
                marker=dict(colors=pie_colors, line=dict(color="#ffffff", width=3)),
                textinfo="label+percent",
                textfont_size=16,
                pull=[0.05 if s == "FAIL" else 0 for s in status_counts["Status"]],
                insidetextorientation="radial",
            )
        )
        fig.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            margin=dict(t=50, b=100, l=50, r=50),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=14),
            annotations=[
                dict(
                    text=f"<b>{total}</b><br><span style='font-size:12px;'>Total Students</span>",
                    x=0.5, y=0.5, font_size=20, showarrow=False, font_color="#f8fafc"
                )
            ],
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### 📊 Statistics")
        for _, row in status_counts.iterrows():
            color = "🟢" if row['Status'] == "PASS" else "🔴"
            bg_color = "#0f172a"
            border_color = "#22c55e" if row['Status'] == "PASS" else "#ef4444"
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem; background: {bg_color}; border: 1px solid {border_color}; border-radius: 8px; margin-bottom: 0.5rem; color: #f8fafc;">
                    <span style="font-weight: 600;">{color} {row['Status']}</span>
                    <span style="font-size: 1.2rem; font-weight: 700;">{int(row['Count'])}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown(
            f"""
            <div style="padding: 1rem; background: #0f172a; border-radius: 8px; border-left: 4px solid #38bdf8; border: 1px solid #334155;">
                <div style="font-size: 0.9rem; color: #94a3b8; margin-bottom: 0.5rem;">Pass Rate</div>
                <div style="font-size: 1.5rem; font-weight: 700; color: #f8fafc;">{status_counts[status_counts['Status']=='PASS']['Percent'].values[0]:.1f}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


    # Enhanced student analysis sections
    tab1, tab2, tab3, tab4 = st.tabs(["👤 Student Status", "📚 Individual Results", "📊 Complete Analysis", "📖 Subject Statistics"])

    with tab1:
        st.markdown("#### 👥 Per-Student Status Overview")
        st.dataframe(per_student, use_container_width=True)

    with tab2:
        st.markdown("#### 📚 Individual Student Subject-wise Results")
        # Clean up columns to show only relevant info
        columns_to_exclude = [': 4MW23CS003', 'Announced/ Updated on', 'Internal', 'Internal\nMarks', 'Unnamed: 0']
        columns_to_show = [col for col in filtered.columns if col not in columns_to_exclude]
        usn_list = filtered['USN'].dropna().astype(str).str.strip().replace('', pd.NA).dropna().unique()

        # Search and filter functionality
        col1, col2 = st.columns([3, 1])
        with col1:
            search_usn = st.text_input("🔍 Search by USN", placeholder="Enter USN to filter results...")
        with col2:
            show_all = st.checkbox("Show All Students", value=False)

        # Filter USN list based on search
        if search_usn:
            usn_list = [usn for usn in usn_list if search_usn.upper() in str(usn).upper()]

        if not show_all and len(usn_list) > 10:
            st.info(f"Showing first 10 students. Use search to find specific students or check 'Show All Students'.")
            usn_list = usn_list[:10]

        for usn in usn_list:
            student_df = filtered[filtered['USN'] == usn]
            if student_df.empty:
                continue
            name = student_df['Name'].iloc[0] if 'Name' in student_df.columns and not student_df['Name'].isnull().all() else 'Unknown'
            sem = student_df['Semester'].iloc[0] if 'Semester' in student_df.columns and not student_df['Semester'].isnull().all() else 'N/A'

            # Calculate student stats
            total_subjects = len(student_df)
            passed = (student_df['Result'].astype(str).str.upper().str.contains(r"PASS|PASSED|^P$")).sum() if 'Result' in student_df.columns else 0
            failed = total_subjects - passed
            pass_rate = (passed / total_subjects * 100) if total_subjects > 0 else 0

            # Color coding based on performance
            if pass_rate == 100:
                status_color = "#10b981"
                status_icon = "✅"
            elif pass_rate >= 50:
                status_color = "#f59e0b"
                status_icon = "⚠️"
            else:
                status_color = "#ef4444"
                status_icon = "❌"

            with st.expander(f"{status_icon} USN: {usn} | Name: {name} | Semester: {sem} | Pass Rate: {pass_rate:.1f}%", expanded=False):
                try:
                    st.dataframe(
                        student_df[columns_to_show],
                        use_container_width=True,
                        hide_index=True
                    )
                    # Enhanced summary with color coding
                    st.markdown(
                        f"""
                        <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 8px; padding: 1rem; border-left: 4px solid {status_color}; border: 1px solid #334155;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div style="color: #cbd5e1;">
                                    <strong>Performance Summary:</strong> {passed} Passed / {failed} Failed out of {total_subjects} subjects
                                </div>
                                <div style="font-size: 1.2rem; font-weight: 700; color: {status_color};">
                                    {pass_rate:.1f}% Pass Rate
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                except Exception as e:
                    st.error(f"Error displaying data for USN {usn}: {e}")

    with tab3:
        st.markdown("#### 📊 Complete Student Analysis")
        # Clean up per_student columns for clarity
        per_student_clean = per_student.copy()
        if 'Semester' in per_student_clean.columns:
            per_student_clean['Semester'] = per_student_clean['Semester'].replace(0, 'N/A')
        # Remove rows with empty or invalid USN
        if 'USN' in per_student_clean.columns:
            per_student_clean = per_student_clean[per_student_clean['USN'].notnull() & (per_student_clean['USN'].astype(str).str.strip() != '')]
        st.dataframe(per_student_clean, use_container_width=True, hide_index=True)

    with tab4:
        st.markdown("#### 📖 Subject-wise Statistics")
        st.dataframe(per_subject, use_container_width=True)

    # Enhanced export section
    st.markdown("### 💾 Export Results")
    st.markdown("Download your analysis results in various formats:")

    col1, col2, col3 = st.columns(3)

    with col1:
        excel_bytes = build_excel_summary(raw=filtered, per_student=per_student, per_subject=per_subject)
        st.download_button(
            label="📊 Excel Summary",
            data=excel_bytes,
            file_name="vtu-results-summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Complete analysis with multiple sheets"
        )

    with col2:
        # Failed students CSV
        failed_df = per_student[per_student["Status"] == "FAIL"]
        failed_csv = failed_df.to_csv(index=False).encode()
        st.download_button(
            label="❌ Failed Students (CSV)",
            data=failed_csv,
            file_name="failed_students.csv",
            mime="text/csv",
            help="List of students who failed"
        )

    with col3:
        # PDF summary
        pdf_bytes = build_pdf_summary(per_student=per_student, per_subject=per_subject, overall=overall)
        st.download_button(
            label="📄 PDF Summary",
            data=pdf_bytes,
            file_name="vtu-results-summary.pdf",
            mime="application/pdf",
            help="Professional PDF report"
        )

    # Additional export options
    with st.expander("📤 More Export Options", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            # All students CSV
            all_students_csv = per_student.to_csv(index=False).encode()
            st.download_button(
                label="👥 All Students (CSV)",
                data=all_students_csv,
                file_name="all_students.csv",
                mime="text/csv",
                help="Complete student analysis data"
            )

        with col2:
            # Subject statistics CSV
            subject_csv = per_subject.to_csv(index=False).encode()
            st.download_button(
                label="📚 Subject Statistics (CSV)",
                data=subject_csv,
                file_name="subject_statistics.csv",
                mime="text/csv",
                help="Subject-wise performance data"
            )


if __name__ == "__main__":
    main()
