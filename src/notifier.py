import time
import requests
import logging
from src.config import config

logger = logging.getLogger(__name__)

SIGNAL_EMOJI = {
    "BUY" : "🟢 شراء",
    "SELL": "🔴 بيع",
    "HOLD": "⚪ انتظار"
}


class TelegramNotifier:

    def __init__(self):
        self.token    = config.TELEGRAM_BOT_TOKEN
        self.chat_id  = config.TELEGRAM_CHAT_ID
        self.base_url = (
            f"https://api.telegram.org/bot{self.token}"
        )
        self.sent_signals = {}

    # ==========================================
    def send_signal(self, signal_data: dict) -> bool:
        """إرسال إشارة تداول"""

        if not config.SEND_SIGNALS:
            return False

        signal = signal_data.get("signal")
        symbol = signal_data.get("symbol")

        if signal == "HOLD":
            return False

        # منع التكرار خلال ساعة
        cache_key = f"{symbol}_{signal}"
        if cache_key in self.sent_signals:
            if time.time() - self.sent_signals[cache_key] < 3600:
                logger.info(
                    f"ℹ️ {symbol}: تم إرسال نفس الإشارة مؤخراً"
                )
                return False

        message = self._format_signal(signal_data)
        success = self._send_message(message)

        if success:
            self.sent_signals[cache_key] = time.time()
            logger.info(f"✅ تم إرسال إشارة {symbol} {signal}")

        return success

    # ==========================================
    def _format_signal(self, d: dict) -> str:
        """تنسيق رسالة الإشارة"""

        signal = d["signal"]
        emoji  = SIGNAL_EMOJI.get(signal, "⚪")

        message = (
            f"{emoji} | {d['symbol_display']}\n\n"
            f"🕐 {d['time']}\n"
            f"💵 السعر: `{d['price']}`\n\n"
            f"📍 *المستويات:*\n"
            f"    ┣ الدخول:        `{d['entry']}`\n"
            f"    ┣ وقف الخسارة:   `{d['sl']}` "
            f"({d['sl_pips']} pips)\n"
            f"    ┣ الهدف الأول:   `{d['tp1']}` "
            f"({d['tp1_pips']} pips)\n"
            f"    ┣ الهدف الثاني:  `{d['tp2']}` "
            f"({d['tp2_pips']} pips)\n"
            f"    ┗ الهدف الثالث:  `{d['tp3']}` "
            f"({d['tp3_pips']} pips)"
        )
        return message

    # ==========================================
    def send_startup_message(self):
        """رسالة بدء التشغيل"""

        symbols_list = "\n".join(
            [
                f"  • {v['display']}"
                for v in config.SYMBOLS.values()
            ]
        )

        message = (
            f"🤖 *الروبوت يعمل الآن*\n\n"
            f"📊 *الأزواج:*\n"
            f"{symbols_list}\n\n"
            f"📐 *إعدادات Pips:*\n"
            f"  • وقف الخسارة:  `{config.SL_PIPS} pips`\n"
            f"  • الهدف الأول:  `{config.TP1_PIPS} pips`\n"
            f"  • الهدف الثاني: `{config.TP2_PIPS} pips`\n"
            f"  • الهدف الثالث: `{config.TP3_PIPS} pips`\n\n"
            f"⏰ الفحص كل `{config.SCAN_INTERVAL_MINUTES}` دقيقة"
        )
        self._send_message(message)

    # ==========================================
    def send_summary(self, signals_summary: list):
        """ملخص كل 5 فحوصات"""

        if not signals_summary:
            return

        lines = ["📋 *ملخص الفحص:*\n"]

        for s in signals_summary:
            if s["signal"] == "BUY":
                emoji = "🟢"
            elif s["signal"] == "SELL":
                emoji = "🔴"
            else:
                emoji = "⚪"

            lines.append(
                f"{emoji} `{s['symbol_display']}` "
                f"→ *{s['signal']}*"
            )

        self._send_message("\n".join(lines))

    # ==========================================
    def send_error(self, message: str):
        """إرسال رسالة خطأ"""
        self._send_message(f"❌ *خطأ:* {message}")

    # ==========================================
    def _send_message(self, text: str) -> bool:
        """إرسال رسالة إلى تيليجرام"""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            resp = requests.post(
                url, json=payload, timeout=15
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"❌ فشل الإرسال: {e}")
            return False

    # ==========================================
    def test_connection(self) -> bool:
        """اختبار الاتصال بتيليجرام"""
        try:
            resp = requests.get(
                f"{self.base_url}/getMe",
                timeout=10
            )
            return resp.status_code == 200
        except Exception:
            return False
