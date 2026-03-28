import sys
from pathlib import Path

# Add rag/ to path
sys.path.insert(0, str(Path(__file__).parent / "rag"))
from ingestion.pdf_loader import load_pdfs

# Test a specific NCERT file
test_path = Path(__file__).parent / "textbooks" / "class 3 maths" / "cemm1dd" / "cemm101.pdf"
print(f"Testing: {test_path.resolve()}")
print(f"Exists: {test_path.exists()}")

if test_path.exists():
    try:
        docs = load_pdfs([str(test_path.resolve())])
        print(f"Successfully extracted {len(docs)} pages.")
        if docs:
            print("First 100 characters of page 1:")
            print(docs[0].page_content[:100])
    except Exception as e:
        print(f"Error during extraction: {e}")
else:
    print("Test file not found! Please check the path.")
