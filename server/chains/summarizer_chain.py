from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

def build_summary_chain():
    llm = ChatOpenAI(model="gpt-4o-mini")
    prompt = PromptTemplate(
        template="Summarize this interview transcript and give improvement advice:\n{transcript}",
        input_variables=["transcript"],
    )
    return LLMChain(llm=llm, prompt=prompt)
