"""
FinPulse Machine Learning — Financial Anomaly Detection Engine.

Implements an Isolation Forest model with behavioral feature engineering,
calibrated anomaly scoring, severity grading (Normal, Low, Medium, High),
and an explainability layer generating contributing behavioral signals.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import OneHotEncoder, RobustScaler

from ml.features import TransactionFeatureEngineer


@dataclass
class AnomalyExplanation:
    """Contributing behavioral signals for an anomalous or evaluated transaction."""

    transaction_id: str
    anomaly_score: float
    is_anomaly: bool
    severity: str
    primary_reason: str
    contributing_signals: list[str]
    model_version: str
    detected_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AnomalyDetector:
    """Isolation Forest anomaly detection model with behavioral explainability."""

    MODEL_VERSION = "finpulse-iforest-v1.0"

    def __init__(
        self,
        contamination: float = 0.08,
        random_state: int = 42,
        n_estimators: int = 150,
    ):
        self.contamination = contamination
        self.random_state = random_state
        self.n_estimators = n_estimators

        self.feature_engineer = TransactionFeatureEngineer()
        self.preprocessor: ColumnTransformer | None = None
        self.model: IsolationForest | None = None
        self.score_min: float = 0.0
        self.score_max: float = 1.0
        self.is_fitted: bool = False

    def _build_preprocessor(self) -> ColumnTransformer:
        numeric_cols = [
            "amount",
            "log_amount",
            "hour",
            "day_of_week",
            "day_of_month",
            "user_rolling_avg_5",
            "user_expanding_mean",
            "user_amount_zscore",
            "user_tx_prior_count",
            "category_user_ratio",
            "merchant_prior_count",
        ]
        binary_cols = ["direction_is_debit", "is_weekend", "is_new_merchant"]
        categorical_cols = ["spending_category", "source_type"]

        return ColumnTransformer(
            transformers=[
                ("num", RobustScaler(), numeric_cols),
                ("bin", "passthrough", binary_cols),
                (
                    "cat",
                    OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                    categorical_cols,
                ),
            ]
        )

    def fit(self, df_transactions: pd.DataFrame) -> "AnomalyDetector":
        """Fit Isolation Forest model on historical transactions."""
        if df_transactions.empty:
            raise ValueError("Cannot fit AnomalyDetector on empty transactions DataFrame.")

        features_df = self.feature_engineer.extract_features(df_transactions, is_training=True)

        self.preprocessor = self._build_preprocessor()
        X_proc = self.preprocessor.fit_transform(features_df)

        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=self.n_estimators,
            max_samples="auto",
            bootstrap=False,
        )
        self.model.fit(X_proc)

        # Baseline score distribution for calibration
        raw_scores = -self.model.score_samples(X_proc)
        self.score_min = float(np.min(raw_scores))
        self.score_max = float(np.max(raw_scores))
        self.is_fitted = True
        return self

    def _calibrate_score(self, raw_score: float) -> float:
        """Calibrate raw isolation forest score to a normalized [0.0, 1.0] scale."""
        if self.score_max <= self.score_min:
            return 0.5
        norm = (raw_score - self.score_min) / (self.score_max - self.score_min)
        return float(np.clip(norm, 0.0, 1.0))

    def _determine_severity(self, calibrated_score: float, is_anomaly: bool) -> str:
        """Determine severity level based on score thresholds and model prediction."""
        if not is_anomaly:
            return "Normal"
        if calibrated_score >= 0.85:
            return "High"
        elif calibrated_score >= 0.70:
            return "Medium"
        else:
            return "Low"

    def _generate_explanation(
        self,
        row: pd.Series,
        calibrated_score: float,
        is_anomaly: bool,
    ) -> tuple[str, list[str]]:
        """Identify contributing behavioral signals for the transaction."""
        signals: list[str] = []

        amount = float(row.get("amount", 0.0))
        zscore = float(row.get("user_amount_zscore", 0.0))
        exp_mean = float(row.get("user_expanding_mean", amount))
        cat_ratio = float(row.get("category_user_ratio", 1.0))
        category = str(row.get("spending_category", "Unknown"))
        is_new_m = int(row.get("is_new_merchant", 0))
        hour = int(row.get("hour", 12))
        merch = str(row.get("merchant_name", "Unknown"))

        # Signal 1: Substantial deviation from historical mean
        if zscore > 2.0 or (exp_mean > 0 and amount >= 2.5 * exp_mean):
            signals.append(
                f"Amount (₹{amount:,.2f}) deviates significantly from user average "
                f"(₹{exp_mean:,.2f}, Z-score: {zscore:.1f})"
            )

        # Signal 2: Novel/unseen merchant
        if is_new_m == 1:
            signals.append(f"First recorded transaction with merchant '{merch}'")

        # Signal 3: Category spending surge
        if cat_ratio >= 2.5:
            signals.append(
                f"Amount is {cat_ratio:.1f}x higher than user's median spend in '{category}'"
            )

        # Signal 4: Unusual timing
        if hour < 6 or hour >= 23:
            signals.append(f"Unusual late-night or early-morning transaction hour ({hour:02d}:00)")

        # Signal 5: Large single debit
        if amount >= 15000.0 and row.get("direction") == "DEBIT":
            signals.append(f"High-value debit outflow of ₹{amount:,.2f}")

        if not is_anomaly:
            primary_reason = "Transaction aligns with typical user spending behavior."
            if not signals:
                signals.append("Normal spending pattern across amount, merchant, and timing.")
        else:
            if signals:
                primary_reason = signals[0]
            else:
                primary_reason = (
                    "Unusual multidimensional feature pattern flagged by Isolation Forest."
                )
                signals.append("Multi-attribute deviation from historical cluster.")

        return primary_reason, signals

    def predict(self, df_transactions: pd.DataFrame) -> list[AnomalyExplanation]:
        """Score transactions and generate anomaly predictions with explanations."""
        if not self.is_fitted or self.model is None or self.preprocessor is None:
            raise RuntimeError("AnomalyDetector must be fitted before predict.")

        if df_transactions.empty:
            return []

        features_df = self.feature_engineer.extract_features(df_transactions, is_training=False)
        X_proc = self.preprocessor.transform(features_df)

        raw_scores = -self.model.score_samples(X_proc)
        preds = self.model.predict(X_proc)  # -1 for anomaly, 1 for inlier

        results: list[AnomalyExplanation] = []
        now_iso = datetime.now(UTC).isoformat()

        for (_, row), raw_s, pred in zip(features_df.iterrows(), raw_scores, preds):
            cal_score = self._calibrate_score(raw_s)
            is_anom = bool(pred == -1)
            severity = self._determine_severity(cal_score, is_anom)
            primary_reason, signals = self._generate_explanation(row, cal_score, is_anom)

            results.append(
                AnomalyExplanation(
                    transaction_id=str(row.get("transaction_id", "")),
                    anomaly_score=round(cal_score, 4),
                    is_anomaly=is_anom,
                    severity=severity,
                    primary_reason=primary_reason,
                    contributing_signals=signals,
                    model_version=self.MODEL_VERSION,
                    detected_at=now_iso,
                )
            )

        return results

    def save(self, output_dir: Path | str) -> Path:
        """Persist model artifacts and preprocessors to disk."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        artifact = {
            "model": self.model,
            "preprocessor": self.preprocessor,
            "feature_engineer": self.feature_engineer,
            "score_min": self.score_min,
            "score_max": self.score_max,
            "contamination": self.contamination,
            "model_version": self.MODEL_VERSION,
            "saved_at": datetime.now(UTC).isoformat(),
        }

        model_file = out_path / "isolation_forest.joblib"
        joblib.dump(artifact, model_file)
        return model_file

    @classmethod
    def load(cls, model_file: Path | str) -> "AnomalyDetector":
        """Load trained model and preprocessors from disk."""
        path = Path(model_file)
        if not path.exists():
            raise FileNotFoundError(f"Model artifact not found at {path}")

        artifact = joblib.load(path)
        detector = cls(contamination=artifact.get("contamination", 0.08))
        detector.model = artifact["model"]
        detector.preprocessor = artifact["preprocessor"]
        detector.feature_engineer = artifact["feature_engineer"]
        detector.score_min = artifact.get("score_min", 0.0)
        detector.score_max = artifact.get("score_max", 1.0)
        detector.is_fitted = True
        return detector
