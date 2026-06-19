import logging
from datetime import datetime
from src.config import config

logger = logging.getLogger(__name__)


class SignalEngine:

    def analyze(self, symbol, df, ai_signal, ai_confidence):
        last = df.iloc[-1]
        sym_config = config.SYMBOLS.get(symbol, {})

        score_buy = 0
        score_sell = 0

        # RSI
        rsi = last.get("RSI", 50)
        if rsi < 30:
            score_buy += 2
        elif rsi < 45:
            score_buy += 1
        elif rsi > 70:
            score_sell += 2
        elif rsi > 55:
            score_sell += 1

        # MACD
        macd = last.get("MACD", 0)
        macd_sig = last.get("MACD_Signal", 0)
        macd_hist = last.get("MACD_Hist", 0)
        if macd > macd_sig and macd_hist > 0:
            score_buy += 1
        if macd < macd_sig and macd_hist < 0:
            score_sell += 1

        # EMA
        ema20 = last.get("EMA_20", 0)
        ema50 = last.get("EMA_50", 0)
        ema200 = last.get("EMA_200", 0)
        close = last.get("Close", 0)

        if ema20 > ema50 > ema200:
            score_buy += 2
        elif ema20 > ema50:
            score_buy += 1
        if ema20 < ema50 < ema200:
            score_sell += 2
        elif ema20 < ema50:
            score_sell += 1

        # Bollinger
        bb_lower = last.get("BB_Lower", 0)
        bb_upper = last.get("BB_Upper", 0)
        bb_pct = last.get("BB_Pct", 0.5)
        if close <= bb_lower:
            score_buy += 2
        elif bb_pct < 0.2:
            score_buy += 1
        if close >= bb_upper:
            score_sell += 2
        elif bb_pct > 0.8:
            score_sell += 1

        # Stochastic
        stoch_k = last.get("Stoch_K", 50)
        stoch_d = last.get("Stoch_D", 50)
        if stoch_k < 20 and stoch_d < 20:
            score_buy += 1
        elif stoch_k > 80 and stoch_d > 80:
            score_sell += 1

        # AI
        if (ai_signal == "BUY" and
                ai_confidence >= config.PREDICTION_THRESHOLD):
            score_buy += 2
        elif (ai_signal == "SELL" and
              ai_confidence >= config.PREDICTION_THRESHOLD):
            score_sell += 2

        # القرار
        min_score = config.MIN_SIGNAL_SCORE
        if score_buy >= min_score and score_buy > score_sell:
            final_signal = "BUY"
        elif score_sell >= min_score and score_sell > score_buy:
            final_signal = "SELL"
        else:
            final_signal = "HOLD"

        atr = float(last.get("ATR", close * 0.001))
        levels = self._calculate_levels(final_signal, close, atr)

        return {
            "symbol": symbol,
            "symbol_display": sym_config.get("display", symbol),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "signal": final_signal,
            "price": round(close, 5),
            **levels
        }

    def _calculate_levels(self, signal, price, atr):
        sl = atr * config.ATR_SL_MULTIPLIER
        tp1 = atr * config.ATR_TP_MULTIPLIER
        tp2 = atr * config.ATR_TP_MULTIPLIER * 2

        if signal == "BUY":
            return {
                "entry": round(price, 5),
                "sl": round(price - sl, 5),
                "tp1": round(price + tp1, 5),
                "tp2": round(price + tp2, 5),
            }
        elif signal == "SELL":
            return {
                "entry": round(price, 5),
                "sl": round(price + sl, 5),
                "tp1": round(price - tp1, 5),
                "tp2": round(price - tp2, 5),
            }
        else:
            return {
                "entry": None,
                "sl": None,
                "tp1": None,
                "tp2": None,
            }
