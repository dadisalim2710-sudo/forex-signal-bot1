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
            # Trend
            df["EMA_9"] = ta.trend.ema_indicator(
                df["Close"], window=9
            )
            df["EMA_20"] = ta.trend.ema_indicator(
                df["Close"], window=20
            )
            df["EMA_50"] = ta.trend.ema_indicator(
                df["Close"], window=50
            )
            df["EMA_200"] = ta.trend.ema_indicator(
                df["Close"], window=200
            )
            df["SMA_20"] = ta.trend.sma_indicator(
                df["Close"], window=20
            )

            macd = ta.trend.MACD(df["Close"])
            df["MACD"] = macd.macd()
            df["MACD_Signal"] = macd.macd_signal()
            df["MACD_Hist"] = macd.macd_diff()

            adx = ta.trend.ADXIndicator(
                df["High"], df["Low"], df["Close"]
            )
            df["ADX"] = adx.adx()
            df["ADX_Pos"] = adx.adx_pos()
            df["ADX_Neg"] = adx.adx_neg()

            # Momentum
            df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
            df["RSI_6"] = ta.momentum.rsi(df["Close"], window=6)

            stoch = ta.momentum.StochasticOscillator(
                df["High"], df["Low"], df["Close"]
            )
            df["Stoch_K"] = stoch.stoch()
            df["Stoch_D"] = stoch.stoch_signal()

            df["Williams_R"] = ta.momentum.williams_r(
                df["High"], df["Low"], df["Close"]
            )
            df["ROC"] = ta.momentum.roc(df["Close"], window=12)
            df["ROC_5"] = ta.momentum.roc(df["Close"], window=5)

            # MFI يحتاج Volume - نتجنب الخطأ
            try:
                df["MFI"] = ta.volume.money_flow_index(
                    df["High"], df["Low"],
                    df["Close"], df["Volume"],
                    window=14
                )
            except Exception:
                df["MFI"] = 50.0  # قيمة محايدة

            # Volatility
            bb = ta.volatility.BollingerBands(df["Close"])
            df["BB_Upper"] = bb.bollinger_hband()
            df["BB_Lower"] = bb.bollinger_lband()
            df["BB_Pct"] = bb.bollinger_pband()
            df["BB_Width"] = bb.bollinger_wband()

            df["ATR"] = ta.volatility.average_true_range(
                df["High"], df["Low"], df["Close"], window=14
            )
            df["ATR_Ratio"] = df["ATR"] / (df["Close"] + 1e-10)

            # OBV - يحتاج Volume
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
                df["OBV_Trend"] = 0  # قيمة محايدة

            # Custom
            df["EMA_Cross_9_20"] = np.where(
                df["EMA_9"] > df["EMA_20"], 1, -1
            )
            df["EMA_Cross_20_50"] = np.where(
                df["EMA_20"] > df["EMA_50"], 1, -1
            )
            df["Price_Above_EMA200"] = np.where(
                df["Close"] > df["EMA_200"], 1, 0
            )
            df["Price_Above_SMA20"] = np.where(
                df["Close"] > df["SMA_20"], 1, 0
            )

            # Returns
            for p in [1, 2, 3, 5, 10]:
                df[f"Return_{p}"] = df["Close"].pct_change(p)

            df["Volatility_10"] = (
                df["Close"].pct_change().rolling(10).std()
            )
            df["Volatility_20"] = (
                df["Close"].pct_change().rolling(20).std()
            )

            # Candle
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
            df["Is_Doji"] = np.where(
                df["Candle_Body_Ratio"] < 0.1, 1, 0
            )
            df["Is_Hammer"] = np.where(
                (df["Lower_Wick"] > 2 * df["Candle_Body"]) &
                (df["Upper_Wick"] < df["Candle_Body"]),
                1, 0
            )
            df["Is_Shooting_Star"] = np.where(
                (df["Upper_Wick"] > 2 * df["Candle_Body"]) &
                (df["Lower_Wick"] < df["Candle_Body"]),
                1, 0
            )

            # Support & Resistance
            df["Pivot"] = (
                df["High"].shift(1) +
                df["Low"].shift(1) +
                df["Close"].shift(1)
            ) / 3
            df["R1"] = 2 * df["Pivot"] - df["Low"].shift(1)
            df["S1"] = 2 * df["Pivot"] - df["High"].shift(1)
            df["Dist_R1"] = (
                (df["R1"] - df["Close"]) /
                (df["Close"] + 1e-10)
            )
            df["Dist_S1"] = (
                (df["Close"] - df["S1"]) /
                (df["Close"] + 1e-10)
            )

            # Time
            df["Hour"] = df.index.hour
            df["DayOfWeek"] = df.index.dayofweek
            df["Hour_Sin"] = np.sin(2 * np.pi * df["Hour"] / 24)
            df["Hour_Cos"] = np.cos(2 * np.pi * df["Hour"] / 24)
            df["Day_Sin"] = np.sin(
                2 * np.pi * df["DayOfWeek"] / 7
            )
            df["Day_Cos"] = np.cos(
                2 * np.pi * df["DayOfWeek"] / 7
            )

            # Sessions
            df["Session_Tokyo"] = np.where(
                df["Hour"].between(0, 8), 1, 0
            )
            df["Session_London"] = np.where(
                df["Hour"].between(8, 16), 1, 0
            )
            df["Session_NewYork"] = np.where(
                df["Hour"].between(13, 21), 1, 0
            )

            df.dropna(inplace=True)
            logger.info(
                f"✅ المؤشرات جاهزة: {len(df)} شمعة"
            )
            return df

        except Exception as e:
            logger.error(f"❌ خطأ في المؤشرات: {e}")
            return df

    @staticmethod
    def get_features() -> list:
        return [
            "EMA_Cross_9_20", "EMA_Cross_20_50",
            "Price_Above_EMA200", "Price_Above_SMA20",
            "ADX", "ADX_Pos", "ADX_Neg",
            "RSI", "RSI_6",
            "MACD", "MACD_Signal", "MACD_Hist",
            "Stoch_K", "Stoch_D",
            "Williams_R", "ROC", "ROC_5", "MFI",
            "BB_Pct", "BB_Width", "ATR_Ratio",
            "OBV_Trend",
            "Return_1", "Return_2", "Return_3",
            "Return_5", "Return_10",
            "Volatility_10", "Volatility_20",
            "Candle_Dir", "Candle_Body_Ratio",
            "Is_Doji", "Is_Hammer", "Is_Shooting_Star",
            "Dist_R1", "Dist_S1",
            "Hour_Sin", "Hour_Cos",
            "Day_Sin", "Day_Cos",
            "Session_Tokyo", "Session_London",
            "Session_NewYork",
        ]

    @staticmethod
    def get_sequence_features() -> list:
        return [
            "RSI", "MACD_Hist", "ADX",
            "BB_Pct", "ATR_Ratio",
            "EMA_Cross_20_50", "Price_Above_EMA200",
            "Return_1", "Return_5",
            "Candle_Dir", "Candle_Body_Ratio",
            "OBV_Trend", "Stoch_K",
            "Hour_Sin", "Hour_Cos",
        ]
