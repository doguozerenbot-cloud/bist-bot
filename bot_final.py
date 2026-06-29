# -*- coding: utf-8 -*-
"""
BIST PYTHON BOT - FINAL VERSION + FAZA 1 (FIXED v3)
Finnhub + Alpha Vantage + Telegram + Email + Database + Logging
FİXED: Timeout parameter, Unicode, 18:00 Shutdown
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
    """BIST Python Bot - Sinyal Ureticisi + Database + Email + Thread Safe"""

    def __init__(self):
        self.fetcher = DataFetcher()
        self.analyzer = BISTAnalyzer()
        self.notifier = TelegramNotifier()
        self.email_notifier = EmailNotifier()
        self.db = DatabaseManager()
        self.scheduler = BackgroundScheduler(timezone=TIMEZONE)
        
        # Thread safety
        self.scan_lock = threading.Lock()
        self.is_scanning = False
        
        # Rate limiting
        self.rate_limiter = RateLimiter(max_requests=5, window_seconds=60)

        self.tarama_sonuclari = {}
        self.son_tarama_zamani = None
        self.tarama_timeout = 45 * 60  # 45 minutes max

        logger.info("Bot Baslatiluyor...")

    def tara(self, index: str = 'BIST100', timeout: int = None) -> Dict:
        """BIST100 Taramasi Yap (Thread-Safe)"""
        
        # Race condition - Lock
        with self.scan_lock:
            if self.is_scanning:
                logger.warning("Tarama zaten calisyor, yeni istek reddedildi")
                return {
                    'hata': 'Tarama zaten calisyor',
                    'toplam': 0,
                    'tarama_gecen': 0
                }
            
            self.is_scanning = True
        
        try:
            if timeout is None:
                timeout = self.tarama_timeout
            
            start_time = time.time()
            perf_tracker.start_timer('tara')
            logger.info(f"Tarama Baslaniyor: {index} (Timeout: {timeout}s)...")

            hisseler = self.fetcher.tarama_yap()

            if not hisseler:
                logger.error(f"Veri Alinamadi: {index}")
                struct_logger.log_event('SCAN_ERROR', {
                    'index': index,
                    'reason': 'Veri alinamadi'
                })
                return {'hata': 'Veri alinamadi', 'toplam': 0, 'tarama_gecen': 0}

            tarama_gecenler = []
            uyarilar = []

            for hisse in hisseler:
                # Timeout kontrol
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    logger.warning(f"Timeout {timeout}s'ye ulasildi, tarama durduruldu")
                    break
                
                kod = hisse.get('kod')

                try:
                    analiz_sonucu = self.analyzer.analiz_hisse(hisse)

                    # Veritabanina kaydet
                    self.db.tarama_kaydet(kod, analiz_sonucu)

                    if analiz_sonucu.get('tarama_gecti'):
                        tarama_gecenler.append(analiz_sonucu)
                        logger.info(f"OK {kod} Tarama Gecti (Skor: {analiz_sonucu.get('skor')}%)")

                        # Sinyal olursa veritabanina kaydet
                        if analiz_sonucu.get('sinyal') in ['BUY', 'CAUTION']:
                            self.db.sinyal_kaydet(kod, analiz_sonucu)
                            struct_logger.log_trade_signal(
                                kod,
                                analiz_sonucu.get('sinyal'),
                                analiz_sonucu
                            )

                    if analiz_sonucu.get('uyari'):
                        uyarilar.append({
                            'kod': kod,
                            'mesaj': analiz_sonucu.get('uyari'),
                        })

                except Exception as e:
                    logger.error(f"HATA {kod}: {str(e)}")
                    struct_logger.log_error_detail(
                        'ANALYSIS_ERROR',
                        str(e),
                        {'kod': kod}
                    )
                    continue

            # En yuksek skordan baslayarak sirala
            tarama_gecenler.sort(key=lambda x: x.get('skor', 0), reverse=True)

            sonuc = {
                'index': index,
                'tarama_zamani': datetime.now(pytz.timezone(TIMEZONE)).isoformat(),
                'toplam': len(hisseler),
                'tarama_gecen': len(tarama_gecenler),
                'uyari_sayisi': len(uyarilar),
                'basari_orani': int(len(tarama_gecenler) / len(hisseler) * 100) if hisseler else 0,
                'hisseler': tarama_gecenler[:10],
                'uyarilar': uyarilar[:5],
            }

            # Istatistik kaydet
            tarih = datetime.now(pytz.timezone(TIMEZONE)).strftime('%Y-%m-%d')
            self.db.tarama_istatistigi_kayret(tarih, {
                'toplam': len(hisseler),
                'gecen': len(tarama_gecenler),
                'oran': sonuc['basari_orani'],
                'ortalama_skor': sum([h.get('skor', 0) for h in tarama_gecenler]) / len(tarama_gecenler) if tarama_gecenler else 0
            })

            self.tarama_sonuclari = sonuc
            self.son_tarama_zamani = datetime.now(pytz.timezone(TIMEZONE))

            # Performance log
            duration = perf_tracker.end_timer('tara')
            struct_logger.log_scan_result(len(hisseler), len(tarama_gecenler), sonuc['basari_orani'])

            logger.info(f"Tarama Bitti: {len(tarama_gecenler)}/{len(hisseler)} gecti ({duration:.2f}s)")

            return sonuc

        finally:
            # Lock'u birak
            with self.scan_lock:
                self.is_scanning = False

    def bildir_tarama_sonuclari(self, sonuclar: Dict):
        """Tarama Sonuclarina Telegram + Email'de Bildir"""

        logger.info("Telegram + Email Bildirimi Gonderiliyor...")

        tr_time = datetime.now(pytz.timezone(TIMEZONE)).strftime('%H:%M:%S')

        mesaj = f"""
BIST TARAMA SONUCLARI
Saat: {tr_time}

OZET:
Taramasi Yapilan: {sonuclar['toplam']}
Tarama Gecen: {sonuclar['tarama_gecen']}
Basari Orani: {sonuclar['basari_orani']}%

KARAR SURESI: 09:50 - 10:00 (10 DAKIKA)
"""

        if sonuclar['hisseler']:
            mesaj += "\nTARAMA GECEN HISSELER (En Iyi 5):\n\n"

            for i, h in enumerate(sonuclar['hisseler'][:5], 1):
                kod = h['kod']
                skor = h['skor']
                fiyat = h.get('fiyat', 0)
                sinyal = h.get('sinyal', 'UNKNOWN')

                mesaj += f"{i}. {kod} ({sinyal})\n"
                mesaj += f"   Fiyat: {fiyat:.2f} TL | Skor: {skor}%\n\n"

        else:
            mesaj += "\nUYARI: Tarama gecen hisse yok\n"

        mesaj += "\n" + "="*50 + "\n"
        mesaj += "MANUEL KARAR VER!\n"
        mesaj += "10:00'DA BIST ACILIYOR\n"
        mesaj += "BOT: SINYAL VERIR, SEN ISLEM YAPARSSIN\n"
        mesaj += "="*50 + "\n"

        try:
            self.notifier.send_message_sync(mesaj)
            logger.info("Telegram Bildirimi Gonderildi")
        except Exception as e:
            logger.error(f"Telegram Hatasi: {str(e)}")
            struct_logger.log_error_detail('TELEGRAM_ERROR', str(e))

        try:
            self.email_notifier.bildir_tarama_sonucu(sonuclar)
            logger.info("Email Bildirimi Gonderildi")
        except Exception as e:
            logger.error(f"Email Hatasi: {str(e)}")
            struct_logger.log_error_detail('EMAIL_ERROR', str(e))

    def setup_scheduler(self):
        """Scheduler'i Kur - Pazartesi-Cuma 09:10 Tarama + 18:00 Kapanisi"""

        # 09:10 Tarama Job'i
        self.scheduler.add_job(
            self.cron_tarama,
            trigger=CronTrigger(
                hour=9,
                minute=10,
                day_of_week='0-4',
                timezone=TIMEZONE
            ),
            id='daily_screen',
            name='09:10 Gunluk Tarama'
        )

        # 18:00 Gunun Sonu Kapanmasi
        self.scheduler.add_job(
            self.kapan_gunun_sonu,
            trigger=CronTrigger(
                hour=18,
                minute=0,
                day_of_week='0-4',
                timezone=TIMEZONE
            ),
            id='daily_shutdown',
            name='18:00 Gunun Sonu Kapanmasi'
        )

        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler Basladi (09:10 Tarama + 18:00 Kapanisi)")

    def cron_tarama(self):
        """Cron Taramasi (Scheduler tarafindan cagirilir)"""
        logger.info("Scheduled Tarama Tetiklendi")
        try:
            sonuclar = self.tara()
            self.bildir_tarama_sonuclari(sonuclar)
        except Exception as e:
            logger.error(f"Cron Tarama Hatasi: {str(e)}")
            self.email_notifier.bildir_hata(
                f"Scheduled tarama baslarisildi: {str(e)}",
                str(e)
            )

    def kapan_gunun_sonu(self):
        """18:00 Gunun Sonu Kapanmasi - Acik Pozisyonlari Kontrol Et"""
        logger.info("18:00 Gunun Sonu - Pozisyon Kontrol")
        
        try:
            # Acik pozisyonlari getir
            sinyaller = self.db.acik_sinyaller_getir()
            acik_pozisyon_sayisi = len(list(sinyaller)) if sinyaller else 0
            
            if acik_pozisyon_sayisi > 0:
                logger.warning(f"UYARI: {acik_pozisyon_sayisi} Acik Pozisyon Kaldi!")
                
                # Email ile uyar
                self.email_notifier.bildir_hata(
                    "GUNUN SONU - Acik Pozisyonlar",
                    f"UYARI: {acik_pozisyon_sayisi} pozisyon acik!\n\nLutfen broker'da manuel olarak TUM POZISYONLARI KAPAYIN!\n\n18:00'den sonra islem yapilamaz."
                )
                
                # Telegram da uyar
                try:
                    kapan_mesaj = f"""
GUNUN SONU - 18:00

UYARI ACIK POZISYON VAR: {acik_pozisyon_sayisi}

LUTFEN:
1. Broker uygulamasini ac
2. TUM POZISYONLARI KAPAT
3. Islem bitirmeden sakin!

18:00'den sonra islem yapilamaz!
"""
                    self.notifier.send_message_sync(kapan_mesaj)
                except:
                    pass
            else:
                logger.info("Gunun Sonu - Tum Pozisyonlar Kapali")
            
            # Log dosyasina kaydet
            struct_logger.log_event('DAILY_SHUTDOWN', {
                'acik_pozisyon': acik_pozisyon_sayisi,
                'saat': datetime.now(pytz.timezone(TIMEZONE)).isoformat()
            })
            
            logger.info("Gunun Sonu Islemi Tamamlandi")
            
        except Exception as e:
            logger.error(f"Gunun Sonu Hatasi: {str(e)}")
            self.email_notifier.bildir_hata(
                "Gunun Sonu Hata",
                str(e)
            )

    def manuel_tarama(self, user_id: str = None) -> Dict:
        """Suan Manuel Tarama Yap (Rate Limited)"""

        logger.info(f"Manuel Tarama Tetiklendi (User: {user_id})")
        
        # Rate limiting
        if user_id:
            if not self.rate_limiter.is_allowed(user_id):
                logger.warning(f"Rate limit exceeded: {user_id}")
                return {
                    'hata': 'Cok fazla istek (5 istek/dakika siniri)',
                    'toplam': 0,
                    'tarama_gecen': 0
                }

        try:
            sonuclar = self.tara()
            self.bildir_tarama_sonuclari(sonuclar)
            return sonuclar
        except Exception as e:
            logger.error(f"Manuel Tarama Hatasi: {str(e)}")
            self.email_notifier.bildir_hata(
                f"Manuel tarama baslarisildi: {str(e)}",
                str(e)
            )
            return {'hata': str(e)}

    def baslat(self):
        """Bot'u Baslat"""
        logger.info("Bot Baslaniyor...")
        self.setup_scheduler()
        logger.info("Bot Hazir ve Calisyor")

    def durdur(self):
        """Bot'u Durdur"""
        logger.info("Bot Durduruluyor...")
        if self.scheduler.running:
            self.scheduler.shutdown()
        logger.info("Bot Durduruldu")

