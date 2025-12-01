# server/chains/generator_chain.py

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

def build_generator_chain():
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.4,
        streaming=True,  # Enable streaming
        callbacks=[]     # We can pass a callback to stream tokens
    )

    prompt = PromptTemplate(
        input_variables=["transcript"],
        template="""
You are an expert interview answer assistant helping a candidate respond to interview questions in real-time.

The interviewer just said: "{transcript}"

Generate a smart, concise answer (2-4 sentences) that:
• Directly addresses the question or topic
• Sounds natural and conversational (not robotic)
• Highlights relevant skills/experience from the candidate's background
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
