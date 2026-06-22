"""Validation and KPI summary generation for GameStudioBI."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import SimulationConfig
from generators.session_generator import derive_player_active_end_dates
from simulation.behaviour_engine import assign_player_behaviours


VALIDATION_CHUNK_SIZE = 200_000
REVIEW_MIN_HOURS_PLAYED = 20.0


def export_validation_artifacts(
    player_frame: pd.DataFrame,
    marketing_frame: pd.DataFrame,
    config: SimulationConfig,
    output_dir: Path,
    sessions_path: Path,
    purchases_path: Path,
    reviews_path: Path,
    finance_path: Path,
    chunk_size: int = VALIDATION_CHUNK_SIZE,
) -> tuple[int, int]:
    """Validate generated outputs and export validation artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    _validate_path(sessions_path, "session")
    _validate_path(purchases_path, "purchase")
    _validate_path(reviews_path, "review")
    _validate_path(finance_path, "finance")

    behaviour_frame = assign_player_behaviours(player_frame, config)
    validation_checks, summary_statistics = _build_validation_outputs(
        player_frame,
        marketing_frame,
        behaviour_frame,
        config,
        sessions_path,
        purchases_path,
        reviews_path,
        finance_path,
        chunk_size,
    )

    validation_checks.to_csv(output_dir / "validation_checks.csv", index=False)
    summary_statistics.to_csv(output_dir / "summary_statistics.csv", index=False)
    return len(validation_checks), len(summary_statistics)


