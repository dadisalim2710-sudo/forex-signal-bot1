"""
فحص أوقات السوق
"""
from datetime import datetime, time
import pytz
import logging

logger = logging.getLogger(__name__)


class MarketHours:

    # ==========================================
    # أوقات السوق بتوقيت UTC
    # ==========================================
    SESSIONS = {
        "Sydney": {
            "open" : time(21, 0),  # 21:00 UTC
            "close": time(6, 0),   # 06:00 UTC
            "symbols": ["AUD/USD"]
        },
        "Tokyo": {
            "open" : time(0, 0),   # 00:00 UTC
            "close": time(9, 0),   # 09:00 UTC
            "symbols": ["USD/JPY"]
        },
        "London": {
            "open" : time(7, 0),   # 07:00 UTC
            "close": time(16, 0),  # 16:00 UTC
            "symbols": [
                "EUR/USD", "GBP/USD",
                "USD/CHF", "XAU/USD"
            ]
        },
        "NewYork": {
            "open" : time(12, 0),  # 12:00 UTC
            "close": time(21, 0),  # 21:00 UTC
            "symbols": [
                "EUR/USD", "GBP/USD",
                "USD/JPY", "USD/CHF",
                "XAU/USD"
            ]
        },
    }

    @staticmethod
    def get_utc_now() -> datetime:
        """الوقت الحالي بتوقيت UTC"""
        return datetime.now(pytz.UTC)

    @staticmethod
    def is_weekend() -> bool:
        """هل اليوم عطلة نهاية الأسبوع؟"""
        utc_now = MarketHours.get_utc_now()
        weekday = utc_now.weekday()

        # السبت = 5, الأحد = 6
        # السوق يغلق الجمعة 21:00 UTC
        # السوق يفتح الأحد 21:00 UTC
        if weekday == 5:  # السبت
            return True
        if weekday == 6:  # الأحد
            if utc_now.hour < 21:
                return True
        if weekday == 4:  # الجمعة
            if utc_now.hour >= 21:
                return True
        return False

    @staticmethod
    def is_forex_open() -> bool:
        """هل سوق الفوركس مفتوح؟"""
        if MarketHours.is_weekend():
            return False
        return True

    @staticmethod
    def is_symbol_active(symbol: str) -> bool:
        """هل الزوج نشط الآن؟"""

        # إذا السوق مغلق
        if not MarketHours.is_forex_open():
            return False

        utc_now  = MarketHours.get_utc_now()
        now_time = utc_now.time().replace(tzinfo=None)

        # فحص كل جلسة
        for session, info in MarketHours.SESSIONS.items():
            if symbol not in info["symbols"]:
                continue

            open_t  = info["open"]
            close_t = info["close"]

            # جلسة تمتد عبر منتصف الليل
            if open_t > close_t:
                if now_time >= open_t or now_time < close_t:
                    return True
            else:
                if open_t <= now_time < close_t:
                    return True

        return False

    @staticmethod
    def get_active_session() -> str:
        """الجلسة النشطة حالياً"""

        if MarketHours.is_weekend():
            return "CLOSED"

        utc_now  = MarketHours.get_utc_now()
        now_time = utc_now.time().replace(tzinfo=None)
        active   = []

        for session, info in MarketHours.SESSIONS.items():
            open_t  = info["open"]
            close_t = info["close"]

            if open_t > close_t:
                if now_time >= open_t or now_time < close_t:
                    active.append(session)
            else:
                if open_t <= now_time < close_t:
                    active.append(session)

        if not active:
            return "CLOSED"

        return " + ".join(active)

    @staticmethod
    def get_next_open() -> str:
        """موعد فتح السوق القادم"""

        utc_now = MarketHours.get_utc_now()
        weekday = utc_now.weekday()

        if weekday == 5:  # السبت
            days_left = 1
            return f"الأحد الساعة 21:00 UTC"
        elif weekday == 6 and utc_now.hour < 21:
            hours_left = 21 - utc_now.hour
            return f"اليوم الأحد بعد {hours_left} ساعة"
        elif weekday == 4 and utc_now.hour >= 21:
            return "الأحد الساعة 21:00 UTC"

        return "السوق مفتوح الآن"

    @staticmethod
    def get_status_text() -> str:
        """نص حالة السوق"""

        session = MarketHours.get_active_session()

        if session == "CLOSED":
            next_open = MarketHours.get_next_open()
            return (
                f"🔴 السوق مغلق\n"
                f"⏰ يفتح: {next_open}"
            )

        return f"🟢 السوق مفتوح | جلسة {session}"
