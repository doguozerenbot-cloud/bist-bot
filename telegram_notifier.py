# -*- coding: utf-8 -*-
"""
Telegram Notifier - Sinyal Bildirimi
Sadece BİLDİRİM - KARAR MANUEL
"""
import logging
import asyncio
import os
from typing import Optional
from telegram import Bot

logger = logging.getLogger(__name__)

# ============================================================================
# TELEGRAM NÖTİFİER
# ============================================================================

class TelegramNotifier:
    """Telegram Bildirimleri - Manuel Karar İçin"""
    
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or os.getenv('TELEGRAM_TOKEN', '')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID', '')
        self.bot = Bot(token=self.token) if self.token else None
        self.logger = logging.getLogger(__name__)
        
        if not self.token or not self.chat_id:
            self.logger.warning("⚠️ Telegram Token veya Chat ID ayarlanmamış")
    
    async def send_message(self, mesaj: str) -> bool:
        """Mesaj Gönder"""
        
        if not self.bot or not self.chat_id:
            self.logger.error("❌ Telegram Ayarları Eksik")
            return False
        
        try:
            self.logger.info(f"📤 Telegram Mesajı Gönderiliyor (Chat: {self.chat_id})...")
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=mesaj,
                parse_mode='HTML'
            )
            
            self.logger.info("✓ Telegram Mesajı Gönderildi")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Telegram Hatası: {str(e)}")
            return False
    
    def send_message_sync(self, mesaj: str) -> bool:
        """Senkron Mesaj Gönder (Async wrapper)"""
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.send_message(mesaj))
    
    # ========================================================================
    # HAZIR MESAJLAR
    # ========================================================================
    
    async def bildir_sinyal(self, kod: str, sinyal: str, açıklama: str):
        """Sinyal Bildiri"""
        
        emoji_sinyal = {
            'BUY': '🟢',
            'CAUTION': '🟡',
            'WATCH': '🔵',
            'HOLD': '⚪',
        }
        
        emoji = emoji_sinyal.get(sinyal, '❓')
        
        mesaj = f"""
{emoji} <b>SİNYAL: {sinyal}</b>

<b>Hisse:</b> {kod}
<b>Açıklama:</b> {açıklama}

⏰ Manuel Karar Ver!
📊 Kendi Analizini Yap!
⚠️ Risk Yönetimi Kurallarına Uy!
"""
        
        await self.send_message(mesaj)
    
    async def bildir_uyarı(self, kod: str, uyarı: str):
        """Uyarı Bildiri"""
        
        mesaj = f"""
⚠️ <b>UYARI: {kod}</b>

{uyarı}

💡 Dikkatli Ol!
📌 Bu sadece bir uyarı - karar sen ver.
"""
        
        await self.send_message(mesaj)

# ============================================================================
# ÖRNEK KULLANIM
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    logging.basicConfig(level=logging.INFO)
    
    notifier = TelegramNotifier()
    
    # Test
    asyncio.run(notifier.bildir_sinyal(
        'AKBNK',
        'BUY',
        'Teknik ve Temel Veriler Uygun'
    ))

