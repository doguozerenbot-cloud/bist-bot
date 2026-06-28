# -*- coding: utf-8 -*-
"""
API İstemci - Veri Çekme
BIST Hisse Verileri + Teknik Göstergeler (Alpha Vantage)
FİXED: Retry, Caching, Rate Limiting, Circuit Breaker
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

    # API Rate Limit
    RATE_LIMIT_DELAY = 0.5  # Saniye
    
    # Retry ayarları
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # Saniye

# ============================================================================
# CIRCUIT BREAKER
# ============================================================================

class CircuitBreaker:
    """Circuit Breaker Pattern"""
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False
        self.logger = logging.getLogger(__name__)
    
    def record_success(self):
        self.failure_count = 0
        self.is_open = False
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            self.logger.warning(f"Circuit Breaker ACILDI ({self.failure_count} hata)")
    
    def can_execute(self) -> bool:
        if not self.is_open:
            return True
        
        if self.last_failure_time:
            elapsed = (datetime.now() - self.last_failure_time).total_seconds()
            if elapsed > self.reset_timeout:
                self.logger.info("Circuit Breaker KAPANDI")
                self.is_open = False
                self.failure_count = 0
                return True
        
        return False

# ============================================================================
# CACHE MANAGER
# ============================================================================

class CacheManager:
    """Basit Cache - 30 dakika tutma"""
    
    def __init__(self, timeout_minutes: int = 30):
        self.cache = {}
        self.timeout = timeout_minutes * 60
        self.logger = logging.getLogger(__name__)
    
    def get(self, key: str) -> Optional[Dict]:
        if key in self.cache:
            data, timestamp = self.cache[key]
            
            if (datetime.now() - timestamp).total_seconds() < self.timeout:
                self.logger.info(f"Cache HIT: {key}")
                return data
            else:
                del self.cache[key]
        
        return None
    
    def set(self, key: str, value: Dict):
        self.cache[key] = (value, datetime.now())
        self.logger.info(f"Cache SET: {key}")

# ============================================================================
# BIST VERİ İSLEMCİSİ
# ============================================================================

class BISTDataClient:
    """BIST Verileri - Finnhub API"""

    def __init__(self, api_key: str = '', api_url: str = ''):
        self.api_key = api_key or APIConfig.BROKER_API_KEY
        self.api_url = api_url or APIConfig.BROKER_API_URL
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
        self.circuit_breaker = CircuitBreaker()
        self.cache = CacheManager()
        
        if not self.api_key:
            self.logger.warning("BROKER_API_KEY bos!")

    def _get(self, endpoint: str, params: Dict = None, retry_count: int = 0) -> Dict:
        """GET Request with Retry"""
        
        if not self.circuit_breaker.can_execute():
            self.logger.error("Circuit Breaker ACIK")
            return {}
        
        try:
            if params is None:
                params = {}

            params['token'] = self.api_key
            url = f"{self.api_url}/{endpoint}"

            self.logger.info(f"API Request: {endpoint} (Attempt {retry_count + 1})")

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            time.sleep(APIConfig.RATE_LIMIT_DELAY)

            self.circuit_breaker.record_success()
            return response.json()

        except requests.exceptions.RequestException as e:
            self.circuit_breaker.record_failure()
            
            if retry_count < APIConfig.MAX_RETRIES:
                wait_time = APIConfig.RETRY_DELAY * (retry_count + 1)
                self.logger.warning(f"Retry {retry_count + 1}/{APIConfig.MAX_RETRIES}")
                time.sleep(wait_time)
                return self._get(endpoint, params, retry_count + 1)
            else:
                self.logger.error(f"API Error: {str(e)}")
                return {}

    def get_hisse(self, kod: str) -> Optional[Dict]:
        """Get Stock Data"""
        try:
            cache_key = f"hisse_{kod}"
            cached = self.cache.get(cache_key)
            if cached:
                return cached
            
            data = self._get('quote', {'symbol': f'{kod}.HE'})

            if data and 'c' in data:
                result = {
                    'kod': kod,
                    'fiyat': data.get('c'),
                    'hacim': data.get('v'),
                    '52w_high': data.get('h'),
                    '52w_low': data.get('l'),
                    'gunluk_high': data.get('h'),
                    'gunluk_low': data.get('l'),
                    'acilis': data.get('o'),
                    'kapanis': data.get('pc'),
                    'saat': datetime.now().isoformat(),
                }
                
                self.cache.set(cache_key, result)
                return result

            return None

        except Exception as e:
            self.logger.error(f"Stock Error ({kod}): {str(e)}")
            return None

    def get_temel_veriler(self, kod: str) -> Optional[Dict]:
        """Get Fundamental Data"""
        try:
            cache_key = f"temel_{kod}"
            cached = self.cache.get(cache_key)
            if cached:
                return cached
            
            data = self._get('stock/metric', {'symbol': f'{kod}.HE', 'metric': 'all'})

            if data and 'metric' in data:
                metric = data['metric']
                result = {
                    'pe': metric.get('peAnnual', 0),
                    'roe': metric.get('roe', 0),
                    'borc_oz': metric.get('debtToEquity', 0),
                    'temettü': metric.get('dividendYield', 0),
                    'piyasa_degeri': metric.get('marketCapitalization', 0),
                    'adv': metric.get('avgVolume', 0) / 1_000_000,
                }
                
                self.cache.set(cache_key, result)
                return result

            return None

        except Exception as e:
            self.logger.error(f"Fundamental Error ({kod}): {str(e)}")
            return None

    def get_hisse_listesi(self, index: str = 'BIST100') -> List[str]:
        """Get BIST100 List"""
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
            self.logger.info(f"BIST100: {len(bist100)} stocks")
            return bist100

        return []

# ============================================================================
# TECHNICAL DATA CLIENT
# ============================================================================

class TechnicalDataClient:
    """Technical Indicators - Alpha Vantage"""

    def __init__(self, api_key: str = '', api_url: str = ''):
        self.api_key = api_key or os.getenv('FINANS_API_KEY', '')
        self.api_url = api_url or os.getenv('FINANS_API_URL', 'https://www.alphavantage.co')
        self.logger = logging.getLogger(__name__)
        self.circuit_breaker = CircuitBreaker()
        self.cache = CacheManager(timeout_minutes=60)
        
        if not self.api_key:
            self.logger.warning("FINANS_API_KEY bos!")

    def _get_alpha_vantage(self, function: str, symbol: str,
                          interval: str = 'daily', params: Dict = None, 
                          retry_count: int = 0) -> Optional[Dict]:
        """Alpha Vantage Call with Retry"""
        
        if not self.circuit_breaker.can_execute():
            self.logger.error("Circuit Breaker ACIK")
            return None
        
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

            self.logger.info(f"Alpha Vantage: {function} {symbol} (Attempt {retry_count + 1})")

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            time.sleep(APIConfig.RATE_LIMIT_DELAY)

            self.circuit_breaker.record_success()
            return data

        except requests.exceptions.RequestException as e:
            self.circuit_breaker.record_failure()
            
            if retry_count < APIConfig.MAX_RETRIES:
                wait_time = APIConfig.RETRY_DELAY * (retry_count + 1)
                self.logger.warning(f"Retry {retry_count + 1}/{APIConfig.MAX_RETRIES}")
                time.sleep(wait_time)
                return self._get_alpha_vantage(function, symbol, interval, params, retry_count + 1)
            else:
                self.logger.error(f"Alpha Vantage Error ({function}): {str(e)}")
                return None

    def get_rsi(self, kod: str, period: int = 14) -> Optional[float]:
        """RSI"""
        try:
            cache_key = f"rsi_{kod}_{period}"
            cached = self.cache.get(cache_key)
            if cached:
                return cached.get('value')
            
            data = self._get_alpha_vantage('RSI', kod, params={'time_period': period})

            if data and 'Technical Analysis: RSI' in data:
                rsi_values = data['Technical Analysis: RSI']
                if not rsi_values:
                    return None

                latest_date = list(rsi_values.keys())[0]
                rsi = float(rsi_values[latest_date]['RSI'])

                self.logger.info(f"RSI {kod}: {rsi:.2f}")
                self.cache.set(cache_key, {'value': rsi})
                return rsi

            return None

        except Exception as e:
            self.logger.error(f"RSI Error ({kod}): {str(e)}")
            return None

    def get_macd(self, kod: str) -> Optional[Dict]:
        """MACD"""
        try:
            cache_key = f"macd_{kod}"
            cached = self.cache.get(cache_key)
            if cached:
                return cached
            
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

                self.logger.info(f"MACD {kod}: {result}")
                self.cache.set(cache_key, result)
                return result

            return None

        except Exception as e:
            self.logger.error(f"MACD Error ({kod}): {str(e)}")
            return None

    def get_adx(self, kod: str, period: int = 14) -> Optional[float]:
        """ADX"""
        try:
            cache_key = f"adx_{kod}_{period}"
            cached = self.cache.get(cache_key)
            if cached:
                return cached.get('value')
            
            data = self._get_alpha_vantage('ADX', kod, params={'time_period': period})

            if data and 'Technical Analysis: ADX' in data:
                adx_values = data['Technical Analysis: ADX']
                if not adx_values:
                    return None

                latest_date = list(adx_values.keys())[0]
                adx = float(adx_values[latest_date]['ADX'])

                self.logger.info(f"ADX {kod}: {adx:.2f}")
                self.cache.set(cache_key, {'value': adx})
                return adx

            return None

        except Exception as e:
            self.logger.error(f"ADX Error ({kod}): {str(e)}")
            return None

    def get_ema(self, kod: str, period: int = 20) -> Optional[float]:
        """EMA"""
        try:
            cache_key = f"ema_{kod}_{period}"
            cached = self.cache.get(cache_key)
            if cached:
                return cached.get('value')
            
            data = self._get_alpha_vantage('EMA', kod, params={'time_period': period})

            if data and 'Technical Analysis: EMA' in data:
                ema_values = data['Technical Analysis: EMA']
                if not ema_values:
                    return None

                latest_date = list(ema_values.keys())[0]
                ema = float(ema_values[latest_date]['EMA'])

                self.logger.info(f"EMA{period} {kod}: {ema:.2f}")
                self.cache.set(cache_key, {'value': ema})
                return ema

            return None

        except Exception as e:
            self.logger.error(f"EMA Error ({kod}): {str(e)}")
            return None

    def get_atr(self, kod: str, period: int = 14) -> Optional[float]:
        """ATR"""
        try:
            cache_key = f"atr_{kod}_{period}"
            cached = self.cache.get(cache_key)
            if cached:
                return cached.get('value')
            
            data = self._get_alpha_vantage('ATR', kod, params={'time_period': period})

            if data and 'Technical Analysis: ATR' in data:
                atr_values = data['Technical Analysis: ATR']
                if not atr_values:
                    return None

                latest_date = list(atr_values.keys())[0]
                atr = float(atr_values[latest_date]['ATR'])

                self.logger.info(f"ATR {kod}: {atr:.2f}")
                self.cache.set(cache_key, {'value': atr})
                return atr

            return None

        except Exception as e:
            self.logger.error(f"ATR Error ({kod}): {str(e)}")
            return None

    def get_göstergeler(self, kod: str) -> Optional[Dict]:
        """Get All Indicators"""
        try:
            cache_key = f"all_teknik_{kod}"
            cached = self.cache.get(cache_key)
            if cached:
                return cached
            
            self.logger.info(f"Getting Technical Indicators: {kod}")

            rsi = self.get_rsi(kod) or 50
            macd = self.get_macd(kod) or {'macd': 0, 'signal': 0, 'histogram': 0}
            adx = self.get_adx(kod) or 20
            ema20 = self.get_ema(kod, 20) or 0
            ema50 = self.get_ema(kod, 50) or 0
            ema200 = self.get_ema(kod, 200) or 0
            atr = self.get_atr(kod) or 0

            result = {
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
            
            self.cache.set(cache_key, result)
            return result

        except Exception as e:
            self.logger.error(f"Technical Indicators Error ({kod}): {str(e)}")
            return None

# ============================================================================
# DATA FETCHER
# ============================================================================

class DataFetcher:
    """Combined Data Fetcher"""

    def __init__(self):
        self.bist_client = BISTDataClient()
        self.tech_client = TechnicalDataClient()
        self.logger = logging.getLogger(__name__)

    def get_bist_verisi(self, kod: str) -> Optional[Dict]:
        """Get Complete Stock Data"""
        try:
            hisse = self.bist_client.get_hisse(kod)
            if not hisse:
                self.logger.warning(f"Price data unavailable: {kod}")
                return None

            temel = self.bist_client.get_temel_veriler(kod) or {}
            teknik = self.tech_client.get_göstergeler(kod) or {}

            return {
                'kod': kod,
                'fiyat': hisse.get('fiyat'),
                'hacim': hisse.get('hacim'),
                'acilis': hisse.get('acilis'),
                'kapanis': hisse.get('kapanis'),
                '52w_high': hisse.get('52w_high'),
                '52w_low': hisse.get('52w_low'),
                'pe': temel.get('pe', 0),
                'roe': temel.get('roe', 0),
                'borc_oz': temel.get('borc_oz', 0),
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
            self.logger.error(f"Data Error ({kod}): {str(e)}")
            return None

    def get_bist100_listesi(self) -> List[str]:
        """Get BIST100 List"""
        return self.bist_client.get_hisse_listesi('BIST100')

    def tarama_yap(self) -> List[Dict]:
        """Scan All BIST100 Stocks"""
        hisseler = self.get_bist100_listesi()
        veriler = []

        for kod in hisseler:
            veri = self.get_bist_verisi(kod)
            if veri:
                veriler.append(veri)
                self.logger.info(f"OK {kod}: {veri.get('fiyat')} TL")
            else:
                self.logger.warning(f"FAIL {kod}")

        self.logger.info(f"Scan Complete: {len(veriler)}/{len(hisseler)}")
        return veriler
