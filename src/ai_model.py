import os
import numpy as np
import joblib
import logging
from sklearn.ensemble import (
    RandomForestClassifier,
    GradientBoostingClassifier
)
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
from sklearn.utils.class_weight import compute_class_weight
from src.config import config
from src.indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


class AIModel:

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.safe_name = (
            symbol.replace("=", "_")
            .replace("/", "_")
            .replace(" ", "_")
        )
        self.model = None
        self.scaler = StandardScaler()
        self.features = TechnicalIndicators.get_features()
        self.is_trained = False
        self.model_path = os.path.join(
            config.MODELS_DIR, f"{self.safe_name}_model.pkl"
        )
        self.scaler_path = os.path.join(
            config.MODELS_DIR, f"{self.safe_name}_scaler.pkl"
        )
        os.makedirs(config.MODELS_DIR, exist_ok=True)

    def _prepare_data(self, df, for_prediction=False):
        available = [f for f in self.features if f in df.columns]
        X = df[available].values

        if not for_prediction:
            future = df["Close"].shift(-5)
            y = (future > df["Close"]).astype(int).values
            X = X[:-5]
            y = y[:-5]
            mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
            X, y = X[mask], y[mask]
            X_scaled = self.scaler.fit_transform(X)
            return X_scaled, y
        else:
            X_last = X[-1:].copy()
            if np.isnan(X_last).any():
                X_last = np.nan_to_num(X_last, nan=0.0)
            return self.scaler.transform(X_last)

    def train(self, df) -> bool:
        logger.info(f"🧠 تدريب {self.symbol}...")

        if len(df) < 300:
            logger.error(f"❌ بيانات غير كافية: {len(df)}")
            return False

        X, y = self._prepare_data(df)

        if len(X) < 200:
            logger.error("❌ بيانات بعد التنظيف غير كافية")
            return False

        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        classes = np.unique(y_train)
        weights = compute_class_weight(
            "balanced", classes=classes, y=y_train
        )
        class_weight = dict(zip(classes, weights))

        rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_split=10,
            min_samples_leaf=5,
            n_jobs=-1,
            random_state=42,
            class_weight=class_weight
        )

        gb = GradientBoostingClassifier(
            n_estimators=150,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            random_state=42
        )

        rf.fit(X_train, y_train)
        gb.fit(X_train, y_train)

        avg_proba = (
            rf.predict_proba(X_test)[:, 1] +
            gb.predict_proba(X_test)[:, 1]
        ) / 2

        y_pred = (avg_proba > 0.5).astype(int)
        accuracy = accuracy_score(y_test, y_pred)
        logger.info(f"✅ دقة {self.symbol}: {accuracy:.2%}")

        self.model = {"rf": rf, "gb": gb}
        self.is_trained = True
        self.save()
        return True

    def predict(self, df):
        if not self.is_trained:
            return "HOLD", 0.0
        try:
            X = self._prepare_data(df, for_prediction=True)
            prob = (
                self.model["rf"].predict_proba(X)[0][1] +
                self.model["gb"].predict_proba(X)[0][1]
            ) / 2

            threshold = config.PREDICTION_THRESHOLD
            if prob >= threshold:
                return "BUY", round(prob, 4)
            elif prob <= (1 - threshold):
                return "SELL", round(1 - prob, 4)
            else:
                return "HOLD", round(abs(prob - 0.5) * 2, 4)

        except Exception as e:
            logger.error(f"❌ خطأ التنبؤ {self.symbol}: {e}")
            return "HOLD", 0.0

    def save(self):
        joblib.dump(self.model, self.model_path)
        joblib.dump(self.scaler, self.scaler_path)
        logger.info(f"💾 حفظ {self.symbol}")

    def load(self) -> bool:
        try:
            if (
                os.path.exists(self.model_path) and
                os.path.exists(self.scaler_path)
            ):
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                self.is_trained = True
                logger.info(f"📂 تحميل {self.symbol}")
                return True
        except Exception as e:
            logger.error(f"❌ فشل تحميل {self.symbol}: {e}")
        return False
