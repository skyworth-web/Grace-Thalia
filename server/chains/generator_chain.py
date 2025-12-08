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


def _load_full_resume() -> str:
    """Load the full resume text from file (1-2 pages, perfect for full context)."""
    resume_path = os.path.join(DATA_DIR, "resume.txt")
    logger.info(f"🔍 Attempting to load resume from: {resume_path}")
    logger.info(f"🔍 DATA_DIR exists: {os.path.exists(DATA_DIR)}")
    logger.info(f"🔍 Resume file exists: {os.path.exists(resume_path)}")
    
    if os.path.exists(resume_path):
        try:
            with open(resume_path, "r", encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                logger.info(f"✅ Loaded full resume ({len(text)} chars)")
                logger.debug(f"📄 Resume preview (first 200 chars): {text[:200]}...")
                return text
            else:
                logger.error(f"❌ Resume file exists but is EMPTY!")
        except Exception as e:
            logger.error(f"❌ Could not load full resume: {e}", exc_info=True)
    else:
        logger.error(f"❌ Resume file NOT FOUND at: {resume_path}")
        logger.error(f"❌ Make sure resume has been uploaded via /ingest endpoint")
    
    return ""


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
        # Still retrieve relevant chunks for additional context, but we'll use full resume as primary
        q = inputs.get("transcript", "")
        docs = resume_retriever.invoke(q)
        logger.info(f"📄 Retrieved {len(docs)} resume chunks (supplementary)")
        return docs
    
    def get_full_resume(inputs):
        # Load full resume text - this is the PRIMARY source for resume info
        # Load it fresh each time to ensure we have the latest version
        full_resume = _load_full_resume()
        if not full_resume or full_resume.startswith("ERROR:"):
            error_msg = "CRITICAL ERROR: Resume file is missing or empty. The LLM cannot generate accurate answers without the resume. Please upload your resume via the /ingest endpoint first. Without the resume, the system will generate placeholder text which is incorrect."
            logger.error(f"❌ {error_msg}")
            return error_msg
        logger.info(f"✅ Full resume loaded for generation ({len(full_resume)} chars)")
        # Log a preview to verify it's actual content
        preview = full_resume[:100].replace('\n', ' ')
        logger.info(f"📄 Resume preview: {preview}...")
        return full_resume

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
    
    def format_chat_history(chat_history):
        """Format chat history for the prompt."""
        if not chat_history:
            logger.info("💭 No chat history - this is the first question")
            return "No previous conversation."
        
        logger.info(f"💭 Formatting {len(chat_history)} previous conversation exchanges")
        formatted = []
        for i, exchange in enumerate(chat_history, 1):
            question = exchange.get("question", "")
            answer = exchange.get("answer", "")
            formatted.append(f"Q{i}: {question}\nA{i}: {answer}")
        
        result = "\n\n".join(formatted)
        logger.debug(f"💭 Chat history formatted ({len(result)} chars)")
        return result

    # ============================================================
    # PROMPT TEMPLATE (clean + transcript-first)
    # ============================================================
    prompt = PromptTemplate(
        input_variables=[
            "transcript_context",
            "full_resume_text",
            "resume_context",
            "summary_context",
            "transcript",
            "chat_history",
            "full_interview_context"
        ],
        template="""You are an advanced INTERVIEW COPILOT.  
Your job is to produce a natural, spoken answer for the candidate.

⚠️ CRITICAL: If the resume text below starts with "ERROR:" or "CRITICAL ERROR:", DO NOT generate an answer. Instead, return: "ERROR: Resume not loaded. Please upload resume first."

====================================================
📄 **COMPLETE RESUME (FULL TEXT - PRIMARY SOURCE)**  
THIS IS THE CANDIDATE'S COMPLETE RESUME. Study it carefully and use it as the PRIMARY source for all resume-related questions.

🚨 ABSOLUTE REQUIREMENTS - NO EXCEPTIONS:
1. Read the resume text below WORD BY WORD
2. Extract ACTUAL names, companies, technologies, projects, achievements
3. Use EXACT information from the resume - do NOT make up or use placeholders
4. If the resume says "Python, Django, React" - use those EXACT technologies
5. If the resume says "Worked at Google" - say "Google", NOT "[Company Name]"
6. NEVER use brackets like [your field], [Company Name], [mention key responsibilities], [specific field or industry]
7. NEVER use placeholder text or generic statements
8. If you don't see specific info in the resume, say what you DO see, don't use placeholders
9. FORBIDDEN PATTERNS (DO NOT USE):
   - "[specific field or industry]"
   - "[Company Name]"
   - "[mention key responsibilities]"
   - "[your field]"
   - Any text in square brackets [like this]

RESUME TEXT (READ THIS CAREFULLY):
{full_resume_text}

====================================================
🎙 **CONVERSATION HISTORY (Transcript-Based Context)**  
Use this FIRST and MOST IMPORTANT when answering:
{transcript_context}

====================================================
📄 **SUPPLEMENTARY RESUME CHUNKS (If needed for additional context)**  
These are semantic search results - use only if full resume above doesn't cover something:
{resume_context}

====================================================
🧠 **PAST SUMMARY CONTEXT (If available)**  
Use this to avoid repeating mistakes and improve consistency:
{summary_context}

====================================================
💬 **WHAT THE INTERVIEWER JUST SAID:**  
"{transcript}"

====================================================
💭 **PREVIOUS CONVERSATION (CHAT HISTORY):**
Use this to maintain context and avoid repetition. Reference previous answers naturally.
{chat_history}

====================================================
📝 **FULL INTERVIEW CONTEXT:**  
(Use lightly — avoid repetition)
{full_interview_context}

====================================================
### 🔥 TASK
Generate an answer the candidate should SAY OUT LOUD.

CRITICAL RULES - READ CAREFULLY:
1. Keep it 2–4 sentences.
2. Be confident, conversational, and natural.
3. Use FIRST PERSON ("I", "my experience…")
4. DO NOT repeat the interviewer's question.
5. Ground answer in transcript FIRST.
6. **MANDATORY: Use ONLY ACTUAL details from the resume above**
7. **FORBIDDEN: NEVER use placeholder text like "[your field]", "[Company Name]", "[mention key responsibilities]"**
8. **FORBIDDEN: NEVER use generic statements - ALWAYS be specific**
9. Use EXACT: company names, technologies, project names, achievements from the resume
10. If you don't see specific info in the resume, say what you DO see, don't use placeholders
11. Sound human, not scripted.

🚨 **IMPORTANT: WHEN TO INTRODUCE YOURSELF:**
- ONLY introduce yourself ("I'm [Name]...") if:
  * This is the FIRST question in the conversation (chat_history is empty)
  * The interviewer explicitly asks "Tell me about yourself" or "Introduce yourself"
  * The interviewer asks "Who are you?" or similar introduction questions
- DO NOT introduce yourself on every question - it sounds repetitive and unnatural
- If you've already introduced yourself, just answer the question directly
- Build on previous answers naturally - reference what you said before when relevant

EXAMPLE OF BAD ANSWERS (DO NOT DO THIS):
1. "I'm [Name], and I have a strong background in [your field], having worked at [Company Name]..." (placeholders)
2. "I'm Eduard Mojar, and I have 5 years of experience..." (introducing on every question - repetitive)

EXAMPLE OF GOOD ANSWERS (DO THIS):
1. FIRST QUESTION: "I'm Eduard Mojar, and I have 5 years of experience in software engineering, having worked at TechCorp where I developed web applications using Python and React. I've led a team of 3 developers and delivered projects that increased user engagement by 40%."
2. FOLLOW-UP QUESTIONS: "At TechCorp, I primarily worked on the payment processing system using Django and PostgreSQL. We reduced transaction processing time by 60% through database optimization." (No introduction - just answer directly)
3. REFERENCING PREVIOUS ANSWER: "As I mentioned, I worked with Python and React at TechCorp. I also used those technologies in my previous role at StartupXYZ where I built a real-time analytics dashboard."

Now produce ONLY the candidate's spoken answer using ACTUAL resume details:
""",
    )

    # ============================================================
    # BUILD LCEL PIPELINE
    # ============================================================

    chain = (
        RunnableMap({
            "transcript_context": RunnableLambda(retrieve_transcript) | RunnableLambda(format_docs),
            "full_resume_text": RunnableLambda(get_full_resume),  # Full resume as primary source
            "resume_context": RunnableLambda(retrieve_resume) | RunnableLambda(format_docs),  # Supplementary chunks
            "summary_context": RunnableLambda(retrieve_summary) | RunnableLambda(format_docs),
            "transcript": itemgetter("transcript"),
            "chat_history": itemgetter("chat_history") | RunnableLambda(format_chat_history),  # Format chat history
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
    logger.warning("⚠ Using fallback generator (no RAG, but will use full resume if available).")
    llm = ChatOpenAI(model="gpt-4o", temperature=0.3, streaming=True)

    def get_resume_for_fallback(inputs):
        full_resume = _load_full_resume()
        return full_resume if full_resume else "No resume available."

    prompt = PromptTemplate(
        input_variables=["transcript", "full_resume_text"],
        template="""
You are an interview copilot. Generate a natural, confident 2–4 sentence spoken answer.

====================================================
📄 **CANDIDATE'S COMPLETE RESUME:**
{full_resume_text}

====================================================
💬 **INTERVIEWER'S QUESTION:**
"{transcript}"

====================================================
### TASK
Generate an answer the candidate should SAY OUT LOUD using:
- ACTUAL details from the resume above (names, companies, technologies, projects)
- NEVER use placeholder text like "[your field]" or generic statements
- Use FIRST PERSON ("I", "my experience…")
- Be specific and confident

Answer:
""",
    )

    chain = (
        RunnableMap({
            "transcript": itemgetter("transcript"),
            "full_resume_text": RunnableLambda(get_resume_for_fallback),
        })
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return chain | RunnableLambda(lambda x: {"answer": x})
