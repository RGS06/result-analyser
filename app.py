import io
import os
import textwrap
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. HELPER FUNCTIONS (Logic Core)
# ==========================================

def parse_vtu_results(file) -> pd.DataFrame:
    """Parses CSV or Excel files into a standard DataFrame."""
    filename = file.name.lower()
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(file)
        elif filename.endswith((".xls", ".xlsx")):
            df = pd.read_excel(file)
        else:
            return pd.DataFrame() 
        
        # Normalize column names (strip spaces, title case)
        df.columns = [str(c).strip().title() for c in df.columns]
        
        # Standardize key column names (Handle variations)
        rename_map = {
            "Usn": "USN", 
            "Sub Code": "Subject Code", 
            "Sub Name": "Subject Name",
            "Student Name": "Name", "Name Of Student": "Name", "Student_Name": "Name",
            "Int": "Internal", "Cie": "Internal", "I.A.": "Internal", "Ia": "Internal",
            "Ext": "External", "See": "External", "Sem End Exam": "External", "Exam": "External",
            "Tot": "Total", "Max": "Total",
            "Res": "Result", 
            "Sec": "Section"
        }
        df = df.rename(columns=rename_map)
        
        # Ensure critical columns exist (fill with 0 if missing to prevent Export crash)
        for col in ["Internal", "External", "Total"]:
            if col not in df.columns:
                df[col] = 0
            else:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
        return df
    except Exception as e:
        st.error(f"Error parsing file: {e}")
        return pd.DataFrame()

def compute_student_status(df):
    """Aggregates subject-wise data to student-level status."""
    if df.empty: return pd.DataFrame()
    
    # Group by USN to get per-student stats
    student_stats = []
    grouped = df.groupby("USN")
    
    for usn, group in grouped:
        # Use .get to safely retrieve Name/Section
        name = group["Name"].iloc[0] if "Name" in group.columns else "Unknown"
        section = group["Section"].iloc[0] if "Section" in group.columns else "N/A"
        
        # Fail Conditions: Result is Fail/Absent OR Total < 40
        fails = group[group["Result"].astype(str).str.upper().isin(["F", "FAIL", "A", "ABSENT"]) | (group["Total"] < 40)]
        is_absent_all = group["Result"].astype(str).str.upper().isin(["A", "ABSENT"]).all()
        
        status = "ABSENT" if is_absent_all else ("FAIL" if not fails.empty else "PASS")
        
        student_stats.append({
            "USN": usn, "Name": name, "Section": section, "Status": status,
            "TotalMarks": group["Total"].sum()
        })
        
    return pd.DataFrame(student_stats)

def compute_subject_statistics(df):
    """Computes pass percentage per subject."""
    if df.empty: return pd.DataFrame()
    
    stats = df.groupby(["Subject Code", "Subject Name"]).agg(
        Total=("USN", "count"),
        Absent=("Result", lambda x: x.astype(str).str.upper().isin(["A", "ABSENT"]).sum()),
        Fail=("Result", lambda x: x.astype(str).str.upper().isin(["F", "FAIL"]).sum())
    ).reset_index()
    
    stats["Appeared"] = stats["Total"] - stats["Absent"]
    stats["Passed"] = stats["Appeared"] - stats["Fail"]
    stats["Pass%"] = (stats["Passed"] / stats["Appeared"].replace(0, np.nan) * 100).fillna(0).round(2)
    return stats

