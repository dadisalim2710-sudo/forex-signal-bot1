import requests
import pandas as pd
import logging
import time
from datetime import datetime, timedelta
from src.config import config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.twelvedata.com"


class DataCollector:

    def __init__(self):
        self.api_key = config.TWELVE_DATA_KEY
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 600

    def _fetch(self, symbol: str, days: int,
               timeframe: str = None) -> pd.DataFrame | None:
        """جلب البيانات من Twelve Data"""
        try:
            tf = timeframe or config.TIMEFRAME
            candles = min(days * 24, 5000)

            params = {
                "symbol"    : symbol,
                "interval"  : tf,
                "outputsize": candles,
                "apikey"    : self.api_key,
                "format"    : "JSON",
                "order"     : "ASC"
            }

            resp = requests.get(
                f"{BASE_URL}/time_series",
                params=params,
                timeout=30
            )
            data = resp.json()

            if data.get("status") == "error":
                logger.error(
                    f"❌ {symbol}: {data.get('message', 'خطأ')}"
                )
                return None

            values = data.get("values")
            if not values:
                logger.error(f"❌ {symbol}: لا توجد بيانات")
                return None

            df = pd.DataFrame(values)
            df["datetime"] = pd.to_datetime(df["datetime"])
            df.set_index("datetime", inplace=True)
            df.sort_index(inplace=True)

            # تحديد الأعمدة المتاحة
            rename_map = {}
            for col in ["open", "high", "low", "close"]:
                if col in df.columns:
                    rename_map[col] = col.capitalize()

            df.rename(columns=rename_map, inplace=True)

            required = ["Open", "High", "Low", "Close"]
            for col in required:
                if col not in df.columns:
                    logger.error(
                        f"❌ {symbol}: عمود {col} مفقود"
                    )
                    return None

            if "volume" in df.columns:
                df.rename(
                    columns={"volume": "Volume"}, inplace=True
                )
            else:
                df["Volume"] = 1000

            df = df[["Open", "High", "Low", "Close", "Volume"]]
            df = df.astype(float)
            df = df[~df.index.duplicated(keep="last")]
            df.dropna(inplace=True)

            return df

        except Exception as e:
            logger.error(f"❌ خطأ في جلب {symbol}: {e}")
            return None

    def get_historical_data(
        self,
        symbol: str,
        days: int = None,
        timeframe: str = None
    ) -> pd.DataFrame | None:
        """جلب البيانات مع الكاش"""

        days = days or config.TRAIN_DATA_DAYS
        tf = timeframe or config.TIMEFRAME
        cache_key = f"{symbol}_{days}_{tf}"

        if cache_key in self.cache:
            elapsed = (
                datetime.now() - self.cache_time[cache_key]
            ).seconds
            if elapsed < self.cache_duration:
                return self.cache[cache_key]

        logger.info(f"📥 جلب {symbol} ({tf})...")
        time.sleep(8)

        df = self._fetch(symbol, days, tf)

        if df is None or len(df) < 50:
            logger.warning(f"⚠️ بيانات غير كافية: {symbol}")
            return None

        self.cache[cache_key] = df
        self.cache_time[cache_key] = datetime.now()

        logger.info(f"✅ {symbol} ({tf}): {len(df)} شمعة")
        return df

    def get_multi_timeframe(
        self, symbol: str
    ) -> dict:
        """جلب بيانات من 3 أطر زمنية"""

        result = {}

        # H1
        df_h1 = self.get_historical_data(
            symbol, days=90, timeframe=config.TIMEFRAME
        )
        if df_h1 is not None:
            result["H1"] = df_h1

        # H4
        df_h4 = self.get_historical_data(
            symbol, days=180, timeframe=config.TIMEFRAME_H4
        )
        if df_h4 is not None:
            result["H4"] = df_h4

        # D1
        df_d1 = self.get_historical_data(
            symbol, days=365, timeframe=config.TIMEFRAME_D1
        )
        if df_d1 is not None:
            result["D1"] = df_d1

        return result

    def test_connection(self) -> bool:
        """اختبار الاتصال"""

        if not self.api_key:
            logger.error("❌ TWELVE_DATA_KEY غير موجود")
            return False

        try:
            params = {
                "symbol"    : "EUR/USD",
                "interval"  : "1h",
                "outputsize": 5,
                "apikey"    : self.api_key,
                "format"    : "JSON"
            }

            resp = requests.get(
                f"{BASE_URL}/time_series",
                params=params,
                timeout=30
            )
            data = resp.json()

            if "values" in data:
                logger.info("✅ Twelve Data متصل بنجاح")
                return True

            logger.error(
                f"❌ Twelve Data: {data.get('message')}"
            )
            return False

        except Exception as e:
            logger.error(f"❌ فشل الاتصال: {e}")
            return False
