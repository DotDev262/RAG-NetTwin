import pypdf
from pathlib import Path
from typing import List, Dict
import re

def extract_text_from_pdf(pdf_path: str) -> List[Dict]:
    """
    Extract text from PDF with page numbers and metadata
    Returns list of dicts with: page_num, text, section_title
    """
    pages = []
    
    with open(pdf_path, 'rb') as file:
        pdf_reader = pypdf.PdfReader(file)
        
        for page_num, page in enumerate(pdf_reader.pages, 1):
            text = page.extract_text()
            
            # Clean text
            text = clean_text(text)
            
            # Try to identify section title
            section_title = extract_section_title(text)
            
            pages.append({
                'page_num': page_num,
                'text': text,
                'section_title': section_title,
                'source_file': Path(pdf_path).name
            })
    
    return pages

def clean_text(text: str) -> str:
    """Clean extracted text"""
    if not text:
        return ""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove page numbers
    text = re.sub(r'\b\d+\s+of\s+\d+\b', '', text)
    # Remove header/footer patterns
    text = re.sub(r'Chapter\s+\d+', '', text, flags=re.IGNORECASE)
    return text.strip()

def extract_section_title(text: str) -> str:
    """Try to extract section title from page text"""
    if not text:
        return "Empty Page"
    lines = text.split('\n')
    # Usually first few lines contain the section title
    for line in lines[:5]:
        line = line.strip()
        if len(line) > 10 and len(line) < 100:
            # Check if it looks like a title (no commands)
            if not line.startswith(('ip ', 'interface ', 'router ', 'access-list ')):
                return line
    return "Unknown Section"

if __name__ == "__main__":
    # Example usage (will fail if file doesn't exist)
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        try:
            pages = extract_text_from_pdf(pdf_path)
            print(f"Extracted {len(pages)} pages from {pdf_path}")
            if pages:
                print(f"First page preview: {pages[0]['text'][:200]}...")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Usage: python pdf_extractor.py <path_to_pdf>")