def compute_sgpa(per_student, df, subject_credits):
    """Calculates SGPA based on VTU grading logic."""
    if per_student.empty: return per_student
    
    def get_points(m):
        if m >= 90: return 10
        elif m >= 80: return 9
        elif m >= 70: return 8
        elif m >= 60: return 7
        elif m >= 50: return 6
        elif m >= 45: return 5
        elif m >= 40: return 4
        return 0

    sgpa_vals = []
    for usn in per_student["USN"]:
        s_df = df[df["USN"] == usn]
        tot_cr = 0
        tot_pts = 0
        for _, row in s_df.iterrows():
            sub_code = str(row["Subject Code"]).strip().upper()
            
            # Skip if absent/fail, points = 0
            if row["Result"] in ["F", "FAIL", "A", "ABSENT"]:
                pts = 0
            else:
                pts = get_points(row["Total"])
            
            # Use specific syllabus credit map, fallback to 4
            cr = subject_credits.get(sub_code, 4) 
            
            tot_cr += cr
            tot_pts += (pts * cr)
        
        sgpa = (tot_pts / tot_cr) if tot_cr > 0 else 0
        sgpa_vals.append(round(sgpa, 2))
        
    per_student["SGPA"] = sgpa_vals
    return per_student

def build_excel_summary(raw, per_student, per_subject):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        per_student.to_excel(writer, sheet_name='Student Status', index=False)
        per_subject.to_excel(writer, sheet_name='Subject Stats', index=False)
        raw.to_excel(writer, sheet_name='Raw Data', index=False)
    output.seek(0)
    return output

def build_pdf_summary(per_student, per_subject, overall):
    return b"PDF Placeholder" 

# ==========================================
# 2. UI HELPERS & HTML GENERATORS
# ==========================================

def _get_footer_html() -> str:
    """Footer HTML without indentation."""
    return """
<div style="max-width: 420px; margin: 4rem auto 2rem auto; padding: 1.5rem; background: linear-gradient(135deg, rgba(30, 41, 59, 0.4), rgba(15, 23, 42, 0.6)); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3); backdrop-filter: blur(12px); font-family: 'Inter', sans-serif; position: relative; overflow: hidden;">
<div style="position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; background: radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 60%); pointer-events: none;"></div>
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
"""

def _get_sgpa_stats_html(avg, mx, mn) -> str:
    return f"""
<div style="display: flex; flex-direction: column; gap: 1rem;">
<div style="background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.2); padding: 1rem; border-radius: 12px; display: flex; justify-content: space-between; align-items: center;">
<div><div style="font-size: 0.75rem; color: #93c5fd; text-transform: uppercase;">Average SGPA</div><div style="font-size: 1.8rem; font-weight: 700; color: #f8fafc;">{avg:.2f}</div></div><div style="font-size: 1.5rem;">📊</div></div>
<div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); padding: 1rem; border-radius: 12px; display: flex; justify-content: space-between; align-items: center;">
<div><div style="font-size: 0.75rem; color: #6ee7b7; text-transform: uppercase;">Highest SGPA</div><div style="font-size: 1.8rem; font-weight: 700; color: #f8fafc;">{mx:.2f}</div></div><div style="font-size: 1.5rem;">🚀</div></div>
<div style="background: rgba(244, 63, 94, 0.1); border: 1px solid rgba(244, 63, 94, 0.2); padding: 1rem; border-radius: 12px; display: flex; justify-content: space-between; align-items: center;">
<div><div style="font-size: 0.75rem; color: #fda4af; text-transform: uppercase;">Lowest SGPA</div><div style="font-size: 1.8rem; font-weight: 700; color: #f8fafc;">{mn:.2f}</div></div><div style="font-size: 1.5rem;">📉</div></div></div>
"""