# ============================================================================
# FLASK APP
# ============================================================================

app = Flask(__name__)
bot = BISTBot()

app.config['JSON_SORT_KEYS'] = False

@app.route('/health', methods=['GET'])
def health():
    """Saglik Kontrolu"""
    turkey_time = datetime.now(pytz.timezone(TIMEZONE)).strftime('%H:%M:%S')
    return jsonify({
        'status': 'healthy',
        'bot_status': 'calisyor',
        'is_scanning': bot.is_scanning,
        'turkey_time': turkey_time,
        'tarama_saati': '09:10 (Pazartesi-Cuma)',
        'kapanma_saati': '18:00',
        'bist_acilis': '10:00',
        'bist_kapanisa': '18:00',
        'mode': 'SIGNAL (Manual Trading)',
        'database': 'SQLite OK',
        'email': 'Enabled',
        'logging': 'Advanced',
        'rate_limiting': 'Enabled',
        'timeout': f'{bot.tarama_timeout}s'
    }), 200

@app.route('/durum', methods=['GET'])
def durum_endpoint():
    """Bot Durumu"""

    return jsonify({
        'status': 'success',
        'bot': {
            'durum': 'Calisyor',
            'tarama_saati': '09:10',
            'kapanma_saati': '18:00',
            'bist_acilis': '10:00',
            'bist_kapanisa': '18:00',
            'timezone': TIMEZONE,
            'is_scanning': bot.is_scanning,
            'son_tarama': bot.son_tarama_zamani.isoformat() if bot.son_tarama_zamani else 'Henuz tarama yok',
            'tarama_sonuclari': len(bot.tarama_sonuclari),
            'database': 'SQLite OK',
            'email_notifier': 'Enabled',
            'logging': 'Advanced',
            'rate_limiting': 'Enabled',
            'timeout': f'{bot.tarama_timeout}s'
        }
    }), 200

