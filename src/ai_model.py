import os
import numpy as np
import joblib
import logging
import warnings
warnings.filterwarnings("ignore")

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

# ==========================================
# تحميل TensorFlow بشكل آمن
# ==========================================
DISABLE_LSTM = os.getenv("DISABLE_LSTM", "false").lower() == "true"

try:
    if DISABLE_LSTM:
        raise ImportError("LSTM معطل يدوياً")
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import (
        LSTM, Dense, Dropout, BatchNormalization
    )
    from tensorflow.keras.callbacks import EarlyStopping
    from tensorflow.keras.optimizers import Adam
    tf.get_logger().setLevel("ERROR")
    LSTM_AVAILABLE = True
    logger.info("✅ TensorFlow متاح - LSTM مفعّل")
except ImportError:
    LSTM_AVAILABLE = False
    logger.warning("⚠️ LSTM معطل - يعمل بـ RF+GB فقط")


class AIModel:
    """نموذج AI متطور: RF + GB + LSTM"""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.safe_name = (
            symbol.replace("=", "_")
            .replace("/", "_")
            .replace(" ", "_")
        )

        # النماذج
        self.rf_model = None
        self.gb_model = None
        self.lstm_model = None

        # المعالجات
        self.scaler_ml = StandardScaler()
        self.scaler_lstm = StandardScaler()

        # الخصائص
        self.features_ml = TechnicalIndicators.get_features()
        self.features_lstm = TechnicalIndicators.get_sequence_features()

        self.is_trained = False
        self.lstm_enabled = LSTM_AVAILABLE
        self.lookback = 24  # 24 شمعة = يوم كامل

        # مسارات الحفظ
        base = os.path.join(config.MODELS_DIR, self.safe_name)
        self.rf_path = f"{base}_rf.pkl"
        self.gb_path = f"{base}_gb.pkl"
        self.scaler_ml_path = f"{base}_scaler_ml.pkl"
        self.scaler_lstm_path = f"{base}_scaler_lstm.pkl"
        self.lstm_path = f"{base}_lstm.keras"

        os.makedirs(config.MODELS_DIR, exist_ok=True)

    # ==========================================
    # تحضير بيانات ML
    # ==========================================
    def _prepare_ml_data(self, df, for_prediction=False):
        """بيانات Random Forest و Gradient Boosting"""
        available = [
            f for f in self.features_ml if f in df.columns
        ]
        X = df[available].values

        if not for_prediction:
            future = df["Close"].shift(-5)
            y = (future > df["Close"]).astype(int).values
            X = X[:-5]
            y = y[:-5]
            mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
            X, y = X[mask], y[mask]
            X_scaled = self.scaler_ml.fit_transform(X)
            return X_scaled, y
        else:
            X_last = np.nan_to_num(X[-1:], nan=0.0)
            return self.scaler_ml.transform(X_last)

    # ==========================================
    # تحضير بيانات LSTM
    # ==========================================
    def _prepare_lstm_data(self, df, for_prediction=False):
        """بيانات LSTM - تسلسل زمني"""
        available = [
            f for f in self.features_lstm if f in df.columns
        ]
        X = df[available].values

        if not for_prediction:
            future = df["Close"].shift(-5)
            y = (future > df["Close"]).astype(int).values

            X_scaled = self.scaler_lstm.fit_transform(X)

            sequences = []
            targets = []

            for i in range(self.lookback, len(X_scaled) - 5):
                sequences.append(
                    X_scaled[i - self.lookback:i]
                )
                targets.append(y[i])

            return np.array(sequences), np.array(targets)

        else:
            X_scaled = self.scaler_lstm.transform(X)

            if len(X_scaled) < self.lookback:
                pad = np.zeros((
                    self.lookback - len(X_scaled),
                    X_scaled.shape[1]
                ))
                X_scaled = np.vstack([pad, X_scaled])

            return X_scaled[-self.lookback:].reshape(
                1, self.lookback, -1
            )

    # ==========================================
    # بناء نموذج LSTM
    # ==========================================
    def _build_lstm(self, input_shape):
        """بناء LSTM خفيف"""
        model = Sequential([
            LSTM(
                64,
                input_shape=input_shape,
                return_sequences=True,
                dropout=0.2
            ),
            BatchNormalization(),

            LSTM(
                32,
                return_sequences=False,
                dropout=0.2
            ),
            BatchNormalization(),

            Dense(32, activation="relu"),
            Dropout(0.2),

            Dense(16, activation="relu"),
            Dropout(0.1),

            Dense(1, activation="sigmoid")
        ])

        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss="binary_crossentropy",
            metrics=["accuracy"]
        )
        return model

    # ==========================================
    # التدريب
    # ==========================================
    def train(self, df) -> bool:
        """تدريب كل النماذج"""
        logger.info(f"🧠 تدريب {self.symbol}...")

        if len(df) < 500:
            logger.error(
                f"❌ بيانات غير كافية: {len(df)} (نحتاج 500+)"
            )
            return False

        # ===== 1. تدريب RF + GB =====
        logger.info(f"   📊 تدريب RF + GB...")
        X_ml, y_ml = self._prepare_ml_data(df)

        if len(X_ml) < 200:
            logger.error("❌ بيانات ML غير كافية")
            return False

        split = int(len(X_ml) * 0.8)
        X_train, X_test = X_ml[:split], X_ml[split:]
        y_train, y_test = y_ml[:split], y_ml[split:]

        classes = np.unique(y_train)
        weights = compute_class_weight(
            "balanced", classes=classes, y=y_train
        )
        class_weight = dict(zip(classes, weights))

        # Random Forest
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

        # Gradient Boosting
        self.gb_model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_split=10,
            random_state=42
        )
        self.gb_model.fit(X_train, y_train)

        # دقة ML
        rf_prob = self.rf_model.predict_proba(X_test)[:, 1]
        gb_prob = self.gb_model.predict_proba(X_test)[:, 1]
        ml_prob = (rf_prob + gb_prob) / 2
        ml_pred = (ml_prob > 0.5).astype(int)
        ml_acc = accuracy_score(y_test, ml_pred)
        logger.info(f"   ✅ دقة RF+GB: {ml_acc:.2%}")

        # ===== 2. تدريب LSTM =====
        if self.lstm_enabled:
            logger.info(f"   🔮 تدريب LSTM...")
            try:
                X_lstm, y_lstm = self._prepare_lstm_data(df)

                if len(X_lstm) < 200:
                    logger.warning(
                        "⚠️ بيانات LSTM قليلة - تخطي"
                    )
                    self.lstm_enabled = False
                else:
                    split_l = int(len(X_lstm) * 0.8)
                    Xl_train = X_lstm[:split_l]
                    Xl_test = X_lstm[split_l:]
                    yl_train = y_lstm[:split_l]
                    yl_test = y_lstm[split_l:]

                    self.lstm_model = self._build_lstm(
                        (X_lstm.shape[1], X_lstm.shape[2])
                    )

                    early_stop = EarlyStopping(
                        monitor="val_loss",
                        patience=5,
                        restore_best_weights=True,
                        verbose=0
                    )

                    self.lstm_model.fit(
                        Xl_train, yl_train,
                        epochs=30,
                        batch_size=32,
                        validation_data=(Xl_test, yl_test),
                        callbacks=[early_stop],
                        verbose=0
                    )

                    lstm_pred = (
                        self.lstm_model.predict(
                            Xl_test, verbose=0
                        ) > 0.5
                    ).astype(int).flatten()

                    lstm_acc = accuracy_score(
                        yl_test, lstm_pred
                    )
                    logger.info(
                        f"   ✅ دقة LSTM: {lstm_acc:.2%}"
                    )

            except Exception as e:
                logger.error(f"   ❌ خطأ LSTM: {e}")
                self.lstm_enabled = False
        else:
            logger.info(
                "   ⚠️ LSTM معطل - يعمل بـ RF+GB فقط"
            )

        self.is_trained = True
        self.save()
        logger.info(f"✅ اكتمل تدريب {self.symbol}")
        return True

    # ==========================================
    # التنبؤ
    # ==========================================
    def predict(self, df) -> tuple:
        """تنبؤ من النماذج مع تصويت موزون"""

        if not self.is_trained:
            return "HOLD", 0.0

        try:
            probabilities = []
            weights = []

            # ===== RF و GB =====
            X_ml = self._prepare_ml_data(
                df, for_prediction=True
            )

            rf_p = self.rf_model.predict_proba(X_ml)[0][1]
            gb_p = self.gb_model.predict_proba(X_ml)[0][1]

            probabilities.extend([rf_p, gb_p])
            weights.extend([0.3, 0.3])

            # ===== LSTM =====
            if (
                self.lstm_enabled and
                self.lstm_model is not None
            ):
                try:
                    X_lstm = self._prepare_lstm_data(
                        df, for_prediction=True
                    )
                    lstm_p = float(
                        self.lstm_model.predict(
                            X_lstm, verbose=0
                        )[0][0]
                    )
                    probabilities.append(lstm_p)
                    weights.append(0.4)
                except Exception as e:
                    logger.debug(f"LSTM predict error: {e}")

            # ===== التصويت الموزون =====
            total_weight = sum(weights)
            weighted_prob = sum(
                p * w
                for p, w in zip(probabilities, weights)
            ) / total_weight

            # ===== القرار =====
            threshold = config.PREDICTION_THRESHOLD

            if weighted_prob >= threshold:
                signal = "BUY"
                confidence = round(weighted_prob, 4)
            elif weighted_prob <= (1 - threshold):
                signal = "SELL"
                confidence = round(1 - weighted_prob, 4)
            else:
                signal = "HOLD"
                confidence = round(
                    abs(weighted_prob - 0.5) * 2, 4
                )

            # معلومات للـ log
            models_used = "RF+GB"
            if (
                self.lstm_enabled and
                len(probabilities) == 3
            ):
                models_used = "RF+GB+LSTM"

            logger.info(
                f"🔮 {self.symbol}: {signal} | "
                f"prob={weighted_prob:.4f} | "
                f"conf={confidence:.2%} | "
                f"نماذج: {models_used}"
            )

            return signal, confidence

        except Exception as e:
            logger.error(
                f"❌ خطأ التنبؤ {self.symbol}: {e}"
            )
            return "HOLD", 0.0

    # ==========================================
    # حفظ النماذج
    # ==========================================
    def save(self):
        """حفظ كل النماذج"""
        try:
            joblib.dump(self.rf_model, self.rf_path)
            joblib.dump(self.gb_model, self.gb_path)
            joblib.dump(self.scaler_ml, self.scaler_ml_path)
            joblib.dump(
                self.scaler_lstm, self.scaler_lstm_path
            )

            if (
                self.lstm_enabled and
                self.lstm_model is not None
            ):
                self.lstm_model.save(self.lstm_path)

            logger.info(f"💾 حفظ نماذج {self.symbol}")

        except Exception as e:
            logger.error(f"❌ فشل الحفظ {self.symbol}: {e}")

    # ==========================================
    # تحميل النماذج
    # ==========================================
    def load(self) -> bool:
        """تحميل النماذج المحفوظة"""
        try:
            if not (
                os.path.exists(self.rf_path) and
                os.path.exists(self.gb_path)
            ):
                return False

            self.rf_model = joblib.load(self.rf_path)
            self.gb_model = joblib.load(self.gb_path)
            self.scaler_ml = joblib.load(self.scaler_ml_path)
            self.scaler_lstm = joblib.load(
                self.scaler_lstm_path
            )

            # تحميل LSTM إن وجد ومفعّل
            if (
                LSTM_AVAILABLE and
                not DISABLE_LSTM and
                os.path.exists(self.lstm_path)
            ):
                self.lstm_model = load_model(self.lstm_path)
                self.lstm_enabled = True
                logger.info(
                    f"📂 تحميل {self.symbol} (RF+GB+LSTM)"
                )
            else:
                self.lstm_enabled = False
                logger.info(
                    f"📂 تحميل {self.symbol} (RF+GB)"
                )

            self.is_trained = True
            return True

        except Exception as e:
            logger.error(
                f"❌ فشل تحميل {self.symbol}: {e}"
            )
            return False
