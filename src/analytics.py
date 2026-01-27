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


# ========================= SGPA =========================
def compute_sgpa(
    per_student: pd.DataFrame,
    df: pd.DataFrame,
    subject_credits: Dict[str, int],
    subject_code_col: str,
    total_col: str,
    result_col: str
) -> pd.DataFrame:

    df = df.copy()
    df[total_col] = pd.to_numeric(df[total_col], errors='coerce').fillna(0)

    df['GradePoint'] = df[total_col].apply(get_grade_point)

    # FAIL or ABSENT → GP = 0
    if result_col in df.columns:
        mask_zero_gp = df[result_col].astype(str).str.upper().str.contains(r"FAIL|^F$|^A$")
        df.loc[mask_zero_gp, 'GradePoint'] = 0

    df['Credit'] = df[subject_code_col].map(subject_credits).fillna(0)
    df['CreditPoints'] = df['Credit'] * df['GradePoint']

    sgpa_stats = df.groupby('USN').agg(
        TotalCredits=('Credit', 'sum'),
        TotalCreditPoints=('CreditPoints', 'sum')
    ).reset_index()

    sgpa_stats['SGPA'] = np.where(
        sgpa_stats['TotalCredits'] > 0,
        sgpa_stats['TotalCreditPoints'] / sgpa_stats['TotalCredits'],
        0.0
    ).round(2)

    merged = pd.merge(per_student, sgpa_stats[['USN', 'SGPA']], on='USN', how='left')
    return merged


# ========================= STUDENT STATUS =========================
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

    if result_col and result_col in data.columns:
        subject_pass = data[result_col].astype(str).str.upper().str.contains(r"PASS|PASSED|^P$")
    else:
        subject_pass = _compute_subject_pass(data[total_col], data[external_col], min_total, min_external)

    data["SubjectPass"] = subject_pass.astype(bool)

    grouped = (
        data.groupby([rollno_col, name_col], dropna=False)
        .agg(
            Subjects=("SubjectPass", "size"),
            SubjectsPassed=("SubjectPass", "sum"),
        )
        .reset_index()
    )

    # -------- ABSENT DETECTION --------
    absent_mask = (
        data.groupby(rollno_col)[result_col]
        .apply(lambda x: x.astype(str).str.upper().eq("A").all())
        .reset_index(name="AllAbsent")
    )

    grouped = grouped.merge(absent_mask, on=rollno_col, how="left")
    grouped["AllAbsent"] = grouped["AllAbsent"].fillna(False)

    grouped["Backlogs"] = grouped["Subjects"] - grouped["SubjectsPassed"]

    grouped["Status"] = np.select(
        [
            grouped["AllAbsent"],
            grouped["Backlogs"] == 0
        ],
        [
            "ABSENT",
            "PASS"
        ],
        default="FAIL"
    )

    return grouped[[rollno_col, name_col, "Subjects", "SubjectsPassed", "Backlogs", "Status"]]


# ========================= SUBJECT STATS =========================
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

    if result_col and result_col in data.columns:
        subject_pass = data[result_col].astype(str).str.upper().str.contains(r"PASS|PASSED|^P$")
    else:
        subject_pass = _compute_subject_pass(data[total_col], data[external_col], min_total, min_external)

    data["SubjectPass"] = subject_pass.astype(bool)

    group_cols = [subject_code_col, subject_name_col]
    stats = (
        data.groupby(group_cols, dropna=False)
        .agg(
            Appeared=("SubjectPass", "size"),
            Passed=("SubjectPass", "sum"),
            AvgTotal=(total_col, "mean")
        )
        .reset_index()
    )

    stats["Failed"] = stats["Appeared"] - stats["Passed"]
    stats["Pass%"] = np.where(stats["Appeared"] > 0, (stats["Passed"] / stats["Appeared"]) * 100.0, np.nan)

    stats["AvgTotal"] = stats["AvgTotal"].round(2)
    stats["Pass%"] = stats["Pass%"].round(2)

    return stats.sort_values([subject_code_col, "Pass%"], ascending=[True, False])


# ========================= OVERALL =========================
def compute_overall_metrics(per_student: pd.DataFrame) -> Dict[str, float]:
    total_students = per_student['USN'].nunique()
    overall_pass = float((per_student["Status"] == "PASS").mean() * 100.0)
    students_with_backlogs = int((per_student["Status"] == "FAIL").sum())

    return {
        "total_students": total_students,
        "overall_pass_percentage": overall_pass,
        "students_with_backlogs": students_with_backlogs,
    }


# ========================= EXPORTS =========================
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

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elems: List = []

    elems.append(Paragraph("VTU Results Summary", styles["Title"]))
    elems.append(Spacer(1, 12))

    kpis = [
        ["Total students", str(overall.get("total_students", 0))],
        ["Overall pass %", f"{overall.get('overall_pass_percentage', 0.0):.2f}%"],
        ["Students with backlogs", str(overall.get("students_with_backlogs", 0))],
    ]
    table = Table(kpis)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
    elems.append(table)

    doc.build(elems)
    return buffer.getvalue()