@app.route('/sonuc', methods=['GET'])
def sonuc_endpoint():
    """Son Tarama Sonuclari"""

    if not bot.tarama_sonuclari:
        return jsonify({'error': 'Henuz tarama yapilmamis'}), 404

    return jsonify({
        'status': 'success',
        'data': bot.tarama_sonuclari
    }), 200

@app.route('/tara', methods=['POST'])
def tara_endpoint():
    """Manuel Tarama Endpoint (Rate Limited)"""

    try:
        user_id = request.json.get('user_id') if request.json else None

        if user_id and user_id not in ALLOWED_USERS:
            logger.warning(f"Yetkilsiz Tarama Istegi: {user_id}")
            return jsonify({'error': 'Yetkiniz yok'}), 403

        logger.info(f"Manuel Tarama Istegi (User: {user_id})")

        sonuclar = bot.manuel_tarama(user_id)

        return jsonify({
            'status': 'success',
            'data': sonuclar
        }), 200

    except Exception as e:
        logger.error(f"Tarama Hatasi: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/hisse/<kod>', methods=['GET'])
def get_hisse_endpoint(kod):
    """Tek Hisse Analizi"""

    try:
        veri = bot.fetcher.get_bist_verisi(kod.upper())

        if not veri:
            return jsonify({'error': f'{kod} Bulunamadi'}), 404

        analiz = bot.analyzer.analiz_hisse(veri)

        return jsonify({
            'status': 'success',
            'data': analiz
        }), 200

    except Exception as e:
        logger.error(f"Hisse Analizi Hatasi ({kod}): {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/acik-sinyaller', methods=['GET'])
def acik_sinyaller_endpoint():
    """Acik Sinyalleri Getir"""

    try:
        sinyaller = bot.db.acik_sinyaller_getir()

        return jsonify({
            'status': 'success',
            'data': [dict(s) for s in sinyaller]
        }), 200

    except Exception as e:
        logger.error(f"Sinyal Getirme Hatasi: {str(e)}")
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
        logger.error(f"Performans Getirme Hatasi: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint Bulunamadi'}), 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server Hatasi: {str(error)}")
    return jsonify({'error': 'Sunucu Hatasi'}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    try:
        bot.baslat()

        port = int(os.environ.get('PORT', 8080))

        logger.info("="*60)
        logger.info(f"Flask App {port} Portunda Baslaniyor...")
        logger.info(f"Tarama: 09:10 (Pazartesi-Cuma)")
        logger.info(f"Kapanisi: 18:00 (Gunun Sonu)")
        logger.info(f"BIST: 10:00-18:00 (Trading Saati)")
        logger.info(f"Mode: SINYAL + TELEGRAM + EMAIL + DATABASE")
        logger.info(f"Logging: Advanced (logs/ klasoru)")
        logger.info(f"Thread Safety: Enabled (Lock + Rate Limit)")
        logger.info(f"Timeout: {bot.tarama_timeout}s")
        logger.info("="*60)

        # FİXED: timeout parametresi kaldırıldı
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            threaded=True
        )

    except KeyboardInterrupt:
        logger.info("Bot kapatiliyor...")
        bot.durdur()

    except Exception as e:
        logger.error(f"HATA: {str(e)}")
        bot.durdur()
