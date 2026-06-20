import logging
from datetime import datetime
from src.config import config
from src.indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


class SignalEngine:

    def analyze(
        self, symbol, df, ai_signal, ai_confidence,
        mtf_data: dict = None
    ):
        """تحليل شامل مع Multi-Timeframe"""

        last       = df.iloc[-1]
        sym_config = config.SYMBOLS.get(symbol, {})
        pip        = sym_config.get("pip", 0.0001)

        # نقاط الإشارة
        score_buy  = 0
        score_sell = 0

        # ===== RSI =====
        rsi = last.get("RSI", 50)
        if rsi < 25:
            score_buy += 3
        elif rsi < 35:
            score_buy += 2
        elif rsi < 45:
            score_buy += 1
        elif rsi > 75:
            score_sell += 3
        elif rsi > 65:
            score_sell += 2
        elif rsi > 55:
            score_sell += 1

        # ===== MACD =====
        macd      = last.get("MACD", 0)
        macd_sig  = last.get("MACD_Signal", 0)
        macd_hist = last.get("MACD_Hist", 0)
        prev_hist = df["MACD_Hist"].iloc[-2] if len(df) > 2 else 0

        if macd > macd_sig and macd_hist > 0:
            score_buy += 1
        if macd_hist > 0 and prev_hist < 0:
            score_buy += 2
        if macd < macd_sig and macd_hist < 0:
            score_sell += 1
        if macd_hist < 0 and prev_hist > 0:
            score_sell += 2

        # ===== EMA =====
        ema20  = last.get("EMA_20", 0)
        ema50  = last.get("EMA_50", 0)
        ema200 = last.get("EMA_200", 0)
        close  = last.get("Close", 0)

        if ema20 > ema50 > ema200:
            score_buy += 2
        elif ema20 > ema50:
            score_buy += 1
        if ema20 < ema50 < ema200:
            score_sell += 2
        elif ema20 < ema50:
            score_sell += 1

        # ===== Bollinger =====
        bb_lower = last.get("BB_Lower", 0)
        bb_upper = last.get("BB_Upper", 0)
        bb_pct   = last.get("BB_Pct", 0.5)

        if close <= bb_lower:
            score_buy += 2
        elif bb_pct < 0.2:
            score_buy += 1
        if close >= bb_upper:
            score_sell += 2
        elif bb_pct > 0.8:
            score_sell += 1

        # ===== Stochastic =====
        stoch_k = last.get("Stoch_K", 50)
        stoch_d = last.get("Stoch_D", 50)
        if stoch_k < 20 and stoch_d < 20:
            score_buy += 1
        elif stoch_k > 80 and stoch_d > 80:
            score_sell += 1

        # ===== ADX =====
        adx = last.get("ADX", 0)
        adx_pos = last.get("ADX_Pos", 0)
        adx_neg = last.get("ADX_Neg", 0)
        if adx > 25:
            if adx_pos > adx_neg:
                score_buy += 1
            else:
                score_sell += 1

        # ===== Candle Patterns =====
        if last.get("Is_Hammer", 0) == 1:
            score_buy += 2
        if last.get("Is_Engulfing_Bull", 0) == 1:
            score_buy += 2
        if last.get("Is_Shooting_Star", 0) == 1:
            score_sell += 2
        if last.get("Is_Engulfing_Bear", 0) == 1:
            score_sell += 2

        # ===== Market Regime =====
        regime    = TechnicalIndicators.get_market_regime(df)
        direction = TechnicalIndicators.get_trend_direction(df)

        # ===== Multi-Timeframe =====
        mtf_score_buy  = 0
        mtf_score_sell = 0
        mtf_confirmed  = False

        if mtf_data and config.REQUIRE_MTF:
            for tf, df_tf in mtf_data.items():
                if df_tf is None or len(df_tf) < 50:
                    continue
                try:
                    from src.indicators import TechnicalIndicators as TI
                    df_tf = TI.add_all(df_tf)
                    tf_dir = TI.get_trend_direction(df_tf)
                    if "BULL" in tf_dir:
                        mtf_score_buy += 1
                    elif "BEAR" in tf_dir:
                        mtf_score_sell += 1
                except Exception:
                    pass

            if mtf_score_buy >= 2:
                score_buy += 2
                mtf_confirmed = True
            elif mtf_score_sell >= 2:
                score_sell += 2
                mtf_confirmed = True

        # ===== AI =====
        if (ai_signal == "BUY" and
                ai_confidence >= config.PREDICTION_THRESHOLD):
            score_buy += 3
        elif (ai_signal == "SELL" and
              ai_confidence >= config.PREDICTION_THRESHOLD):
            score_sell += 3

        # ===== القرار =====
        min_score = config.MIN_SIGNAL_SCORE

        if score_buy >= min_score and score_buy > score_sell:
            final_signal = "BUY"
        elif score_sell >= min_score and score_sell > score_buy:
            final_signal = "SELL"
        else:
            final_signal = "HOLD"

        # فلتر: لا إشارة في سوق عالي التقلب بدون تأكيد
        if (regime == "HIGH_VOLATILITY" and
                not mtf_confirmed and
                final_signal != "HOLD"):
            if ai_confidence < 0.70:
                final_signal = "HOLD"
                logger.info(
                    f"⚠️ {symbol}: تجاهل الإشارة - تقلب عالٍ"
                )

        # ===== المستويات =====
        levels = self._calculate_levels(
            final_signal, close, pip
        )

        return {
            "symbol"        : symbol,
            "symbol_display": sym_config.get("display", symbol),
            "time"          : datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            ),
            "signal"        : final_signal,
            "price"         : round(close, 5),
            "score_buy"     : score_buy,
            "score_sell"    : score_sell,
            "ai_signal"     : ai_signal,
            "ai_confidence" : round(ai_confidence * 100, 1),
            "regime"        : regime,
            "direction"     : direction,
            "mtf_confirmed" : mtf_confirmed,
            **levels
        }

    def _calculate_levels(self, signal, price, pip):
        """حساب المستويات بالـ Pips"""

        sl_dist  = config.SL_PIPS  * pip
        tp1_dist = config.TP1_PIPS * pip
        tp2_dist = config.TP2_PIPS * pip
        tp3_dist = config.TP3_PIPS * pip

        if signal == "BUY":
            return {
                "entry"    : round(price, 5),
                "sl"       : round(price - sl_dist,  5),
                "tp1"      : round(price + tp1_dist, 5),
                "tp2"      : round(price + tp2_dist, 5),
                "tp3"      : round(price + tp3_dist, 5),
                "sl_pips"  : config.SL_PIPS,
                "tp1_pips" : config.TP1_PIPS,
                "tp2_pips" : config.TP2_PIPS,
                "tp3_pips" : config.TP3_PIPS,
            }
        elif signal == "SELL":
            return {
                "entry"    : round(price, 5),
                "sl"       : round(price + sl_dist,  5),
                "tp1"      : round(price - tp1_dist, 5),
                "tp2"      : round(price - tp2_dist, 5),
                "tp3"      : round(price - tp3_dist, 5),
                "sl_pips"  : config.SL_PIPS,
                "tp1_pips" : config.TP1_PIPS,
                "tp2_pips" : config.TP2_PIPS,
                "tp3_pips" : config.TP3_PIPS,
            }
        else:
            return {
                "entry"    : None,
                "sl"       : None,
                "tp1"      : None,
                "tp2"      : None,
                "tp3"      : None,
                "sl_pips"  : None,
                "tp1_pips" : None,
                "tp2_pips" : None,
                "tp3_pips" : None,
            }
