import fitz  # PyMuPDF
import json
import os
from collections import defaultdict

def get_font_styles(doc):
    """
    Analyzes the document to find a hierarchy of font sizes for headings.
    """
    font_counts = defaultdict(int)
    # Analyze a subset of pages for efficiency if the document is very large
    page_limit = min(20, len(doc)) 
    for page in doc.pages(0, page_limit):
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if b['type'] == 0:  # Text block
                for l in b["lines"]:
                    for s in l["spans"]:
                        font_size = round(s["size"])
                        # Ignore very small text which is likely footer/header text
                        if font_size > 6:
                            font_counts[font_size] += len(s['text']) # Weight by length

    if not font_counts:
        # Provide default fallback sizes
        return {"H1": 24, "H2": 18, "H3": 14, "H4": 12, "body": 10}

    # Sort font sizes by frequency to find the body text
    sorted_by_freq = sorted(font_counts.items(), key=lambda item: item[1], reverse=True)
    body_size = sorted_by_freq[0][0] if sorted_by_freq else 10

    # Sort font sizes numerically to find heading levels
    sorted_sizes = sorted(font_counts.keys(), reverse=True)
    
    # Define heading sizes relative to the body text and each other
    styles = {"body": body_size}
    heading_levels = ["H1", "H2", "H3", "H4"]
    current_size_idx = 0
    
    for level in heading_levels:
        # Find the next largest font size that is distinct enough
        while current_size_idx < len(sorted_sizes) and sorted_sizes[current_size_idx] <= styles.get(heading_levels[heading_levels.index(level)-1], body_size):
            current_size_idx += 1
        
        if current_size_idx < len(sorted_sizes):
            styles[level] = sorted_sizes[current_size_idx]
            current_size_idx += 1
        else:
            # If no more larger fonts, assign a size slightly larger than the previous level
            styles[level] = styles.get(heading_levels[heading_levels.index(level)-1], body_size) + 1

    return styles

def extract_outline(pdf_path):
    """
    Extracts a structured outline (Title, H1, H2, etc.) from a PDF.
    This version assembles lines before processing to avoid fragmentation.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening {pdf_path}: {e}")
        return None

    styles = get_font_styles(doc)
    
    # Set thresholds for heading detection
    h_thresholds = {
        "H1": styles.get("H1", 24),
        "H2": styles.get("H2", 18),
        "H3": styles.get("H3", 14),
        "H4": styles.get("H4", 12),
    }
    body_size = styles.get("body", 10)

    title = ""
    outline = []
    
    # Try to get title from metadata first
    if doc.metadata and doc.metadata.get('title'):
        title = doc.metadata['title']

    # Search for a title on the first page if metadata is empty or unhelpful
    if not title or len(title) < 5:
        page = doc[0]
        blocks = page.get_text("dict", sort=True)["blocks"]
        max_font_size = 0
        potential_title_parts = []
        
        # Find the largest font size on the page
        for b in blocks:
            if b['type'] == 0:
                for l in b["lines"]:
                    for s in l["spans"]:
                        if s["size"] > max_font_size:
                            max_font_size = s["size"]
        
        # Collect all text with that largest font size as the title
        for b in blocks:
             if b['type'] == 0:
                for l in b["lines"]:
                    line_text = "".join(s["text"] for s in l["spans"]).strip()
                    # Check if the primary font size of the line matches the max size
                    if l["spans"] and round(l["spans"][0]["size"]) >= max_font_size - 1:
                        potential_title_parts.append(line_text)
        
        title = " ".join(potential_title_parts)

    if not title:
        title = os.path.basename(pdf_path)

    # Extract headings from the document
    ## CHANGED: Page enumeration now starts from 0
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict", sort=True)["blocks"]
        for b in blocks:
            if b['type'] == 0:  # Text block
                for l in b["lines"]:
                    if not l["spans"]:
                        continue

                    ## CHANGED: Assemble the full line text from all its spans
                    text = "".join(s["text"] for s in l["spans"]).strip()
                    font_size = round(l["spans"][0]["size"])
                    font_flags = l["spans"][0]["flags"] # Check for bold

                    # Skip empty, short, or likely non-heading lines
                    if len(text) < 3 or text.isnumeric() or not any(c.isalpha() for c in text):
                        continue

                    level = None
                    # Use font size and bolding to determine the level
                    is_bold = font_flags & 2**4 > 0
                    
                    if font_size >= h_thresholds["H1"]:
                        level = "H1"
                    elif font_size >= h_thresholds["H2"]:
                        level = "H2"
                    elif font_size >= h_thresholds["H3"]:
                        level = "H3"
                    elif font_size >= h_thresholds["H4"] and (font_size > body_size or is_bold):
                        level = "H4"
                        
                    if level:
                        # Avoid adding duplicate headings from running headers/footers
                        if not outline or (outline[-1]["text"] != text and outline[-1]["page"] != page_num):
                            outline.append({
                                "level": level,
                                "text": text,
                                "page": page_num ## CHANGED: Uses 0-indexed page_num
                            })

    return {
        "title": title,
        "outline": outline
    }

# Main execution logic remains the same
def main():
    input_dir = "Adobe_Hackathon\Challenge1A\input" 
    output_dir = "Adobe_Hackathon\Challenge1A\output"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if not os.path.isdir(input_dir):
        print(f"Error: Input directory not found at {input_dir}")
        return

    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(input_dir, filename)
            print(f"Processing {pdf_path}...")
            
            result = extract_outline(pdf_path)
            
            if result:
                # Clean up title by removing RFP if it's already there
                if "request for proposal" in result['title'].lower():
                    result['title'] = result['title'].replace("RFP:","").strip()

                output_filename = os.path.splitext(filename)[0] + ".json"
                output_path = os.path.join(output_dir, output_filename)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=4, ensure_ascii=False)
                print(f"Successfully created {output_path}")

if __name__ == "__main__":
    main()