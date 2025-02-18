import logging

import telebot
import os

from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from PyPDF2 import PdfReader
from config import BOT_TOKEN
from back.new_ai import start_chat, cand_name
from back.db import (get_candidate, get_vacancy,
                     get_requirements, update_marks,
                     update_candidate_info, get_opened_vacancies,
                     get_vacancy_id, get_chat_state)


log = logging.getLogger(__file__)

# Dictionary to store user data
user_data = {}

# Replace 'YOUR_BOT_TOKEN' with your actual bot token
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "Welcome! Please enter your email address:")
    bot.register_next_step_handler(msg, process_email)

def process_email(message):
    chat_id = message.chat.id
    email = message.text
    cand = get_candidate(email)
    print(type(cand['id']))
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
        vacancy_list = "\n".join([f"- {vacancy}" for vacancy in vacancies])
        msg = bot.send_message(chat_id, f"Please select a vacancy from the list below by typing its name:\n{vacancy_list}")
        bot.register_next_step_handler(msg, process_vacancy_selection, cand)
    else:
        bot.send_message(chat_id, "Currently, there are no open vacancies.")

def process_vacancy_selection(message, cand):
    chat_id = message.chat.id
    selected_vacancy = message.text
    vacancy_id = get_vacancy_id(selected_vacancy)
    print(vacancy_id, type(vacancy_id['id']))
    vacancy_requirements = get_requirements(vacancy_id['id'])
    if vacancy_requirements:
        bot.send_message(chat_id, f"Requirements for {selected_vacancy} retrieved.")
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
        msg = bot.send_message(chat_id, greeting)
        update_candidate_info(chat_id, new_state='STARTED')
        bot.register_next_step_handler_by_chat_id(chat_id, interview_candidate, vacancy_id, chat_processor)
    else:
        bot.send_message(chat_id, "Resume not found. Please upload your resume.")
        bot.register_next_step_handler_by_chat_id(chat_id, handle_document_upload)

@bot.message_handler(func=lambda message: get_chat_state(message.chat.id) == 'STARTED')
def interview_candidate(message, vacancy_id, chat_processor):
    chat_id = message.chat.id
    input_msg = message.text
    msg, marks, hist = chat_processor(chat_id, input_msg)

    if marks:
        update_marks(vacancy_id, message.chat.id, marks)
        update_candidate_info(chat_id, new_state='FINISHED')
        bot.send_message(message.chat.id, msg)
    else:
        bot.send_message(message.chat.id, msg)

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