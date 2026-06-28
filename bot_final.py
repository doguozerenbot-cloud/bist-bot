# -*- coding: utf-8 -*-
"""
BIST PYTHON BOT - FINAL VERSION
Finnhub + Alpha Vantage + Telegram + Railway
"""
import logging
import os
from datetime import datetime
import pytz
from typing import Dict, List, Optional

from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from api_client import DataFetcher
from analyzer import BISTAnalyzer
from telegram_notifier import TelegramNotifier
from config import (
    TARAMA_SAATI, BIST_AÇILIŞ, TIMEZONE, ALLOWED_USERS
)

# ============================================================================
# LOGGING
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# ANA BOT
# ============================================================================

class BISTBot:
    """BIST Python Bot - Sinyal Üreticisi"""
    
    def __init__(self):
        self.fetcher = DataFetcher()
        self.analyzer = BISTAnalyzer()
        self.notifier = TelegramNotifier()
        self.scheduler = BackgroundScheduler(timezone=TIMEZONE)
        
        self.tarama_sonuçları = {}
        self.son_tarama_zamanı = None
        
        logger.info("🤖 BIST Bot Başlatılıyor...")
    
    def tara(self, index: str = 'BIST100') -> Dict:
        """BIST100 Taraması Yap"""
        
        logger.info(f"🔍 {index} Taraması Başlıyor...")
        
        hisseler = self.fetcher.tarama_yap()
        
        if not hisseler:
            logger.error(f"❌ {index} Veri Alınamadı")
            return {'hata': 'Veri alınamadı', 'toplam': 0, 'tarama_geçen': 0}
        
        tarama_geçenler = []
        uyarılar = []
        
        for hisse in hisseler:
            kod = hisse.get('kod')
            
            try:
                analiz_sonucu = self.analyzer.analiz_hisse(hisse)
                
                if analiz_sonucu.get('tarama_geçti'):
                    tarama_geçenler.append(analiz_sonucu)
                    logger.info(f"✅ {kod} Tarama Geçti (Skor: {analiz_sonucu.get('skor')}%)")
                
                if analiz_sonucu.get('uyarı'):
                    uyarılar.append({
                        'kod': kod,
                        'mesaj': analiz_sonucu.get('uyarı'),
                    })
            
            except Exception as e:
                logger.error(f"❌ {kod} Analiz Hatası: {str(e)}")
                continue
        
        # En yüksek skordan başlayarak sırala
        tarama_geçenler.sort(key=lambda x: x.get('skor', 0), reverse=True)
        
        sonuç = {
            'index': index,
            'tarama_zamanı': datetime.now(pytz.timezone(TIMEZONE)).isoformat(),
            'toplam': len(hisseler),
            'tarama_geçen': len(tarama_geçenler),
            'uyarı_sayısı': len(uyarılar),
            'başarı_oranı': int(len(tarama_geçenler) / len(hisseler) * 100) if hisseler else 0,
            'hisseler': tarama_geçenler[:10],  # Top 10
            'uyarılar': uyarılar[:5],  # Top 5
        }
        
        self.tarama_sonuçları = sonuç
        self.son_tarama_zamanı = datetime.now(pytz.timezone(TIMEZONE))
        
        logger.info(f"✅ Tarama Tamamlandı: {len(tarama_geçenler)}/{len(hisseler)} geçti")
        
        return sonuç
    
    def bildir_tarama_sonuçları(self, sonuçlar: Dict):
        """Tarama Sonuçlarını Telegram'da Bildir"""
        
        logger.info("📱 Telegram Bildirimi Gönderiliyor...")
        
        tr_time = datetime.now(pytz.timezone(TIMEZONE)).strftime('%H:%M:%S')
        
        mesaj = f"""
🔔 BIST TARAMA SONUÇLARI
⏰ Saat: {tr_time}

📊 ÖZET:
Taraması Yapılan: {sonuçlar['toplam']}
Tarama Geçen: {sonuçlar['tarama_geçen']}
Başarı Oranı: {sonuçlar['başarı_oranı']}%

⏱️ KARAR SÜRESİ: 09:30 - 10:00 (30 DAKIKA)
"""
        
        if sonuçlar['hisseler']:
            mesaj += "\n🟢 TARAMA GEÇEN HİSSELER (En İyi 5):\n\n"
            
            for i, h in enumerate(sonuçlar['hisseler'][:5], 1):
                kod = h['kod']
                skor = h['skor']
                fiyat = h.get('fiyat', 0)
                sinyal = h.get('sinyal', 'UNKNOWN')
                
                mesaj += f"{i}. {kod} ({sinyal})\n"
                mesaj += f"   Fiyat: {fiyat:.2f} TL | Skor: {skor}%\n\n"
        
        else:
            mesaj += "\n⚠️ Tarama geçen hisse yok\n"
        
        mesaj += "\n" + "="*50 + "\n"
        mesaj += "📌 MANUEL KARAR VER!\n"
        mesaj += "🎯 10:00'DA BIST AÇILIYOR\n"
        mesaj += "⚠️ BOT: SİNYAL VERIR, SEN İŞLEM YAPARSSIN\n"
        mesaj += "="*50 + "\n"
        
        try:
            self.notifier.send_message(mesaj)
            logger.info("✅ Telegram Bildirimi Gönderildi")
        except Exception as e:
            logger.error(f"❌ Telegram Hatası: {str(e)}")
    
    def setup_scheduler(self):
        """Scheduler'ı Kur - Pazartesi-Cuma 09:30'da Çalış"""
        
        self.scheduler.add_job(
            self.cron_tarama,
            trigger=CronTrigger(
                hour=9,
                minute=30,
                day_of_week='0-4',  # Pazartesi(0) - Cuma(4)
                timezone=TIMEZONE
            ),
            id='daily_screen',
            name='09:30 Günlük Tarama'
        )
        
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("✅ Scheduler Başlatıldı (Her gün 09:30 - Pazartesi-Cuma)")
    
    def cron_tarama(self):
        """Cron Taraması (Scheduler tarafından çağrılır)"""
        logger.info("⏰ Scheduled Tarama Tetiklendi")
        sonuçlar = self.tara()
        self.bildir_tarama_sonuçları(sonuçlar)
    
    def manuel_tarama(self) -> Dict:
        """Şu Anda Manuel Tarama Yap"""
        
        logger.info("🔍 Manuel Tarama Tetiklendi")
        
        sonuçlar = self.tara()
        self.bildir_tarama_sonuçları(sonuçlar)
        
        return sonuçlar
    
    def başlat(self):
        """Bot'u Başlat"""
        logger.info("🚀 Bot Başlatılıyor...")
        self.setup_scheduler()
        logger.info("✅ Bot Hazır ve Çalışıyor")
    
    def durdur(self):
        """Bot'u Durdur"""
        logger.info("🛑 Bot Durduruluyor...")
        if self.scheduler.running:
            self.scheduler.shutdown()
        logger.info("✅ Bot Durduruldu")

