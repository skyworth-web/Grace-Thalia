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
    
    # Retrieve more context for better answers
    retriever = chroma.as_retriever(search_kwargs={"k": 8})  # Get more chunks for comprehensive context

    prompt = PromptTemplate(
        input_variables=["context", "transcript", "chat_history"],
        template="""You are an expert interview answer assistant helping a candidate respond to interview questions in real-time.

CANDIDATE'S BACKGROUND (from resume and job description):
{context}

Previous conversation:
{chat_history}

The interviewer just asked: "{transcript}"

SPECIAL HANDLING FOR "TELL ME ABOUT YOURSELF":
- If the question is "tell me about yourself", "introduce yourself", "walk me through your background", or similar:
  * ALWAYS start with "My name is [NAME]" if name is available in the resume summary
  * Mention current role/title: "I am a [TITLE]" or "I'm currently a [TITLE]"
  * Include years of experience: "with [X] years of experience" or "I have [X] years of experience"
  * Highlight 2-3 most relevant skills/technologies from the resume
  * Mention 1-2 key achievements or projects that align with the job
  * End with why you're interested in this role (if job description provided)
  * Keep it to 4-6 sentences, natural and conversational
  * Example structure: "My name is [Name] and I'm a [Title] with [X] years of experience in [key areas]. I specialize in [top skills] and have successfully [key achievement]. I'm particularly excited about this opportunity because [connection to job]."

- For other questions:
  * Use SPECIFIC details from the candidate's resume
  * Reference actual projects, roles, or achievements
  * Connect experience to the question
  * Keep it concise (2-4 sentences)

GENERAL RULES:
• Directly addresses the question using SPECIFIC details from the candidate's resume
• Highlights relevant skills, experiences, or achievements from their background
• Aligns with the job requirements (if job description was provided)
• Sounds natural and conversational (not robotic or generic)
• Shows confidence and professionalism
• Uses concrete examples from their experience when relevant
• Avoids repeating the question back
• Is ready to speak - use natural spoken language
• NEVER make up experiences not in the resume - only use what's provided

Provide ONLY the candidate's spoken answer, nothing else.
""",
    )

    # Helper function to format retrieved documents
    def format_context(docs):
        """Format retrieved documents into context string."""
        if not docs:
            return "No resume or job description information available."
        context_parts = []
        summary_found = False
        
        # Prioritize summary if available
        for doc in docs:
            if doc.metadata.get("type") == "summary":
                context_parts.insert(0, doc.page_content)  # Put summary first
                summary_found = True
                break
        
        # Add other documents
        for doc in docs:
            if doc.metadata.get("type") != "summary":
                source = doc.metadata.get("source", "unknown")
                content = doc.page_content.strip()
                if content:
                    context_parts.append(f"[{source}]: {content}")
        
        return "\n\n".join(context_parts) if context_parts else "No relevant information found."
    
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
                "context": itemgetter("transcript") | retriever | RunnableLambda(format_context),
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
