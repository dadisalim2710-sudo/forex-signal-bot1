import yfinance as yf
import pandas as pd
import logging
import time
from datetime import datetime, timedelta
from src.config import config

logger = logging.getLogger(__name__)

# رموز بديلة للذهب نجرب واحداً واحداً
GOLD_SYMBOLS = ["XAUUSD=X", "GC=F", "GLD"]


class DataCollector:

    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 300
        # خريطة الرموز البديلة
        self.symbol_map = {}

    def _try_symbol(self, symbol: str, days: int):
        """محاولة جلب بيانات رمز معين"""
        try:
            ticker = yf.Ticker(symbol)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            df = ticker.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval=config.TIMEFRAME,
                auto_adjust=True
            )

            if df is None or len(df) < 50:
                return None

            df = df[["Open", "High", "Low", "Close", "Volume"]]
            df.dropna(inplace=True)
            df = df[~df.index.duplicated(keep="last")]

            # إزالة timezone
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            if len(df) < 50:
                return None

            return df

        except Exception as e:
            logger.debug(f"فشل {symbol}: {e}")
            return None

    def get_historical_data(self, symbol: str, days: int = None):
        """جلب البيانات مع retry ورموز بديلة"""

        days = days or config.TRAIN_DATA_DAYS
        cache_key = f"{symbol}_{days}"

        # فحص الكاش
        if cache_key in self.cache:
            elapsed = (datetime.now() - self.cache_time[cache_key]).seconds
            if elapsed < self.cache_duration:
                return self.cache[cache_key]

        # قائمة الرموز للمحاولة
        symbols_to_try = [symbol]

        # إضافة رموز بديلة للذهب
        if symbol in ["GC=F", "XAUUSD=X", "GOLD"]:
            symbols_to_try = GOLD_SYMBOLS

        # إضافة الرمز المحفوظ سابقاً إن وجد
        if symbol in self.symbol_map:
            working = self.symbol_map[symbol]
            if working not in symbols_to_try:
                symbols_to_try.insert(0, working)

        df = None
        working_symbol = None

        for sym in symbols_to_try:
            logger.info(f"🔄 محاولة جلب {sym}...")

            # محاولة 3 مرات لكل رمز
            for attempt in range(3):
                df = self._try_symbol(sym, days)
                if df is not None:
                    working_symbol = sym
                    break
                if attempt < 2:
                    time.sleep(2)

            if df is not None:
                break

        if df is None:
            logger.error(f"❌ فشل جلب {symbol} بعد كل المحاولات")
            return None

        # حفظ الرمز الناجح
        if working_symbol and working_symbol != symbol:
            self.symbol_map[symbol] = working_symbol
            logger.info(f"✅ تم استخدام {working_symbol} بدلاً من {symbol}")

        # حفظ في الكاش
        self.cache[cache_key] = df
        self.cache_time[cache_key] = datetime.now()

        logger.info(f"✅ {working_symbol or symbol}: {len(df)} شمعة")
        return df

    def test_connection(self):
        """اختبار الاتصال بعدة رموز"""
        test_symbols = ["EURUSD=X", "XAUUSD=X", "GC=F"]

        for sym in test_symbols:
            try:
                df = self._try_symbol(sym, days=5)
                if df is not None:
                    logger.info(f"✅ اتصال ناجح عبر {sym}")
                    return True
            except Exception:
                continue

        logger.error("❌ فشل جميع اختبارات الاتصال")
        return False
