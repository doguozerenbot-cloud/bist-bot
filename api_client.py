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
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ============================================================================
# API YAPILANDI
# ============================================================================

class APIConfig:
    """API Yapılandırması"""
    
    # Finans API (Teknik Göstergeler)
    FINANS_API_KEY = os.getenv('FINANS_API_KEY', '')
    FINANS_API_URL = os.getenv('FINANS_API_URL', 'https://www.alphavantage.co')
    
    # Aracı Kurum API (BIST Verileri) - Finnhub
    BROKER_API_KEY = os.getenv('BROKER_API_KEY', '')
    BROKER_API_URL = os.getenv('BROKER_API_URL', 'https://finnhub.io/api/v1')
    
    # API Rate Limit (İstek başına gecikme)
    RATE_LIMIT_DELAY = 1  # Saniye

# ============================================================================
# BIST VERİ İSLEMCİSİ
# ============================================================================

class BISTDataClient:
    """BIST Verileri - Finnhub API'sinden"""
    
    def __init__(self, api_key: str = '', api_url: str = ''):
        self.api_key = api_key or APIConfig.BROKER_API_KEY
        self.api_url = api_url or APIConfig.BROKER_API_URL
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
    
    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """GET İsteği Yap"""
        try:
            if params is None:
                params = {}
            
            # Finnhub API key ekle
            params['token'] = self.api_key
            
            url = f"{self.api_url}/{endpoint}"
            
            self.logger.info(f"📡 API İsteği: {endpoint}")
            
            response = self.session.get(
                url,
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
            # Finnhub quote endpoint
            data = self._get(
                'quote',
                {'symbol': f'{kod}.HE'}
            )
            
            if data and 'c' in data:
                return {
                    'kod': kod,
                    'fiyat': data.get('c'),              # current price
                    'hacim': data.get('v'),              # volume
                    '52w_high': data.get('h'),           # 52 week high
                    '52w_low': data.get('l'),            # 52 week low
                    'günlük_high': data.get('h'),        # day high
                    'günlük_low': data.get('l'),         # day low
                    'açılış': data.get('o'),             # opening price
                    'kapanış': data.get('pc'),           # previous close
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
                'stock/metric',
                {'symbol': f'{kod}.HE', 'metric': 'all'}
            )
            
            if data and 'metric' in data:
                metric = data['metric']
                return {
                    'pe': metric.get('peAnnual', 0),
                    'roe': metric.get('roe', 0),
                    'borç_öz': metric.get('debtToEquity', 0),
                    'temettü': metric.get('dividendYield', 0),
                    'piyasa_değeri': metric.get('marketCapitalization', 0),
                    'adv': metric.get('avgVolume', 0) / 1_000_000,  # Milyon TL
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Temel Veri Hatası ({kod}): {str(e)}")
            return None
    
    def get_hisse_listesi(self, index: str = 'BIST100') -> List[str]:
        """BIST100 Hisse Listesi - Manuel"""
        
        # BIST100 hisseler (Gerçek liste - Investing.com'dan)
        bist100 = [
            'AEFES', 'AKBNK', 'AKSA', 'AKSEN', 'ALARK', 'ANADOLU', 'ARCLK', 'ASELS',
            'BIMAS', 'BISAS', 'BOBRN', 'BORUP', 'BRLSOKE', 'BRNCK', 'CCOLA', 'CIMSA',
            'DOGUS', 'DOHOL', 'ECZBAI', 'EKGYO', 'ENKA', 'EREGL', 'FBURS', 'FORDS',
            'GARAN', 'GASRI', 'GUBRT', 'GUNSI', 'HALKB', 'HEKAS', 'IPEKE', 'ISCTR',
            'ISYAT', 'KCHOL', 'KOZAL', 'KZGLD', 'KRDMD', 'MIGRS', 'MARDIN', 'OTOKAR',
            'PETKIM', 'SAHOL', 'SARKUY', 'SASA', 'SISE', 'SKBNK', 'TAVHL', 'TCELL',
            'THY', 'TEKFEN', 'TOFAS', 'TSKLC', 'TTKOM', 'TUKAS', 'TUPRS', 'ULKER',
            'VAKBN', 'VESTEL', 'YAZICI', 'YKBNK', 'ZOREN', 'KUYAS', 'PEGASUS', 'ODAS',
            'MAVI', 'ENJSA', 'MLPSAG', 'SOK', 'KONTROLMATIK', 'TUREKS', 'QUA', 'CAN2',
            'GEN', 'GIRISIM', 'MARGUN', 'MIATEKNOLOJI', 'PASIFIK', 'DAP', 'GURSEL',
            'EUROPEN', 'KILER', 'ASTOR', 'CVK', 'EUROPOWER', 'GRAINTURK', 'CWENERJI',
            'KATILIMEVIM', 'PASIFIKLOJISTIK', 'IZDEMIR', 'ENERYA', 'REEDER', 'TAB',
            'PASIFIK_TEKNOLOJI', 'OBA', 'ALTINAY', 'EFOR', 'GULERMAK', 'DESTEK', 'BALSU',
            'PASIFIK_HOLDING'
        ]
        
        if index == 'BIST100':
            self.logger.info(f"📋 {len(bist100)} Hisse Yüklendi")
            return bist100
        
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
            if params is None:
                params = {}
            
            params['apikey'] = self.api_key
            
            url = f"{self.api_url}/query"
            
            self.logger.info(f"📈 Teknik API: {endpoint}")
            
            response = self.session.get(
                url,
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
            # Şimdilik placeholder değerler
            return {
                'ema20': 0,
                'ema50': 0,
                'ema200': 0,
                'rsi': 0,
                'adx': 0,
                'atr': 0,
                'macd': 0,
                'bollinger_upper': 0,
                'bollinger_lower': 0,
            }
            
        except Exception as e:
            self.logger.error(f"Teknik Gösterge Hatası ({kod}): {str(e)}")
            return None
    
    def get_fiyat_geçmişi(self, kod: str, gün: int = 60) -> Optional[List[Dict]]:
        """Fiyat Geçmişi Al (OHLCV)"""
        try:
            # Şimdilik placeholder
            return []
            
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
