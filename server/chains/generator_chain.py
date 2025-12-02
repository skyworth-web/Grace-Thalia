# server/chains/generator_chain.py

import os
import logging
from operator import itemgetter

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableMap, RunnableLambda

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma")


# ============================================================
# Build Unified Generator Chain (Transcript + Resume RAG)
# ============================================================
def build_generator_chain():
    """
    Retrieval-augmented generation pipeline that uses:
    - transcript context (live STT)
    - resume/job context
    - summary context (optional)
    """

    if not os.path.exists(CHROMA_DIR):
        logger.warning("⚠ Vector DB missing — using simple chain.")
        return _build_simple_chain()

    # LLM for generation (streaming enabled)
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.3,
        streaming=True,
        max_tokens=500,
    )

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    chroma = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
    )

    # --- Retrievers ---
    transcript_retriever = chroma.as_retriever(
        search_kwargs={"k": 6},
        filter={"type": "transcript"}
    )

    resume_retriever = chroma.as_retriever(
        search_kwargs={"k": 6},
        filter={"type": "resume"}
    )

    summary_retriever = chroma.as_retriever(
        search_kwargs={"k": 3},
        filter={"type": "summary"}
    )

    # ============================================================
    # HELPERS
    # ============================================================

    def retrieve_transcript(inputs):
        q = inputs.get("transcript", "")
        docs = transcript_retriever.invoke(q)
        logger.info(f"🗣 Retrieved {len(docs)} transcript chunks")
        return docs

    def retrieve_resume(inputs):
        q = inputs.get("transcript", "")
        docs = resume_retriever.invoke(q)
        logger.info(f"📄 Retrieved {len(docs)} resume chunks")
        return docs

    def retrieve_summary(inputs):
        try:
            q = inputs.get("transcript", "")
            docs = summary_retriever.invoke(q)
            logger.info(f"🧾 Retrieved {len(docs)} summary chunks")
            return docs
        except Exception:
            return []

    def format_docs(docs):
        parts = []
        for d in docs:
            meta = d.metadata.get("type", "unknown")
            parts.append(f"[{meta}] {d.page_content}")
        return "\n\n".join(parts)

    # ============================================================
    # PROMPT TEMPLATE (clean + transcript-first)
    # ============================================================
    prompt = PromptTemplate(
        input_variables=[
            "transcript_context",
            "resume_context",
            "summary_context",
            "transcript",
            "chat_history",
            "full_interview_context"
        ],
        template="""
You are an advanced INTERVIEW COPILOT.  
Your job is to produce a natural, spoken answer for the candidate.

====================================================
🎙 **CONVERSATION HISTORY (Transcript-Based Context)**  
Use this FIRST and MOST IMPORTANT when answering:
{transcript_context}

====================================================
📄 **RESUME / EXPERIENCE CONTEXT**  
Use this when question relates to skills, tech, experience:
{resume_context}

====================================================
🧠 **PAST SUMMARY CONTEXT (If available)**  
Use this to avoid repeating mistakes and improve consistency:
{summary_context}

====================================================
💬 **WHAT THE INTERVIEWER JUST SAID:**  
"{transcript}"

====================================================
📝 **FULL INTERVIEW CONTEXT:**  
(Use lightly — avoid repetition)
{full_interview_context}

====================================================
### 🔥 TASK
Generate an answer the candidate should SAY OUT LOUD.

RULES:
- Keep it 2–4 sentences.
- Be confident, conversational, and natural.
- Use FIRST PERSON ("I", "my experience…")
- DO NOT repeat the interviewer's question.
- Ground answer in transcript FIRST.
- Use resume context only when relevant.
- Never fabricate resume details.
- Sound human, not scripted.

Now produce ONLY the candidate’s spoken answer:
""",
    )

    # ============================================================
    # BUILD LCEL PIPELINE
    # ============================================================

    chain = (
        RunnableMap({
            "transcript_context": RunnableLambda(retrieve_transcript) | RunnableLambda(format_docs),
            "resume_context": RunnableLambda(retrieve_resume) | RunnableLambda(format_docs),
            "summary_context": RunnableLambda(retrieve_summary) | RunnableLambda(format_docs),
            "transcript": itemgetter("transcript"),
            "chat_history": itemgetter("chat_history"),
            "full_interview_context": itemgetter("full_interview_context"),
        })
        | prompt
        | llm
        | StrOutputParser()
    )

    chain = chain | RunnableLambda(lambda text: {"answer": text})
    logger.info("✅ Generator chain ready (Transcript + Resume RAG Active)")
    return chain


# ============================================================
# SIMPLE FALLBACK CHAIN
# ============================================================
def _build_simple_chain():
    logger.warning("⚠ Using fallback generator (no RAG).")
    llm = ChatOpenAI(model="gpt-4o", temperature=0.3, streaming=True)

    prompt = PromptTemplate(
        input_variables=["transcript"],
        template="""
The interviewer said: "{transcript}"

Give a natural, confident 2–4 sentence spoken answer.
""",
    )

    base = prompt | llm | StrOutputParser()
    return base | RunnableLambda(lambda x: {"answer": x})
