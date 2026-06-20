import os
import sys
import time
import logging
import schedule
from datetime import datetime

os.makedirs("logs",   exist_ok=True)
os.makedirs("models", exist_ok=True)
os.makedirs("data",   exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            f"logs/bot_{datetime.now().strftime('%Y%m%d')}.log",
            encoding="utf-8"
        ),
    ],
)

logger = logging.getLogger("main")

from src.config import config
from src.data_collector import DataCollector
from src.indicators import TechnicalIndicators
from src.ai_model import AIModel
from src.signal_engine import SignalEngine
from src.notifier import TelegramNotifier
from src.performance_tracker import PerformanceTracker
from src.market_hours import MarketHours


class SignalBot:

    def __init__(self):
        self.data          = DataCollector()
        self.signal_engine = SignalEngine()
        self.notifier      = TelegramNotifier()
        self.tracker       = PerformanceTracker()
        self.market        = MarketHours()
        self.models        = {}
        self.last_train    = {}
        self.scan_count    = 0
        self.market_was_open = False

    # ==========================================
    def setup(self) -> bool:
        logger.info("=" * 50)
        logger.info("  🤖 روبوت إشارات التداول الاحترافي")
        logger.info("=" * 50)

        if not config.TELEGRAM_BOT_TOKEN:
            logger.error("❌ أضف TELEGRAM_BOT_TOKEN")
            return False

        if not config.TWELVE_DATA_KEY:
            logger.error("❌ أضف TWELVE_DATA_KEY")
            return False

        logger.info("🔗 اختبار تيليجرام...")
        if not self.notifier.test_connection():
            logger.error("❌ فشل تيليجرام")
            return False
        logger.info("✅ تيليجرام متصل")

        logger.info("🔗 اختبار Twelve Data...")
        if not self.data.test_connection():
            logger.error("❌ فشل Twelve Data")
            return False
        logger.info("✅ Twelve Data متصل")

        # تدريب النماذج (يعمل دائماً بغض النظر عن السوق)
        logger.info("🧠 تهيئة النماذج...")
        for symbol in config.SYMBOLS:
            self.models[symbol] = AIModel(symbol)
            if not self.models[symbol].load():
                logger.info(f"   تدريب {symbol}...")
                df = self.data.get_historical_data(
                    symbol, days=config.TRAIN_DATA_DAYS
                )
                if df is not None:
                    df = TechnicalIndicators.add_all(df)
                    self.models[symbol].train(df)
            self.last_train[symbol] = time.time()

        # رسالة البداية
        market_status = MarketHours.get_status_text()
        self.notifier.send_startup_message(market_status)
        logger.info("✅ الروبوت جاهز!")
        return True

    # ==========================================
    def _should_retrain(self, symbol: str) -> bool:
        elapsed = (
            time.time() - self.last_train.get(symbol, 0)
        ) / 3600
        return elapsed >= config.RETRAIN_HOURS

    def _retrain(self, symbol: str):
        logger.info(f"♻️ إعادة تدريب {symbol}...")
        df = self.data.get_historical_data(
            symbol, days=config.TRAIN_DATA_DAYS
        )
        if df is not None and len(df) > 300:
            df = TechnicalIndicators.add_all(df)
            self.models[symbol].train(df)
            self.last_train[symbol] = time.time()

    # ==========================================
    def scan(self):
        """دورة الفحص الرئيسية"""

        self.scan_count += 1
        now = datetime.now().strftime("%H:%M:%S")

        logger.info(f"\n{'─'*40}")
        logger.info(f"🔍 فحص #{self.scan_count} | {now}")
        logger.info(f"{'─'*40}")

        # ===== فحص السوق أولاً =====
        is_open = MarketHours.is_forex_open()
        session = MarketHours.get_active_session()

        if not is_open:
            logger.info(f"🔴 السوق مغلق | {MarketHours.get_next_open()}")

            # إشعار عند إغلاق السوق (مرة واحدة فقط)
            if self.market_was_open:
                self.market_was_open = False
                self.notifier.send_market_closed()

            return

        # ===== السوق مفتوح =====
        logger.info(f"🟢 السوق مفتوح | جلسة: {session}")

        # إشعار عند فتح السوق (مرة واحدة فقط)
        if not self.market_was_open:
            self.market_was_open = True
            self.notifier.send_market_open(session)

        all_signals = []

        for symbol in config.SYMBOLS:
            try:
                # فحص إذا الزوج نشط في هذه الجلسة
                if not MarketHours.is_symbol_active(symbol):
                    logger.info(
                        f"  ⏸ {symbol}: غير نشط في هذه الجلسة"
                    )
                    continue

                # إعادة التدريب إذا لزم
                if self._should_retrain(symbol):
                    self._retrain(symbol)

                # جلب البيانات
                df = self.data.get_historical_data(
                    symbol, days=90
                )
                if df is None or len(df) < 100:
                    logger.warning(
                        f"⚠️ {symbol}: بيانات غير كافية"
                    )
                    continue

                df = TechnicalIndicators.add_all(df)

                # Multi-Timeframe
                mtf_data = None
                if config.REQUIRE_MTF:
                    mtf_data = (
                        self.data.get_multi_timeframe(symbol)
                    )

                # تنبؤ AI
                ai_signal, ai_conf = (
                    self.models[symbol].predict(df)
                )

                # تحليل
                signal_data = self.signal_engine.analyze(
                    symbol, df,
                    ai_signal, ai_conf,
                    mtf_data
                )

                all_signals.append(signal_data)
                self.tracker.record_signal(signal_data)

                logger.info(
                    f"  {signal_data['symbol_display']:15s} | "
                    f"{signal_data['signal']:4s} | "
                    f"AI: {ai_signal} ({ai_conf:.0%}) | "
                    f"BUY:{signal_data['score_buy']} "
                    f"SELL:{signal_data['score_sell']} | "
                    f"{signal_data['regime']}"
                )

                # إرسال الإشارة
                if signal_data["signal"] != "HOLD":
                    sent = self.notifier.send_signal(signal_data)
                    if sent:
                        logger.info(
                            f"  ✅ إشارة أُرسلت: {symbol}"
                        )
                else:
                    logger.info(f"  ⚪ {symbol}: HOLD")

            except Exception as e:
                logger.error(f"❌ خطأ {symbol}: {e}")

        # ملخص كل 5 فحوصات
        if self.scan_count % 5 == 0 and all_signals:
            self.notifier.send_summary(all_signals)
            logger.info(f"\n{self.tracker.get_summary()}")

    # ==========================================
    def run(self):
        if not self.setup():
            sys.exit(1)

        # فحص أولي
        self.scan()

        interval = config.SCAN_INTERVAL_MINUTES
        schedule.every(interval).minutes.do(self.scan)
        logger.info(f"⏰ الفحص كل {interval} دقيقة")

        while True:
            try:
                schedule.run_pending()
                time.sleep(30)
            except KeyboardInterrupt:
                logger.info("⛔ إيقاف")
                break
            except Exception as e:
                logger.error(f"❌ خطأ: {e}")
                time.sleep(60)


if __name__ == "__main__":
    bot = SignalBot()
    bot.run()
