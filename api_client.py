# -*- coding: utf-8 -*-
"""
API İstemci - Veri Çekme
BIST Hisse Verileri + Teknik Göstergeler
"""
import logging
import requests
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

# ============================================================================
# API YAPILANDI
# ============================================================================

class APIConfig:
    """API Yapılandırması"""
    
    # Finans API (Teknik Göstergeler)
    FINANS_API_KEY = os.getenv('FINANS_API_KEY', '')  # Örn: Alpha Vantage, IEX Cloud
    FINANS_API_URL = os.getenv('FINANS_API_URL', 'https://api.example.com')
    
    # Aracı Kurum API (BIST Verileri)
    BROKER_API_KEY = os.getenv('BROKER_API_KEY', '')
    BROKER_API_URL = os.getenv('BROKER_API_URL', 'https://api.broker.com')
    
    # API Rate Limit (İstek başına gecikme)
    RATE_LIMIT_DELAY = 1  # Saniye

# ============================================================================
# BIST VERİ İSLEMCİSİ
# ============================================================================

class BISTDataClient:
    """BIST Verileri - Aracı Kurum API'sinden"""
    
    def __init__(self, api_key: str = '', api_url: str = ''):
        self.api_key = api_key or APIConfig.BROKER_API_KEY
        self.api_url = api_url or APIConfig.BROKER_API_URL
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
    
    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """GET İsteği Yap"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.api_url}/{endpoint}"
            
            self.logger.info(f"📡 API İsteği: {endpoint}")
            
            response = self.session.get(
                url,
                headers=headers,
                params=params,
                timeout=10
            )
            
            response.raise_for_status()
            
            time.sleep(APIConfig.RATE_LIMIT_DELAY)
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ API Hatası: {str(e)}")
            return {}
    
    def get_hisse(self, kod: str) -> Optional[Dict]:
        """Hisse Bilgisi Al"""
        try:
            data = self._get(
                'stocks/current',
                {'symbol': kod}
            )
            
            if data:
                return {
                    'kod': kod,
                    'fiyat': data.get('price'),
                    'hacim': data.get('volume'),
                    '52w_high': data.get('52_week_high'),
                    '52w_low': data.get('52_week_low'),
                    'günlük_high': data.get('day_high'),
                    'günlük_low': data.get('day_low'),
                    'açılış': data.get('open'),
                    'kapanış': data.get('close'),
                    'saat': datetime.now().isoformat(),
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Hisse Bilgisi Hatası ({kod}): {str(e)}")
            return None
    
    def get_temel_veriler(self, kod: str) -> Optional[Dict]:
        """Temel Veriler Al (P/E, ROE, vb.)"""
        try:
            data = self._get(
                'stocks/fundamentals',
                {'symbol': kod}
            )
            
            if data:
                return {
                    'pe': data.get('pe_ratio'),
                    'roe': data.get('roe'),
                    'borç_öz': data.get('debt_equity'),
                    'temettü': data.get('dividend_yield'),
                    'piyasa_değeri': data.get('market_cap'),
                    'adv': data.get('avg_volume') / 1_000_000,  # Milyon TL
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Temel Veri Hatası ({kod}): {str(e)}")
            return None
    
    def get_hisse_listesi(self, index: str = 'BIST100') -> List[str]:
        """Hisse Listesi Al"""
        try:
            data = self._get(
                'indices/components',
                {'index': index}
            )
            
            if data and 'symbols' in data:
                return data['symbols']
            
            return []
            
        except Exception as e:
            self.logger.error(f"Hisse Listesi Hatası: {str(e)}")
            return []

# ============================================================================
# TEKNİK GÖSTERGELERİ İSLEMCİSİ
# ============================================================================

class TechnicalDataClient:
    """Teknik Göstergeler - Finans API'sinden"""
    
    def __init__(self, api_key: str = '', api_url: str = ''):
        self.api_key = api_key or APIConfig.FINANS_API_KEY
        self.api_url = api_url or APIConfig.FINANS_API_URL
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
    
    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """GET İsteği Yap"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.api_url}/{endpoint}"
            
            self.logger.info(f"📈 Teknik API: {endpoint}")
            
            response = self.session.get(
                url,
                headers=headers,
                params=params,
                timeout=10
            )
            
            response.raise_for_status()
            
            time.sleep(APIConfig.RATE_LIMIT_DELAY)
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Teknik API Hatası: {str(e)}")
            return {}
    
    def get_göstergeler(self, kod: str, interval: str = 'daily') -> Optional[Dict]:
        """Teknik Göstergeler Al"""
        try:
            data = self._get(
                'technical/indicators',
                {
                    'symbol': kod,
                    'interval': interval
                }
            )
            
            if data:
                return {
                    'ema20': data.get('ema_20'),
                    'ema50': data.get('ema_50'),
                    'ema200': data.get('ema_200'),
                    'rsi': data.get('rsi'),
                    'adx': data.get('adx'),
                    'atr': data.get('atr'),
                    'macd': data.get('macd'),
                    'bollinger_upper': data.get('bollinger_upper'),
                    'bollinger_lower': data.get('bollinger_lower'),
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Teknik Gösterge Hatası ({kod}): {str(e)}")
            return None
    
    def get_fiyat_geçmişi(self, kod: str, gün: int = 60) -> Optional[List[Dict]]:
        """Fiyat Geçmişi Al (OHLCV)"""
        try:
            data = self._get(
                'historical/daily',
                {
                    'symbol': kod,
                    'days': gün
                }
            )
            
            if data and 'history' in data:
                return data['history']
            
            return None
            
        except Exception as e:
            self.logger.error(f"Fiyat Geçmişi Hatası ({kod}): {str(e)}")
            return None

# ============================================================================
# BİRLEŞTİRİLMİŞ VERİ İSLEMCİSİ
# ============================================================================

class DataFetcher:
    """Tüm Veri Kaynakları - Birleştirilmiş"""
    
    def __init__(self):
        self.bist_client = BISTDataClient()
        self.tech_client = TechnicalDataClient()
        self.logger = logging.getLogger(__name__)
    
    def get_hisse_analizi(self, kod: str) -> Optional[Dict]:
        """Hisse Tam Analiz Verisi"""
        try:
            self.logger.info(f"🔍 {kod} Verisi Çekiliyor...")
            
            # Hisse Fiyat Verileri
            hisse = self.bist_client.get_hisse(kod)
            if not hisse:
                self.logger.error(f"❌ {kod} hisse verisi alınamadı")
                return None
            
            # Temel Veriler
            temel = self.bist_client.get_temel_veriler(kod)
            if not temel:
                self.logger.warning(f"⚠️ {kod} temel veriler alınamadı - Değer 0")
                temel = {
                    'pe': 0,
                    'roe': 0,
                    'borç_öz': 0,
                    'temettü': 0,
                    'piyasa_değeri': 0,
                    'adv': 0,
                }
            
            # Teknik Göstergeler
            teknik = self.tech_client.get_göstergeler(kod)
            if not teknik:
                self.logger.warning(f"⚠️ {kod} teknik göstergeler alınamadı - Değer 0")
                teknik = {
                    'ema20': 0,
                    'ema50': 0,
                    'ema200': 0,
                    'rsi': 0,
                    'adx': 0,
                    'atr': 0,
                    'macd': 0,
                }
            
            # Birleştir
            veri = {
                **hisse,
                **temel,
                **teknik,
                'güncelleme_saati': datetime.now().isoformat(),
            }
            
            self.logger.info(f"✓ {kod} Verisi Başarıyla Çekildi")
            
            return veri
            
        except Exception as e:
            self.logger.error(f"❌ Hisse Analizi Hatası ({kod}): {str(e)}")
            return None
    
    def get_hisse_listesi_analiz(self, index: str = 'BIST100') -> List[Dict]:
        """Tüm Hisselerin Analizi"""
        
        self.logger.info(f"📊 {index} Taraması Başlıyor...")
        
        # Hisse Listesi Al
        hisseler = self.bist_client.get_hisse_listesi(index)
        
        if not hisseler:
            self.logger.error(f"❌ {index} Hisse Listesi Alınamadı")
            return []
        
        self.logger.info(f"📋 {len(hisseler)} Hisse Bulundu")
        
        # Her Hissenin Verisi
        sonuçlar = []
        
        for i, kod in enumerate(hisseler, 1):
            veri = self.get_hisse_analizi(kod)
            
            if veri:
                sonuçlar.append(veri)
            
            # Progress Log
            if i % 10 == 0:
                self.logger.info(f"İlerleme: {i}/{len(hisseler)} (%{int(i/len(hisseler)*100)})")
        
        self.logger.info(f"✓ {len(sonuçlar)}/{len(hisseler)} Hisse Analizi Tamamlandı")
        
        return sonuçlar

# ============================================================================
# ÖRNEK KULLANIM
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test
    fetcher = DataFetcher()
    
    # Tek hisse
    veri = fetcher.get_hisse_analizi('AKBNK')
    if veri:
        print(f"\n✓ {veri['kod']}")
        print(f"  Fiyat: {veri.get('fiyat')} TL")
        print(f"  P/E: {veri.get('pe')}")
        print(f"  RSI: {veri.get('rsi')}")

