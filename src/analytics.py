from __future__ import annotations

import io
from typing import Dict, List

import numpy as np
import pandas as pd


def _compute_subject_pass(series_total: pd.Series | None, series_external: pd.Series | None, min_total: int, min_external: int) -> pd.Series:
    total_ok = (series_total >= min_total) if series_total is not None else True
    external_ok = (series_external >= min_external) if series_external is not None else True
    return total_ok & external_ok


def get_grade_point(mark: float) -> int:
    """Standard VTU 2021/2022 Scheme Grading."""
    if mark >= 90: return 10
    elif mark >= 80: return 9
    elif mark >= 70: return 8
    elif mark >= 60: return 7
    elif mark >= 55: return 6
    elif mark >= 50: return 5
    elif mark >= 40: return 4
    else: return 0


def compute_sgpa(
    per_student: pd.DataFrame,
    df: pd.DataFrame,
    subject_credits: Dict[str, int],
    subject_code_col: str,
    total_col: str,
    result_col: str
) -> pd.DataFrame:
    """Compute SGPA for each student."""
    # We need to go back to the original filtered dataframe to get individual subject marks
    # per_student only has summary stats.
    
    # 1. Map marks to grade points
    df = df.copy()
    
    # Ensure numeric
    df[total_col] = pd.to_numeric(df[total_col], errors='coerce').fillna(0)
    
    # Calculate Grade Points for each row
    df['GradePoint'] = df[total_col].apply(get_grade_point)
    
    # Handle Fail cases - if Result is FAIL, GradePoint matches calculation (usually <40 is 0 anyway) 
    # but strictly speaking, if absent or failed, it should be 0.
    # If result_col exists, use it to force 0 if F
    if result_col in df.columns:
        # If explicitly failed, force 0 GP
        mask_fail = df[result_col].astype(str).str.upper().str.contains(r"FAIL|^F$")
        df.loc[mask_fail, 'GradePoint'] = 0

    # Map Credits
    # subject_credits is {subject_code: credit_value}
    df['Credit'] = df[subject_code_col].map(subject_credits).fillna(0)
    
    # Calculate Credit Points (CP = Credit * GP)
    df['CreditPoints'] = df['Credit'] * df['GradePoint']
    
    # Group by Student (USN)
    sgpa_stats = df.groupby('USN').agg(
        TotalCredits=('Credit', 'sum'),
        TotalCreditPoints=('CreditPoints', 'sum')
    ).reset_index()
    
    # SGPA = TotalCP / TotalCredits
    sgpa_stats['SGPA'] = np.where(
        sgpa_stats['TotalCredits'] > 0, 
        sgpa_stats['TotalCreditPoints'] / sgpa_stats['TotalCredits'], 
        0.0
    )
    
    sgpa_stats['SGPA'] = sgpa_stats['SGPA'].round(2)
    
    # Merge back to per_student
    merged = pd.merge(per_student, sgpa_stats[['USN', 'SGPA']], on='USN', how='left')
    return merged



def compute_student_status(
    df: pd.DataFrame,
    rollno_col: str,
    name_col: str,
    result_col: str | None,
    total_col: str | None,
    external_col: str | None,
    min_total: int,
    min_external: int,
) -> pd.DataFrame:
    data = df.copy()

    series_total = data[total_col] if total_col and total_col in data.columns else None
    series_external = data[external_col] if external_col and external_col in data.columns else None

    if result_col and result_col in data.columns:
        # Accept 'PASS', 'P', 'PASSED' (case-insensitive) as pass
        subject_pass = data[result_col].astype(str).str.upper().str.contains(r"PASS|PASSED|^P$")
    else:
        subject_pass = _compute_subject_pass(series_total, series_external, min_total, min_external)

    data["SubjectPass"] = subject_pass.astype(bool)

    grouped = (
        data.groupby([rollno_col, name_col], dropna=False)
        .agg(
            Subjects=("SubjectPass", "size"),
            SubjectsPassed=("SubjectPass", "sum"),
        )
        .reset_index()
    )

    grouped["Backlogs"] = grouped["Subjects"] - grouped["SubjectsPassed"]
    grouped["Status"] = np.where(grouped["Backlogs"] == 0, "PASS", "FAIL")

    return grouped[[rollno_col, name_col, "Subjects", "SubjectsPassed", "Backlogs", "Status"]]


