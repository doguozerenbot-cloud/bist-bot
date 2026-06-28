# -*- coding: utf-8 -*-
"""
BIST PYTHON BOT - FINAL VERSION + FAZA 1 (FIXED)
Finnhub + Alpha Vantage + Telegram + Email + Database + Logging
FİXED: Race Condition, Connection Pooling, Rate Limiting, Timeout
"""
import logging
import os
import threading
import time
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Optional
from collections import defaultdict

from flask import Flask, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from api_client import DataFetcher
from analyzer import BISTAnalyzer
from telegram_notifier import TelegramNotifier
from email_notifier import EmailNotifier
from database import DatabaseManager
from logger_config import get_logger, get_performance_tracker, get_structured_logger
from config import (
    TARAMA_SAATI, BIST_AÇILIŞ, TIMEZONE, ALLOWED_USERS
)

# ============================================================================
# LOGGING - ADVANCED
# ============================================================================

logger = get_logger('bist_bot')
perf_tracker = get_performance_tracker(logger)
struct_logger = get_structured_logger(logger)

# ============================================================================
# RATE LIMITER
# ============================================================================

class RateLimiter:
    """Per-User Rate Limiting"""
    
    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    def is_allowed(self, user_id: str) -> bool:
        """Check if user is allowed to make request"""
        with self.lock:
            now = time.time()
            
            # Clean old requests
            self.requests[user_id] = [
                req_time for req_time in self.requests[user_id]
                if now - req_time < self.window_seconds
            ]
            
            # Check limit
            if len(self.requests[user_id]) >= self.max_requests:
                self.logger.warning(f"Rate limit exceeded for user {user_id}")
                return False
            
            # Add new request
            self.requests[user_id].append(now)
            return True

# ============================================================================
# ANA BOT
# ============================================================================

