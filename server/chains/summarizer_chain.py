# server/chains/summarizer_chain.py

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI


def build_summary_chain():
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.4,
        streaming=False
    )

    prompt = PromptTemplate(
        input_variables=["transcript"],
        template="""
You are an expert interview coach.

Below is a transcript of an interview answer the candidate gave:

{transcript}

Your job is to produce TWO sections:

---

### **1. Summary (3–5 sentences)**
Provide a clear, neutral summary of how the candidate responded.
Highlight:
- clarity
- structure
- confidence
- relevance to the question
- communication strengths

---

### **2. Improvement Advice (3–6 bullet points)**
Provide short, actionable tips the candidate can use to improve.
Focus on:
- better structure (STAR, clarity, conciseness)
- showcasing relevant experience or achievements
- stronger wording
- confidence and delivery
- common interview pitfalls to avoid

Make the tone encouraging, practical, and easy to apply.
""",
    )

    return LLMChain(llm=llm, prompt=prompt)
