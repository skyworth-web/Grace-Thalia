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
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.5,
        streaming=True,  # Enable streaming
    )

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    chroma = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
    )
    
    # Store chroma instance for use in retrieve_with_summary
    _chroma_instance = chroma
    
    # Retrieve more context for better answers
    retriever = chroma.as_retriever(
        search_kwargs={"k": 10},  # Get more chunks for comprehensive context
    )
    
    # Helper to ensure summary is always included
    def retrieve_with_summary(question):
        """Retrieve documents and always include summary if available."""
        # Get regular retrieval results
        retrieved_docs = retriever.invoke(question)
        
        # Try to get summary document if not already in results
        try:
            # Check if summary is already in retrieved_docs
            summary_in_results = any(
                doc.metadata.get("type") == "summary" for doc in retrieved_docs
            )
            
            if not summary_in_results:
                # Try to find summary document using a general query
                summary_results = _chroma_instance.similarity_search(
                    "resume summary profile name skills experience background",
                    k=1
                )
                
                # Check if any result is a summary
                for doc in summary_results:
                    if doc.metadata.get("type") == "summary":
                        retrieved_docs.insert(0, doc)  # Add summary at the beginning
                        logger.debug("✅ Added summary document to retrieval results")
                        break
        except Exception as e:
            logger.debug(f"Could not fetch summary separately: {e}")
        
        return retrieved_docs

    prompt = PromptTemplate(
        input_variables=["context", "transcript", "chat_history"],
        template="""You are an expert interview answer assistant helping a candidate respond to interview questions in real-time.

CANDIDATE'S COMPLETE BACKGROUND (from resume profile and job description):
{context}

IMPORTANT: The context above includes a comprehensive RESUME PROFILE section that contains ALL key information:
- Name, title, years of experience
- ALL skills and technologies
- Complete work experience with responsibilities
- Education details
- Projects and achievements
- Certifications

Use this information extensively and accurately.

Previous conversation:
{chat_history}

The interviewer just asked: "{transcript}"

SPECIAL HANDLING FOR "TELL ME ABOUT YOURSELF":
- If the question is "tell me about yourself", "introduce yourself", "walk me through your background", or similar:
  * ALWAYS start with "My name is [NAME]" - get the name from the RESUME PROFILE section
  * Mention current role/title: "I am a [TITLE]" or "I'm currently a [TITLE]" - use the CURRENT_TITLE from profile
  * Include years of experience: "with [X] years of experience" - use YEARS_OF_EXPERIENCE from profile
  * Highlight 3-5 most relevant skills/technologies from the KEY SKILLS section
  * Mention 1-2 key achievements or projects from WORK EXPERIENCE or PROJECTS sections
  * End with why you're interested in this role (if job description provided)
  * Keep it to 4-6 sentences, natural and conversational
  * Example: "My name is [Name from profile] and I'm a [Title from profile] with [X] years of experience. I specialize in [skills from profile] and have [achievement from profile]. I'm particularly excited about this opportunity because [connection to job]."

- For questions about skills/technologies:
  * Reference the EXACT skills listed in the KEY SKILLS & TECHNOLOGIES section
  * Mention specific projects or roles where you used those skills from WORK EXPERIENCE
  * Be specific and accurate

- For questions about experience/projects:
  * Use details from the WORK EXPERIENCE section
  * Reference specific companies, roles, and achievements
  * Mention technologies used from each role
  * Use information from PROJECTS & ACHIEVEMENTS section

- For other questions:
  * ALWAYS use SPECIFIC details from the resume profile
  * Reference actual projects, roles, companies, or achievements from the context
  * Connect experience to the question using real information
  * Keep it concise (2-4 sentences)

CRITICAL RULES:
• ALWAYS use information from the RESUME PROFILE section - it contains comprehensive details
• Use SPECIFIC names, companies, technologies, and achievements from the profile
• NEVER make up or guess information - only use what's explicitly in the context
• If information is not in the context, say you don't have that information rather than making it up
• Reference the exact skills, technologies, and experiences listed in the profile
• Sound natural and conversational, not robotic
• Show confidence and professionalism
• Avoid repeating the question back

Provide ONLY the candidate's spoken answer, nothing else.
""",
    )

    # Helper function to format retrieved documents
    def format_context(docs):
        """Format retrieved documents into context string with summary prioritized."""
        if not docs:
            return "No resume or job description information available."
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
            context_parts.append("RESUME PROFILE (Complete Background):")
            context_parts.append("=" * 60)
            context_parts.append(summary_doc.page_content)
            context_parts.append("=" * 60)
            context_parts.append("\nDETAILED RESUME SECTIONS:\n")
        
        # Add other documents (resume chunks and job description)
        for doc in docs:
            if doc.metadata.get("type") != "summary":
                source = doc.metadata.get("source", "unknown")
                content = doc.page_content.strip()
                if content:
                    context_parts.append(f"[{source}]: {content}")
        
        result = "\n\n".join(context_parts) if context_parts else "No relevant information found."
        logger.debug(f"📄 Formatted context ({len(result)} chars) from {len(docs)} documents")
        return result
    
    # Helper to format chat history
    def format_chat_history(history):
        """Format chat history for prompt."""
        if not history or len(history) == 0:
            return "No previous conversation."
        
        formatted = []
        for entry in history[-5:]:  # Last 5 exchanges
            if isinstance(entry, dict):
                q = entry.get("question", entry.get("transcript", ""))
                a = entry.get("answer", "")
                if q and a:
                    formatted.append(f"Interviewer: {q}\nCandidate: {a}")
            elif isinstance(entry, str):
                formatted.append(entry)
        
        result = "\n\n".join(formatted) if formatted else "No previous conversation."
        return result
    
    # Helper to safely get chat history
    def get_chat_history_safe(inputs):
        """Safely extract chat_history from inputs."""
        if isinstance(inputs, dict):
            return inputs.get("chat_history", [])
        return []
    
    # Build retrieval-augmented chain with chat history
    base_chain = (
        RunnableMap(
            {
                "context": itemgetter("transcript") | RunnableLambda(retrieve_with_summary) | RunnableLambda(format_context),
                "transcript": itemgetter("transcript"),
                "chat_history": RunnableLambda(get_chat_history_safe) | RunnableLambda(format_chat_history),
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
        model="gpt-4o-mini",
        temperature=0.4,
        streaming=True,
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
