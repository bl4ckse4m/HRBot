from dotenv import dotenv_values

from log import setup_logger

config = dotenv_values(".env")

BOT_TOKEN = config.get('BOT_TOKEN')
OPEN_AI_KEY = config.get('OPEN_AI_KEY')
SUPABASE_URL = config.get('SUPABASE_URL')
SUPABASE_KEY = config.get('SUPABASE_KEY')
POSTGRES_URL = config.get('POSTGRES_URL')
MODEL = 'gpt-4o-mini'


setup_logger()