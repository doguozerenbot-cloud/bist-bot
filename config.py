import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# BIST SAATLERI
# ============================================================================

BIST_AÇILIŞ = '10:00'
TARAMA_SAATI = '09:10'
TIMEZONE = 'Europe/Istanbul'

# ============================================================================
# FİLTRE KURALLARI
# ============================================================================

FILTER_RULES = {
    'min_pe_ratio': 5,
    'max_pe_ratio': 18,
    'min_roe_percent': 5,                    # ← 8'den 5'e düşürüldü (BIST için daha esnek)
    'max_debt_ratio': 1.5,
    'min_dividend_yield': 1.0,
    'min_adv_milyon': 10,                    # Minimum Average Daily Volume
    'min_market_cap_billion': 0.5,
}

# ============================================================================
# TEKNİK KURALLAR
# ============================================================================

TECHNICAL_RULES = {
    'min_adx': 20,                           # ← 25'ten 20'ye düşürüldü (ADX daha çok veri yakalar)
    'min_rsi': 40,
    'max_rsi': 80,
    'min_volatility_pct': 1.5,
    'max_volatility_pct': 5.0,
}

# ============================================================================
# RİSK YÖNETİMİ
# ============================================================================

RISK_MANAGEMENT = {
    'account_size_tl': 10000,                # Hesap büyüklüğü (Test için)
    'risk_percent': 2,                       # Her işlemde risk yüzdesi
    'min_rr_ratio': 2.0,                     # Minimum Risk/Reward oranı
    'max_position_size': 100000,             # Maksimum pozisyon (TL)
    'max_loss_per_day': 500,                 # Günlük maksimum kayıp (TL)
}

# ============================================================================
# API AYARLARI
# ============================================================================

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
ALLOWED_USERS = os.getenv('ALLOWED_USERS', '').split(',') if os.getenv('ALLOWED_USERS') else []

FINANS_API_KEY = os.getenv('FINANS_API_KEY', '')
FINANS_API_URL = os.getenv('FINANS_API_URL', '')

BROKER_API_KEY = os.getenv('BROKER_API_KEY', '')
BROKER_API_URL = os.getenv('BROKER_API_URL', '')

# ============================================================================
# TARAMA AYARLARI
# ============================================================================

SCAN_INDEX = 'BIST100'
SCAN_INTERVAL = 'daily'

# ============================================================================
# LOGLAMA
# ============================================================================

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = 'bist_bot.log'
