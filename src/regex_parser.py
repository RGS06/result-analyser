import re
import pandas as pd

def parse_vtu_text_regex(text: str) -> list[dict]:
    """
    Parses raw text extracted from VTU result PDFs using regular expressions.
    Handles multiple students in a single text string.
    
    Args:
        text (str): Raw text from OCR or digital PDF extraction.
        
    Returns:
        list[dict]: A list of dictionaries, each containing student and subject details.
    """
    # Regex to find student blocks
    # Fuzzy matching for "University Seat Number" and "Student Name"
    student_header_pattern = re.compile(
        r"(?:Univ.*?Seat.*?Number|USN)\s*[:\-]?\s*([A-Z0-9]+).*?"
        r"(?:Stud.*?Name|Name)\s*[:\-]?\s*([^\n\r]+)",
        re.IGNORECASE | re.DOTALL
    )
    
    # Regex to extract subjects and marks from a block
    # Less strict: allows optional leading whitespace and captures even if line markers are imperfect
    subject_row_pattern = re.compile(
        r"([A-Z0-9]{5,10})\s+(.*?)\s+(\d+|A|AB|NP|--)\s+(\d+|A|AB|NP|--)\s+(\d+|A|AB|NP|--)\s+([A-Z/PFWL]+)",
        re.IGNORECASE
    )
    
    extracted_data = []
    
    # Find all student headers to identify block boundaries
    matches = list(student_header_pattern.finditer(text))
    
    for i, match in enumerate(matches):
        usn = match.group(1).strip().upper()
        name = match.group(2).strip().upper()
        
        # Calculate the text segment for this student
        start_pos = match.end()
        end_pos = matches[i+1].start() if i+1 < len(matches) else len(text)
        student_block = text[start_pos:end_pos]
        
        # Search for subjects within this student's block
        subjects_found = subject_row_pattern.findall(student_block)
        
        for sub in subjects_found:
            subject_data = {
                "Student Name": name,
                "USN": usn,
                "Subject Code": sub[0].strip().upper(),
                "Subject Name": sub[1].strip().upper(),
                "Internal": sub[2].strip().upper(),
                "External": sub[3].strip().upper(),
                "Total": sub[4].strip().upper(),
                "Result": sub[5].strip().upper()
            }
            extracted_data.append(subject_data)
            
    return extracted_data

if __name__ == "__main__":
    # Example usage with mockup text
    sample_text = """
    University Seat Number: 1VT18CS001
    Student Name: JOHN DOE
    18CS31 DATA STRUCTURES 25 45 70 P
    18CS32 COMPUTER ORGANIZATION 20 50 70 P
    18CSL37 ANALOG AND DIGITAL ELECTRONICS LABORATORY 40 50 90 P
    
    University Seat Number: 1VT18CS002
    Student Name: JANE SMITH
    18CS31 DATA STRUCTURES 15 20 35 F
    18CS32 COMPUTER ORGANIZATION 22 40 62 P
    """
    
    results = parse_vtu_text_regex(sample_text)
    for res in results:
        print(res)
