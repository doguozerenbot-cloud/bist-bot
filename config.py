import os
from dotenv import load_dotenv

load_dotenv()

BIST_AÇILIŞ = '10:00'
TARAMA_SAATI = '09:30'
TIMEZONE = 'Europe/Istanbul'

FILTER_RULES = {
    'min_pe_ratio': 5,
    'max_pe_ratio': 18,
    'min_roe_percent': 8,
    'max_debt_ratio': 1.5,
    'min_dividend_yield': 1.0,
    'min_adv_milyon': 10,
    'min_market_cap_billion': 0.5,
}

TECHNICAL_RULES = {
    'min_adx': 25,
    'min_rsi': 40,
    'max_rsi': 80,
    'min_volatility_pct': 1.5,
    'max_volatility_pct': 5.0,
}

RISK_MANAGEMENT = {
    'account_size_tl': 10000,
    'risk_percent': 2,
    'min_rr_ratio': 2.0,
}

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
ALLOWED_USERS = os.getenv('ALLOWED_USERS', '').split(',') if os.getenv('ALLOWED_USERS') else []

FINANS_API_KEY = os.getenv('FINANS_API_KEY', '')
FINANS_API_URL = os.getenv('FINANS_API_URL', '')

BROKER_API_KEY = os.getenv('BROKER_API_KEY', '')
BROKER_API_URL = os.getenv('BROKER_API_URL', '')

SCAN_INDEX = 'BIST100'