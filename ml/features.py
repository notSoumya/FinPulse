"""
FinPulse Machine Learning — Feature Engineering for Financial Anomaly Detection.

Transforms raw/silver transaction records into behavioral and statistical feature vectors.
Prevents target leakage and future-data leakage by computing expanding and rolling windows
strictly in historical chronological sequence per user.
"""

from typing import Any

import numpy as np
import pandas as pd


def infer_category(merchant_name: str | None, direction: str) -> str:
    """Infer spending category consistent with dbt gold_category_spending rules."""
    if direction == "CREDIT":
        return "Income"
    m = (merchant_name or "").strip().lower()
    if "amazon" in m or "flipkart" in m:
        return "Shopping"
    if any(k in m for k in ["swiggy", "zomato", "blinkit", "instamart"]):
        return "Food & Groceries"
    if any(k in m for k in ["uber", "ola", "metro", "irctc"]):
        return "Travel & Commute"
    if "salary" in m:
        return "Income"
    return "Uncategorized"


class TransactionFeatureEngineer:
    """Feature engineering pipeline for financial transaction anomaly detection."""

    FEATURE_COLUMNS = [
        "amount",
        "log_amount",
        "direction_is_debit",
        "hour",
        "day_of_week",
        "day_of_month",
        "is_weekend",
        "user_rolling_avg_5",
        "user_expanding_mean",
        "user_amount_zscore",
        "user_tx_prior_count",
        "category_user_ratio",
        "merchant_prior_count",
        "is_new_merchant",
    ]

    CATEGORICAL_COLUMNS = [
        "spending_category",
        "source_type",
    ]

    def __init__(self):
        self.fitted_user_profiles: dict[str, dict[str, Any]] = {}

    def extract_features(
        self,
        df: pd.DataFrame,
        is_training: bool = True,
    ) -> pd.DataFrame:
        """
        Extract behavioral, statistical, and temporal features from transactions.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame containing transaction columns:
            transaction_id, user_id, amount, direction, transaction_timestamp,
            merchant_name, source_type.
        is_training : bool
            Whether this extraction is for model training (fits/updates user profiles)
            or inference (uses existing profile baselines if available).

        Returns
        -------
        pd.DataFrame
            Feature matrix with engineered features aligned to input rows.
        """
        if df.empty:
            return pd.DataFrame()

        df_work = df.copy()

        # Ensure timestamp is datetime and sort chronologically
        if not pd.api.types.is_datetime64_any_dtype(df_work["transaction_timestamp"]):
            df_work["transaction_timestamp"] = pd.to_datetime(
                df_work["transaction_timestamp"], utc=True
            )

        original_index = df_work.index
        df_work = df_work.sort_values(["user_id", "transaction_timestamp"]).reset_index(drop=True)

        # 1. Base amounts
        df_work["amount"] = df_work["amount"].astype(float)
        df_work["log_amount"] = np.log1p(np.maximum(df_work["amount"], 0.0))
        df_work["direction_is_debit"] = (df_work["direction"] == "DEBIT").astype(int)

        # 2. Temporal features
        dt = df_work["transaction_timestamp"].dt
        df_work["hour"] = dt.hour
        # Support day_of_week across pandas versions
        dow = dt.day_of_week if hasattr(dt, "day_of_week") else dt.dayofweek
        df_work["day_of_week"] = dow
        df_work["day_of_month"] = dt.day
        df_work["is_weekend"] = (dow >= 5).astype(int)

        # 3. Categorization
        if "spending_category" not in df_work.columns:
            df_work["spending_category"] = [
                infer_category(m, d) for m, d in zip(df_work["merchant_name"], df_work["direction"])
            ]
        else:
            df_work["spending_category"] = df_work["spending_category"].fillna("Uncategorized")

        # 4. User-level historical spending patterns (prevent leakage using shift)
        rolling_avgs = []
        expanding_means = []
        zscores = []
        prior_counts = []
        category_ratios = []
        merchant_counts = []
        is_new_merchants = []

        # Group by user to maintain strict tenant isolation
        for user_id, group in df_work.groupby("user_id", sort=False):
            user_amounts = group["amount"].values
            user_categories = group["spending_category"].values
            user_merchants = group["merchant_name"].values

            history_amounts: list[float] = []
            category_amounts: dict[str, list[float]] = {}
            merchant_seen_count: dict[str, int] = {}

            # Seed with fitted profiles if in inference mode
            if not is_training and user_id in self.fitted_user_profiles:
                prof = self.fitted_user_profiles[user_id]
                history_amounts = list(prof.get("amounts", []))
                category_amounts = {k: list(v) for k, v in prof.get("category_amounts", {}).items()}
                merchant_seen_count = dict(prof.get("merchant_counts", {}))

            for amt, cat, merch in zip(user_amounts, user_categories, user_merchants):
                n_prior = len(history_amounts)
                prior_counts.append(n_prior)

                if n_prior == 0:
                    exp_mean = amt
                    exp_std = 0.0
                    r_avg = amt
                    z = 0.0
                else:
                    arr = np.array(history_amounts)
                    exp_mean = float(np.mean(arr))
                    exp_std = float(np.std(arr))
                    recent_5 = arr[-5:]
                    r_avg = float(np.mean(recent_5))
                    z = float((amt - exp_mean) / (exp_std + 1e-4)) if exp_std > 0 else 0.0

                rolling_avgs.append(r_avg)
                expanding_means.append(exp_mean)
                zscores.append(z)

                # Category ratio
                cat_list = category_amounts.get(cat, [])
                if cat_list:
                    cat_mean = float(np.mean(cat_list))
                    category_ratios.append(float(amt / (cat_mean + 1e-4)))
                else:
                    category_ratios.append(1.0)

                # Merchant familiarity
                m_count = merchant_seen_count.get(merch, 0)
                merchant_counts.append(m_count)
                is_new_merchants.append(1 if m_count == 0 else 0)

                # Update running state
                history_amounts.append(amt)
                category_amounts.setdefault(cat, []).append(amt)
                merchant_seen_count[merch] = m_count + 1

            if is_training:
                self.fitted_user_profiles[user_id] = {
                    "amounts": history_amounts,
                    "category_amounts": category_amounts,
                    "merchant_counts": merchant_seen_count,
                    "mean_amount": float(np.mean(history_amounts)) if history_amounts else 0.0,
                    "std_amount": float(np.std(history_amounts)) if history_amounts else 0.0,
                }

        df_work["user_rolling_avg_5"] = rolling_avgs
        df_work["user_expanding_mean"] = expanding_means
        df_work["user_amount_zscore"] = zscores
        df_work["user_tx_prior_count"] = prior_counts
        df_work["category_user_ratio"] = category_ratios
        df_work["merchant_prior_count"] = merchant_counts
        df_work["is_new_merchant"] = is_new_merchants

        # Restore original row ordering
        df_work.index = original_index
        return df_work
