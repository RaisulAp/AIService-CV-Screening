import os
from pathlib import Path
from pdfminer.high_level import extract_text as pdf_extract_text
from docx import Document

def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extracts text from a PDF file using pdfminer.six
    """
    return pdf_extract_text(str(pdf_path))


def extract_text_from_docx(docx_path: Path) -> str:
    """
    Extracts text from a DOCX file using python-docx
    """
    doc = Document(str(docx_path))
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return "\n".join(full_text)


def clean_text(text: str) -> str:
    """
    Normalizes whitespace and removes unwanted characters.
    """
    # Collapse multiple spaces and trim
    cleaned = " ".join(text.split())
    return cleaned


def batch_extract(input_dir: Path, output_dir: Path):
    """
    Walks through input_dir, converts PDFs and DOCXs to cleaned TXT files in output_dir.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    for file_path in input_dir.iterdir():
        if not file_path.is_file():
            continue
        text = None
        if file_path.suffix.lower() == ".pdf":
            text = extract_text_from_pdf(file_path)
        elif file_path.suffix.lower() in [".docx", ".doc"]:
            text = extract_text_from_docx(file_path)
        else:
            continue

        cleaned = clean_text(text)
        output_file = output_dir / f"{file_path.stem}.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(cleaned)
        print(f"Converted {file_path.name} -> {output_file.name}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Batch-convert CVs and job posts to clean TXT")
    parser.add_argument("--input-dir", type=Path, required=True, help="Path to folder with PDF/DOCX files")
    parser.add_argument("--output-dir", type=Path, required=True, help="Destination folder for TXT files")
    args = parser.parse_args()

    batch_extract(args.input_dir, args.output_dir)
