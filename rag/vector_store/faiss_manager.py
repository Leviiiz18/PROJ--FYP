import os
from langchain_community.vectorstores import FAISS

def create_faiss_index(docs, embedding_model, session_id):
    index = FAISS.from_documents(docs, embedding_model)

    path = f"vector_store/{session_id}"
    os.makedirs(path, exist_ok=True)

    index.save_local(path)
    return index

def load_faiss_index(embedding_model, session_id):
    path = f"vector_store/{session_id}"
    return FAISS.load_local(path, embedding_model)
