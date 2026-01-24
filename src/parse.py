from __future__ import annotations

import io
import os
import re
from itertools import product
from typing import IO

import pandas as pd
import pdfplumber

from .ocr import is_scanned, extract_text_from_pdf, ocr_pdf
from .regex_parser import parse_vtu_text_regex


def _clean_table_rows(raw_table: list[list[str | None]]) -> list[list[str]]:
    """Clean raw table rows: strip cells, drop fully empty rows."""
    cleaned: list[list[str]] = []
    for row in raw_table:
        if row is None:
            continue
        normalized = [str(cell).strip() if cell is not None else "" for cell in row]
        if any(cell for cell in normalized):
            cleaned.append(normalized)
    return cleaned


def _pick_header_index(rows: list[list[str]]) -> int:
    """Pick the most reasonable header row index: the first row with the
    maximum count of non-empty cells."""
    if not rows:
        return 0
    non_empty_counts = [sum(1 for c in r if c) for r in rows]
    max_count = max(non_empty_counts)
    for idx, cnt in enumerate(non_empty_counts):
        if cnt == max_count:
            return idx
    return 0


def _drop_empty_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Drop columns that are entirely empty or all NaN after coercion."""
    if df.empty:
        return df
    drop_cols: list[int] = []
    for idx in range(df.shape[1]):
        series = df.iloc[:, idx]
        if series.isna().all():
            drop_cols.append(idx)
            continue
        stripped = series.astype(str).str.strip()
        if stripped.eq("").all():
            drop_cols.append(idx)
    if not drop_cols:
        return df
    # Drop by positional indices to avoid ambiguity when duplicate column names exist.
    keep_cols = [i for i in range(df.shape[1]) if i not in drop_cols]
    return df.iloc[:, keep_cols]


def _ensure_unique_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Guarantee column labels are unique so downstream concat/reindex succeeds."""
    if df.empty:
        return df
    new_cols = []
    seen: dict[str, int] = {}
    for col in df.columns:
        name = str(col) if col is not None else ""
        if name == "":
            name = "Unnamed"
        count = seen.get(name, 0)
        if count:
            new_cols.append(f"{name}_{count}")
        else:
            new_cols.append(name)
        seen[name] = count + 1
    df.columns = new_cols
    return df


