import telebot

from config import BOT_TOKEN

# Replace 'YOUR_BOT_TOKEN' with your actual bot token
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(func=lambda message: True)
def echo(message):
    bot.reply_to(message, message.text)

# Start the bot
bot.polling()