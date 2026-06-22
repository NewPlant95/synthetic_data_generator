"""Daily finance fact generation for GameStudioBI."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import SimulationConfig


FINANCE_CHUNK_SIZE = 200_000


def export_finance_facts(
    purchases_path: Path,
    sessions_path: Path,
    player_frame: pd.DataFrame,
    marketing_frame: pd.DataFrame,
    config: SimulationConfig,
    output_path: Path,
    chunk_size: int = FINANCE_CHUNK_SIZE,
) -> int:
    """Generate a daily finance fact table and export it to CSV."""
    _validate_path(purchases_path, "purchase")
    _validate_path(sessions_path, "session")
    _validate_player_frame(player_frame)
    _validate_marketing_frame(marketing_frame)

    finance_dates = pd.date_range(
        config.simulation_start_date,
        config.simulation_end_date,
        freq="D",
    )
    day_count = len(finance_dates)

    revenue_by_day = _aggregate_revenue_by_day(
        purchases_path,
        config,
        day_count,
        chunk_size,
    )
    session_count_by_day, session_minutes_by_day, daily_active_players = (
        _aggregate_session_metrics_by_day(
            sessions_path,
            config,
            day_count,
            chunk_size,
        )
    )
    marketing_costs_by_day = _allocate_marketing_costs_by_day(
        player_frame,
        marketing_frame,
        config,
        day_count,
    )

    finance_frame = pd.DataFrame(
        {
            "FinanceDate": finance_dates.strftime("%Y-%m-%d"),
            "Revenue": revenue_by_day,
            "OperatingCosts": _calculate_operating_costs(
                daily_active_players,
                session_count_by_day,
                revenue_by_day,
            ),
            "InfrastructureCosts": _calculate_infrastructure_costs(
                session_count_by_day,
                session_minutes_by_day,
            ),
            "MarketingCosts": marketing_costs_by_day,
        }
    )
    finance_frame["ForecastRevenue"] = _calculate_forecast_revenue(finance_frame)
    finance_frame["Budget"] = _calculate_budget(finance_frame)
    finance_frame["MarketingCosts"] = _round_currency_series(
        finance_frame["MarketingCosts"],
        target_total=float(marketing_frame["Spend"].sum()),
    )
    for column in [
        "Revenue",
        "OperatingCosts",
        "InfrastructureCosts",
        "Budget",
        "ForecastRevenue",
    ]:
        finance_frame[column] = _round_currency_series(finance_frame[column])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    finance_frame.to_csv(output_path, index=False)
    return len(finance_frame)


def _aggregate_revenue_by_day(
    purchases_path: Path,
    config: SimulationConfig,
    day_count: int,
    chunk_size: int,
) -> np.ndarray:
    revenue_by_day = np.zeros(day_count, dtype=np.float64)
    simulation_start = pd.Timestamp(config.simulation_start_date)

    for chunk in pd.read_csv(
        purchases_path,
        chunksize=chunk_size,
        usecols=["PurchaseDate", "Revenue"],
    ):
        purchase_offsets = (
            pd.to_datetime(chunk["PurchaseDate"]).dt.normalize() - simulation_start
        ).dt.days.to_numpy(dtype=np.int32)
        valid_mask = (purchase_offsets >= 0) & (purchase_offsets < day_count)
        if not np.any(valid_mask):
            continue

        revenue_by_day += np.bincount(
            purchase_offsets[valid_mask],
            weights=chunk["Revenue"].to_numpy(dtype=np.float64)[valid_mask],
            minlength=day_count,
        )

    return revenue_by_day


def _aggregate_session_metrics_by_day(
    sessions_path: Path,
    config: SimulationConfig,
    day_count: int,
    chunk_size: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    session_count_by_day = np.zeros(day_count, dtype=np.int64)
    session_minutes_by_day = np.zeros(day_count, dtype=np.float64)
    daily_active_players = np.zeros(day_count, dtype=np.int64)
    simulation_start = pd.Timestamp(config.simulation_start_date)

    for chunk in pd.read_csv(
        sessions_path,
        chunksize=chunk_size,
        usecols=["PlayerID", "LoginTime", "SessionLength"],
    ):
        login_offsets = (
            pd.to_datetime(chunk["LoginTime"]).dt.normalize() - simulation_start
        ).dt.days.to_numpy(dtype=np.int32)
        valid_mask = (login_offsets >= 0) & (login_offsets < day_count)
        if not np.any(valid_mask):
            continue

        filtered_chunk = chunk.loc[valid_mask].copy()
        filtered_offsets = login_offsets[valid_mask]

        session_count_by_day += np.bincount(
            filtered_offsets,
            minlength=day_count,
        )
        session_minutes_by_day += np.bincount(
            filtered_offsets,
            weights=filtered_chunk["SessionLength"].to_numpy(dtype=np.float64),
            minlength=day_count,
        )

        active_players = (
            pd.DataFrame(
                {
                    "DayOffset": filtered_offsets,
                    "PlayerID": filtered_chunk["PlayerID"].to_numpy(dtype=np.int64),
                }
            )
            .drop_duplicates()
            .groupby("DayOffset")["PlayerID"]
            .size()
        )
        if not active_players.empty:
            daily_active_players[active_players.index.to_numpy(dtype=np.int32)] += (
                active_players.to_numpy(dtype=np.int64)
            )

    return session_count_by_day, session_minutes_by_day, daily_active_players


def _allocate_marketing_costs_by_day(
    player_frame: pd.DataFrame,
    marketing_frame: pd.DataFrame,
    config: SimulationConfig,
    day_count: int,
) -> np.ndarray:
    marketing_lookup = marketing_frame.loc[:, ["CampaignID", "Spend", "Registrations"]].copy()
    marketing_lookup["SpendPerRegistration"] = (
        marketing_lookup["Spend"] / marketing_lookup["Registrations"].clip(lower=1)
    )

    acquisition_frame = player_frame.loc[:, ["CampaignID", "RegistrationDate"]].merge(
        marketing_lookup.loc[:, ["CampaignID", "SpendPerRegistration"]],
        on="CampaignID",
        how="left",
        validate="many_to_one",
    )
    registration_offsets = (
        pd.to_datetime(acquisition_frame["RegistrationDate"]).dt.normalize()
        - pd.Timestamp(config.simulation_start_date)
    ).dt.days.to_numpy(dtype=np.int32)

    marketing_costs_by_day = np.bincount(
        registration_offsets,
        weights=acquisition_frame["SpendPerRegistration"].to_numpy(dtype=np.float64),
        minlength=day_count,
    ).astype(np.float64)
    return marketing_costs_by_day


def _calculate_operating_costs(
    daily_active_players: np.ndarray,
    session_count_by_day: np.ndarray,
    revenue_by_day: np.ndarray,
) -> np.ndarray:
    base_operating_cost = 2400.0
    support_cost = daily_active_players * 0.42
    live_ops_cost = session_count_by_day * 0.18
    payment_ops_cost = revenue_by_day * 0.035
    return base_operating_cost + support_cost + live_ops_cost + payment_ops_cost


def _calculate_infrastructure_costs(
    session_count_by_day: np.ndarray,
    session_minutes_by_day: np.ndarray,
) -> np.ndarray:
    base_infrastructure_cost = 180.0
    session_compute_cost = session_count_by_day * 0.09
    session_storage_cost = session_minutes_by_day * 0.012
    return base_infrastructure_cost + session_compute_cost + session_storage_cost


def _calculate_forecast_revenue(finance_frame: pd.DataFrame) -> pd.Series:
    revenue_series = finance_frame["Revenue"].astype(float)
    trailing_7 = revenue_series.rolling(window=7, min_periods=1).mean().shift(1)
    trailing_28 = revenue_series.rolling(window=28, min_periods=1).mean().shift(1)
    forecast = 0.7 * trailing_7.fillna(revenue_series) + 0.3 * trailing_28.fillna(
        trailing_7.fillna(revenue_series)
    )
    return forecast.clip(lower=0.0)


def _calculate_budget(finance_frame: pd.DataFrame) -> pd.Series:
    base_costs = (
        finance_frame["OperatingCosts"]
        + finance_frame["InfrastructureCosts"]
        + finance_frame["MarketingCosts"]
    )
    reserve = np.maximum(350.0, finance_frame["ForecastRevenue"] * 0.14)
    return base_costs + reserve


def _round_currency_series(
    values: pd.Series | np.ndarray,
    target_total: float | None = None,
) -> pd.Series:
    rounded = pd.Series(values, copy=True).round(2)
    if target_total is None:
        return rounded

    delta = round(target_total - float(rounded.sum()), 2)
    if abs(delta) < 0.01:
        return rounded

    nonzero_indices = rounded[rounded != 0].index.to_numpy()
    target_index = int(nonzero_indices[-1]) if len(nonzero_indices) else int(rounded.index[-1])
    rounded.iloc[target_index] = round(float(rounded.iloc[target_index]) + delta, 2)
    return rounded


def _validate_path(path: Path, label: str) -> None:
    if not path.exists():
        msg = f"{label.capitalize()} file does not exist: {path}"
        raise FileNotFoundError(msg)


def _validate_player_frame(player_frame: pd.DataFrame) -> None:
    required_columns = {"CampaignID", "RegistrationDate"}
    missing_columns = required_columns.difference(player_frame.columns)
    if missing_columns:
        missing_list = ", ".join(sorted(missing_columns))
        msg = f"player_frame is missing required columns: {missing_list}"
        raise ValueError(msg)


def _validate_marketing_frame(marketing_frame: pd.DataFrame) -> None:
    required_columns = {"CampaignID", "Spend", "Registrations"}
    missing_columns = required_columns.difference(marketing_frame.columns)
    if missing_columns:
        missing_list = ", ".join(sorted(missing_columns))
        msg = f"marketing_frame is missing required columns: {missing_list}"
        raise ValueError(msg)
