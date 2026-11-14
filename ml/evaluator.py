"""
FinPulse Machine Learning — Model Validation & Anomaly Injection Evaluation Suite.

Evaluates the Isolation Forest model using:
1. Time-aware chronological train-test split.
2. Anomaly score distribution analysis.
3. Controlled synthetic anomaly injection benchmarks (measuring score uplift).
4. Rigorous non-leaking documentation of model capabilities and limitations.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.anomaly_detector import AnomalyDetector


class AnomalyEvaluator:
    """Evaluates AnomalyDetector without assuming ground-truth labels."""

    def __init__(self, detector: AnomalyDetector | None = None):
        self.detector = detector or AnomalyDetector()

    def evaluate_time_aware(
        self,
        df: pd.DataFrame,
        split_ratio: float = 0.70,
    ) -> dict[str, Any]:
        """
        Perform time-aware train/test split, score holdout transactions, and summarize.
        """
        if len(df) < 10:
            raise ValueError("Insufficient records for time-aware evaluation.")

        df_sorted = df.sort_values("transaction_timestamp").reset_index(drop=True)
        split_idx = int(len(df_sorted) * split_ratio)
        train_df = df_sorted.iloc[:split_idx].copy()
        test_df = df_sorted.iloc[split_idx:].copy()

        # Fit on past data only
        self.detector.fit(train_df)

        # Predict on future holdout set
        test_explanations = self.detector.predict(test_df)
        scores = [e.anomaly_score for e in test_explanations]
        anom_flags = [e.is_anomaly for e in test_explanations]
        severities = [e.severity for e in test_explanations]

        severity_counts: dict[str, int] = {}
        for s in severities:
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "train_size": len(train_df),
            "test_size": len(test_df),
            "test_date_start": test_df["transaction_timestamp"].min().isoformat(),
            "test_date_end": test_df["transaction_timestamp"].max().isoformat(),
            "anomalies_detected": int(sum(anom_flags)),
            "anomaly_rate_pct": round(float(np.mean(anom_flags)) * 100, 2),
            "score_mean": round(float(np.mean(scores)), 4),
            "score_std": round(float(np.std(scores)), 4),
            "score_min": round(float(np.min(scores)), 4),
            "score_max": round(float(np.max(scores)), 4),
            "severity_counts": severity_counts,
        }

    def evaluate_injected_anomalies(
        self,
        df_base: pd.DataFrame,
        n_injections: int = 5,
    ) -> dict[str, Any]:
        """
        Inject synthetic anomalies into a holdout test set to measure score sensitivity.
        Tests:
        1. Extreme amount debits (> 10x normal).
        2. Off-hours burst transactions (e.g. 03:30 AM).
        3. Novel high-risk merchant spending.
        """
        if not self.detector.is_fitted:
            self.detector.fit(df_base)

        base_explanations = self.detector.predict(df_base)
        base_scores = [e.anomaly_score for e in base_explanations]
        baseline_mean_score = float(np.mean(base_scores))

        # Generate synthetic anomalies based on dataset attributes
        user_id = str(df_base["user_id"].iloc[0])
        max_ts = pd.to_datetime(df_base["transaction_timestamp"]).max()

        injected_records = []
        for i in range(n_injections):
            injected_records.append(
                {
                    "transaction_id": f"injected_extreme_amt_{i + 1}",
                    "user_id": user_id,
                    "amount": 89000.0 + (i * 15000.0),
                    "currency": "INR",
                    "direction": "DEBIT",
                    "transaction_timestamp": (max_ts + timedelta(days=i + 1, hours=3)).isoformat(),
                    "merchant_name": f"Suspicious Foreign Wire {i + 1}",
                    "source_type": "MANUAL",
                }
            )

        df_injected = pd.DataFrame(injected_records)
        injected_explanations = self.detector.predict(df_injected)
        injected_scores = [e.anomaly_score for e in injected_explanations]
        injected_flags = [e.is_anomaly for e in injected_explanations]
        injected_mean_score = float(np.mean(injected_scores))

        score_uplift = injected_mean_score - baseline_mean_score
        detection_rate = float(np.mean(injected_flags))

        return {
            "baseline_mean_score": round(baseline_mean_score, 4),
            "injected_mean_score": round(injected_mean_score, 4),
            "score_uplift": round(score_uplift, 4),
            "injected_detected_ratio": round(detection_rate, 2),
            "injected_count": n_injections,
            "test_passed": bool(score_uplift > 0.15 and detection_rate >= 0.80),
        }

    def generate_full_report(
        self,
        df: pd.DataFrame,
        output_file: Path | str | None = None,
    ) -> dict[str, Any]:
        """Run full evaluation suite and save JSON report."""
        time_aware_results = self.evaluate_time_aware(df)
        injection_results = self.evaluate_injected_anomalies(df)

        report = {
            "evaluation_timestamp": datetime.now(UTC).isoformat(),
            "model_version": self.detector.MODEL_VERSION,
            "time_aware_holdout": time_aware_results,
            "synthetic_injection_benchmark": injection_results,
            "evaluation_notes": [
                "Unsupervised evaluation: No pseudo ground-truth precision/recall assumed.",
                "Sensitivity verified via controlled synthetic anomaly injection score uplift.",
                "Temporal holdout prevents future-to-past information leakage.",
            ],
        }

        if output_file:
            p = Path(output_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)

        return report
