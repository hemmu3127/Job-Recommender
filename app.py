import streamlit as st
import json
import os
from parsers import parse_resume_with_gemini
from job_scraper import scrape_jobs
from ats_scorer import calculate_ats_score
from chat import chat_with_gemini
import google.generativeai as genai
import logging
import chromadb
from langchain.text_splitter import RecursiveCharacterTextSplitter
import pickle
import hashlib

__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger("chromadb").setLevel(logging.WARNING)

# Gemini API configuration
genai.configure(api_key=os.getenv("GEMINI_API_KEY", "AIzaSyDlDLNXXLb7XQK8zLwGCpt2BwSjRlcbq3k"))

# File paths (using relative paths for portability)
BASE_DIR = os.path.dirname(__file__)
TEXT_FILE_PATH = os.path.join(BASE_DIR, "dataset.txt")  # Assumes dataset.txt is in the same directory
EMBEDDINGS_CACHE = os.path.join(BASE_DIR, "embeddings_cache.pkl")
CHROMA_DB_PATH = os.path.join(BASE_DIR, "chroma_db")
REFERRER_DATA_PATH = os.path.join(BASE_DIR, "referrer_data.json")

# Load referrer data
try:
    with open(REFERRER_DATA_PATH, 'r') as f:
        referrer_data = json.load(f)
except FileNotFoundError:
    st.error(f"Referrer data file not found at {REFERRER_DATA_PATH}. Please ensure it exists.")
    referrer_data = {}

# Helper Functions for Career Guidance Chatbot
def get_file_hash(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return hashlib.md5(file.read().encode()).hexdigest()

def load_or_create_embeddings():
    file_hash = get_file_hash(TEXT_FILE_PATH)
    if os.path.exists(EMBEDDINGS_CACHE):
        with open(EMBEDDINGS_CACHE, 'rb') as f:
            cached_data = pickle.load(f)
            if cached_data['file_hash'] == file_hash:
                return cached_data['chunks'], cached_data['embeddings']
    with open(TEXT_FILE_PATH, "r", encoding="utf-8") as file:
        combined_text = file.read()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50, separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""])
    chunks = text_splitter.split_text(combined_text)
    embeddings = []
    for chunk in chunks:
        emb = get_embedding(chunk)
        if emb:
            embeddings.append(emb)
    with open(EMBEDDINGS_CACHE, 'wb') as f:
        pickle.dump({'file_hash': file_hash, 'chunks': chunks, 'embeddings': embeddings}, f)
    return chunks, embeddings

def get_embedding(text):
    try:
        response = genai.embed_content(model="models/embedding-001", content=text, task_type="retrieval_document", title="Career Guidance")
        return response["embedding"]
    except Exception as e:
        logging.error(f"Embedding failed: {e}")
        return None

def initialize_chroma_db(chunks, embeddings):
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    if "career_guidance" in client.list_collections():
        collection = client.get_collection(name="career_guidance")
        if collection.count() == len(chunks):
            return collection
    if "career_guidance" in client.list_collections():
        client.delete_collection(name="career_guidance")
    collection = client.create_collection(name="career_guidance")
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        collection.add(documents=[chunk], ids=[str(i)], embeddings=[emb])
    return collection

# Load data for Career Guidance Chatbot
try:
    chunks, embeddings = load_or_create_embeddings()
    collection = initialize_chroma_db(chunks, embeddings)
except FileNotFoundError:
    st.error(f"Dataset file not found at {TEXT_FILE_PATH}. Please ensure it exists.")
    chunks, embeddings, collection = [], [], None

def get_relevant_chunks(query, n_results=3):
    if not collection:
        return []
    query_embedding = get_embedding(query)
    if not query_embedding:
        return []
    results = collection.query(query_embeddings=[query_embedding], n_results=n_results)
    return [doc for doc in results.get("documents", [[]])[0] if doc]

def generate_answer(prompt):
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        return model.generate_content(prompt).text
    except Exception as e:
        logging.error(f"Failed to generate answer: {e}")
        return "Sorry, I couldn't generate an answer at this time."

def build_prompt(query, context_chunks, chat_history):
    history_str = ""
    for entry in chat_history:
        history_str += f"User: {entry['user']}\nAssistant: {entry['bot']}\n\n"
    context = "\n\n".join(context_chunks) if context_chunks else "No specific context found. Answer based on general career guidance knowledge."
    prompt = (
        f"You are a career guidance expert. Below is the conversation with the user and some relevant context for the user's current question. "
        f"Please continue the conversation by providing a structured answer to the user's last question, focusing on interview prep, skill development, or career planning as relevant.\n\n"
        f"Conversation:\n{history_str}User: {query}\n\n"
        f"Relevant context:\n{context}\n\n"
        "Assistant:"
    )
    return prompt

