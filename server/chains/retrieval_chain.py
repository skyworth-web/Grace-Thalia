from langchain.chains import ConversationalRetrievalChain
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")

def ingest_docs():
    """Ingest resume and job description into Chroma vector store"""
    # Ensure directories exist
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CHROMA_DIR, exist_ok=True)
    
    # Check if API key is set
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    emb = OpenAIEmbeddings(model="text-embedding-3-small")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    
    # Initialize or load existing Chroma database
    # If collection exists, delete it to start fresh
    try:
        if os.path.exists(CHROMA_DIR):
            import shutil
            shutil.rmtree(CHROMA_DIR)
            os.makedirs(CHROMA_DIR, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not clear existing database: {e}")
    
    chroma = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=emb
    )
    
    all_docs = []
    
    # Process resume
    resume_path = os.path.join(DATA_DIR, "resume.txt")
    if os.path.exists(resume_path):
        with open(resume_path, "r", encoding="utf-8") as f:
            text = f.read()
        if text.strip():
            docs = splitter.create_documents([text])
            # Add metadata to identify source
            for doc in docs:
                doc.metadata = {"source": "resume"}
            all_docs.extend(docs)
    
    # Process job description
    job_path = os.path.join(DATA_DIR, "job.txt")
    if os.path.exists(job_path):
        with open(job_path, "r", encoding="utf-8") as f:
            text = f.read()
        if text.strip():
            docs = splitter.create_documents([text])
            for doc in docs:
                doc.metadata = {"source": "job_description"}
            all_docs.extend(docs)
    
    # Process profile info if available
    profile_path = os.path.join(DATA_DIR, "profile.json")
    if os.path.exists(profile_path):
        import json
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)
        profile_text = f"Profile Information:\n"
        if profile.get("name"):
            profile_text += f"Name: {profile['name']}\n"
        if profile.get("experience"):
            profile_text += f"Experience: {profile['experience']}\n"
        if profile.get("skills"):
            profile_text += f"Skills: {profile['skills']}\n"
        
        if profile_text.strip():
            docs = splitter.create_documents([profile_text])
            for doc in docs:
                doc.metadata = {"source": "profile"}
            all_docs.extend(docs)
    
    if all_docs:
        chroma.add_documents(all_docs)
        chroma.persist()
        print(f"✅ Ingested {len(all_docs)} document chunks")
    else:
        print("⚠️ No documents to ingest")

def build_chain():
    """Build the conversational retrieval chain"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7,
        streaming=False
    )
    
    emb = OpenAIEmbeddings(model="text-embedding-3-small")
    
    # Load existing Chroma database
    if not os.path.exists(CHROMA_DIR):
        raise ValueError("Vector store not found. Please ingest documents first.")
    
    chroma = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=emb
    )
    
    retriever = chroma.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 4}
    )
    
    # Create chain with custom prompt
    from langchain.prompts import PromptTemplate
    
    template = """You are an AI interview assistant helping a candidate during a live interview.
Use the following pieces of context (resume, job description, and profile) to provide concise, helpful answer suggestions.

Context:
{context}

Current conversation:
{chat_history}

Question: {question}

Provide a brief, natural-sounding answer suggestion (2-3 sentences max) that:
1. Directly addresses the question
2. Incorporates relevant experience from the resume
3. Aligns with the job requirements
4. Sounds conversational and confident

Answer:"""
    
    QA_PROMPT = PromptTemplate(
        template=template,
        input_variables=["context", "chat_history", "question"]
    )
    
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        return_source_documents=False,
        verbose=False,
        combine_docs_chain_kwargs={"prompt": QA_PROMPT}
    )
    
    return chain
