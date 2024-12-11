from dotenv import dotenv_values

config = dotenv_values(".env")

BOT_TOKEN = config.get('BOT_TOKEN')