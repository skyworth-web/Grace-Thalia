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


def build_generator_chain():
    """
    Build a retrieval-augmented generator chain that uses resume/job context
    to generate smart interview answers.
    """
    if not os.path.exists(CHROMA_DIR):
        logger.warning("⚠️ Vector store missing - generator will work without resume context")
        return _build_simple_chain()
    
    # Use GPT-4o with optimized settings for accurate, context-aware responses
    from langchain_core.messages import SystemMessage
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    
    llm = ChatOpenAI(
        model="gpt-4o",  # Best model for reasoning and context understanding
        temperature=0.3,  # Lower for more accurate, deterministic responses based on resume
        streaming=True,  # Enable streaming for real-time answers
        max_tokens=500,  # Limit length for concise, interview-appropriate answers
    )

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    chroma = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
    )
    
    # Store chroma instance for use in retrieve_with_summary
    _chroma_instance = chroma
    
    # Smart retrieval with MMR (Maximum Marginal Relevance) for diverse, relevant chunks
    retriever = chroma.as_retriever(
        search_type="mmr",  # Use MMR for better diversity and relevance
        search_kwargs={
            "k": 12,  # Get more chunks for comprehensive context
            "fetch_k": 20,  # Fetch more candidates for MMR selection
            "lambda_mult": 0.7  # Balance between relevance (1.0) and diversity (0.0)
        },
    )
    
    # Helper to ensure summary is always included and use smart retrieval
    def retrieve_with_summary(inputs):
        """
        Smart retrieval that uses full interview context to improve query understanding.
        Retrieves documents and always includes summary if available.
        """
        # Extract question/transcript from inputs (could be dict or string)
        if isinstance(inputs, dict):
            question = inputs.get("transcript", inputs.get("question", ""))
            full_context = inputs.get("full_interview_context", "")
        else:
            question = str(inputs)
            full_context = ""
        
        # Build smarter query: combine current question with context from interview
        # This helps understand what the interviewer is really asking
        if full_context and len(full_context) > 50:
            # Extract key topics from full interview to improve retrieval
            # Use the current question as primary, but add context
            smart_query = f"{question} [Context from interview: {full_context[-500:]}]"  # Last 500 chars for context
        else:
            smart_query = question
        
        # Get retrieval results with smart query
        logger.info(f"🔍 Retrieving documents for query: '{question[:100]}...'")
        try:
            retrieved_docs = retriever.invoke(smart_query)
            logger.info(f"📚 Retrieved {len(retrieved_docs)} documents")
        except Exception as e:
            logger.error(f"❌ Retrieval error: {e}", exc_info=True)
            # Fallback: try to get all documents
            try:
                retrieved_docs = _chroma_instance.similarity_search(question, k=10)
                logger.info(f"📚 Fallback retrieval: {len(retrieved_docs)} documents")
            except Exception as e2:
                logger.error(f"❌ Fallback retrieval also failed: {e2}")
                retrieved_docs = []
        
        # ALWAYS ensure summary is included - it's critical for accurate answers
        try:
            # Check if summary is already in retrieved_docs
            summary_in_results = any(
                doc.metadata.get("type") == "summary" for doc in retrieved_docs
            )
            
            if not summary_in_results:
                logger.warning("⚠️ Summary not in retrieval results, fetching separately...")
                # Try to find summary document using a general query
                summary_results = _chroma_instance.similarity_search(
                    "resume summary profile name skills experience background",
                    k=3  # Get more candidates
                )
                
                # Check if any result is a summary
                for doc in summary_results:
                    if doc.metadata.get("type") == "summary":
                        retrieved_docs.insert(0, doc)  # Add summary at the beginning
                        logger.info("✅ Added summary document to retrieval results")
                        break
                else:
                    # If still no summary, try direct search
                    logger.warning("⚠️ Summary not found with similarity search, trying direct metadata search...")
                    # Get all documents and find summary
                    all_docs = _chroma_instance.get()
                    for doc_id, metadata in zip(all_docs.get('ids', []), all_docs.get('metadatas', [])):
                        if metadata and metadata.get('type') == 'summary':
                            # Found summary, retrieve it
                            summary_doc = _chroma_instance.get(ids=[doc_id])
                            if summary_doc and summary_doc.get('documents'):
                                from langchain_core.documents import Document
                                summary_doc_obj = Document(
                                    page_content=summary_doc['documents'][0],
                                    metadata=metadata
                                )
                                retrieved_docs.insert(0, summary_doc_obj)
                                logger.info("✅ Found and added summary document")
                                break
        except Exception as e:
            logger.error(f"❌ Error fetching summary: {e}", exc_info=True)
        
        # Log what we retrieved
        if retrieved_docs:
            logger.info(f"📄 Retrieved documents: {[doc.metadata.get('type', 'unknown') for doc in retrieved_docs[:5]]}")
        else:
            logger.error("❌ NO DOCUMENTS RETRIEVED! Resume may not be ingested properly.")
        
        return retrieved_docs

    prompt = PromptTemplate(
        input_variables=["context", "transcript", "chat_history", "full_interview_context"],
        template="""You are an interview copilot. Generate spoken answers for job interviews using the candidate's resume information.

RESUME INFORMATION (provided below):
{context}

FULL INTERVIEW CONVERSATION:
{full_interview_context}

RECENT Q&A:
{chat_history}

CURRENT QUESTION: "{transcript}"

TASK: Generate what the candidate should SAY to the interviewer. This is for a LIVE INTERVIEW - generate spoken answers they can say out loud.

INSTRUCTIONS:
1. USE THE RESUME INFORMATION ABOVE - it contains the candidate's skills, experience, education, projects
2. For skill questions (e.g., "Do you know Java?"): 
   - Check the KEY SKILLS & TECHNOLOGIES section in the resume information above
   - If the skill is listed: Answer "Yes, I have experience with [skill]. I used it [where/how from work experience]."
   - If NOT listed: Answer honestly "I haven't worked with [skill] professionally, but [related experience if any]"
3. Use SPECIFIC details from the resume: company names, projects, technologies, achievements
4. Keep answers concise (2-4 sentences)
5. Sound natural and conversational - like speaking, not reading
6. Use first person ("I", "my", "me")

EXAMPLE for "Do you know Java?":
- If Java is in resume skills: "Yes, I have experience with Java. I used it in my role at [Company] to develop [project]. I'm comfortable with [Java technologies from resume]."
- If Java is NOT in resume: "I haven't worked with Java professionally, but I have experience with [similar language from resume] and I'm confident I could learn it quickly."

IMPORTANT:
- The resume information IS PROVIDED above - use it to answer questions
- Generate ONLY the spoken answer - what the candidate should say
- Do NOT say "I can't access files" - the resume data is in the context above
- Do NOT analyze or summarize - generate what to SAY in the interview
""",
    )

    # Helper function to format retrieved documents
    def format_context(docs):
        """Format retrieved documents into context string with summary prioritized."""
        if not docs:
            logger.error("❌ NO DOCUMENTS TO FORMAT - Resume may not be ingested!")
            return "ERROR: No resume information available. Please ensure resume has been uploaded and ingested via /ingest endpoint."
        
        context_parts = []
        summary_doc = None
        
        # Find and prioritize summary document
        for doc in docs:
            if doc.metadata.get("type") == "summary":
                summary_doc = doc
                break
        
        # Always include summary first if available
        if summary_doc:
            context_parts.append("=" * 60)
            context_parts.append("RESUME PROFILE (Complete Background - USE THIS DATA):")
            context_parts.append("=" * 60)
            context_parts.append(summary_doc.page_content)
            context_parts.append("=" * 60)
            context_parts.append("\nDETAILED RESUME SECTIONS:\n")
            logger.info(f"✅ Found resume summary ({len(summary_doc.page_content)} chars)")
        else:
            logger.warning("⚠️ No summary document found in retrieval results")
        
        # Add other documents (resume chunks and job description)
        for doc in docs:
            if doc.metadata.get("type") != "summary":
                source = doc.metadata.get("source", "unknown")
                content = doc.page_content.strip()
                if content:
                    context_parts.append(f"[{source}]: {content}")
        
        result = "\n\n".join(context_parts) if context_parts else "ERROR: No relevant information found in resume."
        logger.info(f"📄 Formatted context ({len(result)} chars) from {len(docs)} documents")
        
        # Log a sample to verify it has data
        if len(result) < 100:
            logger.error(f"❌ Context is too short ({len(result)} chars) - resume data may be missing!")
        else:
            logger.debug(f"✅ Context sample: {result[:300]}...")
        
        return result
    
    # Helper to format chat history
    def format_chat_history(history):
        """Format chat history for prompt."""
        if not history or len(history) == 0:
            return "No previous Q&A exchanges."
        
        formatted = []
        for entry in history[-5:]:  # Last 5 exchanges
            if isinstance(entry, dict):
                q = entry.get("question", entry.get("transcript", ""))
                a = entry.get("answer", "")
                if q and a:
                    formatted.append(f"Q: {q}\nA: {a}")
            elif isinstance(entry, str):
                formatted.append(entry)
        
        result = "\n\n".join(formatted) if formatted else "No previous Q&A exchanges."
        return result
    
    # Helper to format full interview context
    def format_full_interview_context(context):
        """Format the full interview transcript for context."""
        if not context or not context.strip():
            return "This is the beginning of the interview."
        
        # Clean up and format the full transcript
        cleaned = context.strip()
        # Limit to last 2000 words to avoid token limits while keeping recent context
        words = cleaned.split()
        if len(words) > 2000:
            cleaned = " ".join(words[-2000:])
            return f"[Earlier conversation truncated. Recent conversation:]\n\n{cleaned}"
        
        return cleaned
    
    # Helper to safely get chat history
    def get_chat_history_safe(inputs):
        """Safely extract chat_history from inputs."""
        if isinstance(inputs, dict):
            return inputs.get("chat_history", [])
        return []
    
    # Helper to safely get full interview context
    def get_full_interview_context_safe(inputs):
        """Safely extract full_interview_context from inputs."""
        if isinstance(inputs, dict):
            return inputs.get("full_interview_context", "")
        return ""
    
    # Build retrieval-augmented chain with chat history and full interview context
    # Pass full inputs to retrieve_with_summary so it can use interview context
    def prepare_retrieval_inputs(inputs):
        """Prepare inputs for smart retrieval that uses full interview context."""
        return inputs  # Pass through full inputs dict
    
    base_chain = (
        RunnableMap(
            {
                "context": RunnableLambda(prepare_retrieval_inputs) | RunnableLambda(retrieve_with_summary) | RunnableLambda(format_context),
                "transcript": itemgetter("transcript"),
                "chat_history": RunnableLambda(get_chat_history_safe) | RunnableLambda(format_chat_history),
                "full_interview_context": RunnableLambda(get_full_interview_context_safe) | RunnableLambda(format_full_interview_context),
            }
        )
        | prompt
        | llm
        | StrOutputParser()
    )
    
    wrapped_chain = base_chain | RunnableLambda(lambda s: {"text": s})
    logger.info("✅ Retrieval-augmented generator chain ready")
    return wrapped_chain


def _build_simple_chain():
    """Fallback chain without retrieval (if resume not uploaded)."""
    logger.warning("⚠️ Building generator chain without resume context")
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.3,  # Lower for more accurate responses
        streaming=True,
        max_tokens=500,
    )

    prompt = PromptTemplate(
        input_variables=["transcript"],
        template="""You are an expert interview answer assistant helping a candidate respond to interview questions in real-time.

The interviewer just said: "{transcript}"

Generate a smart, concise answer (2-4 sentences) that:
• Directly addresses the question or topic
• Sounds natural and conversational (not robotic)
• Shows confidence and professionalism
• Avoids repeating the question back
• Is ready to speak - use natural spoken language

IMPORTANT: 
- Keep it brief and punchy (2-4 sentences max)
- Make it sound like a real person speaking, not a written essay
- Focus on the key point, don't over-explain
- If the transcript is unclear or incomplete, provide a general professional response

Provide ONLY the candidate's spoken answer, nothing else.
""",
    )

    base_chain = prompt | llm | StrOutputParser()
    wrapped_chain = base_chain | RunnableLambda(lambda s: {"text": s})
    return wrapped_chain
