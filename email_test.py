# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
from email_notifier import EmailNotifier

load_dotenv()

print("="*60)
print("EMAIL NOTIFIER TEST")
print("="*60)

notifier = EmailNotifier()

print("\nAYARLAR:")
print(f"  Email: {notifier.email if notifier.email else 'Yok'}")
print(f"  Password: {'Var' if notifier.password else 'Yok'}")
print(f"  Recipient: {notifier.recipient if notifier.recipient else 'Yok'}")
print(f"  Enabled: {'Evet' if notifier.enabled else 'Hayir'}")

if notifier.enabled:
    print("\nTEST MAILI GONDERILIYOR...")
    
    subject = "TEST - BIST Bot Email"
    body = "<html><body><h1>Test Email</h1><p>Email ayarlari basarili!</p></body></html>"
    
    result = notifier.send_email(subject, body, html=True)
    
    if result:
        print("BASARILI! Test maili gonderildi!")
    else:
        print("HATA! Mail gonderilemedi")
else:
    print("\nHATA: Email ayarlari eksik!")

print("="*60)