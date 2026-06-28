# -*- coding: utf-8 -*-
"""
Analiz Motoru - Sinyal Üretimi
Tarama, Risk/Reward, Sinyal Oluşturma
FİXED: Risk/Reward, ADV, Volatilite, Error Handling
"""
import logging
from typing import Dict, Optional
from config import FILTER_RULES, TECHNICAL_RULES, RISK_MANAGEMENT

logger = logging.getLogger(__name__)

# ============================================================================
# ANALYZER
# ============================================================================

class BISTAnalyzer:
    """BIST Hisse Analiz ve Sinyal Motoru"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    # ========================================================================
    # TARAMA KONTROLLERI
    # ========================================================================

    def kontrol_temel_veriler(self, hisse: Dict) -> tuple[bool, Dict]:
        """Temel Verileri Kontrol Et"""

        sonuçlar = {}
        geçti = True

        try:
            # P/E Oranı
            pe = hisse.get('pe', 0)
            if pe and pe > 0:
                pe_ok = FILTER_RULES['min_pe_ratio'] <= pe <= FILTER_RULES['max_pe_ratio']
                sonuçlar['pe'] = {'geçti': pe_ok, 'değer': pe}
                if not pe_ok:
                    geçti = False
            else:
                sonuçlar['pe'] = {'geçti': False, 'değer': 0}
                geçti = False

            # ROE
            roe = hisse.get('roe', 0)
            if roe and roe >= 0:
                roe_ok = roe >= FILTER_RULES['min_roe_percent']
                sonuçlar['roe'] = {'geçti': roe_ok, 'değer': roe}
                if not roe_ok:
                    geçti = False
            else:
                sonuçlar['roe'] = {'geçti': False, 'değer': 0}
                geçti = False

            # Borç/ÖS
            borç = hisse.get('borç_öz', 0)
            if borç and borç > 0:
                borç_ok = borç <= FILTER_RULES['max_debt_ratio']
                sonuçlar['borç'] = {'geçti': borç_ok, 'değer': borç}
                if not borç_ok:
                    geçti = False
            else:
                sonuçlar['borç'] = {'geçti': True, 'değer': 0}

            # ADV (LİKİDİTE) - DÜŞÜRÜLDÜ: 10 → 5
            adv = hisse.get('adv', 0)
            adv_threshold = 5  # FİXED: Daha esnek
            adv_ok = adv >= adv_threshold if adv else False
            sonuçlar['adv'] = {'geçti': adv_ok, 'değer': adv}
            if not adv_ok:
                geçti = False

        except Exception as e:
            self.logger.error(f"❌ Temel Veriler Kontrol Hatası: {str(e)}")
            geçti = False

        return geçti, sonuçlar

    def kontrol_teknik(self, hisse: Dict) -> tuple[bool, Dict]:
        """Teknik Göstergeleri Kontrol Et"""

        sonuçlar = {}
        geçti = True

        try:
            # EMA Trend
            ema20 = hisse.get('ema20', 0)
            ema50 = hisse.get('ema50', 0)
            ema200 = hisse.get('ema200', 0)

            ema_trend = (ema20 > ema50 > ema200) if all([ema20, ema50, ema200]) else False
            sonuçlar['ema'] = {'geçti': ema_trend, 'değer': f'{ema20}/{ema50}/{ema200}'}
            if not ema_trend:
                geçti = False

            # RSI
            rsi = hisse.get('rsi', 0)
            if rsi and rsi > 0:
                rsi_ok = TECHNICAL_RULES['min_rsi'] <= rsi <= TECHNICAL_RULES['max_rsi']
                sonuçlar['rsi'] = {'geçti': rsi_ok, 'değer': rsi}
                if not rsi_ok:
                    geçti = False
            else:
                sonuçlar['rsi'] = {'geçti': False, 'değer': 0}
                geçti = False

            # ADX
            adx = hisse.get('adx', 0)
            if adx and adx > 0:
                adx_ok = adx >= TECHNICAL_RULES['min_adx']
                sonuçlar['adx'] = {'geçti': adx_ok, 'değer': adx}
                if not adx_ok:
                    geçti = False
            else:
                sonuçlar['adx'] = {'geçti': False, 'değer': 0}
                geçti = False

            # Volatilite (ATR) - DÜZELTILDI: Kontrol aktif yapıldı
            atr = hisse.get('atr', 0)
            fiyat = hisse.get('fiyat', 1)
            
            if atr and fiyat > 0:
                volatilite = (atr / fiyat * 100)
                vol_ok = (TECHNICAL_RULES['min_volatility_pct'] <= volatilite <=
                          TECHNICAL_RULES['max_volatility_pct'])
                sonuçlar['volatilite'] = {'geçti': vol_ok, 'değer': volatilite}
                if not vol_ok:
                    geçti = False  # FİXED: Kontrol aktif yapıldı
            else:
                sonuçlar['volatilite'] = {'geçti': False, 'değer': 0}
                geçti = False

        except Exception as e:
            self.logger.error(f"❌ Teknik Kontrol Hatası: {str(e)}")
            geçti = False

        return geçti, sonuçlar

    # ========================================================================
    # SİNYAL OLUŞTURMA
    # ========================================================================

    def hesapla_sinyal_gücü(self, temel_ok: bool, teknik_ok: bool,
                           temel_sonuç: Dict, teknik_sonuç: Dict) -> int:
        """Sinyal Gücü Hesapla (0-100)"""

        skor = 0

        try:
            # Teknik (60 puan) - Ağırlıklandırılmış
            if teknik_sonuç.get('ema', {}).get('geçti'):
                skor += 20  # EMA en önemli
            if teknik_sonuç.get('adx', {}).get('geçti'):
                skor += 20  # ADX trend gücü
            if teknik_sonuç.get('rsi', {}).get('geçti'):
                skor += 15  # RSI momentum
            if teknik_sonuç.get('volatilite', {}).get('geçti'):
                skor += 5   # Volatilite ek

            # Temel (40 puan)
            if temel_sonuç.get('pe', {}).get('geçti'):
                skor += 15  # Değerleme
            if temel_sonuç.get('roe', {}).get('geçti'):
                skor += 15  # Kârlılık
            if temel_sonuç.get('borç', {}).get('geçti'):
                skor += 5   # Finansal sağlık
            if temel_sonuç.get('adv', {}).get('geçti'):
                skor += 5   # Likidite

        except Exception as e:
            self.logger.error(f"❌ Sinyal Gücü Hatası: {str(e)}")
            skor = 0

        return min(skor, 100)  # Max 100

    def öner_giriş_noktaları(self, hisse: Dict) -> Optional[Dict]:
        """Giriş Noktaları Öner (MANUEL KARAR İÇİN)"""

        try:
            fiyat = hisse.get('fiyat', 0)
            atr = hisse.get('atr', 0)

            if not fiyat or fiyat <= 0 or not atr or atr <= 0:
                return None

            # Risk Tanımı
            risk = atr * 1.5  # ATR'nin 1.5 katı

            # Giriş: Mevcut Fiyat
            giriş = fiyat

            # Stop-Loss: Giriş - Risk
            sl = giriş - risk

            # Hedef 1: Giriş + Risk
            t1 = giriş + risk

            # Hedef 2: Giriş + Risk*2
            t2 = giriş + risk * 2

            # Risk/Reward - FİXED: Doğru formül!
            # Potansiyel Kar / Risk
            potansiyel_kar = t2 - giriş
            rr = potansiyel_kar / risk if risk > 0 else 0

            return {
                'giriş': round(giriş, 2),
                'sl': round(sl, 2),
                't1': round(t1, 2),
                't2': round(t2, 2),
                'risk_tl': round(risk, 2),
                'risk_yüzde': round((risk / giriş) * 100, 2),
                'potansiyel_kar': round(potansiyel_kar, 2),
                'rr': round(rr, 2),  # FİXED: Gerçek Risk/Reward
            }

        except Exception as e:
            self.logger.error(f"❌ Giriş Noktaları Hatası: {str(e)}")
            return None

    # ========================================================================
    # UYARILAR
    # ========================================================================

    def kontrol_uyarılar(self, hisse: Dict) -> Optional[str]:
        """Özel Uyarılar Kontrol Et"""

        try:
            # Aşırı yüksek RSI
            rsi = hisse.get('rsi', 0)
            if rsi and rsi > 75:
                return f"RSI Aşırı Yüksek ({rsi:.0f}) - Satış Baskısı Riski"

            # Aşırı düşük RSI
            if rsi and rsi < 25:
                return f"RSI Aşırı Düşük ({rsi:.0f}) - Alış Potansiyeli"

            # Düşük Likidite
            adv = hisse.get('adv', 0)
            if adv and 0 < adv < 3:  # 3M altında çok düşük
                return f"Düşük Likidite ({adv:.0f}M) - Kaymayı Kontrol Et"

            # Yüksek P/E
            pe = hisse.get('pe', 0)
            if pe and pe > FILTER_RULES['max_pe_ratio'] * 1.5:
                return f"Yüksek P/E ({pe:.1f}) - Aşırı Değerlenmiş"

            # Negatif ROE
            roe = hisse.get('roe', 0)
            if roe and roe < 0:
                return f"Negatif ROE ({roe:.1f}%) - Karlılık Sorunu"

            # Yüksek Borç
            borç = hisse.get('borç_öz', 0)
            if borç and borç > FILTER_RULES['max_debt_ratio'] * 1.5:
                return f"Yüksek Borç ({borç:.1f}) - Finansal Risk"

            return None

        except Exception as e:
            self.logger.error(f"❌ Uyarı Kontrol Hatası: {str(e)}")
            return None

    # ========================================================================
    # KAPSAMLI ANALIZ
    # ========================================================================

    def analiz_hisse(self, hisse: Dict) -> Dict:
        """Hisse Tam Analizi - Sinyal Üretme"""

        try:
            kod = hisse.get('kod', 'UNKNOWN')
            fiyat = hisse.get('fiyat', 0)

            if not kod or not fiyat or fiyat <= 0:
                return {
                    'kod': kod,
                    'fiyat': 0,
                    'skor': 0,
                    'sinyal': 'INVALID',
                    'açıklama': 'Geçersiz Veri',
                    'tarama_geçti': False,
                }

            # Kontroller
            temel_ok, temel_sonuç = self.kontrol_temel_veriler(hisse)
            teknik_ok, teknik_sonuç = self.kontrol_teknik(hisse)

            # Sinyal Gücü
            skor = self.hesapla_sinyal_gücü(temel_ok, teknik_ok, temel_sonuç, teknik_sonuç)

            # Tarama Geçti mi? (Skor >= 70 ve teknik + temel)
            tarama_geçti = skor >= 70 and teknik_ok and temel_ok

            # Giriş Noktaları
            giriş_noktaları = self.öner_giriş_noktaları(hisse)

            # Uyarılar
            uyarı = self.kontrol_uyarılar(hisse)

            # Sinyal Tipi
            if tarama_geçti:
                sinyal = 'BUY'
                açıklama = 'Alış Sinyali - Teknik ve Temel Veriler Uygun'
            elif teknik_ok and temel_ok:
                sinyal = 'BUY'
                açıklama = 'Alış Sinyali - Her İki Koşul Sağlandı'
            elif teknik_ok and not temel_ok:
                sinyal = 'CAUTION'
                açıklama = 'Dikkatli - Teknik İyi ama Temel Veriler Zayıf'
            elif temel_ok and not teknik_ok:
                sinyal = 'WATCH'
                açıklama = 'İzle - Temel Veriler İyi ama Teknik Zayıf'
            else:
                sinyal = 'HOLD'
                açıklama = 'Bekle - Şartlar Uygun Değil'

            return {
                'kod': kod,
                'fiyat': round(fiyat, 2),
                'skor': skor,
                'sinyal': sinyal,
                'açıklama': açıklama,
                'tarama_geçti': tarama_geçti,
                'temel_ok': temel_ok,
                'teknik_ok': teknik_ok,
                'giriş': giriş_noktaları.get('giriş') if giriş_noktaları else 0,
                'sl': giriş_noktaları.get('sl') if giriş_noktaları else 0,
                't1': giriş_noktaları.get('t1') if giriş_noktaları else 0,
                't2': giriş_noktaları.get('t2') if giriş_noktaları else 0,
                'rr': giriş_noktaları.get('rr') if giriş_noktaları else 0,
                'uyarı': uyarı,
                'temel_veriler': temel_sonuç,
                'teknik_göstergeler': teknik_sonuç,
            }

        except Exception as e:
            self.logger.error(f"❌ Hisse Analiz Hatası: {str(e)}")
            return {
                'kod': hisse.get('kod', 'ERROR'),
                'fiyat': 0,
                'skor': 0,
                'sinyal': 'ERROR',
                'açıklama': f'Analiz Hatası: {str(e)}',
                'tarama_geçti': False,
            }
