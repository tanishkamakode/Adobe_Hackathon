import fitz  # PyMuPDF
import json
import os
import statistics
from collections import defaultdict

def get_font_styles(doc):
    """
    Analyzes the document to find common font sizes and styles.
    This helps in identifying what constitutes a heading.
    """
    font_counts = defaultdict(int)
    for page in doc:
        # CORRECTED LINE: Removed the 'flags' parameter
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if b['type'] == 0:  # Text block
                for l in b["lines"]:
                    for s in l["spans"]:
                        font_size = round(s["size"])
                        font_counts[font_size] += 1
    
    # Filter out very rare font sizes to focus on common body and heading styles
    sorted_fonts = sorted(font_counts.keys(), reverse=True)
    if not sorted_fonts:
        return 24, 16, 12, 10 # Default sizes

    # Heuristic to determine heading levels
    # Assumes Title > H1 > H2 > H3 > Body text
    h1_size = sorted_fonts[0] if len(sorted_fonts) > 0 else 24
    h2_size = sorted_fonts[1] if len(sorted_fonts) > 1 else 16
    h3_size = sorted_fonts[2] if len(sorted_fonts) > 2 else 12
    
    # Try to find a common body text size
    body_size = 10
    if len(sorted_fonts) > 3:
        # Assume the most frequent size is body text
        body_size = max(font_counts, key=font_counts.get)

    # Ensure heading sizes are larger than body text
    h1_size = max(h1_size, body_size + 4)
    h2_size = max(h2_size, body_size + 2)
    h3_size = max(h3_size, body_size + 1)

    # Make sure H1 > H2 > H3
    h2_size = min(h2_size, h1_size -1)
    h3_size = min(h3_size, h2_size -1)

    return h1_size, h2_size, h3_size, body_size


def extract_outline(pdf_path):
    """
    Extracts a structured outline (Title, H1, H2, H3) from a PDF.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening {pdf_path}: {e}")
        return None

    h1_size, h2_size, h3_size, body_size = get_font_styles(doc)
    
    title = ""
    outline = []
    
    # Attempt to get title from metadata first
    if doc.metadata and doc.metadata['title']:
        title = doc.metadata['title']

    # Search for a title on the first page if metadata is empty
    if not title:
        page = doc[0]
        # CORRECTED LINE: Removed the 'flags' parameter
        blocks = page.get_text("dict")["blocks"]
        max_font_size = 0
        for b in blocks:
            if b['type'] == 0:
                for l in b["lines"]:
                    for s in l["spans"]:
                        if s["size"] > max_font_size:
                            max_font_size = s["size"]
                            title = s["text"].strip()
    
    # Fallback title
    if not title:
        title = os.path.basename(pdf_path)

    # Extract headings from the rest of the document
    for page_num, page in enumerate(doc, 1):
        # CORRECTED LINE: Removed the 'flags' parameter
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if b['type'] == 0:  # Text block
                for l in b["lines"]:
                    # Heuristic: A line with one span is more likely a heading
                    if len(l["spans"]) == 1:
                        span = l["spans"][0]
                        text = span["text"].strip()
                        font_size = round(span["size"])

                        # Skip very short or non-alphanumeric lines
                        if len(text) < 3 or not any(c.isalnum() for c in text):
                            continue

                        level = None
                        # Check against determined font sizes
                        if font_size >= h1_size:
                            level = "H1"
                        elif font_size >= h2_size:
                            level = "H2"
                        elif font_size >= h3_size and font_size > body_size:
                            level = "H3"
                        
                        if level:
                            outline.append({
                                "level": level,
                                "text": text,
                                "page": page_num
                            })

    return {
        "title": title,
        "outline": outline
    }

def main():
    """
    Main function to process all PDFs in the input directory.
    """
    # This path MUST match the path inside the Docker container
    input_dir = "Adobe_Hackathon\Challenge1A\input" 
    output_dir = "Adobe_Hackathon\Challenge1A\output"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Check if input directory exists
    if not os.path.isdir(input_dir):
        print(f"Error: Input directory not found at {input_dir}")
        print("Please make sure you are mounting your local PDF directory correctly.")
        return

    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(input_dir, filename)
            print(f"Processing {pdf_path}...")
            
            result = extract_outline(pdf_path)
            
            if result:
                output_filename = os.path.splitext(filename)[0] + ".json"
                output_path = os.path.join(output_dir, output_filename)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=4, ensure_ascii=False)
                print(f"Successfully created {output_path}")

if __name__ == "__main__":
    main()
