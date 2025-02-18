from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import START, MessagesState, StateGraph, END

from config import OPEN_AI_KEY

# Create an instance of the OpenAI LLM
chat = ChatOpenAI(model="gpt-4o-mini", api_key=OPEN_AI_KEY)

messages = [
    SystemMessage(content="You're a helpful assistant")
]

workflow = StateGraph(state_schema = MessagesState)

# Define a chatbot function
def call_model(input_text):
    # Use the chat model to generate a response
    messages.append( HumanMessage(content=input_text))
    response = chat.invoke(messages)
    messages.append(AIMessage(content=response.content))
    return response.content
