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

        # حساب المستويات بالـ Pips
        pip = sym_config.get("pip", 0.0001)
        levels = self._calculate_levels(
            final_signal, close, pip
        )

        return {
            "symbol": symbol,
            "symbol_display": sym_config.get("display", symbol),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "signal": final_signal,
            "price": round(close, 5),
            "score_buy": score_buy,
            "score_sell": score_sell,
            **levels
        }

    def _calculate_levels(self, signal, price, pip):
        """
        حساب المستويات بالـ Pips الثابتة:
        وقف الخسارة  = 50 pip
        الهدف الأول  = 100 pip
        الهدف الثاني = 200 pip
        الهدف الثالث = 300 pip
        """

        sl_pips   = config.SL_PIPS    # 50
        tp1_pips  = config.TP1_PIPS   # 100
        tp2_pips  = config.TP2_PIPS   # 200
        tp3_pips  = config.TP3_PIPS   # 300

        sl_distance  = sl_pips  * pip
        tp1_distance = tp1_pips * pip
        tp2_distance = tp2_pips * pip
        tp3_distance = tp3_pips * pip

        if signal == "BUY":
            return {
                "entry" : round(price, 5),
                "sl"    : round(price - sl_distance,  5),
                "tp1"   : round(price + tp1_distance, 5),
                "tp2"   : round(price + tp2_distance, 5),
                "tp3"   : round(price + tp3_distance, 5),
                "sl_pips" : sl_pips,
                "tp1_pips": tp1_pips,
                "tp2_pips": tp2_pips,
                "tp3_pips": tp3_pips,
            }
        elif signal == "SELL":
            return {
                "entry" : round(price, 5),
                "sl"    : round(price + sl_distance,  5),
                "tp1"   : round(price - tp1_distance, 5),
                "tp2"   : round(price - tp2_distance, 5),
                "tp3"   : round(price - tp3_distance, 5),
                "sl_pips" : sl_pips,
                "tp1_pips": tp1_pips,
                "tp2_pips": tp2_pips,
                "tp3_pips": tp3_pips,
            }
        else:
            return {
                "entry"   : None,
                "sl"      : None,
                "tp1"     : None,
                "tp2"     : None,
                "tp3"     : None,
                "sl_pips" : None,
                "tp1_pips": None,
                "tp2_pips": None,
                "tp3_pips": None,
            }
