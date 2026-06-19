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
            df["EMA_20"] = ta.trend.ema_indicator(
                df["Close"], window=20
            )
            df["EMA_50"] = ta.trend.ema_indicator(
                df["Close"], window=50
            )
            df["EMA_200"] = ta.trend.ema_indicator(
                df["Close"], window=200
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

            stoch = ta.momentum.StochasticOscillator(
                df["High"], df["Low"], df["Close"]
            )
            df["Stoch_K"] = stoch.stoch()
            df["Stoch_D"] = stoch.stoch_signal()

            df["Williams_R"] = ta.momentum.williams_r(
                df["High"], df["Low"], df["Close"]
            )
            df["ROC"] = ta.momentum.roc(df["Close"], window=12)
            df["MFI"] = ta.volume.money_flow_index(
                df["High"], df["Low"],
                df["Close"], df["Volume"],
                window=14
            )

            # Volatility
            bb = ta.volatility.BollingerBands(df["Close"])
            df["BB_Upper"] = bb.bollinger_hband()
            df["BB_Lower"] = bb.bollinger_lband()
            df["BB_Pct"] = bb.bollinger_pband()
            df["BB_Width"] = bb.bollinger_wband()

            df["ATR"] = ta.volatility.average_true_range(
                df["High"], df["Low"], df["Close"], window=14
            )

            # Custom
            df["EMA_Cross"] = np.where(
                df["EMA_20"] > df["EMA_50"], 1, -1
            )
            df["Price_Above_EMA200"] = np.where(
                df["Close"] > df["EMA_200"], 1, 0
            )
            df["Return_1"] = df["Close"].pct_change(1)
            df["Return_5"] = df["Close"].pct_change(5)
            df["Volatility"] = (
                df["Close"].pct_change().rolling(20).std()
            )
            df["Candle_Dir"] = np.where(
                df["Close"] >= df["Open"], 1, -1
            )

            # Time
            df["Hour"] = df.index.hour
            df["Hour_Sin"] = np.sin(2 * np.pi * df["Hour"] / 24)
            df["Hour_Cos"] = np.cos(2 * np.pi * df["Hour"] / 24)

            df.dropna(inplace=True)
            return df

        except Exception as e:
            logger.error(f"❌ خطأ في المؤشرات: {e}")
            return df

    @staticmethod
    def get_features() -> list:
        return [
            "RSI", "MACD", "MACD_Signal", "MACD_Hist",
            "ADX", "ADX_Pos", "ADX_Neg",
            "BB_Pct", "BB_Width", "ATR",
            "Stoch_K", "Stoch_D",
            "Williams_R", "ROC", "MFI",
            "EMA_Cross", "Price_Above_EMA200",
            "Return_1", "Return_5", "Volatility",
            "Candle_Dir", "Hour_Sin", "Hour_Cos",
        ]