def _build_validation_outputs(
    player_frame: pd.DataFrame,
    marketing_frame: pd.DataFrame,
    behaviour_frame: pd.DataFrame,
    config: SimulationConfig,
    sessions_path: Path,
    purchases_path: Path,
    reviews_path: Path,
    finance_path: Path,
    chunk_size: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    simulation_dates = pd.date_range(
        config.simulation_start_date,
        config.simulation_end_date,
        freq="D",
    )
    day_count = len(simulation_dates)
    max_player_id = int(player_frame["PlayerID"].max())
    valid_player_lookup = np.zeros(max_player_id + 1, dtype=bool)
    valid_player_lookup[player_frame["PlayerID"].to_numpy(dtype=np.int64)] = True

    active_end_dates = derive_player_active_end_dates(
        player_frame,
        behaviour_frame,
        config,
    )
    active_end_lookup = np.full(max_player_id + 1, -1, dtype=np.int32)
    active_end_offsets = (
        pd.to_datetime(active_end_dates["ActiveEndDate"]).dt.normalize()
        - pd.Timestamp(config.simulation_start_date)
    ).dt.days.to_numpy(dtype=np.int32)
    active_end_lookup[
        active_end_dates["PlayerID"].to_numpy(dtype=np.int64)
    ] = active_end_offsets

    session_metrics = _validate_sessions(
        sessions_path,
        valid_player_lookup,
        active_end_lookup,
        config,
        day_count,
        chunk_size,
    )
    purchase_metrics = _validate_purchases(
        purchases_path,
        valid_player_lookup,
        config,
        day_count,
        chunk_size,
    )
    review_metrics = _validate_reviews(reviews_path, valid_player_lookup)
    campaign_metrics = _validate_campaign_links(player_frame, marketing_frame)
    finance_metrics = _validate_finance(finance_path, purchase_metrics["revenue_total"])

    validation_checks = _build_validation_checks(
        session_metrics,
        purchase_metrics,
        review_metrics,
        campaign_metrics,
        finance_metrics,
    )
    summary_statistics = _build_summary_statistics(
        player_frame,
        session_metrics,
        purchase_metrics,
        active_end_lookup,
        simulation_dates,
    )
    return validation_checks, summary_statistics


def _validate_sessions(
    sessions_path: Path,
    valid_player_lookup: np.ndarray,
    active_end_lookup: np.ndarray,
    config: SimulationConfig,
    day_count: int,
    chunk_size: int,
) -> dict[str, object]:
    max_player_id = len(valid_player_lookup) - 1
    activity_matrix = np.zeros((day_count, max_player_id + 1), dtype=bool)
    session_fk_invalid = 0
    churn_violations = 0
    session_length_sum = 0.0
    session_rows = 0
    simulation_start = pd.Timestamp(config.simulation_start_date)

    for chunk in pd.read_csv(
        sessions_path,
        chunksize=chunk_size,
        usecols=["PlayerID", "LoginTime", "SessionLength"],
    ):
        player_ids = chunk["PlayerID"].to_numpy(dtype=np.int64)
        login_offsets = (
            pd.to_datetime(chunk["LoginTime"]).dt.normalize() - simulation_start
        ).dt.days.to_numpy(dtype=np.int32)
        safe_player_ids = np.clip(player_ids, 0, max_player_id)
        valid_player_mask = player_ids <= max_player_id
        valid_player_mask &= valid_player_lookup[safe_player_ids]
        session_fk_invalid += int((~valid_player_mask).sum())

        valid_mask = valid_player_mask & (login_offsets >= 0) & (login_offsets < day_count)
        if not np.any(valid_mask):
            continue

        valid_player_ids = player_ids[valid_mask]
        valid_offsets = login_offsets[valid_mask]
        churn_violations += int(
            np.count_nonzero(valid_offsets > active_end_lookup[valid_player_ids])
        )
        activity_matrix[valid_offsets, valid_player_ids] = True
        session_rows += int(valid_mask.sum())
        session_length_sum += float(
            chunk["SessionLength"].to_numpy(dtype=np.float64)[valid_mask].sum()
        )

    dau_series = activity_matrix[:, 1:].sum(axis=1).astype(np.int64)
    return {
        "session_fk_invalid": session_fk_invalid,
        "churn_violations": churn_violations,
        "session_rows": session_rows,
        "session_length_sum": session_length_sum,
        "activity_matrix": activity_matrix,
        "dau_series": dau_series,
    }


def _validate_purchases(
    purchases_path: Path,
    valid_player_lookup: np.ndarray,
    config: SimulationConfig,
    day_count: int,
    chunk_size: int,
) -> dict[str, object]:
    max_player_id = len(valid_player_lookup) - 1
    purchase_fk_invalid = 0
    revenue_total = 0.0
    revenue_by_day = np.zeros(day_count, dtype=np.float64)
    simulation_start = pd.Timestamp(config.simulation_start_date)

    for chunk in pd.read_csv(
        purchases_path,
        chunksize=chunk_size,
        usecols=["PlayerID", "PurchaseDate", "Revenue"],
    ):
        player_ids = chunk["PlayerID"].to_numpy(dtype=np.int64)
        safe_player_ids = np.clip(player_ids, 0, max_player_id)
        valid_player_mask = player_ids <= max_player_id
        valid_player_mask &= valid_player_lookup[safe_player_ids]
        purchase_fk_invalid += int((~valid_player_mask).sum())

        purchase_offsets = (
            pd.to_datetime(chunk["PurchaseDate"]).dt.normalize() - simulation_start
        ).dt.days.to_numpy(dtype=np.int32)
        valid_mask = valid_player_mask & (purchase_offsets >= 0) & (purchase_offsets < day_count)
        if not np.any(valid_mask):
            continue

        revenues = chunk["Revenue"].to_numpy(dtype=np.float64)[valid_mask]
        revenue_total += float(revenues.sum())
        revenue_by_day += np.bincount(
            purchase_offsets[valid_mask],
            weights=revenues,
            minlength=day_count,
        )

    return {
        "purchase_fk_invalid": purchase_fk_invalid,
        "revenue_total": round(revenue_total, 2),
        "revenue_by_day": revenue_by_day,
    }


def _validate_reviews(
    reviews_path: Path,
    valid_player_lookup: np.ndarray,
) -> dict[str, object]:
    review_frame = pd.read_csv(reviews_path)
    if review_frame.empty:
        return {
            "review_fk_invalid": 0,
            "review_hours_invalid": 0,
        }

    max_player_id = len(valid_player_lookup) - 1
    player_ids = review_frame["PlayerID"].to_numpy(dtype=np.int64)
    safe_player_ids = np.clip(player_ids, 0, max_player_id)
    valid_player_mask = player_ids <= max_player_id
    valid_player_mask &= valid_player_lookup[safe_player_ids]
    review_fk_invalid = int((~valid_player_mask).sum())
    review_hours_invalid = int(
        np.count_nonzero(
            review_frame["HoursPlayed"].to_numpy(dtype=np.float64) < REVIEW_MIN_HOURS_PLAYED
        )
    )
    return {
        "review_fk_invalid": review_fk_invalid,
        "review_hours_invalid": review_hours_invalid,
    }


def _validate_campaign_links(
    player_frame: pd.DataFrame,
    marketing_frame: pd.DataFrame,
) -> dict[str, object]:
    campaign_lookup = marketing_frame.set_index("CampaignID")
    valid_campaign_ids = set(campaign_lookup.index.to_list())
    player_campaign_ids = set(player_frame["CampaignID"].tolist())
    missing_campaign_links = len(player_campaign_ids.difference(valid_campaign_ids))

    linked_player_frame = player_frame.merge(
        marketing_frame.loc[:, ["CampaignID", "Channel", "Registrations"]],
        on="CampaignID",
        how="left",
        validate="many_to_one",
    )
    channel_mismatches = int(
        np.count_nonzero(
            linked_player_frame["Acquisition Channel"].to_numpy(dtype=object)
            != linked_player_frame["Channel"].to_numpy(dtype=object)
        )
    )

    registration_reconciliation = (
        player_frame.groupby("CampaignID", as_index=False)
        .size()
        .rename(columns={"size": "PlayerCount"})
        .merge(
            marketing_frame.loc[:, ["CampaignID", "Registrations"]],
            on="CampaignID",
            how="right",
            validate="one_to_one",
        )
    )
    registration_mismatches = int(
        np.count_nonzero(
            registration_reconciliation["PlayerCount"].fillna(0).to_numpy(dtype=np.int64)
            != registration_reconciliation["Registrations"].to_numpy(dtype=np.int64)
        )
    )

    return {
        "missing_campaign_links": missing_campaign_links,
        "channel_mismatches": channel_mismatches,
        "registration_mismatches": registration_mismatches,
    }


def _validate_finance(finance_path: Path, purchase_revenue_total: float) -> dict[str, object]:
    finance_frame = pd.read_csv(finance_path)
    finance_revenue_total = round(float(finance_frame["Revenue"].sum()), 2)
    return {
        "finance_rows": len(finance_frame),
        "finance_revenue_total": finance_revenue_total,
        "revenue_match": finance_revenue_total == round(purchase_revenue_total, 2),
    }


def _build_validation_checks(
    session_metrics: dict[str, object],
    purchase_metrics: dict[str, object],
    review_metrics: dict[str, object],
    campaign_metrics: dict[str, object],
    finance_metrics: dict[str, object],
) -> pd.DataFrame:
    checks = [
        _check_row(
            "foreign_keys_valid",
            all(
                (
                    session_metrics["session_fk_invalid"] == 0,
                    purchase_metrics["purchase_fk_invalid"] == 0,
                    review_metrics["review_fk_invalid"] == 0,
                    campaign_metrics["missing_campaign_links"] == 0,
                )
            ),
            (
                f"invalid_session_players={session_metrics['session_fk_invalid']}; "
                f"invalid_purchase_players={purchase_metrics['purchase_fk_invalid']}; "
                f"invalid_review_players={review_metrics['review_fk_invalid']}; "
                f"missing_campaign_ids={campaign_metrics['missing_campaign_links']}"
            ),
        ),
        _check_row(
            "every_purchase_belongs_to_player",
            purchase_metrics["purchase_fk_invalid"] == 0,
            f"invalid_purchase_players={purchase_metrics['purchase_fk_invalid']}",
        ),
        _check_row(
            "every_session_belongs_to_player",
            session_metrics["session_fk_invalid"] == 0,
            f"invalid_session_players={session_metrics['session_fk_invalid']}",
        ),
        _check_row(
            "churned_players_stop_generating_sessions",
            session_metrics["churn_violations"] == 0,
            f"session_after_churn_cutoff={session_metrics['churn_violations']}",
        ),
        _check_row(
            "revenue_equals_sum_of_purchases",
            bool(finance_metrics["revenue_match"]),
            (
                f"finance_revenue={finance_metrics['finance_revenue_total']}; "
                f"purchase_revenue={purchase_metrics['revenue_total']}"
            ),
        ),
        _check_row(
            "players_linked_to_campaigns_correctly",
            all(
                (
                    campaign_metrics["missing_campaign_links"] == 0,
                    campaign_metrics["channel_mismatches"] == 0,
                    campaign_metrics["registration_mismatches"] == 0,
                )
            ),
            (
                f"missing_campaign_ids={campaign_metrics['missing_campaign_links']}; "
                f"channel_mismatches={campaign_metrics['channel_mismatches']}; "
                f"registration_mismatches={campaign_metrics['registration_mismatches']}"
            ),
        ),
    ]
    return pd.DataFrame(checks)


def _build_summary_statistics(
    player_frame: pd.DataFrame,
    session_metrics: dict[str, object],
    purchase_metrics: dict[str, object],
    active_end_lookup: np.ndarray,
    simulation_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    activity_matrix = session_metrics["activity_matrix"]
    dau_series = session_metrics["dau_series"]
    revenue_by_day = purchase_metrics["revenue_by_day"]
    player_count = len(player_frame)

    month_periods = simulation_dates.to_period("M")
    unique_months = month_periods.unique()
    mau_values = []
    for month in unique_months:
        month_mask = month_periods == month
        mau_values.append(int(activity_matrix[month_mask, 1:].any(axis=0).sum()))
    mau_series = np.array(mau_values, dtype=np.int64)

    registration_offsets = (
        pd.to_datetime(player_frame["RegistrationDate"]).dt.normalize()
        - simulation_dates[0]
    ).dt.days.to_numpy(dtype=np.int32)
    player_ids = player_frame["PlayerID"].to_numpy(dtype=np.int64)
    retention_metrics = _calculate_retention_metrics(
        activity_matrix,
        player_ids,
        registration_offsets,
        len(simulation_dates),
    )

    overall_churn_rate = float(np.mean(active_end_lookup[player_ids] < len(simulation_dates) - 1))
    arpu = float(purchase_metrics["revenue_total"]) / player_count if player_count else 0.0
    average_session_length = (
        float(session_metrics["session_length_sum"]) / float(session_metrics["session_rows"])
        if session_metrics["session_rows"]
        else 0.0
    )

    summary_rows = [
        _metric_row("Average DAU", float(dau_series.mean())),
        _metric_row("Peak DAU", float(dau_series.max() if len(dau_series) else 0.0)),
        _metric_row("Average MAU", float(mau_series.mean() if len(mau_series) else 0.0)),
        _metric_row("Latest MAU", float(mau_series[-1] if len(mau_series) else 0.0)),
        _metric_row("Total Revenue", float(purchase_metrics["revenue_total"])),
        _metric_row("Average Daily Revenue", float(revenue_by_day.mean())),
        _metric_row("Day 1 Retention", retention_metrics["day_1"]),
        _metric_row("Day 7 Retention", retention_metrics["day_7"]),
        _metric_row("Day 30 Retention", retention_metrics["day_30"]),
        _metric_row("Overall Churn Rate", overall_churn_rate),
        _metric_row("ARPU", arpu),
        _metric_row("Average Session Length", average_session_length),
    ]
    return pd.DataFrame(summary_rows)


def _calculate_retention_metrics(
    activity_matrix: np.ndarray,
    player_ids: np.ndarray,
    registration_offsets: np.ndarray,
    day_count: int,
) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for offset, label in ((1, "day_1"), (7, "day_7"), (30, "day_30")):
        eligible_mask = registration_offsets + offset < day_count
        if not np.any(eligible_mask):
            metrics[label] = 0.0
            continue

        eligible_player_ids = player_ids[eligible_mask]
        target_offsets = registration_offsets[eligible_mask] + offset
        retained = activity_matrix[target_offsets, eligible_player_ids]
        metrics[label] = float(np.mean(retained))
    return metrics


def _metric_row(metric: str, value: float) -> dict[str, object]:
    return {"Metric": metric, "Value": round(value, 4)}


def _check_row(check_name: str, passed: bool, details: str) -> dict[str, object]:
    return {
        "CheckName": check_name,
        "Status": "PASS" if passed else "FAIL",
        "Details": details,
    }


def _validate_path(path: Path, label: str) -> None:
    if not path.exists():
        msg = f"{label.capitalize()} file does not exist: {path}"
        raise FileNotFoundError(msg)