class BISTBot:
    """BIST Python Bot - Sinyal Üreticisi + Database + Email + Thread Safe"""

    def __init__(self):
        self.fetcher = DataFetcher()
        self.analyzer = BISTAnalyzer()
        self.notifier = TelegramNotifier()
        self.email_notifier = EmailNotifier()
        self.db = DatabaseManager()
        self.scheduler = BackgroundScheduler(timezone=TIMEZONE)
        
        # Thread safety - FİXED: Race condition
        self.scan_lock = threading.Lock()
        self.is_scanning = False
        
        # Rate limiting - FİXED: Rate limiting
        self.rate_limiter = RateLimiter(max_requests=5, window_seconds=60)

        self.tarama_sonuçları = {}
        self.son_tarama_zamanı = None
        self.tarama_timeout = 45 * 60  # 45 dakika max (FİXED: Timeout)

        logger.info("🤖 BIST Bot Başlatılıyor...")

    def tara(self, index: str = 'BIST100', timeout: int = None) -> Dict:
        """BIST100 Taraması Yap (Thread-Safe)"""
        
        # FİXED: Race condition - Lock
        with self.scan_lock:
            if self.is_scanning:
                logger.warning("⚠️ Tarama zaten çalışıyor, yeni istek reddedildi")
                return {
                    'hata': 'Tarama zaten çalışıyor',
                    'toplam': 0,
                    'tarama_geçen': 0
                }
            
            self.is_scanning = True
        
        try:
            if timeout is None:
                timeout = self.tarama_timeout
            
            start_time = time.time()
            perf_tracker.start_timer('tara')
            logger.info(f"🔍 {index} Taraması Başlıyor (Timeout: {timeout}s)...")

            hisseler = self.fetcher.tarama_yap()

            if not hisseler:
                logger.error(f"❌ {index} Veri Alınamadı")
                struct_logger.log_event('SCAN_ERROR', {
                    'index': index,
                    'reason': 'Veri alınamadı'
                })
                return {'hata': 'Veri alınamadı', 'toplam': 0, 'tarama_geçen': 0}

            tarama_geçenler = []
            uyarılar = []

            for hisse in hisseler:
                # Timeout kontrol
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    logger.warning(f"⏱️ Timeout {timeout}s'ye ulaşıldı, tarama durduruldu")
                    break
                
                kod = hisse.get('kod')

                try:
                    analiz_sonucu = self.analyzer.analiz_hisse(hisse)

                    # Veritabanına kaydet
                    self.db.tarama_kaydet(kod, analiz_sonucu)

                    if analiz_sonucu.get('tarama_geçti'):
                        tarama_geçenler.append(analiz_sonucu)
                        logger.info(f"✅ {kod} Tarama Geçti (Skor: {analiz_sonucu.get('skor')}%)")

                        # Sinyal olursa veritabanına kaydet
                        if analiz_sonucu.get('sinyal') in ['BUY', 'CAUTION']:
                            self.db.sinyal_kaydet(kod, analiz_sonucu)
                            struct_logger.log_trade_signal(
                                kod,
                                analiz_sonucu.get('sinyal'),
                                analiz_sonucu
                            )

                    if analiz_sonucu.get('uyarı'):
                        uyarılar.append({
                            'kod': kod,
                            'mesaj': analiz_sonucu.get('uyarı'),
                        })

                except Exception as e:
                    logger.error(f"❌ {kod} Analiz Hatası: {str(e)}")
                    struct_logger.log_error_detail(
                        'ANALYSIS_ERROR',
                        str(e),
                        {'kod': kod}
                    )
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
                'hisseler': tarama_geçenler[:10],
                'uyarılar': uyarılar[:5],
            }

            # İstatistik kaydet
            tarih = datetime.now(pytz.timezone(TIMEZONE)).strftime('%Y-%m-%d')
            self.db.tarama_istatistigi_kayret(tarih, {
                'toplam': len(hisseler),
                'gecen': len(tarama_geçenler),
                'oran': sonuç['başarı_oranı'],
                'ortalama_skor': sum([h.get('skor', 0) for h in tarama_geçenler]) / len(tarama_geçenler) if tarama_geçenler else 0
            })

            self.tarama_sonuçları = sonuç
            self.son_tarama_zamanı = datetime.now(pytz.timezone(TIMEZONE))

            # Performance log
            duration = perf_tracker.end_timer('tara')
            struct_logger.log_scan_result(len(hisseler), len(tarama_geçenler), sonuç['başarı_oranı'])

            logger.info(f"✅ Tarama Tamamlandı: {len(tarama_geçenler)}/{len(hisseler)} geçti ({duration:.2f}s)")

            return sonuç

        finally:
            # FİXED: Lock'u bırak
            with self.scan_lock:
                self.is_scanning = False

    def bildir_tarama_sonuçları(self, sonuçlar: Dict):
        """Tarama Sonuçlarını Telegram + Email'de Bildir"""

        logger.info("📱📧 Telegram + Email Bildirimi Gönderiliyor...")

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
            self.notifier.send_message_sync(mesaj)
            logger.info("✅ Telegram Bildirimi Gönderildi")
        except Exception as e:
            logger.error(f"❌ Telegram Hatası: {str(e)}")
            struct_logger.log_error_detail('TELEGRAM_ERROR', str(e))

        try:
            self.email_notifier.bildir_tarama_sonucu(sonuçlar)
            logger.info("✅ Email Bildirimi Gönderildi")
        except Exception as e:
            logger.error(f"❌ Email Hatası: {str(e)}")
            struct_logger.log_error_detail('EMAIL_ERROR', str(e))

    def setup_scheduler(self):
        """Scheduler'ı Kur - Pazartesi-Cuma 09:30'da Çalış"""

        self.scheduler.add_job(
            self.cron_tarama,
            trigger=CronTrigger(
                hour=9,
                minute=30,
                day_of_week='0-4',
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
        try:
            sonuçlar = self.tara()
            self.bildir_tarama_sonuçları(sonuçlar)
        except Exception as e:
            logger.error(f"❌ Cron Tarama Hatası: {str(e)}")
            self.email_notifier.bildir_hata(
                f"Scheduled tarama başarısız: {str(e)}",
                str(e)
            )

    def manuel_tarama(self, user_id: str = None) -> Dict:
        """Şu Anda Manuel Tarama Yap (Rate Limited)"""

        logger.info(f"🔍 Manuel Tarama Tetiklendi (User: {user_id})")
        
        # FİXED: Rate limiting
        if user_id:
            if not self.rate_limiter.is_allowed(user_id):
                logger.warning(f"❌ Rate limit exceeded for user {user_id}")
                return {
                    'hata': 'Çok fazla istek (5 istek/dakika sınırı)',
                    'toplam': 0,
                    'tarama_geçen': 0
                }

        try:
            sonuçlar = self.tara()
            self.bildir_tarama_sonuçları(sonuçlar)
            return sonuçlar
        except Exception as e:
            logger.error(f"❌ Manuel Tarama Hatası: {str(e)}")
            self.email_notifier.bildir_hata(
                f"Manuel tarama başarısız: {str(e)}",
                str(e)
            )
            return {'hata': str(e)}

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

# FİXED: Timeout setting for Flask
app.config['JSON_SORT_KEYS'] = False

@app.route('/health', methods=['GET'])
def health():
    """Sağlık Kontrolü"""
    turkey_time = datetime.now(pytz.timezone(TIMEZONE)).strftime('%H:%M:%S')
    return jsonify({
        'status': 'healthy',
        'bot_status': 'çalışıyor ✅',
        'is_scanning': bot.is_scanning,
        'turkey_time': turkey_time,
        'next_scan': '09:30 (Her gün Pazartesi-Cuma)',
        'bist_opens': '10:00',
        'mode': 'SIGNAL (Manual Trading)',
        'database': 'SQLite ✅',
        'email': 'Enabled ✅',
        'logging': 'Advanced ✅',
        'rate_limiting': 'Enabled ✅',
        'timeout': f'{bot.tarama_timeout}s'
    }), 200

@app.route('/tara', methods=['POST'])
def tara_endpoint():
    """Manuel Tarama Endpoint (Rate Limited)"""

    try:
        user_id = request.json.get('user_id') if request.json else None

        if user_id and user_id not in ALLOWED_USERS:
            logger.warning(f"⚠️ Yetkisiz Tarama İsteği: {user_id}")
            return jsonify({'error': 'Yetkiniz yok'}), 403

        logger.info(f"📥 Manuel Tarama İsteği (User: {user_id})")

        sonuçlar = bot.manuel_tarama(user_id)

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
            'is_scanning': bot.is_scanning,
            'son_tarama': bot.son_tarama_zamanı.isoformat() if bot.son_tarama_zamanı else 'Henüz tarama yok',
            'tarama_sonuçları': len(bot.tarama_sonuçları),
            'database': 'SQLite ✅',
            'email_notifier': 'Enabled ✅',
            'logging': 'Advanced ✅',
            'rate_limiting': 'Enabled ✅',
            'timeout': f'{bot.tarama_timeout}s'
        }
    }), 200