def compute_subject_statistics(
    df: pd.DataFrame,
    subject_code_col: str,
    subject_name_col: str,
    result_col: str | None,
    total_col: str | None,
    external_col: str | None,
    min_total: int,
    min_external: int,
) -> pd.DataFrame:
    data = df.copy()

    series_total = data[total_col] if total_col and total_col in data.columns else None
    series_external = data[external_col] if external_col and external_col in data.columns else None

    if result_col and result_col in data.columns:
        # Accept 'PASS', 'P', 'PASSED' (case-insensitive) as pass
        subject_pass = data[result_col].astype(str).str.upper().str.contains(r"PASS|PASSED|^P$")
    else:
        subject_pass = _compute_subject_pass(series_total, series_external, min_total, min_external)

    data["SubjectPass"] = subject_pass.astype(bool)

    group_cols = [c for c in [subject_code_col, subject_name_col] if c in data.columns]
    if not group_cols:
        group_cols = [subject_code_col]

    stats = (
        data.groupby(group_cols, dropna=False)
        .agg(
            Appeared=("SubjectPass", "size"),
            Passed=("SubjectPass", "sum"),
            AvgTotal=(total_col, "mean") if (total_col and total_col in data.columns) else ("SubjectPass", "mean"),
        )
        .reset_index()
    )

    stats["Failed"] = stats["Appeared"] - stats["Passed"]
    stats["Pass%"] = np.where(stats["Appeared"] > 0, (stats["Passed"] / stats["Appeared"]) * 100.0, np.nan)

    # Order by subject code then pass%
    sort_cols = [c for c in [subject_code_col, "Pass%", "Appeared"] if c in stats.columns]
    stats = stats.sort_values(sort_cols, ascending=[True, False, False])

    # Round metrics
    for col in ["AvgTotal", "Pass%"]:
        if col in stats.columns:
            stats[col] = stats[col].round(2)

    return stats


def compute_overall_metrics(per_student: pd.DataFrame) -> Dict[str, float]:
    # Count unique, non-empty USNs for total_students
    if 'USN' in per_student.columns:
        total_students = per_student['USN'].dropna().astype(str).str.strip().replace('', pd.NA).dropna().nunique()
    else:
        total_students = 0
    overall_pass = float((per_student["Status"] == "PASS").mean() * 100.0) if total_students else 0.0
    students_with_backlogs = int((per_student["Backlogs"] > 0).sum())
    return {
        "total_students": total_students,
        "overall_pass_percentage": overall_pass,
        "students_with_backlogs": students_with_backlogs,
    }


def build_excel_summary(raw: pd.DataFrame, per_student: pd.DataFrame, per_subject: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        raw.to_excel(writer, sheet_name="Raw", index=False)
        per_student.to_excel(writer, sheet_name="PerStudent", index=False)
        per_subject.to_excel(writer, sheet_name="PerSubject", index=False)
    return output.getvalue()


def build_pdf_summary(
    per_student: pd.DataFrame,
    per_subject: pd.DataFrame,
    overall: Dict[str, float],
    department: str | None = None,
) -> bytes:
    """Create a compact PDF with overall KPIs and subject-wise table."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except Exception:  # noqa: BLE001
        # If reportlab is not available for some reason, return empty bytes
        return b""

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elems: List = []

    title = "VTU Results Summary"
    if department:
        title = f"{department} - {title}"
    elems.append(Paragraph(title, styles["Title"]))
    elems.append(Spacer(1, 12))

    kpis = [
        ["Total students", str(overall.get("total_students", 0))],
        ["Overall pass %", f"{overall.get('overall_pass_percentage', 0.0):.2f}%"],
        ["Students with backlogs", str(overall.get("students_with_backlogs", 0))],
    ]
    kpi_table = Table(kpis, hAlign="LEFT")
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    elems.append(kpi_table)
    elems.append(Spacer(1, 12))

    # Subject-wise table (limited columns for readability)
    columns = [c for c in ["Subject Code", "Subject Name", "Appeared", "Passed", "Failed", "Pass%"] if c in per_subject.columns]
    subj_df = per_subject[columns].copy()
    data = [columns] + subj_df.astype(str).values.tolist()
    table = Table(data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
    ]))
    elems.append(Paragraph("Subject-wise summary", styles["Heading2"]))
    elems.append(table)

    doc.build(elems)
    return buffer.getvalue()
