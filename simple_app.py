import streamlit as st
import pandas as pd
import tempfile
import os
import time
from src.ocr import is_scanned, extract_text_from_pdf
from src.parse import parse_vtu_results

def main():
    st.set_page_config(page_title="VTU Result OCR Analyzer", page_icon="📝")
    
    st.title("📝 VTU Result OCR Analyzer")
    st.markdown("""
    Upload a VTU Result PDF (digital or scanned). 
    This tool will automatically detect the type, perform OCR if necessary, and extract structured data.
    """)

    uploaded_file = st.file_uploader("Upload VTU Result PDF", type=["pdf"])

    if uploaded_file is not None:
        try:
            with st.spinner("🔍 Processing PDF..."):
                # Read bytes for detection and text extraction
                file_bytes = uploaded_file.read()
                
                # 1. Detect PDF Type
                scanned = is_scanned(file_bytes)
                if scanned:
                    st.warning("🕵️ Scanned PDF detected. Using OCR engine...")
                else:
                    st.success("📄 Text-based PDF detected. Using digital extraction...")

                # 2. Extract Text (for display/preview)
                with st.expander("👁️ View Extracted Raw Text"):
                    raw_text = extract_text_from_pdf(file_bytes)
                    st.text_area("Raw Text Output", raw_text, height=300)

                # 3. Parse structured results
                # We need to reset the file pointer or pass the bytes again
                uploaded_file.seek(0)
                df = parse_vtu_results(uploaded_file)

                if df is not None and not df.empty:
                    st.subheader("📊 Structured Results")
                    st.dataframe(df, use_container_width=True)

                    # 4. Download CSV
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Results as CSV",
                        data=csv,
                        file_name=f"VTU_Results_{int(time.time())}.csv",
                        mime="text/csv",
                    )
                else:
                    st.error("❌ Failed to parse any results from the PDF. Please ensure it's a valid VTU result document.")

        except Exception as e:
            st.error(f"⚠️ An error occurred during processing: {str(e)}")
            st.info("Tip: Ensure Tesseract OCR and Poppler are installed on your system if you are running locally.")

if __name__ == "__main__":
    main()
