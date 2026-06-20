import os
import numpy as np
import joblib
import logging
import warnings
warnings.filterwarnings("ignore")

from sklearn.ensemble import (
    RandomForestClassifier,
    GradientBoostingClassifier,
    VotingClassifier
)
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score
)
from sklearn.utils.class_weight import compute_class_weight

try:
    from xgboost import XGBClassifier
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

from src.config import config
from src.indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


class AIModel:
    """نموذج AI احترافي: RF + GB + XGBoost"""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.safe_name = (
            symbol.replace("=", "_")
            .replace("/", "_")
            .replace(" ", "_")
        )

        self.rf_model  = None
        self.gb_model  = None
        self.xgb_model = None
        self.scaler    = StandardScaler()
        self.features  = TechnicalIndicators.get_features()
        self.is_trained = False
        self.metrics   = {}

        base = os.path.join(config.MODELS_DIR, self.safe_name)
        self.rf_path     = f"{base}_rf.pkl"
        self.gb_path     = f"{base}_gb.pkl"
        self.xgb_path    = f"{base}_xgb.pkl"
        self.scaler_path = f"{base}_scaler.pkl"
        self.metrics_path = f"{base}_metrics.pkl"

        os.makedirs(config.MODELS_DIR, exist_ok=True)

    def _prepare_data(self, df, for_prediction=False):
        """تحضير البيانات"""
        available = [
            f for f in self.features if f in df.columns
        ]
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
            X_last = np.nan_to_num(X[-1:], nan=0.0)
            return self.scaler.transform(X_last)

    def train(self, df) -> bool:
        """تدريب النماذج"""
        logger.info(f"🧠 تدريب {self.symbol}...")

        if len(df) < 500:
            logger.error(f"❌ بيانات غير كافية: {len(df)}")
            return False

        X, y = self._prepare_data(df)

        if len(X) < 200:
            return False

        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        classes = np.unique(y_train)
        weights = compute_class_weight(
            "balanced", classes=classes, y=y_train
        )
        class_weight = dict(zip(classes, weights))

        # ===== Random Forest =====
        logger.info(f"   📊 تدريب Random Forest...")
        self.rf_model = RandomForestClassifier(
            n_estimators=300,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=5,
            max_features="sqrt",
            n_jobs=-1,
            random_state=42,
            class_weight=class_weight
        )
        self.rf_model.fit(X_train, y_train)

        # ===== Gradient Boosting =====
        logger.info(f"   📊 تدريب Gradient Boosting...")
        self.gb_model = GradientBoostingClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_split=10,
            random_state=42
        )
        self.gb_model.fit(X_train, y_train)

        # ===== XGBoost =====
        if XGB_AVAILABLE:
            logger.info(f"   📊 تدريب XGBoost...")
            scale_pos = (
                len(y_train[y_train == 0]) /
                (len(y_train[y_train == 1]) + 1e-10)
            )
            self.xgb_model = XGBClassifier(
                n_estimators=300,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=scale_pos,
                random_state=42,
                eval_metric="logloss",
                verbosity=0
            )
            self.xgb_model.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
                verbose=False
            )

        # ===== التقييم =====
        probs = self._get_weighted_prob(X_test)
        y_pred = (probs > 0.5).astype(int)

        acc  = accuracy_score(y_test, y_pred)
        prec = precision_score(
            y_test, y_pred, zero_division=0
        )
        rec  = recall_score(
            y_test, y_pred, zero_division=0
        )

        self.metrics = {
            "accuracy" : acc,
            "precision": prec,
            "recall"   : rec,
        }

        logger.info(
            f"   ✅ دقة: {acc:.2%} | "
            f"Precision: {prec:.2%} | "
            f"Recall: {rec:.2%}"
        )

        self.is_trained = True
        self.save()
        logger.info(f"✅ اكتمل تدريب {self.symbol}")
        return True

    def _get_weighted_prob(self, X) -> np.ndarray:
        """حساب الاحتمالية الموزونة"""
        probs  = []
        weights = []

        rf_p = self.rf_model.predict_proba(X)[:, 1]
        probs.append(rf_p)
        weights.append(0.30)

        gb_p = self.gb_model.predict_proba(X)[:, 1]
        probs.append(gb_p)
        weights.append(0.30)

        if XGB_AVAILABLE and self.xgb_model is not None:
            xgb_p = self.xgb_model.predict_proba(X)[:, 1]
            probs.append(xgb_p)
            weights.append(0.40)

        total = sum(weights)
        weighted = sum(
            p * w for p, w in zip(probs, weights)
        ) / total

        return weighted

    def predict(self, df) -> tuple:
        """التنبؤ"""
        if not self.is_trained:
            return "HOLD", 0.0

        try:
            X = self._prepare_data(df, for_prediction=True)
            prob = float(self._get_weighted_prob(X)[0])

            threshold = config.PREDICTION_THRESHOLD

            if prob >= threshold:
                signal     = "BUY"
                confidence = round(prob, 4)
            elif prob <= (1 - threshold):
                signal     = "SELL"
                confidence = round(1 - prob, 4)
            else:
                signal     = "HOLD"
                confidence = round(abs(prob - 0.5) * 2, 4)

            models = "RF+GB"
            if XGB_AVAILABLE and self.xgb_model:
                models = "RF+GB+XGB"

            logger.info(
                f"🔮 {self.symbol}: {signal} | "
                f"prob={prob:.4f} | "
                f"conf={confidence:.2%} | "
                f"{models}"
            )

            return signal, confidence

        except Exception as e:
            logger.error(
                f"❌ خطأ التنبؤ {self.symbol}: {e}"
            )
            return "HOLD", 0.0

    def get_feature_importance(self) -> dict:
        """أهم المؤشرات"""
        if not self.is_trained:
            return {}

        available = [
            f for f in self.features
            if f in TechnicalIndicators.get_features()
        ]

        rf_imp = dict(zip(
            available,
            self.rf_model.feature_importances_
        ))

        top = sorted(
            rf_imp.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return dict(top)

    def save(self):
        """حفظ النماذج"""
        try:
            joblib.dump(self.rf_model,  self.rf_path)
            joblib.dump(self.gb_model,  self.gb_path)
            joblib.dump(self.scaler,    self.scaler_path)
            joblib.dump(self.metrics,   self.metrics_path)

            if XGB_AVAILABLE and self.xgb_model:
                joblib.dump(self.xgb_model, self.xgb_path)

            logger.info(f"💾 حفظ نماذج {self.symbol}")
        except Exception as e:
            logger.error(f"❌ فشل الحفظ: {e}")

    def load(self) -> bool:
        """تحميل النماذج"""
        try:
            if not (
                os.path.exists(self.rf_path) and
                os.path.exists(self.gb_path)
            ):
                return False

            self.rf_model = joblib.load(self.rf_path)
            self.gb_model = joblib.load(self.gb_path)
            self.scaler   = joblib.load(self.scaler_path)

            if os.path.exists(self.metrics_path):
                self.metrics = joblib.load(self.metrics_path)

            if (
                XGB_AVAILABLE and
                os.path.exists(self.xgb_path)
            ):
                self.xgb_model = joblib.load(self.xgb_path)
                logger.info(
                    f"📂 تحميل {self.symbol} (RF+GB+XGB)"
                )
            else:
                logger.info(
                    f"📂 تحميل {self.symbol} (RF+GB)"
                )

            self.is_trained = True
            return True

        except Exception as e:
            logger.error(f"❌ فشل تحميل {self.symbol}: {e}")
            return False
