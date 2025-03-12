import logging
import json

import telebot
import os

from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from PyPDF2 import PdfReader
from config import BOT_TOKEN
from back.ai import start_chat, evaluate
from back.db import (get_candidate, get_vacancy,
                     get_requirements, update_marks,
                     update_candidate_info, get_opened_vacancies,
                     get_vacancy_id, get_chat_state, transform_marks, get_requirements_ids)


log = logging.getLogger(__file__)

# Dictionary to store user data
user_data = {}

# Replace 'YOUR_BOT_TOKEN' with your actual bot token
bot = telebot.TeleBot(BOT_TOKEN)
log.info('Bot started')

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "Welcome! Please enter your email address:")
    bot.register_next_step_handler(msg, process_email)

def process_email(message):
    chat_id = message.chat.id
    email = message.text
    cand = get_candidate(email)
    if cand:
        bot.send_message(chat_id, "We found your resume.")
        update_candidate_info(chat_id, new_resume = cand['resume'], new_state='found resume', cand_id = cand['id'])
        show_vacancies(chat_id, cand)
    else:
        bot.send_message(chat_id, "We couldn't find your resume. Please upload it as a .pdf file.")
        bot.register_next_step_handler(message, handle_document_upload, email)

def show_vacancies(chat_id, cand):
    vacancies = get_opened_vacancies()
    if vacancies:
        markup = telebot.types.InlineKeyboardMarkup()
        for vacancy in vacancies:
            data_dict = {'id': vacancy['id'], 'name': vacancy['name']}
            callback_data = f"{data_dict['id']}|{data_dict['name']}"
            print(callback_data)
            print(len(callback_data))
            markup.add(telebot.types.InlineKeyboardButton(text=vacancy['name'], callback_data=callback_data))
        bot.send_message(chat_id, "Выберите вакансию из списка ниже:", reply_markup=markup)
        # vacancy_list = "\n".join([f"- {vacancy["name"]}" for vacancy in vacancies])
        # msg = bot.send_message(chat_id, f"Please select a vacancy from the list below by typing its name:\n{vacancy_list}")
        create_callback_handler(cand)
    else:
        bot.send_message(chat_id, "Currently, there are no open vacancies.")

def create_callback_handler(cand):
    @bot.callback_query_handler(func=lambda call: True)
    def process_vacancy_selection(call):
        chat_id = call.message.chat.id
        #chat_id = message.chat.id
        data = call.data.split('|')
        vacancy_id = int(data[0])
        vacancy_name = data[1]
        # selected_vacancy = message.text
        #vacancy_id = get_vacancy_id(selected_vacancy)
        #print(vacancy_id, type(vacancy_id['id']))
        bot.answer_callback_query(call.id, f"Вы выбрали вакансию: {vacancy_name}")

        vacancy_requirements = get_requirements(vacancy_id)
        if vacancy_requirements:
            bot.send_message(chat_id, f"Requirements for {vacancy_name} retrieved.")
            initiate_llm_chat(chat_id, vacancy_id, cand, vacancy_requirements)
        else:
            msg = bot.send_message(chat_id, "Vacancy not found. Please enter a valid vacancy name.")
            bot.register_next_step_handler(msg, process_vacancy_selection, cand)


def handle_document_upload(message, email):
    chat_id = message.chat.id
    if message.content_type == 'document' and message.document.mime_type == 'application/pdf':
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        # Save the file to your desired location
        resume_path = f"{email}_resume.pdf"
        with open(resume_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        update_candidate_info(chat_id, new_resume = extract_text_from_pdf(resume_path), new_state= 'got resume')
        bot.send_message(chat_id, "Resume received and updated.")
        show_vacancies(chat_id, email)
    else:
        msg = bot.send_message(chat_id, "Please upload a valid .pdf file.")
        bot.register_next_step_handler(msg, handle_document_upload, email)

def initiate_llm_chat(chat_id, vacancy_id, cand, vacancy_requirements):
    if cand:
        greeting, chat_processor = start_chat(chat_id, vacancy_id, cand, vacancy_requirements)
        greeting_msg = greeting['messages'][-1].content
        bot.send_message(chat_id, greeting_msg)
        if greeting['is_finished']:
            marks = evaluate(chat_id, cand, vacancy_requirements)
            if marks:
                id_marks = transform_marks(marks, get_requirements_ids())
                update_marks(vacancy_id, chat_id, id_marks)
                update_candidate_info(chat_id, new_state='FINISHED')
            else:
                log.info('Interview finished, but marks not found')
        else:
            update_candidate_info(chat_id, new_state='STARTED')
            bot.register_next_step_handler_by_chat_id(chat_id, interview_candidate, chat_processor, vacancy_id, cand, vacancy_requirements)
    else:
        bot.send_message(chat_id, "Resume not found. Please upload your resume.")
        bot.register_next_step_handler_by_chat_id(chat_id, handle_document_upload)

@bot.message_handler(func=lambda message: get_chat_state(message.chat.id) == 'STARTED')
def interview_candidate(message,  chat_processor, vacancy_id, cand, requirements):
    chat_id = message.chat.id
    input_msg = message.text
    msg, finish, hist = chat_processor(chat_id, input_msg, vacancy_id)

    if finish:
        marks = evaluate(chat_id, cand, vacancy_id, requirements)
        if marks:
            id_marks = transform_marks(marks, get_requirements_ids())
            update_marks(vacancy_id, message.chat.id, id_marks)
            update_candidate_info(chat_id, new_state='FINISHED')
            bot.send_message(message.chat.id, msg)
        else:
            log.info('Interview finished, but marks not found')
    else:
        bot.send_message(message.chat.id, msg)
        bot.register_next_step_handler_by_chat_id(chat_id, interview_candidate,  chat_processor, vacancy_id, cand, requirements)

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



# Start the bot
bot.polling(logger_level=logging.INFO)