def _coalesce_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse duplicate-named columns by taking first non-null value row-wise."""
    if df.empty or not df.columns.duplicated().any():
        return df
    ordered_cols: list[str] = []
    combined: dict[str, pd.Series] = {}
    for idx, col in enumerate(df.columns):
        name = str(col)
        series = df.iloc[:, idx]
        if name not in combined:
            combined[name] = series
            ordered_cols.append(name)
        else:
            combined[name] = combined[name].combine_first(series)
    return pd.DataFrame({col: combined[col] for col in ordered_cols})


def _extract_tables_from_pdf(pdf_bytes: bytes) -> pd.DataFrame | None:
    """Try multiple pdfplumber strategies and page rotations to extract tables.

    Returns the concatenated DataFrame if any tables are found; otherwise None.
    """
    all_frames: list[pd.DataFrame] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        # Strategies inspired by pdfplumber table extraction options
        vertical_strategies = ["lines", "text", "explicit", "edges"]
        horizontal_strategies = ["lines", "text", "explicit", "edges"]
        # Try normal and rotated views
        rotations = [0, 90, 180, 270]

        for page_index, page in enumerate(pdf.pages):
            for angle in rotations:
                try:
                    pg = page if angle == 0 else page.rotate(angle)
                except Exception:  # noqa: BLE001
                    pg = page

                for v_strat, h_strat in product(vertical_strategies, horizontal_strategies):
                    try:
                        tables = pg.extract_tables(
                            table_settings={
                                "vertical_strategy": v_strat,
                                "horizontal_strategy": h_strat,
                                # more generous snap distance helps imperfect lines
                                "snap_tolerance": 3,
                                "join_tolerance": 3,
                                "edge_min_length": 3,
                                "min_words_vertical": 1,
                                "min_words_horizontal": 1,
                            }
                        )
                    except Exception:
                        tables = []

                    for table in tables or []:
                        cleaned = _clean_table_rows(table)
                        if len(cleaned) < 2:
                            continue
                        header_idx = _pick_header_index(cleaned[:3])  # look at first few rows for header
                        header = cleaned[header_idx]
                        body = cleaned[header_idx + 1 :]
                        if not body:
                            continue
                        # Ensure column count consistency by padding/truncation
                        col_count = len(header)
                        normalized_body = [
                            (row + [""] * (col_count - len(row)))[:col_count]
                            for row in body
                        ]
                        try:
                            df = pd.DataFrame(normalized_body, columns=header)
                        except Exception:
                            # Fallback to generic column names
                            df = pd.DataFrame(normalized_body)
                        if not df.empty:
                            df = _drop_empty_columns(df)
                            df = _ensure_unique_columns(df)
                            all_frames.append(df)

    if all_frames:
        return pd.concat(all_frames, ignore_index=True)
    return None


def _extract_with_camelot(pdf_bytes: bytes) -> pd.DataFrame | None:
    try:
        import camelot  # type: ignore
    except Exception:
        return None
    try:
        tmp_path = "_tmp_parse.pdf"
        with open(tmp_path, "wb") as f:
            f.write(pdf_bytes)
        frames: list[pd.DataFrame] = []
        for flavor in ["lattice", "stream"]:
            try:
                tables = camelot.read_pdf(tmp_path, pages="all", flavor=flavor)
                for t in tables:
                    df = t.df
                    if not df.empty:
                        # First row as header if it looks like one
                        header = df.iloc[0].tolist()
                        body = df.iloc[1:]
                        body.columns = header
                        clean = _drop_empty_columns(body)
                        clean = _ensure_unique_columns(clean)
                        frames.append(clean)
            except Exception:
                continue
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        if frames:
            return pd.concat(frames, ignore_index=True)
    except Exception:
        return None
    return None


def _extract_with_tabula(pdf_bytes: bytes) -> pd.DataFrame | None:
    try:
        import tabula  # type: ignore
    except Exception:
        return None
    try:
        tmp_path = "_tmp_parse.pdf"
        with open(tmp_path, "wb") as f:
            f.write(pdf_bytes)
        try:
            dfs = tabula.read_pdf(tmp_path, pages="all", multiple_tables=True, lattice=True)
        except Exception:
            dfs = []
        frames: list[pd.DataFrame] = []
        for df in dfs or []:
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            df = _drop_empty_columns(df)
            df = _ensure_unique_columns(df)
            frames.append(df)
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        if frames:
            return pd.concat(frames, ignore_index=True)
    except Exception:
        return None
    return None


def _extract_with_ocr(pdf_bytes: bytes) -> pd.DataFrame | None:
    """Very lightweight OCR fallback: convert PDF pages to images and run
    regex-based extraction on the OCR output."""
    # Use the improved OCR logic from ocr.py
    text = ocr_pdf(pdf_bytes)
    if not text or "OCR Failure" in text:
        return None

    try:
        # Use the new robust regex parser
        data = parse_vtu_text_regex(text)
        if not data:
            return None
            
        return pd.DataFrame(data)
    except Exception:
        return None


def _extract_pdf_metadata(pdf_bytes: bytes) -> dict[str, str]:
    """Grab USN/Name/Semester info from plain text."""
    meta: dict[str, str] = {}
    try:
        if is_scanned(pdf_bytes):
            # For scanned PDFs, we only OCR the first 2 pages for performance reasons
            text = extract_text_from_pdf(pdf_bytes[:2000000]) # Roughly 2MB for first page or so, or better use a dedicated function
            # Actually ocr_pdf does all pages, let's keep it simple for now or use pdf2image for specific pages
            text = ocr_pdf(pdf_bytes) 
        else:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                text = "\n".join(filter(None, (page.extract_text() for page in pdf.pages[:2])))
    except Exception:
        return meta

    lines = [ln.strip() for ln in text.splitlines() if ln and ln.strip()]

    def _extract_value(keyword: str) -> str | None:
        keyword_lower = keyword.lower()
        for idx, line in enumerate(lines):
            cleaned = line.strip()
            if cleaned.lower().startswith(keyword_lower):
                after_colon = cleaned.split(":", 1)
                if len(after_colon) > 1 and after_colon[1].strip():
                    return after_colon[1].strip()
                if idx + 1 < len(lines):
                    nxt = lines[idx + 1].lstrip(":").strip()
                    if nxt:
                        return nxt
        return None

    usn = _extract_value("University Seat Number")
    name = _extract_value("Student Name")
    semester = _extract_value("Semester")
    if usn:
        meta["USN"] = usn
    if name:
        meta["Name"] = name.title()
    if semester:
        meta["Semester"] = semester
    return meta


def _cleanup_pdf_results(df: pd.DataFrame, metadata: dict[str, str]) -> pd.DataFrame:
    if df.empty:
        return df
    if "Subject Code" in df.columns:
        mask = df["Subject Code"].notna() & df["Subject Code"].astype(str).str.strip().ne("")
        df = df[mask].copy()
    if metadata:
        for key, value in metadata.items():
            df[key] = value
    if "Semester" not in df.columns:
        df["Semester"] = metadata.get("Semester", 0)
    desired = [
        "USN",
        "Name",
        "Semester",
        "Subject Code",
        "Subject Name",
        "Internal",
        "External",
        "Total",
        "Result",
        "Announced / Updated on",
    ]
    existing = [c for c in desired if c in df.columns]
    if existing:
        df = df[existing].copy()
    if "Subject Code" in df.columns:
        subset_cols = [c for c in ["USN", "Subject Code", "Subject Name", "Total", "Result"] if c in df.columns]
        df = df.drop_duplicates(subset=subset_cols, keep="first")
    return df.reset_index(drop=True)


def _read_file(uploaded) -> tuple[pd.DataFrame, dict[str, str]]:
    name = getattr(uploaded, "name", "").lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded), {}
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded), {}
    if name.endswith(".pdf"):
        uploaded.seek(0)
        pdf_bytes = uploaded.read()
        metadata = _extract_pdf_metadata(pdf_bytes)
        try:
            # 1) Native pdfplumber multi-strategy
            df = _extract_tables_from_pdf(pdf_bytes)
            if df is not None and not df.empty:
                return df, metadata
            # 2) Camelot
            df = _extract_with_camelot(pdf_bytes)
            if df is not None and not df.empty:
                return df, metadata
            # 3) Tabula
            df = _extract_with_tabula(pdf_bytes)
            if df is not None and not df.empty:
                return df, metadata
            # 4) Improved OCR + Regex fallback
            df = _extract_with_ocr(pdf_bytes)
            if df is not None and not df.empty:
                return df, metadata
            
            # 5) Direct text-to-regex fallback (for text-based PDFs where table extraction missed)
            try:
                text = extract_text_from_pdf(pdf_bytes)
                data = parse_vtu_text_regex(text)
                if data:
                    return pd.DataFrame(data), metadata
            except Exception:
                pass
            # Save diagnostics
            import streamlit as st
            st.error("❌ PDF Processing Failed")
            st.write("No usable tables were found after trying multiple engines (pdfplumber, Camelot, Tabula, OCR).")
            st.write("• If this is a scanned PDF, ensure good image quality or convert to CSV/Excel.")
            st.write("• For ruled tables, installing Java (for Tabula) and Ghostscript (for Camelot) improves results.")
            raise ValueError("No tables found in PDF file.")
        except Exception as e:  # noqa: BLE001
            import streamlit as st
            st.error(f"❌ PDF Processing Error: {e}")
            st.write("**Troubleshooting tips:**")
            st.write("• Ensure the PDF contains tabular data (not just images)")
            st.write("• Try converting the PDF to CSV/Excel first")
            st.write("• Check if the PDF is password-protected")
            raise
    # Try CSV then Excel fallbacks
    try:
        uploaded.seek(0)
        return pd.read_csv(uploaded), {}
    except Exception:
        uploaded.seek(0)
        return pd.read_excel(uploaded), {}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    import streamlit as st
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    # st.info(f"Extracted columns: {list(df.columns)}")
    # Drop junk columns: single characters, 'Unnamed', or columns with special chars that look like OCR artifacts
    junk_patterns = [
        r'^Unnamed.*$',  # Unnamed columns
        r'^[a-zA-Z]$',   # Single letters
        r'^[\ue218\x00]+$',  # Special unicode or null chars
        r'^[0-9]+$',     # Pure numbers (likely split parts)
        r'^[:/]$',       # Punctuation
    ]
    keep_cols = []
    for col in df.columns:
        is_junk = any(re.match(pattern, col) for pattern in junk_patterns)
        if not is_junk:
            keep_cols.append(col)
    df = df[keep_cols]
    # Map common alternative column names to expected ones
    col_map = {
        'Roll No': 'USN',
        'RollNo': 'USN',
        'Roll_Number': 'USN',
        'Student Name': 'Name',
        'Student_Name': 'Name',
        'SubjectCode': 'Subject Code',
        'Subject_Name': 'Subject Name',
        'Sem': 'Semester',
        'Ext': 'External',
        'Tot': 'Total',
        'ResultStatus': 'Result',
        'University Seat Number': 'USN',
        'Subject\nCode': 'Subject Code',
        'External\nMarks': 'External',
        'Internal\nMarks': 'Internal',
        # PDF-specific variations
        'USN': 'USN',
        'Name': 'Name',
        'Subject Code': 'Subject Code',
        'Subject Name': 'Subject Name',
        'Semester': 'Semester',
        'External': 'External',
        'Total': 'Total',
        'Result': 'Result',
        'Internal': 'Internal',
        # Common VTU variations
        'University Seat No': 'USN',
        'Seat Number': 'USN',
        'Reg No': 'USN',
        'Registration No': 'USN',
        'Student': 'Name',
        'Subject': 'Subject Name',
        'Sub Code': 'Subject Code',
        'Marks': 'Total',
        'External Marks': 'External',
        'Internal Marks': 'Internal',
        'Status': 'Result',
        'Grade': 'Result',
        # Handle split columns by merging similar ones
        'Subject Code': 'Subject Code',
        'Subject Name': 'Subject Name',
        'External Marks': 'External',
        'Internal Marks': 'Internal',
        'Total Marks': 'Total',
        'Result Status': 'Result',
    }
    # Also handle columns with actual newlines (not just escaped)
    df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)
    df.rename(columns={c: c.replace('\n', ' ').replace('\r', ' ').replace('  ', ' ').strip() for c in df.columns}, inplace=True)
    # After cleaning, map again for any columns that now match
    df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)
    df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)
    df = _coalesce_duplicate_columns(df)
    # Fill missing columns with default values so analysis can proceed
    required = ['USN', 'Name', 'Subject Code', 'Subject Name', 'Semester', 'External', 'Total', 'Result']
    missing = [col for col in required if col not in df.columns]
    if missing:
        # st.sidebar.warning(f"Missing required columns: {missing}. Filling with default values.")
        for col in missing:
            if col == 'Semester':
                df[col] = 0  # or any default semester value
            elif col == 'Name':
                df[col] = 'Unknown'
            else:
                df[col] = ''
    # Convert relevant columns to numeric if they exist
    for col in ['External', 'Total', 'Internal']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def parse_vtu_results(uploaded: IO[bytes]) -> pd.DataFrame:
    """Parse VTU results file into a normalized DataFrame.

    The function is resilient to column name differences; downstream
    functions accept configurable column names.
    """
    df, metadata = _read_file(uploaded)
    df = _normalize_columns(df)
    if metadata:
        df = _cleanup_pdf_results(df, metadata)
    return df
