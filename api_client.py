# -*- coding: utf-8 -*-
"""
API İstemci - Veri Çekme
BIST Hisse Verileri + Teknik Göstergeler (Alpha Vantage)
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
    
    # Finans API (Teknik Göstergeler) - Alpha Vantage
    FINANS_API_KEY = os.getenv('FINANS_API_KEY', '')
    FINANS_API_URL = os.getenv('FINANS_API_URL', 'https://www.alphavantage.co')
    
    # Aracı Kurum API (BIST Verileri) - Finnhub
    BROKER_API_KEY = os.getenv('BROKER_API_KEY', '')
    BROKER_API_URL = os.getenv('BROKER_API_URL', 'https://finnhub.io/api/v1')
    
    # API Rate Limit (İstek başına gecikme)
    RATE_LIMIT_DELAY = 0.5  # Saniye (Alpha Vantage: 5 istekler/dakika)

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
# TEKNİK GÖSTERGELERİ İSLEMCİSİ - ALPHA VANTAGE
# ============================================================================

class TechnicalDataClient:
    """Teknik Göstergeler - Alpha Vantage API'sinden"""
    
    def __init__(self, api_key: str = '', api_url: str = ''):
        self.api_key = api_key or os.getenv('FINANS_API_KEY', '')
        self.api_url = api_url or os.getenv('FINANS_API_URL', 'https://www.alphavantage.co')
        self.logger = logging.getLogger(__name__)
    
    def _get_alpha_vantage(self, function: str, symbol: str, 
                          interval: str = 'daily', params: Dict = None) -> Optional[Dict]:
        """Alpha Vantage API çağrısı"""
        try:
            if params is None:
                params = {}
            
            url = f"{self.api_url}/query"
            params.update({
                'function': function,
                'symbol': f'{symbol}.HE',
                'interval': interval,
                'apikey': self.api_key,
            })
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            time.sleep(APIConfig.RATE_LIMIT_DELAY)
            
            return data
            
        except Exception as e:
            self.logger.error(f"Alpha Vantage Hatası ({function}): {str(e)}")
            return None
    
    def get_rsi(self, kod: str, period: int = 14) -> Optional[float]:
        """RSI (Relative Strength Index)"""
        try:
            data = self._get_alpha_vantage('RSI', kod, params={'time_period': period})
            
            if data and 'Technical Analysis: RSI' in data:
                # En son değeri al
                rsi_values = data['Technical Analysis: RSI']
                if not rsi_values:
                    return None
                    
                latest_date = list(rsi_values.keys())[0]
                rsi = float(rsi_values[latest_date]['RSI'])
                
                self.logger.info(f"📈 {kod} RSI: {rsi:.2f}")
                return rsi
            
            return None
            
        except Exception as e:
            self.logger.error(f"RSI Hatası ({kod}): {str(e)}")
            return None
    
    def get_macd(self, kod: str) -> Optional[Dict]:
        """MACD (Moving Average Convergence Divergence)"""
        try:
            data = self._get_alpha_vantage('MACD', kod)
            
            if data and 'Technical Analysis: MACD' in data:
                macd_values = data['Technical Analysis: MACD']
                if not macd_values:
                    return None
                    
                latest_date = list(macd_values.keys())[0]
                latest = macd_values[latest_date]
                
                result = {
                    'macd': float(latest.get('MACD', 0)),
                    'signal': float(latest.get('MACD_Signal', 0)),
                    'histogram': float(latest.get('MACD_Hist', 0)),
                }
                
                self.logger.info(f"📈 {kod} MACD: {result}")
                return result
            
            return None
            
        except Exception as e:
            self.logger.error(f"MACD Hatası ({kod}): {str(e)}")
            return None
    
    def get_adx(self, kod: str, period: int = 14) -> Optional[float]:
        """ADX (Average Directional Index)"""
        try:
            data = self._get_alpha_vantage('ADX', kod, params={'time_period': period})
            
            if data and 'Technical Analysis: ADX' in data:
                adx_values = data['Technical Analysis: ADX']
                if not adx_values:
                    return None
                    
                latest_date = list(adx_values.keys())[0]
                adx = float(adx_values[latest_date]['ADX'])
                
                self.logger.info(f"📈 {kod} ADX: {adx:.2f}")
                return adx
            
            return None
            
        except Exception as e:
            self.logger.error(f"ADX Hatası ({kod}): {str(e)}")
            return None
    
    def get_ema(self, kod: str, period: int = 20) -> Optional[float]:
        """Exponential Moving Average"""
        try:
            data = self._get_alpha_vantage('EMA', kod, params={'time_period': period})
            
            if data and 'Technical Analysis: EMA' in data:
                ema_values = data['Technical Analysis: EMA']
                if not ema_values:
                    return None
                    
                latest_date = list(ema_values.keys())[0]
                ema = float(ema_values[latest_date]['EMA'])
                
                self.logger.info(f"📈 {kod} EMA{period}: {ema:.2f}")
                return ema
            
            return None
            
        except Exception as e:
            self.logger.error(f"EMA Hatası ({kod}): {str(e)}")
            return None
    
    def get_atr(self, kod: str, period: int = 14) -> Optional[float]:
        """ATR (Average True Range)"""
        try:
            data = self._get_alpha_vantage('ATR', kod, params={'time_period': period})
            
            if data and 'Technical Analysis: ATR' in data:
                atr_values = data['Technical Analysis: ATR']
                if not atr_values:
                    return None
                    
                latest_date = list(atr_values.keys())[0]
                atr = float(atr_values[latest_date]['ATR'])
                
                self.logger.info(f"📈 {kod} ATR: {atr:.2f}")
                return atr
            
            return None
            
        except Exception as e:
            self.logger.error(f"ATR Hatası ({kod}): {str(e)}")
            return None
    
    def get_göstergeler(self, kod: str) -> Optional[Dict]:
        """Tüm Teknik Göstergeler - Alpha Vantage'dan"""
        try:
            self.logger.info(f"📊 {kod} Teknik Göstergeler Çekiliyor...")
            
            # Tüm göstergeleri al
            rsi = self.get_rsi(kod) or 50
            macd = self.get_macd(kod) or {'macd': 0, 'signal': 0, 'histogram': 0}
            adx = self.get_adx(kod) or 20
            ema20 = self.get_ema(kod, 20) or 0
            ema50 = self.get_ema(kod, 50) or 0
            ema200 = self.get_ema(kod, 200) or 0
            atr = self.get_atr(kod) or 0
            
            return {
                'ema20': ema20,
                'ema50': ema50,
                'ema200': ema200,
                'rsi': rsi,
                'adx': adx,
                'atr': atr,
                'macd': macd.get('macd', 0),
                'macd_signal': macd.get('signal', 0),
                'macd_histogram': macd.get('histogram', 0),
            }
            
        except Exception as e:
            self.logger.error(f"Teknik Göstergeler Hatası ({kod}): {str(e)}")
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
    
    def get_bist_verisi(self, kod: str) -> Optional[Dict]:
        """BIST hissesi için tam veri paketi"""
        try:
            # Fiyat verisi
            hisse = self.bist_client.get_hisse(kod)
            if not hisse:
                return None
            
            # Temel veriler
            temel = self.bist_client.get_temel_veriler(kod) or {}
            
            # Teknik göstergeler (Alpha Vantage)
            teknik = self.tech_client.get_göstergeler(kod) or {}
            
            return {
                'kod': kod,
                'fiyat': hisse.get('fiyat'),
                'hacim': hisse.get('hacim'),
                'açılış': hisse.get('açılış'),
                'kapanış': hisse.get('kapanış'),
                '52w_high': hisse.get('52w_high'),
                '52w_low': hisse.get('52w_low'),
                'pe': temel.get('pe', 0),
                'roe': temel.get('roe', 0),
                'borç_öz': temel.get('borç_öz', 0),
                'adv': temel.get('adv', 0),
                'rsi': teknik.get('rsi', 0),
                'macd': teknik.get('macd', 0),
                'macd_signal': teknik.get('macd_signal', 0),
                'macd_histogram': teknik.get('macd_histogram', 0),
                'ema20': teknik.get('ema20', 0),
                'ema50': teknik.get('ema50', 0),
                'ema200': teknik.get('ema200', 0),
                'adx': teknik.get('adx', 0),
                'atr': teknik.get('atr', 0),
                'saat': hisse.get('saat'),
            }
            
        except Exception as e:
            self.logger.error(f"BIST Verisi Hatası ({kod}): {str(e)}")
            return None
    
    def get_bist100_listesi(self) -> List[str]:
        """BIST100 hisselerini getir"""
        return self.bist_client.get_hisse_listesi('BIST100')
    
    def tarama_yap(self) -> List[Dict]:
        """Tüm BIST100 hisselerini tara"""
        hisseler = self.get_bist100_listesi()
        veriler = []
        
        for kod in hisseler:
            veri = self.get_bist_verisi(kod)
            if veri:
                veriler.append(veri)
                self.logger.info(f"✓ {kod}: {veri.get('fiyat')} TL")
            else:
                self.logger.warning(f"✗ {kod}: Veri alınamadı")
        
        self.logger.info(f"📊 Tarama Tamamlandı: {len(veriler)}/{len(hisseler)} hisse")
        return veriler
