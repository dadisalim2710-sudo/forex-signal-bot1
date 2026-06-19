import json
import os
import logging
from datetime import datetime
from src.config import config

logger = logging.getLogger(__name__)


class PerformanceTracker:

    def __init__(self):
        os.makedirs(config.DATA_DIR, exist_ok=True)
        self.stats_file = os.path.join(
            config.DATA_DIR, "signals_history.json"
        )
        self.stats = self._load()

    def _load(self):
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "total_signals": 0,
            "buy_signals": 0,
            "sell_signals": 0,
            "history": []
        }

    def _save(self):
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"فشل الحفظ: {e}")

    def record_signal(self, signal_data: dict):
        signal = signal_data.get("signal", "HOLD")
        self.stats["total_signals"] += 1

        if signal == "BUY":
            self.stats["buy_signals"] += 1
        elif signal == "SELL":
            self.stats["sell_signals"] += 1

        self.stats["history"].append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "symbol": signal_data.get("symbol"),
            "signal": signal,
            "price": signal_data.get("price"),
            "sl": signal_data.get("sl"),
            "tp1": signal_data.get("tp1"),
        })

        if len(self.stats["history"]) > 500:
            self.stats["history"] = self.stats["history"][-500:]

        self._save()

    def get_summary(self) -> str:
        total = self.stats["total_signals"]
        if total == 0:
            return "لا توجد إشارات بعد"
        return (
            f"📊 إجمالي: {total} | "
            f"🟢 شراء: {self.stats['buy_signals']} | "
            f"🔴 بيع: {self.stats['sell_signals']}"
        )
