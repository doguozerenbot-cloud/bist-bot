# -*- coding: utf-8 -*-
"""
Veritabanı - SQLite
Sinyal, Hisse, Performance Takip
"""
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import os

logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE CONFIG
# ============================================================================

DB_PATH = os.getenv('DB_PATH', 'bist_bot.db')

# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    """SQLite Veritabanı Yöneticisi"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.init_db()
    
    def get_connection(self):
        """Veritabanı Bağlantısı Al"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            self.logger.error(f"❌ Veritabanı Bağlantı Hatası: {str(e)}")
            return None
    
    def init_db(self):
        """Veritabanını Başlat"""
        try:
            conn = self.get_connection()
            if not conn:
                return
            
            cursor = conn.cursor()
            
            # Hisseler Tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hisseler (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kod TEXT UNIQUE NOT NULL,
                    ad TEXT,
                    sektor TEXT,
                    piyasa_degeri REAL,
                    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    guncelleme TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tarama Sonuçları Tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tarama_sonuclari (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kod TEXT NOT NULL,
                    fiyat REAL,
                    sinyal TEXT,
                    skor INTEGER,
                    rsi REAL,
                    macd REAL,
                    adx REAL,
                    ema20 REAL,
                    ema50 REAL,
                    pe REAL,
                    roe REAL,
                    aciklama TEXT,
                    uyari TEXT,
                    tarama_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (kod) REFERENCES hisseler(kod)
                )
            ''')
            
            # Sinyaller Tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sinyaller (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kod TEXT NOT NULL,
                    sinyal_tipi TEXT,
                    fiyat_sinyali REAL,
                    skor INTEGER,
                    giriş_notu TEXT,
                    stop_loss REAL,
                    target_1 REAL,
                    target_2 REAL,
                    risk_reward REAL,
                    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    durum TEXT DEFAULT 'AÇIK',
                    FOREIGN KEY (kod) REFERENCES hisseler(kod)
                )
            ''')
            
            # İşlemler Tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS islemler (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kod TEXT NOT NULL,
                    islem_tipi TEXT,
                    fiyat REAL,
                    miktar INTEGER,
                    toplam REAL,
                    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notlar TEXT,
                    FOREIGN KEY (kod) REFERENCES hisseler(kod)
                )
            ''')
            
            # Performans Tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    toplam_sinyaller INTEGER DEFAULT 0,
                    basarili_sinyaller INTEGER DEFAULT 0,
                    basarisiz_sinyaller INTEGER DEFAULT 0,
                    basar_orani REAL DEFAULT 0,
                    toplam_kar_zarar REAL DEFAULT 0,
                    max_kazanc REAL DEFAULT 0,
                    max_zarar REAL DEFAULT 0,
                    risk_reward_oranı REAL DEFAULT 0,
                    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    guncelleme TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tarama İstatistikleri Tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tarama_istatistikleri (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tarama_tarihi DATE UNIQUE,
                    toplam_hisse INTEGER,
                    tarama_gecen INTEGER,
                    basari_orani REAL,
                    ortalama_skor REAL,
                    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
            self.logger.info("✅ Veritabanı Başlatıldı")
        
        except Exception as e:
            self.logger.error(f"❌ Veritabanı Başlatma Hatası: {str(e)}")
    
    # ========================================================================
    # HISSE İŞLEMLERİ
    # ========================================================================
    
    def hisse_kaydet(self, kod: str, ad: str = '', sektor: str = '', 
                    piyasa_degeri: float = 0) -> bool:
        """Hisse Kaydet"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
            
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO hisseler 
                (kod, ad, sektor, piyasa_degeri, guncelleme)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (kod, ad, sektor, piyasa_degeri))
            
            conn.commit()
            conn.close()
            return True
        
        except Exception as e:
            self.logger.error(f"❌ Hisse Kayıt Hatası ({kod}): {str(e)}")
            return False
    
    def hisse_getir(self, kod: str) -> Optional[Dict]:
        """Hisse Getir"""
        try:
            conn = self.get_connection()
            if not conn:
                return None
            
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM hisseler WHERE kod = ?', (kod,))
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None
        
        except Exception as e:
            self.logger.error(f"❌ Hisse Getirme Hatası ({kod}): {str(e)}")
            return None
    
    # ========================================================================
    # TARAMA SONUCU İŞLEMLERİ
    # ========================================================================
    
    def tarama_kaydet(self, kod: str, veri: Dict) -> bool:
        """Tarama Sonucunu Kaydet"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
            
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tarama_sonuclari
                (kod, fiyat, sinyal, skor, rsi, macd, adx, ema20, ema50, pe, roe, aciklama, uyari)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                kod,
                veri.get('fiyat'),
                veri.get('sinyal'),
                veri.get('skor'),
                veri.get('rsi'),
                veri.get('macd'),
                veri.get('adx'),
                veri.get('ema20'),
                veri.get('ema50'),
                veri.get('pe'),
                veri.get('roe'),
                veri.get('açıklama'),
                veri.get('uyarı')
            ))
            
            conn.commit()
            conn.close()
            return True
        
        except Exception as e:
            self.logger.error(f"❌ Tarama Kayıt Hatası ({kod}): {str(e)}")
            return False
    
    def tarama_getir(self, kod: str, gun: int = 1) -> List[Dict]:
        """Son N günün tarama sonuçlarını getir"""
        try:
            conn = self.get_connection()
            if not conn:
                return []
            
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM tarama_sonuclari 
                WHERE kod = ? AND tarih >= date('now', '-' || ? || ' days')
                ORDER BY tarih DESC
            ''', (kod, gun))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        
        except Exception as e:
            self.logger.error(f"❌ Tarama Getirme Hatası ({kod}): {str(e)}")
            return []
    
    # ========================================================================
    # SİNYAL İŞLEMLERİ
    # ========================================================================
    
    def sinyal_kaydet(self, kod: str, sinyal_data: Dict) -> bool:
        """Sinyal Kaydet"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
            
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sinyaller
                (kod, sinyal_tipi, fiyat_sinyali, skor, giriş_notu, stop_loss, 
                 target_1, target_2, risk_reward, durum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                kod,
                sinyal_data.get('sinyal'),
                sinyal_data.get('fiyat'),
                sinyal_data.get('skor'),
                sinyal_data.get('giriş'),
                sinyal_data.get('sl'),
                sinyal_data.get('t1'),
                sinyal_data.get('t2'),
                sinyal_data.get('rr'),
                'AÇIK'
            ))
            
            conn.commit()
            conn.close()
            self.logger.info(f"✓ Sinyal Kaydedildi: {kod}")
            return True
        
        except Exception as e:
            self.logger.error(f"❌ Sinyal Kayıt Hatası ({kod}): {str(e)}")
            return False
    
    def acik_sinyaller_getir(self) -> List[Dict]:
        """Açık Sinyalleri Getir"""
        try:
            conn = self.get_connection()
            if not conn:
                return []
            
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM sinyaller 
                WHERE durum = 'AÇIK'
                ORDER BY tarih DESC
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        
        except Exception as e:
            self.logger.error(f"❌ Sinyal Getirme Hatası: {str(e)}")
            return []
    
    # ========================================================================
    # PERFORMANS İŞLEMLERİ
    # ========================================================================
    
    def performans_guncelle(self, performans_data: Dict) -> bool:
        """Performans Güncelle"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
            
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE performans SET
                toplam_sinyaller = ?,
                basarili_sinyaller = ?,
                basarisiz_sinyaller = ?,
                basar_orani = ?,
                toplam_kar_zarar = ?,
                max_kazanc = ?,
                max_zarar = ?,
                risk_reward_oranı = ?,
                guncelleme = CURRENT_TIMESTAMP
                WHERE id = 1
            ''', (
                performans_data.get('toplam_sinyaller', 0),
                performans_data.get('basarili', 0),
                performans_data.get('basarisiz', 0),
                performans_data.get('oran', 0),
                performans_data.get('kar_zarar', 0),
                performans_data.get('max_kazanc', 0),
                performans_data.get('max_zarar', 0),
                performans_data.get('rr', 0),
            ))
            
            conn.commit()
            conn.close()
            return True
        
        except Exception as e:
            self.logger.error(f"❌ Performans Güncelleme Hatası: {str(e)}")
            return False
    
    def performans_getir(self) -> Optional[Dict]:
        """Performans Getir"""
        try:
            conn = self.get_connection()
            if not conn:
                return None
            
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM performans WHERE id = 1')
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None
        
        except Exception as e:
            self.logger.error(f"❌ Performans Getirme Hatası: {str(e)}")
            return None
    
    # ========================================================================
    # İSTATİSTİK İŞLEMLERİ
    # ========================================================================
    
    def tarama_istatistigi_kaydet(self, tarih: str, istatistik: Dict) -> bool:
        """Tarama İstatistiğini Kaydet"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
            
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO tarama_istatistikleri
                (tarama_tarihi, toplam_hisse, tarama_gecen, basari_orani, ortalama_skor)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                tarih,
                istatistik.get('toplam', 0),
                istatistik.get('gecen', 0),
                istatistik.get('oran', 0),
                istatistik.get('ortalama_skor', 0)
            ))
            
            conn.commit()
            conn.close()
            return True
        
        except Exception as e:
            self.logger.error(f"❌ İstatistik Kayıt Hatası: {str(e)}")
            return False
