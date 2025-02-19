import os

from config import SUPABASE_URL, SUPABASE_KEY
from retry import retry
from typing import Optional
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

TTL = 600
TRIES = 3
DELAY = 2
BACKOFF = 2


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
         .select('name')
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
def get_chat_state(chat_id):
    chat = (supabase.table('chat')
            .select("state")
            .eq('id', chat_id)
            .maybe_single().execute())
    if chat:
        return chat.data

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
def update_marks(vacancy_id, cand_id, marks):
    (supabase.table('marks')
     .upsert([dict(vacancy_id=vacancy_id,
                   chat_id=cand_id,
                   requirement_id=id,
                   value=val)
              for id, val in marks.items()])
     .execute())

@retry(tries=TRIES, delay=DELAY, backoff=BACKOFF)
def update_candidate_info(chat_id, cand_id: Optional[int] = None, new_resume: Optional[str] = None, new_state: Optional[str]=None):
    data = {
        'id': chat_id
    }
    if cand_id is not None:
        data['candidate_id'] = cand_id
    if new_resume is not None:
        data['resume'] = new_resume
    if new_state is not None:
        data['state'] = new_state
    supabase.table('chat').upsert(data).execute()