def _show_header() -> bool:
    st.set_page_config(
        page_title="VTU Results Analyzer",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.sidebar.markdown("## 🎨 Appearance")
    dark_mode = st.sidebar.checkbox("🌙 Dark Mode", value=True)

    # CSS Injection
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400&display=swap');
        
        :root {
            --bg-dark: #0f172a;
            --surface-dark: #1e293b;
            --surface-light: #334155;
            --primary-gradient: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --info-color: #3b82f6;
        }
        
        .stApp { font-family: 'Inter', sans-serif !important; background-color: var(--bg-dark); }
        h1, h2, h3, h4, h5 { color: var(--text-primary) !important; letter-spacing: -0.02em; }
        p, label, span { color: var(--text-secondary) !important; }
        
        /* Stat Cards */
        .stat-card {
            background: var(--surface-dark); border: 1px solid #334155; border-radius: 16px; padding: 1.5rem;
            text-align: center; transition: transform 0.2s;
        }
        .stat-card:hover { transform: translateY(-5px); border-color: #6366f1; }
        .stat-value { font-size: 2.2rem; font-weight: 800; color: var(--text-primary); }
        
        /* Tags Color Fix - Set to BLUE */
        span[data-baseweb="tag"] {
            background-color: rgba(59, 130, 246, 0.8) !important;
            border: 1px solid #3b82f6 !important;
        }
        span[data-baseweb="tag"] span { color: white !important; }
        
        /* Buttons */
        .stButton button { background: var(--surface-light); color: white; border-radius: 8px; border: 1px solid #334155; }
        .stButton button:hover { background: var(--primary-gradient); border-color: transparent; }
        
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div style="text-align: center; padding: 3rem 1rem; margin-bottom: 3rem; background: radial-gradient(circle at center, rgba(59, 130, 246, 0.15) 0%, rgba(15, 23, 42, 0) 70%); border-bottom: 1px solid #334155;">
            <h1 style="font-size: 3.5rem; background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem;">VTU Results Analytics</h1>
        </div>
    """, unsafe_allow_html=True)
    
    return dark_mode

def _default_config():
    return {
        "min_total": 40, "result_col": "Result", "total_col": "Total", "rollno_col": "USN",
        "name_col": "Name", "subject_code_col": "Subject Code", "subject_name_col": "Subject Name",
        "semester_col": "Semester"
    }

def check_dependencies():
    pass 

# ==========================================
# 3. MAIN APP LOGIC
# ==========================================

def main():
    dark_mode = _show_header()
    config = _default_config()

    # Upload
    col1, col2 = st.columns([1, 4])
    with col2:
        st.markdown("### 📤 Import Data")
        uploaded = st.file_uploader("Upload CSV/Excel", type=["csv", "xls", "xlsx"], accept_multiple_files=True, label_visibility="collapsed")
    with col1:
        st.info("Supported: CSV, Excel. (PDF currently disabled for stability)")

    if not uploaded:
        st.markdown("<div style='margin-top: 3rem; border-top: 1px solid #334155;'></div>", unsafe_allow_html=True)
        st.markdown(_get_footer_html(), unsafe_allow_html=True)
        return

    # Process
    df = pd.concat([parse_vtu_results(f) for f in uploaded], ignore_index=True)
    if df.empty:
        st.error("No valid data found.")
        return

    # Filters
    st.markdown("<div style='margin-top: 2rem; border-top: 1px solid #334155; margin-bottom: 2rem;'></div>", unsafe_allow_html=True)
    st.markdown("### 🛠️ Data Filters")
    c1, c2, c3 = st.columns(3)
    with c1:
        sub_opts = sorted(df["Subject Code"].unique()) if "Subject Code" in df.columns else []
        sel_codes = st.multiselect("Subjects", sub_opts, default=sub_opts)
    with c2:
        sem_opts = sorted(df["Semester"].unique()) if "Semester" in df.columns else []
        sel_sem = st.multiselect("Semesters", sem_opts, default=sem_opts)
    with c3:
        sec_opts = sorted(df["Section"].dropna().unique()) if "Section" in df.columns else []
        sel_sec = st.multiselect("Sections", sec_opts, default=sec_opts)

    # Filter Logic
    if sel_codes: df = df[df["Subject Code"].isin(sel_codes)]
    if sel_sem: df = df[df["Semester"].isin(sel_sem)]
    if sel_sec: df = df[df["Section"].isin(sel_sec)]

    # Compute
    per_student = compute_student_status(df)
    analysis_students = per_student[per_student["Status"] != "ABSENT"]
    
    # ----------------------------------------------------
    # SGPA Calculation with Syllabus Credits
    # ----------------------------------------------------
    syllabus_credits = {
        "BCS501": 3,
        "BCS502": 4,
        "BCS503": 4,
        "BCSL504": 1,
        "BCS515A": 3,
        "BCS515B": 3,
        "BRMK557": 3,
        "BNSK559": 0,
        "BCS586": 2,
        "BCS508": 2

         # -------- 7th Semester --------
    "BCS701": 4,
    "BCS702": 4,
    "BCS703": 4,
    "BCS786": 6, 
    "BME755C": 3,
    "BCS714D": 3,
    "BEC755A": 3,
    "BCS714B": 3,
    "BCV755B": 3,
    "BME755A": 3
    }
    
    per_student = compute_sgpa(per_student, df, syllabus_credits)
    
    # KPIs
    total_st = len(per_student)
    backlogs = len(analysis_students[analysis_students["Status"] == "FAIL"])
    pass_pct = (len(analysis_students[analysis_students["Status"] == "PASS"]) / len(analysis_students) * 100) if not analysis_students.empty else 0

    st.markdown("<br>", unsafe_allow_html=True)
    k1, k2, k3 = st.columns(3)
    k1.markdown(f"<div class='stat-card'><div class='stat-label'>Total Students</div><div class='stat-value' style='color:#3b82f6'>{total_st}</div></div>", unsafe_allow_html=True)
    k2.markdown(f"<div class='stat-card'><div class='stat-label'>With Backlogs</div><div class='stat-value' style='color:#ef4444'>{backlogs}</div></div>", unsafe_allow_html=True)
    k3.markdown(f"<div class='stat-card'><div class='stat-label'>Pass Percentage</div><div class='stat-value' style='color:#10b981'>{pass_pct:.1f}%</div></div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 3rem; border-top: 1px solid #334155; margin-bottom: 2rem;'></div>", unsafe_allow_html=True)

    # Charts
    c_chart, c_stats = st.columns([1, 1])
    with c_chart:
        st.markdown("#### 🍩 Pass/Fail Distribution")
        # Pie Chart Logic
        pie_data = per_student[per_student["Status"] != "ABSENT"]["Status"].value_counts().reset_index()
        pie_data.columns = ["Status", "Count"]
        colors = {"PASS": "#10b981", "FAIL": "#ef4444"}
        fig = go.Figure(go.Pie(
            labels=pie_data["Status"], values=pie_data["Count"],
            hole=0.65, marker=dict(colors=[colors.get(x, '#888') for x in pie_data["Status"]], line=dict(color='#0f172a', width=5)),
            textinfo='percent', textposition='outside', textfont=dict(size=14, color="#cbd5e1")
        ))
        fig.update_layout(showlegend=True, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          annotations=[dict(text=f"<span style='color:#94a3b8'>Total</span><br><span style='font-size:24px; color:white'>{pie_data['Count'].sum()}</span>", showarrow=False, x=0.5, y=0.5)])
        st.plotly_chart(fig, use_container_width=True)

    with c_stats:
        st.markdown("#### 🏅 Quick Statistics")
        p_count = pie_data[pie_data["Status"]=="PASS"]["Count"].sum() if not pie_data.empty else 0
        f_count = pie_data[pie_data["Status"]=="FAIL"]["Count"].sum() if not pie_data.empty else 0
        st.markdown(f"""
        <div style="background: #1e293b; padding: 1.5rem; border-radius: 12px; border: 1px solid #334155;">
            <div style="display:flex; justify-content:space-between; margin-bottom:1rem; border-bottom:1px solid #334155; padding-bottom:1rem;">
                <span style="color:#94a3b8">Passing</span><span style="color:#10b981; font-weight:bold; font-size:1.2rem">{p_count}</span>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span style="color:#94a3b8">Failing</span><span style="color:#ef4444; font-weight:bold; font-size:1.2rem">{f_count}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # SGPA Stats
    st.markdown("<div style='margin-top: 3rem; border-top: 1px solid #334155; margin-bottom: 2rem;'></div>", unsafe_allow_html=True)
    st.markdown("### 📈 SGPA Analytics")
    valid_sgpa = per_student[(per_student['SGPA'] > 0) & (per_student['Status'] != 'ABSENT')]
    
    if not valid_sgpa.empty:
        sc1, sc2 = st.columns([2, 1])
        with sc1:
            fig_hist = px.histogram(valid_sgpa, x="SGPA", nbins=20, color_discrete_sequence=["#3b82f6"])
            fig_hist.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#94a3b8")
            st.plotly_chart(fig_hist, use_container_width=True)
        with sc2:
            st.markdown(_get_sgpa_stats_html(valid_sgpa['SGPA'].mean(), valid_sgpa['SGPA'].max(), valid_sgpa['SGPA'].min()), unsafe_allow_html=True)

    # Subject Toppers
    st.markdown("<div style='margin-top: 3rem; border-top: 1px solid #334155; margin-bottom: 2rem;'></div>", unsafe_allow_html=True)
    st.markdown("### 🏆 Subject Toppers")
    avail_subs = sorted(df["Subject Code"].unique())
    if avail_subs:
        sel_sub = st.selectbox("Select Subject", avail_subs)
        sub_df = df[df["Subject Code"] == sel_sub].copy()
        if "Total" in sub_df.columns:
            sub_df["Total"] = pd.to_numeric(sub_df["Total"], errors='coerce').fillna(0)
            toppers = sub_df.sort_values("Total", ascending=False).head(10)
            if not toppers.empty:
                top1 = toppers.iloc[0]
                
                # FIXED: Check Name column existence to prevent KeyError
                t_name = top1.get("Name", "Unknown")
                t_usn = top1.get("USN", "Unknown")
                t_score = int(top1.get("Total", 0))
                
                tc1, tc2 = st.columns([1, 2])
                with tc1:
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, rgba(251, 191, 36, 0.1), rgba(15, 23, 42, 0.6)); border: 2px solid #fbbf24; border-radius: 16px; padding: 2rem; text-align: center;">
                        <div style="font-size: 3rem;">🏆</div>
                        <div style="color:#fbbf24; font-weight:bold; margin:0.5rem 0;">SUBJECT TOPPER</div>
                        <div style="color:white; font-size:1.2rem; font-weight:bold;">{t_name}</div>
                        <div style="color:#94a3b8; font-size:0.9rem;">{t_usn}</div>
                        <div style="margin-top:1rem; background:rgba(251,191,36,0.2); color:#fbbf24; padding:0.5rem; border-radius:20px; font-weight:bold;">{t_score} Marks</div>
                    </div>
                    """, unsafe_allow_html=True)
                with tc2:
                    st.dataframe(toppers[["USN", "Name", "Total", "Result"]].reset_index(drop=True), use_container_width=True)

    # Exports
    st.markdown("<div style='margin-top: 3rem; border-top: 1px solid #334155; margin-bottom: 2rem;'></div>", unsafe_allow_html=True)
    st.markdown("### 💾 Exports")
    
    with st.expander("🔽 Advanced Export Options", expanded=True):
        ec1, ec2, ec3 = st.columns(3)
        with ec1:
            # Detailed Section Report
           if "Section" in per_student.columns:
    try:
        import io
        import pandas as pd

        # 🔥 Ensure numeric columns before pivot
        for col in ["Internal", "External", "Total"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Optional: replace NaN with 0 (only if you want)
        df[["Internal", "External", "Total"]] = df[["Internal", "External", "Total"]].fillna(0)

        out = io.BytesIO()

        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:

            for sec in sorted(per_student["Section"].dropna().unique()):

                # Filter students of that section
                sec_usns = per_student[per_student["Section"] == sec]["USN"]
                raw_sec = df[df["USN"].isin(sec_usns)]

                # 🔹 Pivot subject-wise marks
                pivot = raw_sec.pivot_table(
                    index="USN",
                    columns="Subject Code",
                    values=["Internal", "External", "Total"],
                    aggfunc="first"
                )

                # 🔹 Flatten MultiIndex columns
                pivot = pivot.swaplevel(0, 1, axis=1).sort_index(axis=1)
                pivot.columns = [f"{c[0]} {c[1]}" for c in pivot.columns]

                # 🔹 Merge with student summary info
                final = (
                    per_student[per_student["Section"] == sec][
                        ["USN", "Name", "SGPA", "Status"]
                    ]
                    .merge(pivot, on="USN", how="left")
                )

                # 🔹 Calculate Grand Total
                tot_cols = [c for c in final.columns if " Total" in c]
                final["Grand Total"] = final[tot_cols].sum(axis=1)

                # 🔹 Reorder columns (Grand Total before SGPA)
                cols = list(final.columns)
                cols.remove("Grand Total")
                sgpa_idx = cols.index("SGPA")
                cols.insert(sgpa_idx, "Grand Total")
                final = final[cols]

                # 🔹 Write to Excel sheet
                final.to_excel(writer, sheet_name=f"Sec_{sec}", index=False)

        out.seek(0)

        st.download_button(
            "📑 Detailed Section Report (Excel)",
            out,
            "Detailed_Section_Report.xlsx",
            "application/vnd.ms-excel"
        )

    except Exception as e:
        st.error(f"Error: {e}")

else:
    st.caption("No Section info")


        with ec2:
            # Broadsheet Matrix (Simplified)
            if "Section" in df.columns:
                try:
                    out_b = io.BytesIO()
                    with pd.ExcelWriter(out_b, engine='xlsxwriter') as writer:
                        for sec in sorted(df["Section"].dropna().unique()):
                            sec_raw = df[df["Section"] == sec]
                            piv = sec_raw.pivot_table(index=["USN", "Name"], columns="Subject Code", values=["Total", "Result"], aggfunc="first")
                            piv = piv.swaplevel(0, 1, axis=1).sort_index(axis=1)
                            piv.columns = [f"{c[0]}_{c[1]}" for c in piv.columns]
                            piv.to_excel(writer, sheet_name=f"Matrix_{sec}")
                    out_b.seek(0)
                    st.download_button("📉 Result Matrix (Excel)", out_b, "Result_Matrix.xlsx", "application/vnd.ms-excel")
                except Exception as e: st.error(f"Error: {e}")
        
        with ec3:
             # Section Subject Stats
            if "Section" in df.columns:
                try:
                    out_s = io.BytesIO()
                    with pd.ExcelWriter(out_s, engine='xlsxwriter') as writer:
                        for sec in sorted(df["Section"].dropna().unique()):
                            sec_raw = df[df["Section"] == sec]
                            stats = sec_raw.groupby(["Subject Code", "Subject Name"]).agg(
                                Total=('USN', 'count'),
                                Absent=('Result', lambda x: x.astype(str).str.upper().isin(["A", "ABSENT"]).sum()),
                                Fail=('Result', lambda x: x.astype(str).str.upper().isin(["F", "FAIL"]).sum())
                            ).reset_index()
                            stats["Appeared"] = stats["Total"] - stats["Absent"]
                            stats["Passed"] = stats["Appeared"] - stats["Fail"]
                            stats["Pass%"] = (stats["Passed"] / stats["Appeared"].replace(0, np.nan) * 100).fillna(0).round(2)
                            stats.to_excel(writer, sheet_name=f"Stats_{sec}", index=False)
                    out_s.seek(0)
                    st.download_button("📊 Section Subject Stats", out_s, "Section_Subject_Stats.xlsx", "application/vnd.ms-excel")
                except Exception as e: st.error(f"Error: {e}")

    st.markdown("<div style='margin-top: 5rem;'></div>", unsafe_allow_html=True)
    st.markdown(_get_footer_html(), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