def get_relevant_jobs(resume_json):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY", "AIzaSyDlDLNXXLb7XQK8zLwGCpt2BwSjRlcbq3k"))
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = (
        f"Based on this resume data: {json.dumps(resume_json)}, suggest 5 relevant job titles. "
        "Return the result as a single-line JSON string in this exact format: "
        "{\"job_titles\": [\"title1\", \"title2\", \"title3\", \"title4\", \"title5\"]}. "
        "Do not include any additional text, explanations, or line breaks outside the JSON string."
    )
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        return json.loads(response_text)['job_titles']
    except json.JSONDecodeError as e:
        print(f"JSON Parsing Error: {e}")
        print(f"Raw Response (Failed JSON): {response_text}")
        return ["Software Engineer", "Data Analyst", "Project Manager", "Business Analyst", "Product Manager"]
    except Exception as e:
        raise Exception(f"Gemini API Error: {e}")

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []
if 'jobs' not in st.session_state:
    st.session_state['jobs'] = []
if 'career_history' not in st.session_state:
    st.session_state['career_history'] = []

st.title("Resume ATS Analyzer & Job Matcher and Career Chatbot")

tab1, tab2 = st.tabs(["Resume ATS Analyzer & Job Matcher", "Career Guidance Chatbot"])

with tab1:
    st.subheader("Resume ATS Analyzer & Job Matcher")
    # Upload resume
    uploaded_file = st.file_uploader("Upload your resume (PDF)", type="pdf")
    if uploaded_file:
        with st.spinner("Parsing resume..."):
            resume_json = parse_resume_with_gemini(uploaded_file)
        if "error" in resume_json:
            st.error(f"Failed to parse resume: {resume_json['error']}")
        else:
            st.success("Resume parsed successfully!")
            st.json(resume_json)
            st.download_button(
                label="📥 Download Extracted JSON",
                data=json.dumps(resume_json, indent=4),
                file_name="parsed_resume.json",
                mime="application/json"
            )
            # Get relevant job titles
            with st.spinner("Fetching relevant job titles..."):
                try:
                    job_titles = get_relevant_jobs(resume_json)
                except Exception as e:
                    st.error(f"Error fetching job titles: {e}")
                    job_titles = ["Software Engineer", "Data Analyst", "Project Manager", "Business Analyst", "Product Manager"]
            st.write("Suggested Job Titles:", job_titles)
            # Scrape jobs based on selected job title
            selected_job_title = st.selectbox("Select a job title to search for:", job_titles)
            if st.button("Search Jobs"):
                with st.spinner("Scraping job listings..."):
                    try:
                        jobs = scrape_jobs(selected_job_title, resume_json)
                        st.session_state['jobs'] = jobs
                        st.success(f"Found {len(jobs)} jobs!")
                    except Exception as e:
                        st.error(f"Error scraping jobs: {e}")
                        st.session_state['jobs'] = []
            # Display jobs and calculate ATS score
            if st.session_state['jobs']:
                for i, job in enumerate(st.session_state['jobs']):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{job.get('Job Title', 'Job Title not found')}** - {job.get('Company', 'Company not found')}")
                        st.write(job.get('Job Description', {}).get('Description', 'No description available')[:200] + "...")
                    with col2:
                        if st.button(f"View ATS Score", key=f"ats_{i}"):
                            score = calculate_ats_score(resume_json, job.get('Job Description', {}).get('Description', ''))
                            st.write(f"ATS Score: {score}%")
                        referrer = referrer_data.get(job.get('Company', ''), "No referrer available")
                        st.write(f"Referrer: {referrer}")
            # Chat section
            st.subheader("Chat with Resume & Job Description")
            if st.session_state['jobs']:
                job_options = [f"{job.get('Job Title', 'Unknown')} at {job.get('Company', 'Unknown')}" for job in st.session_state['jobs']]
                selected_job_option = st.selectbox("Select a job to chat about:", job_options)
                selected_job = next((job for job in st.session_state['jobs'] if f"{job.get('Job Title', 'Unknown')} at {job.get('Company', 'Unknown')}" == selected_job_option), None)
                if selected_job:
                    job_desc = selected_job.get('Job Description', {}).get('Description', '')
                    for entry in st.session_state['chat_history']:
                        with st.chat_message("user"):
                            st.write(entry['user'])
                        with st.chat_message("assistant"):
                            st.write(entry['ai'])
                    user_input = st.text_input("Ask a question about your resume or this job:", key="chat_input")
                    if st.button("Send"):
                        if user_input:
                            response = chat_with_gemini(resume_json, job_desc, user_input, st.session_state['chat_history'])
                            st.session_state['chat_history'].append({"user": user_input, "ai": response})
                            st.rerun()

with tab2:
    st.header("Career Guidance Chatbot")
    for entry in st.session_state['career_history']:
        with st.chat_message("user"):
            st.write(entry['user'])
        with st.chat_message("assistant"):
            st.write(entry['bot'])
    career_input = st.chat_input("Ask any career-related question")
    if career_input:
        with st.spinner("Thinking..."):
            relevant_chunks = get_relevant_chunks(career_input)
            prompt = build_prompt(career_input, relevant_chunks, st.session_state['career_history'])
            response = generate_answer(prompt)
            st.session_state['career_history'].append({"user": career_input, "bot": response})
        st.rerun()

if __name__ == "__main__":
    st.write("Career Guidance App")