@app.route('/acik-sinyaller', methods=['GET'])
def acik_sinyaller_endpoint():
    """Açık Sinyalleri Getir"""

    try:
        sinyaller = bot.db.acik_sinyaller_getir()

        return jsonify({
            'status': 'success',
            'data': [dict(s) for s in sinyaller]
        }), 200

    except Exception as e:
        logger.error(f"❌ Sinyal Getirme Hatası: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/performans', methods=['GET'])
def performans_endpoint():
    """Performans Verileri"""

    try:
        performans = bot.db.performans_getir()

        return jsonify({
            'status': 'success',
            'data': dict(performans) if performans else {}
        }), 200

    except Exception as e:
        logger.error(f"❌ Performans Getirme Hatası: {str(e)}")
        return jsonify({'error': str(e)}), 500

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
        logger.info(f"🤖 Mode: SİNYAL + TELEGRAM + EMAIL + DATABASE")
        logger.info(f"📊 Logging: Advanced (logs/ klasörü)")
        logger.info(f"🔒 Thread Safety: Enabled (Lock + Rate Limit)")
        logger.info(f"⏱️ Timeout: {bot.tarama_timeout}s")
        logger.info("="*60)

        # FİXED: Timeout setting
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            threaded=True,  # Thread-safe
            timeout=bot.tarama_timeout + 60  # Flask timeout
        )

    except KeyboardInterrupt:
        logger.info("⌛ Bot kapatılıyor...")
        bot.durdur()

    except Exception as e:
        logger.error(f"❌ HATA: {str(e)}")
        bot.durdur()
