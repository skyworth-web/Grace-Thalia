from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI
from .retrieval_chain import build_retriever  # we will create this helper

def build_generator_chain():
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

    template = """
You are an elite interview co-pilot.

Use ALL of the following:
- Candidate resume (embedded)
- Job description (embedded)
- Transcript of what the interviewer just said

Goal:
Generate a **short (3–5 sentences) perfect interview answer**
that:
1. Directly addresses the question
2. Uses the most relevant skills from the resume
3. Aligns strongly with the job description
4. Sounds confident, concise, professional
5. Uses first-person voice ("I")

Transcript:
{transcript}

Answer:
"""

    prompt = PromptTemplate(
        template=template,
        input_variables=["transcript"],
    )

    retriever = build_retriever(k=5)

    chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=False
    )

    return chain
