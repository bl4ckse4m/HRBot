import logging
import json
from contextlib import asynccontextmanager

import telebot
import os
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from telebot import TeleBot, types
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from PyPDF2 import PdfReader
from fastapi import FastAPI, Request, Response, Body
from fastapi.responses import JSONResponse
from config import BOT_TOKEN
from back.ai import start_chat, evaluate
from back.db import (get_chat,
                     get_vacancy, get_requirements,
                     update_marks, update_chat_info, get_opened_vacancies,
                     get_vacancy_id, transform_marks, get_requirements_ids, get_session, upsert_session,
                     get_session_state, get_all_candidates, get_candidate_details, get_all_vacancies,
                     get_candidates_by_vacancy, init_db, get_marks, get_session_by_id
                     )

log = logging.getLogger(__file__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        # Remove webhook if exists
        bot.remove_webhook()

        webhook_url = WEBHOOK_URL_BASE + WEBHOOK_URL_PATH
        # Set webhook
        bot.set_webhook(
            url=webhook_url,
            #certificate=open(WEBHOOK_SSL_CERT, 'r')
        )

        init_db()

        log.info(f'Webhook setup completed {webhook_url}')
        yield
    finally:
        # Cleanup
        try:
            bot.remove_webhook()
            log.info('Webhook removed during shutdown')
        except Exception as e:
            log.error(f"Error removing webhook: {str(e)}")

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

# Dictionary to store user data
user_data = {}

# Initialize bot
bot = TeleBot(BOT_TOKEN)

WEBHOOK_HOST = os.environ.get('WEBHOOK_HOST', 'localhost')
WEBHOOK_PORT = int(os.environ.get('WEBHOOK_PORT', '8443'))
WEBHOOK_SSL_CERT = './webhook_cert.pem'
WEBHOOK_SSL_PRIV = './webhook_pkey.pem'

WEBHOOK_URL_BASE = f"https://{WEBHOOK_HOST}"
WEBHOOK_URL_PATH = f"/{BOT_TOKEN}/"





@app.post(f"/{BOT_TOKEN}/")

def process_webhook(request: dict = Body(...)):
    #if request.method != "POST":
    #    return JSONResponse({"error": "Invalid request method"}, status_code=405)

    try:
        update = request
        update = types.Update.de_json(update)
        bot.process_new_updates([update])
        return {"status": "ok"}
    except Exception as e:
        log.error(f"Webhook error: {str(e)}")
        return {"status": "error"}, 500


templates = Jinja2Templates(directory="templates")

@app.get("/vacancies")
def read_candidates(request: Request):
    vacancies = get_all_vacancies()
    return templates.TemplateResponse("vacancies.html", {"request": request, "vacancies": vacancies})

@app.get("/vacancies/{vacancy_id}/candidates")
def candidates_page(request: Request, vacancy_id: int):
    candidates = get_candidates_by_vacancy(vacancy_id)
    return templates.TemplateResponse("candidates.html", {"request": request, "candidates": candidates, "vacancy_id": vacancy_id})

@app.get("/vacancies/{vacancy_id}/candidates/{candidate_id}")
def read_candidate(request: Request, vacancy_id: int, candidate_id: int):
    candidate, marks, chat_history = get_candidate_details(candidate_id)
    return templates.TemplateResponse("candidate_detail.html", {
        "request": request,
        "candidate": candidate,
        "marks": marks,
        "chat_history": chat_history
    })

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    chat_info = get_chat(chat_id)
    if chat_info:
        msg = bot.send_message(chat_id, "Пожалуйста загрузите ваше актуальное резюме в формате .pdf")
        bot.register_next_step_handler(msg, handle_document_upload)
    else:
        msg = bot.send_message(chat_id, "Здравствуйте! Введите ваше ФИО (в формате: Фамилия Имя Отчество)")
        bot.register_next_step_handler(msg, process_fio)


def process_fio(message):
    chat_id = message.chat.id
    fio = message.text
    update_chat_info(chat_id, name=fio)
    bot.send_message(chat_id, "Введите ваш email.")
    bot.register_next_step_handler(message, process_email)

def process_email(message):
    chat_id = message.chat.id
    email = message.text
    update_chat_info(chat_id, email = email)
    bot.send_message(chat_id, "Пожалуйста загрузите ваше актуальное резюме в формате .pdf")
    bot.register_next_step_handler(message, handle_document_upload)

def handle_document_upload(message):
    chat_id = message.chat.id
    #bot.send_message(chat_id, "Загрузите ваше резюме в формате .pdf в этот чат.")
    if message.content_type == 'document' and message.document.mime_type == 'application/pdf':
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        # Save the file to your desired location
        resume_path = f"{chat_id}_resume.pdf"
        with open(resume_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        update_chat_info(chat_id, new_resume = extract_text_from_pdf(resume_path))
        os.remove(resume_path)
        bot.send_message(chat_id, "Резюме получено и обновлено.")
        show_vacancies(chat_id)
    else:
        msg = bot.send_message(chat_id, "Please upload a valid .pdf file.")
        bot.register_next_step_handler(msg, handle_document_upload)

def show_vacancies(chat_id):
    vacancies = get_opened_vacancies()
    if vacancies:
        markup = telebot.types.InlineKeyboardMarkup()
        for vacancy in vacancies:
            #print(callback_data)
            #print(len(callback_data))
            markup.add(telebot.types.InlineKeyboardButton(text=vacancy['name'], callback_data=vacancy['id']))
        bot.send_message(chat_id, "Выберите вакансию из списка ниже:", reply_markup=markup)
        # vacancy_list = "\n".join([f"- {vacancy["name"]}" for vacancy in vacancies])
        # msg = bot.send_message(chat_id, f"Please select a vacancy from the list below by typing its name:\n{vacancy_list}")
    else:
        bot.send_message(chat_id, "Currently, there are no open vacancies.")

@bot.callback_query_handler(func=lambda call: True)
def process_vacancy_selection(call):
    chat_id = call.message.chat.id
    #chat_id = message.chat.id
    data = call.data
    vacancy_id = int(data)
    vacancy_name = get_vacancy(vacancy_id)['name']
    sesh = get_session(chat_id, vacancy_id)
    if sesh:
        if sesh['state'] == 'finished':
            bot.send_message(chat_id, "Вы уже проходили интервью на эту вакансию, пожалуйста выберите другую или дождитесь следующей волны отбора.")
        else:
            cand = get_chat(chat_id)
            vacancy_requirements = get_requirements(vacancy_id)
            session_id = get_session(chat_id, vacancy_id)['id']
            bot.send_message(chat_id, "Вернемся к интервью")
            initiate_llm_chat(chat_id,vacancy_id, session_id, cand, vacancy_requirements)
    else:
        upsert_session(chat_id, vacancy_id, state = 'started')
        bot.send_message(chat_id, f"Вы выбрали вакансию: {vacancy_name}")
        cand = get_chat(chat_id)
        vacancy_requirements = get_requirements(vacancy_id)
        session_id = get_session(chat_id, vacancy_id)['id']
        update_chat_info(chat_id, session_id=session_id)
        initiate_llm_chat(chat_id,vacancy_id, session_id,  cand, vacancy_requirements)






def initiate_llm_chat(chat_id, vacancy_id, session_id, cand, vacancy_requirements):
    if cand:
        greeting, chat_processor = start_chat(session_id, cand, vacancy_requirements)
        greeting_msg = greeting['messages'][-1].content
        bot.send_message(chat_id, greeting_msg)
        if greeting['is_finished']:
            bot.send_message('Интервью на данную вакансию было завершено.')
        else:#update_chat_info(chat_id, new_state='STARTED')
            bot.register_next_step_handler_by_chat_id(chat_id, interview_candidate, chat_processor, vacancy_id, session_id, cand, vacancy_requirements)
    else:
        bot.send_message(chat_id, "Resume not found. Please upload your resume.")
        bot.register_next_step_handler_by_chat_id(chat_id, handle_document_upload)

#@bot.message_handler(func=lambda message: get_session_state(message.chat.id) == 'started')
def interview_candidate(message,  chat_processor, vacancy_id, session_id,  cand, requirements):
    chat_id = message.chat.id
    input_msg = message.text
    msg, finish, hist = chat_processor(input_msg)

    if finish:
        marks = evaluate(session_id, cand, requirements)
        if marks:
            id_marks = transform_marks(marks, get_requirements_ids())
            update_marks(vacancy_id, message.chat.id, id_marks)
            upsert_session(chat_id, vacancy_id, 'finished')
            bot.send_message(message.chat.id, msg)
        else:
            log.info('Interview finished, but marks not found')
    else:
        bot.send_message(message.chat.id, msg)
        bot.register_next_step_handler_by_chat_id(chat_id, interview_candidate,  chat_processor, vacancy_id, session_id, cand, requirements)

# @bot.message_handler(func=lambda message: True)
# def echo(message):
#     log.info(message)
#     response = call_model(message.text)
#     log.info(response)
#     bot.reply_to(message, response)



def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file."""
    text = ""
    with open(pdf_path, "rb") as file:
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text


if __name__ == "__main__":
    import uvicorn

    ssl_cert = os.environ.get('SSL_CERT', WEBHOOK_SSL_CERT)
    ssl_key = os.environ.get('SSL_KEY', WEBHOOK_SSL_PRIV)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=WEBHOOK_PORT,
        #ssl_certfile=ssl_cert,
        #ssl_keyfile=ssl_key
    )