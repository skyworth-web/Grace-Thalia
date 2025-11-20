# server/chains/retrieval_chain.py

import os
import logging
from operator import itemgetter

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableMap, RunnableLambda
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")


# ---------------------------
# INGEST DOCUMENTS
# ---------------------------
def ingest_docs() -> None:
    """
    Read resume.txt and job.txt from ../data, split into chunks,
    and store them in a persistent Chroma vector store.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CHROMA_DIR, exist_ok=True)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    import shutil
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)
    os.makedirs(CHROMA_DIR, exist_ok=True)

    chroma = Chroma(
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
    )

    docs = []

    # Resume
    resume_path = os.path.join(DATA_DIR, "resume.txt")
    if os.path.exists(resume_path):
        with open(resume_path, "r", encoding="utf-8") as f:
            text = f.read()
        if text.strip():
            for d in splitter.create_documents([text]):
                d.metadata = {"source": "resume"}
                docs.append(d)

    # Job description
    job_path = os.path.join(DATA_DIR, "job.txt")
    if os.path.exists(job_path):
        with open(job_path, "r", encoding="utf-8") as f:
            text = f.read()
        if text.strip():
            for d in splitter.create_documents([text]):
                d.metadata = {"source": "job"}
                docs.append(d)

    if not docs:
        logger.warning("⚠ No documents to ingest")
        return

    chroma.add_documents(docs)
    chroma.persist()
    logger.info("✅ Ingestion complete (%d chunks)", len(docs))


# ---------------------------
# BUILD RETRIEVAL CHAIN — LCEL
# ---------------------------
def build_chain():
    """
    Build an LCEL retrieval chain that matches the old
    ConversationalRetrievalChain interface:

    chain.invoke({"question": str, "chat_history": list}) -> {"answer": str}
    """
    if not os.path.exists(CHROMA_DIR):
        raise ValueError("Vector store missing — run /ingest first")

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.6,
        streaming=False,
    )

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    chroma = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
    )

    retriever = chroma.as_retriever(search_kwargs={"k": 4})

    prompt = PromptTemplate(
        input_variables=["context", "question", "chat_history"],
        template="""
You are an AI interview coach.

Use this context:

{context}

Chat history:
{chat_history}

Question:
{question}

Write a confident, concise (2–3 sentence) interview answer.

Answer:
"""
    )

    # Base LCEL pipeline:
    # {question, chat_history} -> {"context", "question", "chat_history"} -> prompt -> llm -> text
    base_chain = (
        RunnableMap(
            {
                "context": itemgetter("question") | retriever,
                "question": itemgetter("question"),
                "chat_history": itemgetter("chat_history"),
            }
        )
        | prompt
        | llm
        | StrOutputParser()
    )

    # Wrap so main.py can still do: result = chain.invoke(...); answer = result["answer"]
    chain = base_chain | RunnableLambda(lambda text: {"answer": text})

    logger.info("✅ LCEL Retrieval chain ready")
    return chain


# ---------------------------
# SIMPLE RETRIEVER (optional)
# ---------------------------
def build_retriever(k: int = 5):
    """
    Just return a retriever instance if you want to use it elsewhere.
    """
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    if not os.path.exists(CHROMA_DIR):
        raise ValueError("Vector store missing — run /ingest first")

    chroma = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
    )

    return chroma.as_retriever(search_kwargs={"k": k})
