import yfinance as yf
import pandas as pd
import logging
from datetime import datetime, timedelta
from src.config import config

logger = logging.getLogger(__name__)


class DataCollector:

    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 300

    def get_historical_data(self, symbol: str, days: int = None):
        days = days or config.TRAIN_DATA_DAYS
        cache_key = f"{symbol}_{days}"

        if cache_key in self.cache:
            elapsed = (datetime.now() - self.cache_time[cache_key]).seconds
            if elapsed < self.cache_duration:
                return self.cache[cache_key]

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

            if df is None or len(df) < 100:
                logger.warning(f"بيانات غير كافية لـ {symbol}")
                return None

            df = df[["Open", "High", "Low", "Close", "Volume"]]
            df.dropna(inplace=True)
            df = df[~df.index.duplicated(keep="last")]
            df.index = df.index.tz_localize(None)

            self.cache[cache_key] = df
            self.cache_time[cache_key] = datetime.now()

            logger.info(f"✅ {symbol}: {len(df)} شمعة")
            return df

        except Exception as e:
            logger.error(f"❌ خطأ {symbol}: {e}")
            return None

    def test_connection(self):
        try:
            df = self.get_historical_data("GC=F", days=5)
            return df is not None
        except Exception:
            return False
