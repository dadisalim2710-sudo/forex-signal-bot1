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
        self.cache_duration = 600  # 10 دقائق كاش

    def _fetch(self, symbol: str, days: int) -> pd.DataFrame | None:
        """جلب البيانات من Twelve Data"""
        try:
            candles = min(days * 24, 5000)

            params = {
                "symbol": symbol,
                "interval": config.TIMEFRAME,
                "outputsize": candles,
                "apikey": self.api_key,
                "format": "JSON",
                "order": "ASC"
            }

            url = f"{BASE_URL}/time_series"
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()

            # فحص الأخطاء
            if data.get("status") == "error":
                logger.error(
                    f"❌ {symbol}: {data.get('message', 'خطأ')}"
                )
                return None

            values = data.get("values")
            if not values:
                logger.error(f"❌ {symbol}: لا توجد بيانات")
                return None

            # تحويل إلى DataFrame
            df = pd.DataFrame(values)
            df["datetime"] = pd.to_datetime(df["datetime"])
            df.set_index("datetime", inplace=True)
            df.sort_index(inplace=True)

            # ===== الحل: تحديد الأعمدة المتاحة =====
            # Twelve Data لا يرسل volume للفوركس دائماً
            available_cols = df.columns.tolist()

            rename_map = {}
            if "open" in available_cols:
                rename_map["open"] = "Open"
            if "high" in available_cols:
                rename_map["high"] = "High"
            if "low" in available_cols:
                rename_map["low"] = "Low"
            if "close" in available_cols:
                rename_map["close"] = "Close"

            df.rename(columns=rename_map, inplace=True)

            # تأكد من وجود الأعمدة الأساسية
            required = ["Open", "High", "Low", "Close"]
            for col in required:
                if col not in df.columns:
                    logger.error(f"❌ {symbol}: عمود {col} مفقود")
                    return None

            # إضافة Volume = 0 إذا غير موجود
            if "volume" in available_cols:
                df.rename(columns={"volume": "Volume"}, inplace=True)
            else:
                df["Volume"] = 1000  # قيمة افتراضية

            # الأعمدة النهائية
            df = df[["Open", "High", "Low", "Close", "Volume"]]
            df = df.astype(float)
            df = df[~df.index.duplicated(keep="last")]
            df.dropna(inplace=True)

            return df

        except Exception as e:
            logger.error(f"❌ خطأ في جلب {symbol}: {e}")
            return None

    def get_historical_data(
        self, symbol: str, days: int = None
    ) -> pd.DataFrame | None:
        """جلب البيانات مع الكاش والتأخير"""

        days = days or config.TRAIN_DATA_DAYS
        cache_key = f"{symbol}_{days}"

        # فحص الكاش
        if cache_key in self.cache:
            elapsed = (
                datetime.now() - self.cache_time[cache_key]
            ).seconds
            if elapsed < self.cache_duration:
                logger.debug(f"[Cache] {symbol}")
                return self.cache[cache_key]

        logger.info(f"📥 جلب {symbol}...")

        # ===== تأخير بين الطلبات =====
        # حد مجاني = 8 طلبات/دقيقة
        # 60 ثانية / 8 = 7.5 ثانية بين كل طلب
        time.sleep(8)

        df = self._fetch(symbol, days)

        if df is None or len(df) < 50:
            logger.warning(f"⚠️ بيانات غير كافية: {symbol}")
            return None

        # حفظ في الكاش
        self.cache[cache_key] = df
        self.cache_time[cache_key] = datetime.now()

        logger.info(f"✅ {symbol}: {len(df)} شمعة")
        return df

    def test_connection(self) -> bool:
        """اختبار الاتصال"""

        if not self.api_key:
            logger.error("❌ TWELVE_DATA_KEY غير موجود")
            return False

        try:
            params = {
                "symbol": "EUR/USD",
                "interval": "1h",
                "outputsize": 5,
                "apikey": self.api_key,
                "format": "JSON"
            }

            resp = requests.get(
                f"{BASE_URL}/time_series",
                params=params,
                timeout=30
            )
            data = resp.json()

            if data.get("status") == "error":
                logger.error(
                    f"❌ Twelve Data: {data.get('message')}"
                )
                return False

            if "values" in data:
                logger.info("✅ Twelve Data متصل بنجاح")
                return True

            logger.error(f"❌ رد غير متوقع: {data}")
            return False

        except Exception as e:
            logger.error(f"❌ فشل الاتصال: {e}")
            return False
