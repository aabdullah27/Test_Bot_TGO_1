import streamlit as st
from llama_index.core import VectorStoreIndex, Document, Settings
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.llms.groq import Groq
import faiss
from docx import Document as DocxDocument
import pymupdf4llm
import tempfile
import os

# Initialize session state variables
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "google_api_key" not in st.session_state:
    st.session_state.google_api_key = ""
if "current_page" not in st.session_state:
    st.session_state.current_page = "upload"
if "index" not in st.session_state:
    st.session_state.index = None
if "assessment_history" not in st.session_state:
    st.session_state.assessment_history = []

def read_file(file):
    if file.name.endswith('.pdf'):
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file.getvalue())
            tmp_file_path = tmp_file.name
        try:
            md_text = pymupdf4llm.to_markdown(tmp_file_path)
        finally:
            os.unlink(tmp_file_path)
        return md_text
    elif file.name.endswith('.docx'):
        return "\n".join(para.text for para in DocxDocument(file).paragraphs)
    else:
        return file.getvalue().decode()

def process_documents(uploaded_files):
    documents = [Document(text=read_file(file), metadata={"filename": file.name}) 
                for file in uploaded_files]
    
    d = 768  # Dimension for Google embeddings
    faiss_index = faiss.IndexFlatL2(d)
    vector_store = FaissVectorStore(faiss_index=faiss_index)
    
    st.session_state.index = VectorStoreIndex.from_documents(
        documents,
        vector_store=vector_store
    )

def generate_mcq(context, num_questions=5):
    prompt = f"""
    Based on the following context, generate {num_questions} multiple choice questions.
    Each question should have 4 options with only one correct answer.
    Format:
    Q1. [Question]
    a) [Option]
    b) [Option]
    c) [Option]
    d) [Option]
    Correct Answer: [a/b/c/d]

    Context: {context}
    """
    
    query_engine = st.session_state.index.as_query_engine(
        response_mode="compact"
    )
    response = query_engine.query(prompt)
    return str(response)

def generate_free_response(context):
    prompt = """
    Based on the context, generate 3 open-ended questions that test understanding
    of the key concepts. Include model answers for assessment.
    """
    query_engine = st.session_state.index.as_query_engine(
        response_mode="compact"
    )
    response = query_engine.query(prompt)
    return str(response)

# Streamlit UI
st.set_page_config(page_title="Learning Assessment App", page_icon="📚", layout="wide")

# Sidebar for API keys and document upload
with st.sidebar:
    st.header("🔑 API Keys")
    st.session_state.api_key = st.text_input("Enter your Groq API Key:", type="password")
    st.session_state.google_api_key = st.text_input("Enter your Google API Key:", type="password")
    
    if st.session_state.current_page == "upload":
        st.header("📁 Document Upload")
        uploaded_files = st.file_uploader(
            "Upload your learning materials (PDF, DOCX, TXT)",
            accept_multiple_files=True,
            type=['pdf', 'docx', 'txt']
        )
        
        if uploaded_files and st.session_state.api_key and st.session_state.google_api_key:
            with st.spinner("Processing documents..."):
                llm = Groq(api_key=st.session_state.api_key, model="llama-3.3-70b-versatile")
                embed_model = GeminiEmbedding(api_key=st.session_state.google_api_key)
                
                Settings.embed_model = embed_model
                Settings.llm = llm
                
                process_documents(uploaded_files)
            st.success(f"{len(uploaded_files)} document(s) processed successfully!")
            st.session_state.current_page = "menu"

# Main content area
st.title("📚 Learning Assessment Platform")

if st.session_state.current_page == "upload":
    st.info("Please upload your learning materials in the sidebar to get started!")

elif st.session_state.current_page == "menu":
    st.header("Choose Assessment Type")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📝 Knowledge Assessment (MCQ)", use_container_width=True):
            st.session_state.current_page = "mcq"
    
    with col2:
        if st.button("💭 Skills Development (Free Response)", use_container_width=True):
            st.session_state.current_page = "free_response"

elif st.session_state.current_page == "mcq":
    st.header("Multiple Choice Assessment")
    if st.button("← Back to Menu"):
        st.session_state.current_page = "menu"
    
    num_questions = st.slider("Number of questions:", 5, 20, 10)
    if st.button("Generate MCQ Assessment"):
        with st.spinner("Generating questions..."):
            mcq_questions = generate_mcq(context="", num_questions=num_questions)
            st.markdown(mcq_questions)
            st.download_button(
                "Download Questions",
                mcq_questions,
                file_name="mcq_assessment.txt"
            )

elif st.session_state.current_page == "free_response":
    st.header("Free Response Assessment")
    if st.button("← Back to Menu"):
        st.session_state.current_page = "menu"
    
    if st.button("Generate Free Response Questions"):
        with st.spinner("Generating questions..."):
            free_response_questions = generate_free_response(context="")
            st.markdown(free_response_questions)
            st.download_button(
                "Download Questions",
                free_response_questions,
                file_name="free_response_assessment.txt"
            )
