from dotenv import dotenv_values

from log import setup_logger

config = dotenv_values(".env")

BOT_TOKEN = config.get('BOT_TOKEN')
OPEN_AI_KEY = config.get('OPEN_AI_KEY')

setup_logger()