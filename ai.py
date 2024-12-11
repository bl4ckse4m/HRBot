from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from config import OPEN_AI_KEY

# Create an instance of the OpenAI LLM
chat = ChatOpenAI(model="gpt-4o-mini", api_key=OPEN_AI_KEY)

messages = [
    SystemMessage(content="You're a helpful assistant")
]

# Define a chat bot function
def chat_bot(input_text):
    # Use the chat model to generate a response
    messages.append( HumanMessage(content=input_text))
    response = chat.invoke(messages)
    messages.append(AIMessage(content=response.content))
    return response.content

