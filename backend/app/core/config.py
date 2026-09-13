import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
CUSTOMERS_FILE = DATA_DIR / 'customers.json'

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MODEL_NAME = os.getenv('MODEL_NAME', 'gpt-4o-mini')
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
FRONTEND_ORIGIN = os.getenv('FRONTEND_ORIGIN')
