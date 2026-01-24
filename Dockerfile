FROM python:3.10-slim

# Install system dependencies required for PDF processing
# - default-jre: Required for tabula-py
# - ghostscript: Required for camelot-py
# - poppler-utils: Required for pdf2image
# - tesseract-ocr: Required for pytesseract
# - libgl1-mesa-glx: Required for opencv
RUN apt-get update && apt-get install -y \
    default-jre \
    ghostscript \
    poppler-utils \
    tesseract-ocr \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port Streamlit runs on
EXPOSE 8501

# Run the application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
