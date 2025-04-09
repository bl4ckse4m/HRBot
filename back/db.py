import os

import psycopg
from fastapi import HTTPException

from back.custom_postgres import PostgresChatMessageHistory

from config import SUPABASE_URL, SUPABASE_KEY, conn_info
from retry import retry
from typing import Optional
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

TTL = 600
TRIES = 3
DELAY = 2
BACKOFF = 2

table_name = 'chat_history'


@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_all_vacancies():
    response = supabase.table("session").select("vacancies:vacancy_id (id, name)").execute()
    if response:
        return [item['vacancies'] for item in response.data]
    else:
        raise HTTPException(status_code=500, detail="Failed to retrieve vacancies")


@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_candidates_by_vacancy(vacancy_id: int):
    response = (
        supabase.table("session")
        .select("chat:chat_id (id, name, email), state")
        .eq("vacancy_id", vacancy_id)
        .execute()
    )
    if response:
        return response.data
    else:
        raise HTTPException(status_code=500, detail="Failed to retrieve candidates")
    # Extract the 'chat' data from the response


@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_all_candidates():
    response = (supabase.table("chat")
                .select("id, name, email, session:session_id(state)")
                .filter('session_id', 'neq', 'null')
                .execute())
    if response:
        return response.data
    else:
        raise HTTPException(status_code=500, detail="Failed to retrieve candidates")


@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_candidate_details(candidate_id: int):
    # Fetch candidate information
    candidate_response = supabase.table("chat").select("*").eq("id", candidate_id).single().execute()
    if candidate_response:
        candidate = candidate_response.data
    else:
        raise HTTPException(status_code=500, detail="Failed to retrieve candidates details")


    # Fetch related marks
    marks_response = supabase.table("marks").select("*").eq("chat_id", candidate_id).execute()
    if marks_response:
        marks = marks_response.data
    else:
        raise HTTPException(status_code=500, detail="Failed to retrieve marks")


    # Fetch chat history
    chat_history_response = supabase.table("chat_history").select("*").eq("session_id", candidate["session_id"]).execute()
    if chat_history_response:
        chat_history = chat_history_response.data
    else:
        raise HTTPException(status_code=500, detail="Failed to retrieve message history")


    return candidate, marks, chat_history

#@st.cache_resource(ttl=TTL)
@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_vacancy(vacancy_id):
    v = (supabase.table('vacancies')
         .select('*')
         .eq('id', vacancy_id)
         .maybe_single()
         .execute())
    if v:
        return v.data




@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_opened_vacancies():
    v = (supabase.table('vacancies')
         .select('id','name')
         .execute())
    if v:
        return v.data

@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_vacancy_id(vacancy_name):
    v = (supabase.table('vacancies')
         .select('id')
         .eq('name', vacancy_name)
         .maybe_single()
         .execute())
    if v:
        return v.data

@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_requirements_ids():
    v = (supabase.table('requirements')
         .select('id', 'name')
         .execute())
    if v:
        return v.data

def transform_marks(marks_dict, reqs_dict):
    name_to_id = {item['name']: item['id'] for item in reqs_dict}
    transformed_dict = {name_to_id[key]: value for key, value in marks_dict.items() if key in name_to_id}
    return transformed_dict


#@st.cache_resource(ttl=TTL)
@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_requirements(vacancy_id: int):
    v = (supabase.table('requirements')
         .select('*')
         .eq('vacancy_id', vacancy_id)
         .execute())
    return v.data

@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_session_state(chat_id):
    state = (supabase.table('chat')
            .select("session:session_id(state)")
            .eq('id', chat_id)
            .maybe_single().execute())

    if state:
        return state.data['session']['state']

#@st.cache_resource(ttl=TTL)
@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_candidate(email: str):
    cand = (supabase.table('candidates')
            .select("id,name,resume")
            .eq('email', email.lower().strip())
            .filter('resume', 'neq', 'null')
            .maybe_single()
            .execute())
    if cand:
        return cand.data

@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_chat(id: int):
    cand = (supabase.table('chat')
            .select("*")
            .eq('id', id)
            .maybe_single()
            .execute())
    if cand:
        return cand.data

@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_marks(chat_id: int, vacancy_id: int):
    marks = (supabase.table('marks')
            .select("*")
            .eq('chat_id', chat_id)
            .eq('vacancy_id', vacancy_id)
            .execute())
    if marks:
        return marks.data

@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_session(chat_id: int, vacancy_id: int):
    sesh = (supabase.table('session')
            .select("*")
            .eq('chat_id', chat_id)
            .eq('vacancy_id', vacancy_id)
            .maybe_single()
            .execute())
    if sesh:
        return sesh.data


@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_session_by_id(sesh_id: int):
    sesh = (supabase.table('session')
            .select("*")
            .eq('id', sesh_id)
            .maybe_single()
            .execute())
    if sesh:
        return sesh.data

@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def get_candidate_by_id(id: int):
    cand = (supabase.table('chat')
            .select("*")
            .eq('id', id)
            #.filter('resume', 'neq', 'null')
            .maybe_single()
            .execute())
    if cand:
        return cand.data

@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def upsert_session(chat_id, vacancy_id, state):
    (supabase.table('session')
     .upsert(dict(vacancy_id=vacancy_id, chat_id=chat_id, state = state))
     .execute())



@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def update_marks(vacancy_id, cand_id, marks):
    (supabase.table('marks')
     .upsert([dict(vacancy_id=vacancy_id,
                   chat_id=cand_id,
                   requirement_id=id,
                   value=val)
              for id, val in marks.items()])
     .execute())

@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def update_chat_info(chat_id, name: Optional[str]=None, email: Optional[str]=None, new_resume: Optional[str] = None, session_id: Optional[int] = None):
    data = {
        'id': chat_id
    }
    if name is not None:
        data['name'] = name
    if email is not None:
        data['email'] = email
    if new_resume is not None:
        data['resume'] = new_resume
    if session_id is not None:
        data['session_id'] = session_id
    supabase.table('chat').upsert(data).execute()


def init_db():
    global table_name
    with psycopg.connect(conn_info, prepare_threshold=None) as conn:
        try:
            sync_connection = conn
            print("Connected to the database")
        except Exception as e:
            print(f"Unable to connect to the database: {e}")
        PostgresChatMessageHistory.create_tables(sync_connection, table_name)
