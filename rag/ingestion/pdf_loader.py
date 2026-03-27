from pypdf import PdfReader
from langchain.schema import Document

def load_pdfs(file_paths):
    documents = []

    for path in file_paths:
        reader = PdfReader(path)

        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                documents.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": path,
                            "page": page_num + 1
                        }
                    )
                )

    return documents
