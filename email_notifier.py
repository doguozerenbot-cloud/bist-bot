# -*- coding: utf-8 -*-
"""
Email Notifier - Telegram Backup
Gmail ile email gönderme
"""
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================================
# EMAIL NOTIFIER
# ============================================================================

class EmailNotifier:
    """Email Bildirimleri - Telegram Backup"""
    
    def __init__(self, email: Optional[str] = None, password: Optional[str] = None, 
                 recipient: Optional[str] = None):
        self.email = email or os.getenv('EMAIL_ADDRESS', '')
        self.password = password or os.getenv('EMAIL_PASSWORD', '')
        self.recipient = recipient or os.getenv('EMAIL_RECIPIENT', '')
        self.logger = logging.getLogger(__name__)
        
        if not self.email or not self.password:
            self.logger.warning("⚠️ Email credentials ayarlanmamış - SMTP devre dışı")
            self.enabled = False
        else:
            self.enabled = True
    
    def send_email(self, subject: str, body: str, html: bool = False) -> bool:
        """Email Gönder"""
        
        if not self.enabled or not self.recipient:
            self.logger.warning("⚠️ Email gönderilemedi - Ayarlar eksik")
            return False
        
        try:
            self.logger.info(f"📧 Email Gönderiliyor: {subject}")
            
            # SMTP bağlantısı
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(self.email, self.password)
            
            # Mesaj oluştur
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = self.email
            message['To'] = self.recipient
            
            if html:
                message.attach(MIMEText(body, 'html'))
            else:
                message.attach(MIMEText(body, 'plain'))
            
            # Gönder
            server.sendmail(self.email, self.recipient, message.as_string())
            server.quit()
            
            self.logger.info("✅ Email Gönderildi")
            return True
        
        except Exception as e:
            self.logger.error(f"❌ Email Gönderme Hatası: {str(e)}")
            return False
    
    def bildir_tarama_sonucu(self, sonuç: dict) -> bool:
        """Tarama Sonucunu Email ile Bildir"""
        
        subject = f"BIST Bot - Tarama Sonucu ({sonuç.get('tarama_zamanı', 'N/A')})"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>🔔 BIST TARAMA SONUÇLARI</h2>
                
                <h3>📊 ÖZET</h3>
                <ul>
                    <li><b>Taraması Yapılan:</b> {sonuç.get('toplam', 0)}</li>
                    <li><b>Tarama Geçen:</b> {sonuç.get('tarama_geçen', 0)}</li>
                    <li><b>Başarı Oranı:</b> {sonuç.get('başarı_oranı', 0)}%</li>
                    <li><b>Tarama Zamanı:</b> {sonuç.get('tarama_zamanı', 'N/A')}</li>
                </ul>
                
                <h3>🟢 TARAMA GEÇEN HİSSELER (Top 5)</h3>
                <table style="border-collapse: collapse; width: 100%;">
                    <tr style="background-color: #f2f2f2;">
                        <th style="border: 1px solid #ddd; padding: 8px;">Sıra</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Kod</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Sinyal</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Skor</th>
                        <th style="border: 1px solid #ddd; padding: 8px;">Fiyat (TL)</th>
                    </tr>
        """
        
        if sonuç.get('hisseler'):
            for i, h in enumerate(sonuç['hisseler'][:5], 1):
                html_body += f"""
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px;">{i}</td>
                        <td style="border: 1px solid #ddd; padding: 8px;"><b>{h.get('kod', 'N/A')}</b></td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{h.get('sinyal', 'N/A')}</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{h.get('skor', 0)}%</td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{h.get('fiyat', 0):.2f}</td>
                    </tr>
                """
        
        html_body += """
                </table>
                
                <h3>⚠️ ÖNEMLI</h3>
                <ul>
                    <li>📌 MANUEL KARAR VER!</li>
                    <li>🎯 10:00'DA BIST AÇILIYOR</li>
                    <li>⚠️ BOT: SİNYAL VERIR, SEN İŞLEM YAPARSSIN</li>
                    <li>💼 Risk yönetimi kurallarına uy!</li>
                </ul>
                
                <hr>
                <p style="color: #888; font-size: 12px;">
                    Bu email BIST Bot tarafından otomatik olarak gönderilmiştir.
                </p>
            </body>
        </html>
        """
        
        return self.send_email(subject, html_body, html=True)
    
    def bildir_sinyal(self, kod: str, sinyal: str, veri: dict) -> bool:
        """Sinyal Bildiri"""
        
        subject = f"🔔 BIST SİNYAL: {kod} - {sinyal}"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>🔔 YENİ SİNYAL!</h2>
                
                <h3>📊 SİNYAL BİLGİSİ</h3>
                <table style="border-collapse: collapse; width: 100%;">
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">Hisse Kodu:</td>
                        <td style="padding: 8px;">{kod}</td>
                    </tr>
                    <tr style="background-color: #f2f2f2;">
                        <td style="padding: 8px; font-weight: bold;">Sinyal:</td>
                        <td style="padding: 8px; color: green; font-weight: bold;">{sinyal}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">Skor:</td>
                        <td style="padding: 8px;">{veri.get('skor', 0)}%</td>
                    </tr>
                    <tr style="background-color: #f2f2f2;">
                        <td style="padding: 8px; font-weight: bold;">Fiyat:</td>
                        <td style="padding: 8px;">{veri.get('fiyat', 0):.2f} TL</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">Giriş Noktası:</td>
                        <td style="padding: 8px;">{veri.get('giriş', 0):.2f} TL</td>
                    </tr>
                    <tr style="background-color: #f2f2f2;">
                        <td style="padding: 8px; font-weight: bold;">Stop Loss:</td>
                        <td style="padding: 8px; color: red;">{veri.get('sl', 0):.2f} TL</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">Target 1:</td>
                        <td style="padding: 8px; color: green;">{veri.get('t1', 0):.2f} TL</td>
                    </tr>
                    <tr style="background-color: #f2f2f2;">
                        <td style="padding: 8px; font-weight: bold;">Target 2:</td>
                        <td style="padding: 8px; color: green;">{veri.get('t2', 0):.2f} TL</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">Risk/Reward:</td>
                        <td style="padding: 8px;">{veri.get('rr', 0):.2f}</td>
                    </tr>
                </table>
                
                <h3>📈 TEKNİK GÖSTERGELER</h3>
                <ul>
                    <li>RSI: {veri.get('rsi', 'N/A')}</li>
                    <li>MACD: {veri.get('macd', 'N/A')}</li>
                    <li>ADX: {veri.get('adx', 'N/A')}</li>
                    <li>EMA20: {veri.get('ema20', 'N/A')}</li>
                    <li>EMA50: {veri.get('ema50', 'N/A')}</li>
                </ul>
                
                <h3>⚠️ UYARI</h3>
                <ul>
                    <li>✅ MANUEL KARAR VER!</li>
                    <li>✅ KENDİ ANALIZINI YAP!</li>
                    <li>✅ RISK YÖNETİMİNE UY!</li>
                </ul>
                
                <hr>
                <p style="color: #888; font-size: 12px;">
                    Bu email BIST Bot tarafından otomatik olarak gönderilmiştir.
                </p>
            </body>
        </html>
        """
        
        return self.send_email(subject, html_body, html=True)
    
    def bildir_hata(self, hata_aciklama: str, stack_trace: str = '') -> bool:
        """Hata Bildiri"""
        
        subject = "❌ BIST Bot - HATA BİLDİRİMİ"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>❌ BOT HATASI</h2>
                
                <h3>Hata Açıklaması:</h3>
                <p style="color: red; font-weight: bold;">{hata_aciklama}</p>
                
                <h3>Stack Trace:</h3>
                <pre style="background-color: #f2f2f2; padding: 10px; border-radius: 5px;">
{stack_trace}
                </pre>
                
                <h3>⚠️ İŞLEM:</h3>
                <ol>
                    <li>Hataları kontrol et</li>
                    <li>Bot log dosyasını incele</li>
                    <li>Gerekirse bot'u yeniden başlat</li>
                </ol>
                
                <hr>
                <p style="color: #888; font-size: 12px;">
                    Bu email BIST Bot tarafından otomatik olarak gönderilmiştir.
                </p>
            </body>
        </html>
        """
        
        return self.send_email(subject, html_body, html=True)
