import logging
import uuid
import psycopg
from langchain_community.callbacks import get_openai_callback
from langchain_core.output_parsers import PydanticOutputParser
from langchain_postgres import PostgresChatMessageHistory
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_core.prompts import PromptTemplate,ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate
from langgraph.graph import START, MessagesState, StateGraph, END
from pydantic import create_model, BaseModel, Field


from config import OPEN_AI_KEY, POSTGRES_URL

log = logging.getLogger(__name__)

# Create an instance of the OpenAI LLM
chat = ChatOpenAI(model="gpt-4o-mini", api_key=OPEN_AI_KEY)

with open('back/hr_prompt.md', encoding='utf-8') as f:
    top_template = f.read()
with open('back/hr_prompt2.md', encoding='utf-8') as f:
    bot_template = f.read()
with open('back/start_msg.md', encoding='utf-8') as f:
    start_template = f.read()
with open('back/evaluate_prompt.md', encoding='utf-8') as f:
    eval_template = f.read()




conn_info = POSTGRES_URL

with psycopg.connect(conn_info, prepare_threshold=None) as conn:
    try:
        sync_connection = conn
        print("Connected to the database")
    except Exception as e:
        print(f"Unable to connect to the database: {e}")
    table_name = 'chat_history'
    PostgresChatMessageHistory.create_tables(sync_connection, table_name)


def cand_name(cand):
    return f'{cand["first_name"]} {cand["last_name"]}'

def get_session_history(session_id: str, connection) -> PostgresChatMessageHistory:
    return PostgresChatMessageHistory(
        table_name,
        session_id,
        sync_connection=connection
    )

class State(MessagesState):
    is_finished: bool

class Result(BaseModel):
    """Answer to user query."""
    question: str
    finished: bool = Field(
        ..., description="""Indicates that the interview is finished."""
    )

def start_chat(chat_id, vacancy_id, cand, requirements):
    cand_id = chat_id
    config = {"configurable": {"thread_id": cand_id}}

    # class State(MessagesState):
    #     input: str
    parser = PydanticOutputParser(pydantic_object=Result)

    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(top_template).format(requirements='\n'.join([f"* {r['name']} : {r['description']}"
                                                                              for r in requirements]),
                                                      resume=cand['resume']),
            MessagesPlaceholder(variable_name="messages"),
            SystemMessagePromptTemplate.from_template(bot_template).format(format_instructions=parser.get_format_instructions())
            #('human', '{input}')
        ]
    )





    def call_model(state: State, config: dict):
        # Use the chat model to generate a response
        with psycopg.connect(conn_info, prepare_threshold=None) as conn:
            session_id = config.get('configurable').get('thread_id')
            session_id_uuid = uuid.UUID(int=session_id)
            chat_history = get_session_history(str(session_id_uuid), conn)
            previous_messages = chat_history.messages
            if previous_messages is not None:
                response = chat.invoke(prompt.invoke(previous_messages))
            else:
                prompted_messages = prompt.invoke(state['messages'])
                response = chat.invoke(prompted_messages)
                chat_history.add_messages([state['messages'][-1]]+[response])
            return {"messages": [AIMessage(content = parser.invoke(response.content).question)], "is_finished": parser.invoke(response.content).finished}



    workflow = StateGraph(state_schema=State)
    workflow.add_node('talk_to_candidate', call_model)
    workflow.add_edge(START, 'talk_to_candidate')
    workflow.add_edge('talk_to_candidate', END)
    #workflow.add_node("set_marks", set_marks)

    memory = MemorySaver()
    graph = workflow.compile(checkpointer=memory)

    start_msg = PromptTemplate.from_template(start_template).format(name=cand['name'])
    with get_openai_callback() as cb:
        initial_state = {'messages': [SystemMessage(content=start_msg)]}
        greeting = graph.invoke(initial_state, config)
        #log.info(f'Greeting - ${cb.total_cost:.4f}')

    def process_candidate_input(chat_id, input):
        log.info(f'user : {input}')
        user_state = {'messages': [HumanMessage(content=input)]}
        with get_openai_callback() as cb:
            resp = graph.invoke(user_state, config)
            #log.info(f'Question - ${cb.total_cost:.4f}')
        msg = resp['messages'][-1].content
        finish = resp['is_finished']

        session_id = config.get('configurable').get('thread_id')
        session_id_uuid = uuid.UUID(int=session_id)
        with psycopg.connect(conn_info, prepare_threshold=None) as conn:
            hist = get_session_history(str(session_id_uuid), conn).messages
            return msg, finish, hist

    return greeting, process_candidate_input



def evaluate(chat_id, cand, requirements):
    cand_id = chat_id
    config = {"configurable": {"thread_id": cand_id}}
    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(eval_template).format(
                requirements='\n'.join([f"* {r['name']} : {r['description']}"
                                        for r in requirements]),
                resume=cand['resume']),
            MessagesPlaceholder(variable_name="messages"),
            # ('human', '{input}')
        ]
    )

    Marks = create_model('set_marks',
                         __doc__='Отправить в систему оценки кандидата выставленные по критериям',
                         **{r['name']: (int, ...) for r in requirements})
    tools = [Marks]

    llm_with_tools = chat.bind_tools(tools)

    def call_evaluate(config: dict):
        # Use the chat model to generate a response
        with psycopg.connect(conn_info, prepare_threshold=None) as conn:
            session_id = config.get('configurable').get('thread_id')
            session_id_uuid = uuid.UUID(int=session_id)
            chat_history = get_session_history(str(session_id_uuid), conn)
            previous_messages = chat_history.messages
            prompted_messages = prompt.invoke(previous_messages)
            response = llm_with_tools.invoke(prompted_messages)
            return {"messages": response}

    with get_openai_callback() as cb:
        resp = call_evaluate(config)
        # log.info(f'Question - ${cb.total_cost:.4f}')
    marks = None
    for tc in resp['messages'].tool_calls or []:
        if tc['name'] == Marks.__name__:
            marks = tc['args']
    if marks:
        log.info(f'Set marks : {marks}')
    return marks
