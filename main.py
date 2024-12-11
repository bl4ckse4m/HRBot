import logging

import telebot

from ai import chat_bot
from config import BOT_TOKEN

log = logging.getLogger(__file__)


# Replace 'YOUR_BOT_TOKEN' with your actual bot token
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(func=lambda message: True)
def echo(message):
    log.info(message)
    response = chat_bot(message.text)
    log.info(response)
    bot.reply_to(message, response)

# Start the bot
bot.polling(logger_level=logging.INFO)