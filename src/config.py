import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    # تيليجرام
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    SEND_SIGNALS = os.getenv("SEND_SIGNALS", "true").lower() == "true"

    # أزواج التداول
    SYMBOLS = {
        "EURUSD=X": {
            "name": "EUR/USD",
            "display": "🇪🇺 EUR/USD",
            "pip": 0.0001,
            "type": "forex"
        },
        "GBPUSD=X": {
            "name": "GBP/USD",
            "display": "🇬🇧 GBP/USD",
            "pip": 0.0001,
            "type": "forex"
        },
        "USDJPY=X": {
            "name": "USD/JPY",
            "display": "🇯🇵 USD/JPY",
            "pip": 0.01,
            "type": "forex"
        },
        "USDCHF=X": {
            "name": "USD/CHF",
            "display": "🇨🇭 USD/CHF",
            "pip": 0.0001,
            "type": "forex"
        },
        "AUDUSD=X": {
            "name": "AUD/USD",
            "display": "🇦🇺 AUD/USD",
            "pip": 0.0001,
            "type": "forex"
        },
        "XAUUSD=X": {
            "name": "GOLD",
            "display": "🥇 GOLD/USD",
            "pip": 0.01,
            "type": "gold"
        },
    }

    # إعدادات البيانات
    TIMEFRAME = "1h"
    TRAIN_DATA_DAYS = int(os.getenv("TRAIN_DATA_DAYS", "365"))
    LOOKBACK_PERIOD = 60

    # إعدادات AI
    PREDICTION_THRESHOLD = float(os.getenv("PREDICTION_THRESHOLD", "0.62"))
    RETRAIN_HOURS = int(os.getenv("RETRAIN_HOURS", "24"))

    # إعدادات الإشارات
    MIN_SIGNAL_SCORE = 3
    ATR_SL_MULTIPLIER = 1.5
    ATR_TP_MULTIPLIER = 3.0

    # إعدادات التشغيل
    SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # مسارات
    MODELS_DIR = "models"
    LOGS_DIR = "logs"
    DATA_DIR = "data"


config = Config()