# ============================================================================
# FLASK APP
# ============================================================================

app = Flask(__name__)
bot = BISTBot()

@app.route('/health', methods=['GET'])
def health():
    """Sağlık Kontrolü"""
    turkey_time = datetime.now(pytz.timezone(TIMEZONE)).strftime('%H:%M:%S')
    return jsonify({
        'status': 'healthy',
        'bot_status': 'çalışıyor ✅',
        'turkey_time': turkey_time,
        'next_scan': '09:30 (Her gün Pazartesi-Cuma)',
        'bist_opens': '10:00',
        'mode': 'SIGNAL (Manual Trading)'
    }), 200

@app.route('/tara', methods=['POST'])
def tara_endpoint():
    """Manuel Tarama Endpoint"""
    
    try:
        user_id = request.json.get('user_id') if request.json else None
        
        if user_id and user_id not in ALLOWED_USERS:
            logger.warning(f"⚠️ Yetkisiz Tarama İsteği: {user_id}")
            return jsonify({'error': 'Yetkiniz yok'}), 403
        
        logger.info(f"📥 Manuel Tarama İsteği")
        
        sonuçlar = bot.manuel_tarama()
        
        return jsonify({
            'status': 'success',
            'data': sonuçlar
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Tarama Hatası: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/sonuç', methods=['GET'])
def sonuç_endpoint():
    """Son Tarama Sonuçları"""
    
    if not bot.tarama_sonuçları:
        return jsonify({'error': 'Henüz tarama yapılmamış'}), 404
    
    return jsonify({
        'status': 'success',
        'data': bot.tarama_sonuçları
    }), 200

@app.route('/hisse/<kod>', methods=['GET'])
def get_hisse_endpoint(kod):
    """Tek Hisse Analizi"""
    
    try:
        veri = bot.fetcher.get_bist_verisi(kod.upper())
        
        if not veri:
            return jsonify({'error': f'{kod} Bulunamadı'}), 404
        
        analiz = bot.analyzer.analiz_hisse(veri)
        
        return jsonify({
            'status': 'success',
            'data': analiz
        }), 200
    
    except Exception as e:
        logger.error(f"❌ Hisse Analizi Hatası ({kod}): {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/durum', methods=['GET'])
def durum_endpoint():
    """Bot Durumu"""
    
    return jsonify({
        'status': 'success',
        'bot': {
            'durum': 'Çalışıyor ✅',
            'tarama_saati': '09:30',
            'bist_açılış': '10:00',
            'timezone': TIMEZONE,
            'son_tarama': bot.son_tarama_zamanı.isoformat() if bot.son_tarama_zamanı else 'Henüz tarama yok',
            'tarama_sonuçları': len(bot.tarama_sonuçları),
        }
    }), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint Bulunamadı'}), 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"❌ Server Hatası: {str(error)}")
    return jsonify({'error': 'Sunucu Hatası'}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    try:
        bot.başlat()
        
        port = int(os.environ.get('PORT', 8080))
        
        logger.info("="*60)
        logger.info(f"🌐 Flask App {port} Portunda Başlıyor...")
        logger.info(f"📅 Tarama: 09:30 (Pazartesi-Cuma)")
        logger.info(f"⏰ BIST: 10:00 (Senin karar zamanı)")
        logger.info(f"🤖 Mode: SİNYAL + TELEGRAM BİLDİRİMİ")
        logger.info("="*60)
        
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    
    except KeyboardInterrupt:
        logger.info("⌛ Bot kapatılıyor...")
        bot.durdur()
    
    except Exception as e:
        logger.error(f"❌ HATA: {str(e)}")
        bot.durdur()
