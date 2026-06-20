import pandas as pd
import numpy as np
import ta
import logging

logger = logging.getLogger(__name__)


class TechnicalIndicators:

    @staticmethod
    def add_all(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        try:
            # ===== Trend =====
            for w in [9, 20, 50, 100, 200]:
                df[f"EMA_{w}"] = ta.trend.ema_indicator(
                    df["Close"], window=w
                )
            df["SMA_20"] = ta.trend.sma_indicator(
                df["Close"], window=20
            )
            df["SMA_50"] = ta.trend.sma_indicator(
                df["Close"], window=50
            )

            macd = ta.trend.MACD(df["Close"])
            df["MACD"]        = macd.macd()
            df["MACD_Signal"] = macd.macd_signal()
            df["MACD_Hist"]   = macd.macd_diff()

            adx = ta.trend.ADXIndicator(
                df["High"], df["Low"], df["Close"]
            )
            df["ADX"]     = adx.adx()
            df["ADX_Pos"] = adx.adx_pos()
            df["ADX_Neg"] = adx.adx_neg()

            # Ichimoku
            ich = ta.trend.IchimokuIndicator(
                df["High"], df["Low"]
            )
            df["Ich_A"]    = ich.ichimoku_a()
            df["Ich_B"]    = ich.ichimoku_b()
            df["Ich_Base"] = ich.ichimoku_base_line()
            df["Ich_Conv"] = ich.ichimoku_conversion_line()

            # ===== Momentum =====
            df["RSI"]   = ta.momentum.rsi(df["Close"], window=14)
            df["RSI_6"] = ta.momentum.rsi(df["Close"], window=6)

            stoch = ta.momentum.StochasticOscillator(
                df["High"], df["Low"], df["Close"]
            )
            df["Stoch_K"] = stoch.stoch()
            df["Stoch_D"] = stoch.stoch_signal()

            df["Williams_R"] = ta.momentum.williams_r(
                df["High"], df["Low"], df["Close"]
            )
            for w in [5, 10, 12, 20]:
                df[f"ROC_{w}"] = ta.momentum.roc(
                    df["Close"], window=w
                )

            try:
                df["MFI"] = ta.volume.money_flow_index(
                    df["High"], df["Low"],
                    df["Close"], df["Volume"], window=14
                )
            except Exception:
                df["MFI"] = 50.0

            # CCI
            df["CCI"] = ta.trend.cci(
                df["High"], df["Low"], df["Close"], window=20
            )

            # ===== Volatility =====
            bb = ta.volatility.BollingerBands(df["Close"])
            df["BB_Upper"] = bb.bollinger_hband()
            df["BB_Lower"] = bb.bollinger_lband()
            df["BB_Mid"]   = bb.bollinger_mavg()
            df["BB_Pct"]   = bb.bollinger_pband()
            df["BB_Width"] = bb.bollinger_wband()

            df["ATR"] = ta.volatility.average_true_range(
                df["High"], df["Low"], df["Close"], window=14
            )
            df["ATR_Ratio"] = df["ATR"] / (df["Close"] + 1e-10)

            kc = ta.volatility.KeltnerChannel(
                df["High"], df["Low"], df["Close"]
            )
            df["KC_Upper"] = kc.keltner_channel_hband()
            df["KC_Lower"] = kc.keltner_channel_lband()
            df["KC_Pct"] = (df["Close"] - df["KC_Lower"]) / (
                df["KC_Upper"] - df["KC_Lower"] + 1e-10
            )

            # Squeeze Momentum
            df["Squeeze"] = np.where(
                (df["BB_Upper"] < df["KC_Upper"]) &
                (df["BB_Lower"] > df["KC_Lower"]),
                1, 0
            )

            # ===== Volume =====
            try:
                df["OBV"] = ta.volume.on_balance_volume(
                    df["Close"], df["Volume"]
                )
                df["OBV_EMA"] = ta.trend.ema_indicator(
                    df["OBV"], window=20
                )
                df["OBV_Trend"] = np.where(
                    df["OBV"] > df["OBV_EMA"], 1, -1
                )
            except Exception:
                df["OBV_Trend"] = 0

            # ===== Price Action =====
            df["EMA_Cross_9_20"] = np.where(
                df["EMA_9"] > df["EMA_20"], 1, -1
            )
            df["EMA_Cross_20_50"] = np.where(
                df["EMA_20"] > df["EMA_50"], 1, -1
            )
            df["EMA_Cross_50_200"] = np.where(
                df["EMA_50"] > df["EMA_200"], 1, -1
            )
            df["Price_Above_EMA200"] = np.where(
                df["Close"] > df["EMA_200"], 1, 0
            )
            df["Price_Above_SMA50"] = np.where(
                df["Close"] > df["SMA_50"], 1, 0
            )

            # Golden/Death Cross
            df["Golden_Cross"] = np.where(
                (df["EMA_50"] > df["EMA_200"]) &
                (df["EMA_50"].shift(1) <= df["EMA_200"].shift(1)),
                1, 0
            )
            df["Death_Cross"] = np.where(
                (df["EMA_50"] < df["EMA_200"]) &
                (df["EMA_50"].shift(1) >= df["EMA_200"].shift(1)),
                1, 0
            )

            # ===== Returns =====
            for p in [1, 2, 3, 5, 10, 20]:
                df[f"Return_{p}"] = df["Close"].pct_change(p)

            for w in [5, 10, 20]:
                df[f"Volatility_{w}"] = (
                    df["Close"].pct_change().rolling(w).std()
                )

            # ===== Candle Patterns =====
            df["Candle_Dir"] = np.where(
                df["Close"] >= df["Open"], 1, -1
            )
            df["Candle_Body"] = abs(df["Close"] - df["Open"])
            df["Candle_Range"] = df["High"] - df["Low"]
            df["Candle_Body_Ratio"] = (
                df["Candle_Body"] /
                (df["Candle_Range"] + 1e-10)
            )
            df["Upper_Wick"] = (
                df["High"] -
                df[["Open", "Close"]].max(axis=1)
            )
            df["Lower_Wick"] = (
                df[["Open", "Close"]].min(axis=1) - df["Low"]
            )

            # أنماط الشموع
            df["Is_Doji"] = np.where(
                df["Candle_Body_Ratio"] < 0.1, 1, 0
            )
            df["Is_Hammer"] = np.where(
                (df["Lower_Wick"] > 2 * df["Candle_Body"]) &
                (df["Upper_Wick"] < df["Candle_Body"]) &
                (df["Candle_Dir"] == 1),
                1, 0
            )
            df["Is_Shooting_Star"] = np.where(
                (df["Upper_Wick"] > 2 * df["Candle_Body"]) &
                (df["Lower_Wick"] < df["Candle_Body"]) &
                (df["Candle_Dir"] == -1),
                1, 0
            )
            df["Is_Engulfing_Bull"] = np.where(
                (df["Candle_Dir"] == 1) &
                (df["Candle_Dir"].shift(1) == -1) &
                (df["Close"] > df["Open"].shift(1)) &
                (df["Open"] < df["Close"].shift(1)),
                1, 0
            )
            df["Is_Engulfing_Bear"] = np.where(
                (df["Candle_Dir"] == -1) &
                (df["Candle_Dir"].shift(1) == 1) &
                (df["Close"] < df["Open"].shift(1)) &
                (df["Open"] > df["Close"].shift(1)),
                1, 0
            )

            # ===== Support & Resistance =====
            df["Pivot"] = (
                df["High"].shift(1) +
                df["Low"].shift(1) +
                df["Close"].shift(1)
            ) / 3
            df["R1"] = 2 * df["Pivot"] - df["Low"].shift(1)
            df["S1"] = 2 * df["Pivot"] - df["High"].shift(1)
            df["R2"] = df["Pivot"] + (
                df["High"].shift(1) - df["Low"].shift(1)
            )
            df["S2"] = df["Pivot"] - (
                df["High"].shift(1) - df["Low"].shift(1)
            )
            df["Dist_R1"] = (
                (df["R1"] - df["Close"]) /
                (df["Close"] + 1e-10)
            )
            df["Dist_S1"] = (
                (df["Close"] - df["S1"]) /
                (df["Close"] + 1e-10)
            )

            # ===== Time & Sessions =====
            df["Hour"]      = df.index.hour
            df["DayOfWeek"] = df.index.dayofweek
            df["Hour_Sin"]  = np.sin(2 * np.pi * df["Hour"] / 24)
            df["Hour_Cos"]  = np.cos(2 * np.pi * df["Hour"] / 24)
            df["Day_Sin"]   = np.sin(
                2 * np.pi * df["DayOfWeek"] / 7
            )
            df["Day_Cos"]   = np.cos(
                2 * np.pi * df["DayOfWeek"] / 7
            )

            df["Session_Tokyo"]   = np.where(
                df["Hour"].between(0, 8), 1, 0
            )
            df["Session_London"]  = np.where(
                df["Hour"].between(8, 16), 1, 0
            )
            df["Session_NewYork"] = np.where(
                df["Hour"].between(13, 21), 1, 0
            )
            df["Session_Overlap"] = np.where(
                df["Hour"].between(13, 16), 1, 0
            )

            # ===== Market Regime =====
            df["Market_Trend"] = np.where(
                df["ADX"] > 25, 1, 0
            )
            df["Market_Strong_Trend"] = np.where(
                df["ADX"] > 40, 1, 0
            )
            df["Market_Bull"] = np.where(
                (df["EMA_20"] > df["EMA_50"]) &
                (df["EMA_50"] > df["EMA_200"]),
                1, 0
            )
            df["Market_Bear"] = np.where(
                (df["EMA_20"] < df["EMA_50"]) &
                (df["EMA_50"] < df["EMA_200"]),
                1, 0
            )

            df.dropna(inplace=True)
            logger.info(
                f"✅ المؤشرات جاهزة: {len(df)} شمعة | "
                f"{len(df.columns)} مؤشر"
            )
            return df

        except Exception as e:
            logger.error(f"❌ خطأ في المؤشرات: {e}")
            return df

    @staticmethod
    def get_features() -> list:
        return [
            # Trend
            "EMA_Cross_9_20", "EMA_Cross_20_50",
            "EMA_Cross_50_200",
            "Price_Above_EMA200", "Price_Above_SMA50",
            "Golden_Cross", "Death_Cross",
            "ADX", "ADX_Pos", "ADX_Neg",
            "Ich_A", "Ich_B",

            # Momentum
            "RSI", "RSI_6",
            "MACD", "MACD_Signal", "MACD_Hist",
            "Stoch_K", "Stoch_D",
            "Williams_R",
            "ROC_5", "ROC_10", "ROC_12", "ROC_20",
            "MFI", "CCI",

            # Volatility
            "BB_Pct", "BB_Width",
            "ATR_Ratio", "KC_Pct", "Squeeze",

            # Volume
            "OBV_Trend",

            # Returns
            "Return_1", "Return_2", "Return_3",
            "Return_5", "Return_10", "Return_20",
            "Volatility_5", "Volatility_10", "Volatility_20",

            # Candle
            "Candle_Dir", "Candle_Body_Ratio",
            "Is_Doji", "Is_Hammer", "Is_Shooting_Star",
            "Is_Engulfing_Bull", "Is_Engulfing_Bear",

            # S&R
            "Dist_R1", "Dist_S1",

            # Time
            "Hour_Sin", "Hour_Cos",
            "Day_Sin", "Day_Cos",
            "Session_Tokyo", "Session_London",
            "Session_NewYork", "Session_Overlap",

            # Market Regime
            "Market_Trend", "Market_Strong_Trend",
            "Market_Bull", "Market_Bear",
        ]

    @staticmethod
    def get_trend_direction(df: pd.DataFrame) -> str:
        """تحديد اتجاه السوق"""
        last = df.iloc[-1]

        ema20  = last.get("EMA_20", 0)
        ema50  = last.get("EMA_50", 0)
        ema200 = last.get("EMA_200", 0)
        adx    = last.get("ADX", 0)
        close  = last.get("Close", 0)

        if (ema20 > ema50 > ema200 and
                close > ema200 and adx > 25):
            return "STRONG_BULL"
        elif ema20 > ema50 and close > ema50:
            return "BULL"
        elif (ema20 < ema50 < ema200 and
              close < ema200 and adx > 25):
            return "STRONG_BEAR"
        elif ema20 < ema50 and close < ema50:
            return "BEAR"
        else:
            return "NEUTRAL"

    @staticmethod
    def get_market_regime(df: pd.DataFrame) -> str:
        """تحديد نوع السوق"""
        last = df.iloc[-1]
        adx      = last.get("ADX", 20)
        bb_width = last.get("BB_Width", 0.05)

        if adx > 40:
            return "STRONG_TREND"
        elif adx > 25:
            return "TREND"
        elif bb_width < 0.01:
            return "SQUEEZE"
        elif bb_width > 0.05:
            return "HIGH_VOLATILITY"
        else:
            return "RANGE"
