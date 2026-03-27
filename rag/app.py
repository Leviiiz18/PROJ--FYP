import streamlit as st
import tempfile

from utils.session import create_session_id
from ingestion.pdf_loader import load_pdfs
from embeddings.embedder import get_embedding_model
from vector_store.faiss_manager import create_faiss_index
from retriever.retrieval import get_retriever
from llm.qa_chain import build_answer

st.set_page_config(page_title="RAG PDF Assistant", layout="wide")

st.title("📄 RAG PDF Assistant")
st.write("Upload documents and ask questions based on their content.")

# Session handling
if "session_id" not in st.session_state:
    st.session_state.session_id = create_session_id()

uploaded_files = st.file_uploader(
    "Upload PDF files",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    with st.spinner("Indexing documents..."):
        temp_paths = []

        for file in uploaded_files:
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file.write(file.read())
            temp_paths.append(temp_file.name)

        # Load & index documents
        docs = load_pdfs(temp_paths)
        embeddings = get_embedding_model()
        vector_store = create_faiss_index(
            docs, embeddings, st.session_state.session_id
        )

        retriever = get_retriever(vector_store)

    st.success("Documents indexed successfully!")

    query = st.text_input("Ask a question")

    if query:
        with st.spinner("Thinking..."):
            # 🔍 Retrieve relevant chunks
            retrieved_docs = retriever.get_relevant_documents(query)

            if not retrieved_docs:
                st.warning("No relevant information found in uploaded documents.")
            else:
                # 🧠 Build context
                context = "\n\n".join(
                    [
                        f"(Source: {doc.metadata.get('source')}, Page {doc.metadata.get('page')})\n{doc.page_content}"
                        for doc in retrieved_docs
                    ]
                )

                # 🤖 Generate answer via OpenRouter
                answer = build_answer(context, query)

                st.subheader("Answer")
                st.write(answer)

                with st.expander("Sources"):
                    for doc in retrieved_docs:
                        st.write(
                            f"- {doc.metadata.get('source')} | Page {doc.metadata.get('page')}"
                        )
