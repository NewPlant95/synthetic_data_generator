"""Purchase and review fact generation for GameStudioBI."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import SimulationConfig
from generators.scenario_generator import build_scenario_calendar


PURCHASE_CHUNK_SIZE = 200_000
REVIEW_MIN_HOURS_PLAYED = 20.0
REVIEW_TYPE_BONUS = {
    "Explorer": 0.02,
    "Builder": 0.015,
    "Trader": 0.01,
    "Casual": -0.005,
    "Hardcore": 0.03,
}
RECOMMENDATION_TYPE_BONUS = {
    "Explorer": 0.03,
    "Builder": 0.02,
    "Trader": 0.015,
    "Casual": -0.02,
    "Hardcore": 0.04,
}

ITEM_CATALOG: dict[str, list[dict[str, float | int | str]]] = {
    "Explorer": [
        {"item": "Warp Cell Bundle", "weight": 0.32, "price": 4.99, "min_qty": 1, "max_qty": 3},
        {"item": "Scanner Upgrade Module", "weight": 0.24, "price": 9.99, "min_qty": 1, "max_qty": 1},
        {"item": "Exosuit Slot Unlock", "weight": 0.18, "price": 7.99, "min_qty": 1, "max_qty": 2},
        {"item": "Rare Survey Charts", "weight": 0.26, "price": 3.99, "min_qty": 1, "max_qty": 4},
    ],
    "Builder": [
        {"item": "Construction Alloy Pack", "weight": 0.30, "price": 5.99, "min_qty": 1, "max_qty": 4},
        {"item": "Decorative Parts Set", "weight": 0.23, "price": 8.99, "min_qty": 1, "max_qty": 2},
        {"item": "Power Grid Kit", "weight": 0.22, "price": 6.99, "min_qty": 1, "max_qty": 3},
        {"item": "Storage Vault Unlock", "weight": 0.25, "price": 10.99, "min_qty": 1, "max_qty": 1},
    ],
    "Trader": [
        {"item": "Trade Goods Cache", "weight": 0.29, "price": 6.99, "min_qty": 1, "max_qty": 3},
        {"item": "Market Scanner Module", "weight": 0.25, "price": 11.99, "min_qty": 1, "max_qty": 1},
        {"item": "Cargo Expansion Slot", "weight": 0.18, "price": 12.99, "min_qty": 1, "max_qty": 2},
        {"item": "Refinery Booster Pack", "weight": 0.28, "price": 4.99, "min_qty": 1, "max_qty": 4},
    ],
    "Casual": [
        {"item": "Traveler Cosmetic Pack", "weight": 0.31, "price": 4.99, "min_qty": 1, "max_qty": 2},
        {"item": "Companion Treat Bundle", "weight": 0.24, "price": 3.99, "min_qty": 1, "max_qty": 3},
        {"item": "Quickstart Supply Crate", "weight": 0.27, "price": 5.99, "min_qty": 1, "max_qty": 2},
        {"item": "Emote Collection", "weight": 0.18, "price": 2.99, "min_qty": 1, "max_qty": 1},
    ],
    "Hardcore": [
        {"item": "Multi-Tool Upgrade Kit", "weight": 0.28, "price": 12.99, "min_qty": 1, "max_qty": 2},
        {"item": "Combat Shield Module", "weight": 0.22, "price": 9.99, "min_qty": 1, "max_qty": 2},
        {"item": "Expedition Pass", "weight": 0.26, "price": 14.99, "min_qty": 1, "max_qty": 1},
        {"item": "Capital Ship Upgrade", "weight": 0.24, "price": 16.99, "min_qty": 1, "max_qty": 1},
    ],
}

COSMETIC_ITEMS = {
    "Traveler Cosmetic Pack",
    "Companion Treat Bundle",
    "Emote Collection",
    "Decorative Parts Set",
}


def export_purchase_facts(
    sessions_path: Path,
    player_frame: pd.DataFrame,
    behaviour_frame: pd.DataFrame,
    config: SimulationConfig,
    output_path: Path,
    scenario_calendar: pd.DataFrame | None = None,
    chunk_size: int = PURCHASE_CHUNK_SIZE,
) -> int:
    """Generate purchase facts from the session fact table."""
    _validate_player_frame(player_frame)
    _validate_behaviour_frame(behaviour_frame)
    _validate_sessions_path(sessions_path)

    purchase_profile = player_frame.loc[:, ["PlayerID", "Player Type"]].merge(
        behaviour_frame.loc[:, ["PlayerID", "PurchaseProbability"]],
        on="PlayerID",
        how="inner",
        validate="one_to_one",
    )
    purchase_profile = purchase_profile.set_index("PlayerID")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    header_written = False
    purchase_count = 0
    next_purchase_id = 1
    rng = np.random.default_rng(config.random_seed + 3)
    purchase_lift_by_event_id = {
        event.event_id: event.purchase_lift
        for event in config.live_service_events
    }
    scenario_day_lookup = _build_scenario_day_lookup(config, scenario_calendar)

    for chunk in pd.read_csv(
        sessions_path,
        chunksize=chunk_size,
        dtype={
            "EventID": "Int64",
            "EventName": "string",
            "EventType": "string",
        },
        low_memory=False,
    ):
        purchase_chunk = _build_purchase_chunk(
            chunk,
            purchase_profile,
            purchase_lift_by_event_id,
            scenario_day_lookup,
            rng,
        )
        if purchase_chunk.empty:
            continue

        chunk_rows = len(purchase_chunk)
        purchase_chunk.insert(
            0,
            "PurchaseID",
            np.arange(
                next_purchase_id,
                next_purchase_id + chunk_rows,
                dtype=np.int64,
            ),
        )
        purchase_chunk.to_csv(
            output_path,
            mode="a" if header_written else "w",
            header=not header_written,
            index=False,
        )

        header_written = True
        next_purchase_id += chunk_rows
        purchase_count += chunk_rows

    if not header_written:
        _empty_purchase_frame().to_csv(output_path, index=False)

    return purchase_count


def export_review_facts(
    sessions_path: Path,
    player_frame: pd.DataFrame,
    behaviour_frame: pd.DataFrame,
    config: SimulationConfig,
    output_path: Path,
    scenario_calendar: pd.DataFrame | None = None,
    chunk_size: int = PURCHASE_CHUNK_SIZE,
) -> int:
    """Generate player review facts from session history."""
    _validate_player_frame(player_frame)
    _validate_behaviour_frame(behaviour_frame)
    _validate_sessions_path(sessions_path)

    player_ids, total_minutes, session_counts, first_days, last_days = (
        _aggregate_session_metrics(
            sessions_path,
            config,
            chunk_size,
            player_frame["PlayerID"].max(),
        )
    )

    if len(player_ids) == 0:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _empty_review_frame().to_csv(output_path, index=False)
        return 0

    session_summary = pd.DataFrame(
        {
            "PlayerID": player_ids,
            "HoursPlayed": np.round(total_minutes / 60.0, 2),
            "SessionCount": session_counts,
            "FirstDayOffset": first_days,
            "LastDayOffset": last_days,
        }
    )

    review_frame = session_summary.merge(
        player_frame.loc[:, ["PlayerID", "Player Type"]],
        on="PlayerID",
        how="inner",
        validate="one_to_one",
    ).merge(
        behaviour_frame.loc[
            :,
            ["PlayerID", "ChurnProbability", "MissionCompletionProbability"],
        ],
        on="PlayerID",
        how="inner",
        validate="one_to_one",
    )

    eligible_reviews = review_frame[
        review_frame["HoursPlayed"] >= REVIEW_MIN_HOURS_PLAYED
    ].copy()
    if eligible_reviews.empty:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _empty_review_frame().to_csv(output_path, index=False)
        return 0

    rng = np.random.default_rng(config.random_seed + 4)
    review_probabilities = _calculate_review_probabilities(eligible_reviews)
    review_draws = rng.random(len(eligible_reviews))
    selected_reviews = eligible_reviews.loc[review_draws < review_probabilities].copy()

    if selected_reviews.empty:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _empty_review_frame().to_csv(output_path, index=False)
        return 0

    recommendation_probabilities = _calculate_recommendation_probabilities(
        selected_reviews
    )
    review_date_lookup = _build_scenario_day_lookup(config, scenario_calendar)
    selected_reviews["ReviewDate"] = _sample_review_dates(
        selected_reviews,
        config,
        rng,
        review_date_lookup,
    )
    scenario_review_shifts = selected_reviews["ReviewDate"].map(
        lambda value: review_date_lookup.get(
            pd.Timestamp(value).normalize(),
            {"ReviewRecommendationShift": 0.0, "ReviewScoreShift": 0.0},
        )["ReviewRecommendationShift"]
    ).to_numpy(dtype=np.float64)
    recommendation_probabilities = np.clip(
        recommendation_probabilities + scenario_review_shifts,
        0.03,
        0.99,
    )
    selected_reviews["Recommended"] = (
        rng.random(len(selected_reviews)) < recommendation_probabilities
    )

    review_score_base = (
        2.2
        + 5.0 * recommendation_probabilities
        + 0.9 * np.clip(selected_reviews["HoursPlayed"].to_numpy() / 120.0, 0.0, 1.0)
        - 2.5 * selected_reviews["ChurnProbability"].to_numpy()
        + rng.normal(loc=0.0, scale=0.9, size=len(selected_reviews))
    )
    scenario_score_shifts = selected_reviews["ReviewDate"].map(
        lambda value: review_date_lookup.get(
            pd.Timestamp(value).normalize(),
            {"ReviewRecommendationShift": 0.0, "ReviewScoreShift": 0.0},
        )["ReviewScoreShift"]
    ).to_numpy(dtype=np.float64)
    selected_reviews["ReviewScore"] = np.clip(
        np.rint(review_score_base + scenario_score_shifts).astype(np.int16),
        1,
        10,
    )

    selected_reviews = selected_reviews.loc[
        :,
        ["PlayerID", "HoursPlayed", "Recommended", "ReviewScore", "ReviewDate"],
    ].sort_values("ReviewDate").reset_index(drop=True)
    selected_reviews.insert(
        0,
        "ReviewID",
        np.arange(1, len(selected_reviews) + 1, dtype=np.int64),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    selected_reviews.to_csv(output_path, index=False)
    return len(selected_reviews)


def _build_purchase_chunk(
    session_chunk: pd.DataFrame,
    purchase_profile: pd.DataFrame,
    purchase_lift_by_event_id: dict[int, float],
    scenario_day_lookup: dict[pd.Timestamp, dict[str, float]],
    rng: np.random.Generator,
) -> pd.DataFrame:
    enriched_chunk = session_chunk.merge(
        purchase_profile,
        left_on="PlayerID",
        right_index=True,
        how="left",
        validate="many_to_one",
    )
    event_purchase_lifts = enriched_chunk["EventID"].map(purchase_lift_by_event_id).fillna(1.0)
    scenario_days = pd.to_datetime(enriched_chunk["LoginTime"]).dt.normalize()
    scenario_purchase_lifts = scenario_days.map(
        lambda value: scenario_day_lookup.get(
            value,
            {
                "PurchaseLift": 1.0,
                "PurchasePriceLift": 1.0,
                "CosmeticPurchaseLift": 1.0,
            },
        )["PurchaseLift"]
    ).to_numpy(dtype=np.float64)
    scenario_price_lifts = scenario_days.map(
        lambda value: scenario_day_lookup.get(
            value,
            {
                "PurchaseLift": 1.0,
                "PurchasePriceLift": 1.0,
                "CosmeticPurchaseLift": 1.0,
            },
        )["PurchasePriceLift"]
    ).to_numpy(dtype=np.float64)
    scenario_cosmetic_lifts = scenario_days.map(
        lambda value: scenario_day_lookup.get(
            value,
            {
                "PurchaseLift": 1.0,
                "PurchasePriceLift": 1.0,
                "CosmeticPurchaseLift": 1.0,
            },
        )["CosmeticPurchaseLift"]
    ).to_numpy(dtype=np.float64)
    effective_purchase_probability = np.clip(
        enriched_chunk["PurchaseProbability"].to_numpy(dtype=np.float64)
        * event_purchase_lifts.to_numpy(dtype=np.float64)
        * scenario_purchase_lifts
        * (
            0.55
            + enriched_chunk["SessionLength"].to_numpy(dtype=np.float64) / 180.0
            + 0.06
            * np.minimum(
                enriched_chunk["MissionsCompleted"].to_numpy(dtype=np.float64),
                4.0,
            )
        ),
        0.0,
        0.85,
    )

    purchase_mask = rng.random(len(enriched_chunk)) < effective_purchase_probability
    purchase_sessions = enriched_chunk.loc[purchase_mask].copy()
    if purchase_sessions.empty:
        return _empty_purchase_frame()

    extra_line_probability = np.clip(
        purchase_sessions["PurchaseProbability"].to_numpy(dtype=np.float64) * 0.75,
        0.05,
        0.45,
    )
    line_counts = 1 + rng.binomial(2, extra_line_probability, size=len(purchase_sessions))
    purchase_lines = purchase_sessions.loc[
        purchase_sessions.index.repeat(line_counts)
    ].reset_index(drop=True)
    purchase_lines["ScenarioPriceLift"] = scenario_price_lifts[purchase_mask].repeat(
        line_counts
    )
    purchase_lines["CosmeticPurchaseLift"] = scenario_cosmetic_lifts[purchase_mask].repeat(
        line_counts
    )

    _assign_purchase_items(purchase_lines, rng)

    session_lengths = purchase_lines["SessionLength"].to_numpy(dtype=np.int32)
    purchase_offsets = np.array(
        [rng.integers(0, session_length + 1) for session_length in session_lengths],
        dtype=np.int32,
    )
    purchase_timestamps = pd.to_datetime(purchase_lines["LoginTime"]) + pd.to_timedelta(
        purchase_offsets,
        unit="m",
    )

    purchase_lines["PurchaseDate"] = purchase_timestamps.dt.strftime("%Y-%m-%d %H:%M:%S")
    purchase_lines["Revenue"] = np.round(
        purchase_lines["Quantity"] * purchase_lines["Price"],
        2,
    )
    return purchase_lines.loc[
        :,
        ["PlayerID", "Item", "Quantity", "Price", "Revenue", "PurchaseDate"],
    ]


def _assign_purchase_items(
    purchase_lines: pd.DataFrame,
    rng: np.random.Generator,
) -> None:
    purchase_lines["Item"] = ""
    purchase_lines["Price"] = 0.0
    purchase_lines["Quantity"] = 0

    player_types = purchase_lines["Player Type"].to_numpy(dtype=object)
    for player_type, catalog in ITEM_CATALOG.items():
        player_mask = player_types == player_type
        if not np.any(player_mask):
            continue

        player_indices = np.flatnonzero(player_mask)
        cosmetic_lifts = purchase_lines.loc[
            player_mask,
            "CosmeticPurchaseLift",
        ].to_numpy(dtype=np.float64)
        selected_items: list[dict[str, float | int | str]] = []

        for lift in np.unique(cosmetic_lifts):
            lift_mask = cosmetic_lifts == lift
            batch_size = int(lift_mask.sum())
            if batch_size == 0:
                continue

            adjusted_weights = np.array(
                [
                    float(entry["weight"])
                    * (float(lift) if str(entry["item"]) in COSMETIC_ITEMS else 1.0)
                    for entry in catalog
                ],
                dtype=np.float64,
            )
            adjusted_weights = adjusted_weights / adjusted_weights.sum()
            item_indices = rng.choice(
                len(catalog),
                size=batch_size,
                p=adjusted_weights,
            )
            items_for_lift = [catalog[index] for index in item_indices]
            lift_indices = player_indices[lift_mask]
            for row_index, item in zip(lift_indices, items_for_lift, strict=True):
                selected_items.append((row_index, item))

        for row_index, entry in selected_items:
            purchase_lines.at[row_index, "Item"] = str(entry["item"])
            purchase_lines.at[row_index, "Price"] = float(entry["price"])
            purchase_lines.at[row_index, "Quantity"] = int(
                rng.integers(int(entry["min_qty"]), int(entry["max_qty"]) + 1)
            )

    purchase_lines["Price"] = (
        purchase_lines["Price"].astype(float)
        * purchase_lines["ScenarioPriceLift"].astype(float)
    ).round(2)
    purchase_lines["Quantity"] = purchase_lines["Quantity"].astype(np.int16)


def _aggregate_session_metrics(
    sessions_path: Path,
    config: SimulationConfig,
    chunk_size: int,
    max_player_id: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    total_minutes = np.zeros(max_player_id + 1, dtype=np.int64)
    session_counts = np.zeros(max_player_id + 1, dtype=np.int32)
    first_days = np.full(max_player_id + 1, np.iinfo(np.int32).max, dtype=np.int32)
    last_days = np.full(max_player_id + 1, -1, dtype=np.int32)
    start_timestamp = pd.Timestamp(config.simulation_start_date)

    for chunk in pd.read_csv(
        sessions_path,
        chunksize=chunk_size,
        usecols=["PlayerID", "LoginTime", "SessionLength"],
    ):
        player_ids = chunk["PlayerID"].to_numpy(dtype=np.int64)
        session_lengths = chunk["SessionLength"].to_numpy(dtype=np.int32)
        total_minutes += np.bincount(
            player_ids,
            weights=session_lengths,
            minlength=max_player_id + 1,
        ).astype(np.int64)
        session_counts += np.bincount(
            player_ids,
            minlength=max_player_id + 1,
        ).astype(np.int32)

        day_offsets = (
            pd.to_datetime(chunk["LoginTime"]).dt.normalize() - start_timestamp
        ).dt.days.to_numpy(dtype=np.int32)
        day_frame = pd.DataFrame({"PlayerID": player_ids, "DayOffset": day_offsets})
        day_agg = day_frame.groupby("PlayerID", as_index=False)["DayOffset"].agg(
            ["min", "max"]
        )
        chunk_player_ids = day_agg.index.to_numpy(dtype=np.int64)
        first_days[chunk_player_ids] = np.minimum(
            first_days[chunk_player_ids],
            day_agg["min"].to_numpy(dtype=np.int32),
        )
        last_days[chunk_player_ids] = np.maximum(
            last_days[chunk_player_ids],
            day_agg["max"].to_numpy(dtype=np.int32),
        )

    active_player_ids = np.flatnonzero(session_counts)
    return (
        active_player_ids,
        total_minutes[active_player_ids],
        session_counts[active_player_ids],
        first_days[active_player_ids],
        last_days[active_player_ids],
    )


def _calculate_review_probabilities(review_frame: pd.DataFrame) -> np.ndarray:
    type_bonus = review_frame["Player Type"].map(REVIEW_TYPE_BONUS).to_numpy(
        dtype=np.float64
    )
    hours_factor = np.clip(
        (review_frame["HoursPlayed"].to_numpy(dtype=np.float64) - REVIEW_MIN_HOURS_PLAYED)
        / 80.0,
        0.0,
        1.0,
    )
    review_probabilities = (
        0.04
        + 0.12 * hours_factor
        + type_bonus
        + 0.05 * review_frame["MissionCompletionProbability"].to_numpy(dtype=np.float64)
        - 0.08 * review_frame["ChurnProbability"].to_numpy(dtype=np.float64)
    )
    return np.clip(review_probabilities, 0.02, 0.35)


def _calculate_recommendation_probabilities(review_frame: pd.DataFrame) -> np.ndarray:
    type_bonus = review_frame["Player Type"].map(RECOMMENDATION_TYPE_BONUS).to_numpy(
        dtype=np.float64
    )
    return np.clip(
        0.36
        + 0.48
        * review_frame["MissionCompletionProbability"].to_numpy(dtype=np.float64)
        - 0.78 * review_frame["ChurnProbability"].to_numpy(dtype=np.float64)
        + 0.10
        * np.clip(review_frame["HoursPlayed"].to_numpy(dtype=np.float64) / 120.0, 0.0, 1.0)
        + type_bonus,
        0.05,
        0.98,
    )


def _sample_review_dates(
    review_frame: pd.DataFrame,
    config: SimulationConfig,
    rng: np.random.Generator,
    scenario_day_lookup: dict[pd.Timestamp, dict[str, float]],
) -> pd.Series:
    hours_played = review_frame["HoursPlayed"].to_numpy(dtype=np.float64)
    first_offsets = review_frame["FirstDayOffset"].to_numpy(dtype=np.int32)
    last_offsets = review_frame["LastDayOffset"].to_numpy(dtype=np.int32)
    progression_ratio = np.clip(REVIEW_MIN_HOURS_PLAYED / hours_played, 0.0, 1.0)
    earliest_offsets = np.floor(
        first_offsets + (last_offsets - first_offsets) * progression_ratio
    ).astype(np.int32)
    sampled_offsets = np.empty(len(review_frame), dtype=np.int32)
    for index, (start_offset, end_offset) in enumerate(
        zip(earliest_offsets, last_offsets, strict=True)
    ):
        if start_offset >= end_offset:
            sampled_offsets[index] = int(end_offset)
            continue

        candidate_offsets = np.arange(start_offset, end_offset + 1, dtype=np.int32)
        candidate_dates = pd.Timestamp(config.simulation_start_date) + pd.to_timedelta(
            candidate_offsets,
            unit="D",
        )
        weights = np.array(
            [
                1.0
                + abs(
                    scenario_day_lookup.get(
                        candidate_date.normalize(),
                        {
                            "ReviewRecommendationShift": 0.0,
                            "ReviewScoreShift": 0.0,
                        },
                    )["ReviewScoreShift"]
                )
                * 0.22
                + abs(
                    scenario_day_lookup.get(
                        candidate_date.normalize(),
                        {
                            "ReviewRecommendationShift": 0.0,
                            "ReviewScoreShift": 0.0,
                        },
                    )["ReviewRecommendationShift"]
                )
                * 2.8
                for candidate_date in candidate_dates
            ],
            dtype=np.float64,
        )
        weights = weights / weights.sum()
        sampled_offsets[index] = int(rng.choice(candidate_offsets, p=weights))

    review_dates = pd.Timestamp(config.simulation_start_date) + pd.to_timedelta(
        sampled_offsets,
        unit="D",
    )
    return review_dates.strftime("%Y-%m-%d")


def _build_scenario_day_lookup(
    config: SimulationConfig,
    scenario_calendar: pd.DataFrame | None,
) -> dict[pd.Timestamp, dict[str, float]]:
    calendar_frame = scenario_calendar
    if calendar_frame is None:
        calendar_frame = build_scenario_calendar(config)
    scenario_lookup_frame = calendar_frame.copy()
    scenario_lookup_frame["Date"] = pd.to_datetime(scenario_lookup_frame["Date"])
    return {
        row.Date.normalize(): {
            "PurchaseLift": float(row.PurchaseLift),
            "PurchasePriceLift": float(row.PurchasePriceLift),
            "CosmeticPurchaseLift": float(row.CosmeticPurchaseLift),
            "ReviewScoreShift": float(row.ReviewScoreShift),
            "ReviewRecommendationShift": float(row.ReviewRecommendationShift),
        }
        for row in scenario_lookup_frame.itertuples(index=False)
    }


def _empty_purchase_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "PurchaseID",
            "PlayerID",
            "Item",
            "Quantity",
            "Price",
            "Revenue",
            "PurchaseDate",
        ]
    )


def _empty_review_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "ReviewID",
            "PlayerID",
            "HoursPlayed",
            "Recommended",
            "ReviewScore",
            "ReviewDate",
        ]
    )


def _validate_player_frame(player_frame: pd.DataFrame) -> None:
    required_columns = {"PlayerID", "Player Type"}
    missing_columns = required_columns.difference(player_frame.columns)
    if missing_columns:
        missing_list = ", ".join(sorted(missing_columns))
        msg = f"player_frame is missing required columns: {missing_list}"
        raise ValueError(msg)


def _validate_behaviour_frame(behaviour_frame: pd.DataFrame) -> None:
    required_columns = {
        "PlayerID",
        "PurchaseProbability",
        "ChurnProbability",
        "MissionCompletionProbability",
    }
    missing_columns = required_columns.difference(behaviour_frame.columns)
    if missing_columns:
        missing_list = ", ".join(sorted(missing_columns))
        msg = f"behaviour_frame is missing required columns: {missing_list}"
        raise ValueError(msg)


def _validate_sessions_path(sessions_path: Path) -> None:
    if not sessions_path.exists():
        msg = f"Session file does not exist: {sessions_path}"
        raise FileNotFoundError(msg)
