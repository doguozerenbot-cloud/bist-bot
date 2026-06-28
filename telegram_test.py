#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Test - Mesaj Gönder
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# .env'den al
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Telegram API
url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# Mesaj
mesaj = """
🤖 BOT TEST - BAŞARILI! ✅

BIST Trading Bot Telegram bağlantısı çalışıyor!

📅 Pazartesi 09:30'da sinyaller gelecek...

Test: 28 Haziran 2026
"""

# Gönder
data = {
    'chat_id': TELEGRAM_CHAT_ID,
    'text': mesaj,
    'parse_mode': 'HTML'
}

response = requests.post(url, data=data)

if response.status_code == 200:
    print("✓ Telegram mesajı BAŞARILI gönderildi!")
    print(f"Response: {response.json()}")
else:
    print(f"✗ Hata: {response.status_code}")
    print(f"Response: {response.json()}")