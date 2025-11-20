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
You are an expert interview answer assistant.

Below is what the interviewer said:

"{transcript}"

Write a strong, polished interview response in 3–5 sentences that:

• directly answers the implied question  
• sounds confident, natural, and conversational  
• focuses on relevant professional skills, experience, or achievements  
• avoids repeating the transcript verbatim  
• frames the candidate in a positive, capable light  
• uses simple and clear English

Provide only the candidate’s answer.
""",
    )

    base_chain = prompt | llm | StrOutputParser()
    wrapped_chain = base_chain | RunnableLambda(lambda s: {"text": s})
    return wrapped_chain
