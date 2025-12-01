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
    
    # Retrieve more context for better answers (5-6 chunks)
    retriever = chroma.as_retriever(search_kwargs={"k": 6})

    prompt = PromptTemplate(
        input_variables=["context", "transcript"],
        template="""You are an expert interview answer assistant helping a candidate respond to interview questions in real-time.

CANDIDATE'S BACKGROUND (from resume and job description):
{context}

The interviewer just asked: "{transcript}"

Generate a smart, personalized answer (2-4 sentences) that:
• Directly addresses the question using SPECIFIC details from the candidate's resume
• Highlights relevant skills, experiences, or achievements from their background
• Aligns with the job requirements (if job description was provided)
• Sounds natural and conversational (not robotic or generic)
• Shows confidence and professionalism
• Uses concrete examples from their experience when relevant
• Avoids repeating the question back
• Is ready to speak - use natural spoken language

IMPORTANT RULES:
- ALWAYS use specific details from the candidate's resume/background
- If the question is about skills/experience, reference their actual projects/roles
- If the question is about why they want the job, connect their background to the role
- Keep it brief and punchy (2-4 sentences max)
- Make it sound like a real person speaking, not a written essay
- If the transcript is unclear, infer the likely question and provide a relevant answer
- NEVER make up experiences not in the resume - only use what's provided

Provide ONLY the candidate's spoken answer, nothing else.
""",
    )

    # Helper function to format retrieved documents
    def format_context(docs):
        """Format retrieved documents into context string."""
        if not docs:
            return "No resume or job description information available."
        context_parts = []
        for doc in docs:
            source = doc.metadata.get("source", "unknown")
            content = doc.page_content.strip()
            if content:
                context_parts.append(f"[{source}]: {content}")
        return "\n\n".join(context_parts) if context_parts else "No relevant information found."
    
    # Build retrieval-augmented chain
    base_chain = (
        RunnableMap(
            {
                "context": itemgetter("transcript") | retriever | RunnableLambda(format_context),
                "transcript": itemgetter("transcript"),
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
