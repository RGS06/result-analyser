import io
import cv2
import numpy as np
import pdfplumber
import pytesseract
import platform
import os
from pdf2image import convert_from_bytes, convert_from_path
from PIL import Image

# For Windows, try to find Tesseract if not in PATH
if platform.system() == "Windows":
    windows_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Users\{}\AppData\Local\Tesseract-OCR\tesseract.exe'.format(os.getlogin() if os.getlogin() else 'default'),
    ]
    for path in windows_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            break

def is_scanned(pdf_source) -> bool:
    """
    Detects whether a PDF is scanned or text-based.
    Accepts file path (str) or file content (bytes).
    Returns True if scanned, False if text-based.
    """
    try:
        if isinstance(pdf_source, bytes):
            pdf = pdfplumber.open(io.BytesIO(pdf_source))
        else:
            pdf = pdfplumber.open(pdf_source)
            
        with pdf:
            # Check first 3 pages
            for page in pdf.pages[:3]:
                text = page.extract_text()
                if text and text.strip():
                    return False
        return True
    except Exception:
        return True

def deskew(image: np.ndarray) -> np.ndarray:
    """
    Detects the skew angle of the image and rotates it to align horizontally.
    """
    coords = np.column_stack(np.where(image > 0))
    angle = cv2.minAreaRect(coords)[-1]
    
    # The cv2.minAreaRect returns angles between -90 and 0
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
        
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    
    return rotated

def preprocess_image(image: Image.Image) -> np.ndarray:
    """
    Advanced preprocessing for OCR:
    1. Grayscale conversion
    2. Gaussian Blur (noise reduction)
    3. Adaptive Thresholding (handles uneven lighting)
    4. Deskewing (straightens tilted scans)
    """
    # Convert PIL Image to OpenAI format (BGR)
    img_array = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    
    # 1. Apply Gaussian Blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # 2. Apply Adaptive Thresholding
    # This is often better than static thresholding for scanned documents with shadows
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 11, 2
    )
    
    # 3. Deskew the image
    deskewed = deskew(thresh)
    
    # 4. Invert back to black-on-white (Tesseract usually prefers this or specified by PSM)
    # However, many OCR engines prefer white-on-black for internal processing, 
    # but for text-to-string, we'll return a clean binary image.
    final = cv2.bitwise_not(deskewed)
    
    return final

def ocr_pdf(pdf_source) -> str:
    """
    Converts all pages of a scanned PDF to images and runs Tesseract OCR.
    """
    try:
        if isinstance(pdf_source, bytes):
            images = convert_from_bytes(pdf_source, dpi=300)
        else:
            images = convert_from_path(pdf_source, dpi=300)
            
        full_text = []
        for img in images:
            processed_img = preprocess_image(img)
            # Run OCR
            text = pytesseract.image_to_string(processed_img, config='--psm 6')
            full_text.append(text)
            
        return "\n\n".join(full_text)
    except Exception as e:
        return f"OCR Failure: {e}"

def extract_text_from_pdf(pdf_source) -> str:
    """
    Extracts text from PDF. Automatically decides between text-extraction and OCR.
    """
    if is_scanned(pdf_source):
        return ocr_pdf(pdf_source)
    else:
        try:
            if isinstance(pdf_source, bytes):
                pdf = pdfplumber.open(io.BytesIO(pdf_source))
            else:
                pdf = pdfplumber.open(pdf_source)
                
            with pdf:
                return "\n\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as e:
            return ocr_pdf(pdf_source)  # Fallback to OCR on error
