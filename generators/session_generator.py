"""Session fact generation for GameStudioBI."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import LiveServiceEventConfig, SimulationConfig
from generators.scenario_generator import build_scenario_calendar


LOGIN_TIME_SHAPES: dict[str, tuple[float, float]] = {
    "Explorer": (2.4, 2.5),
    "Builder": (3.2, 2.1),
    "Trader": (2.6, 2.4),
    "Casual": (4.5, 2.0),
    "Hardcore": (2.2, 1.9),
}

PLANET_VISIT_RATES: dict[str, float] = {
    "Explorer": 1.55,
    "Builder": 0.65,
    "Trader": 0.95,
    "Casual": 0.55,
    "Hardcore": 1.10,
}

MISSION_START_RATES: dict[str, float] = {
    "Explorer": 1.10,
    "Builder": 0.75,
    "Trader": 0.95,
    "Casual": 0.60,
    "Hardcore": 1.45,
}

RESOURCE_COLLECTION_RATES: dict[str, float] = {
    "Explorer": 120.0,
    "Builder": 150.0,
    "Trader": 180.0,
    "Casual": 70.0,
    "Hardcore": 165.0,
}

DEATH_RATES: dict[str, float] = {
    "Explorer": 0.10,
    "Builder": 0.05,
    "Trader": 0.08,
    "Casual": 0.05,
    "Hardcore": 0.18,
}

BASE_PIECE_RATES: dict[str, float] = {
    "Explorer": 1.8,
    "Builder": 8.5,
    "Trader": 1.4,
    "Casual": 0.8,
    "Hardcore": 3.2,
}

BIOME_WEIGHTS: dict[str, dict[str, float]] = {
    "Explorer": {
        "Lush": 0.18,
        "Frozen": 0.16,
        "Desert": 0.14,
        "Toxic": 0.11,
        "Radiated": 0.11,
        "Volcanic": 0.10,
        "Oceanic": 0.12,
        "Exotic": 0.08,
    },
    "Builder": {
        "Lush": 0.34,
        "Oceanic": 0.16,
        "Desert": 0.10,
        "Frozen": 0.10,
        "Toxic": 0.08,
        "Radiated": 0.06,
        "Volcanic": 0.06,
        "Exotic": 0.10,
    },
    "Trader": {
        "Desert": 0.22,
        "Lush": 0.16,
        "Frozen": 0.10,
        "Toxic": 0.10,
        "Radiated": 0.10,
        "Volcanic": 0.09,
        "Oceanic": 0.08,
        "Exotic": 0.15,
    },
    "Casual": {
        "Lush": 0.36,
        "Oceanic": 0.18,
        "Frozen": 0.12,
        "Desert": 0.12,
        "Exotic": 0.10,
        "Toxic": 0.05,
        "Radiated": 0.04,
        "Volcanic": 0.03,
    },
    "Hardcore": {
        "Volcanic": 0.18,
        "Radiated": 0.17,
        "Toxic": 0.15,
        "Frozen": 0.12,
        "Desert": 0.10,
        "Exotic": 0.12,
        "Lush": 0.08,
        "Oceanic": 0.08,
    },
}

MISSION_TYPE_WEIGHTS: dict[str, dict[str, float]] = {
    "Explorer": {
        "Exploration": 0.34,
        "Survey": 0.20,
        "Story": 0.18,
        "Combat": 0.10,
        "Trade": 0.08,
        "Base Building": 0.10,
    },
    "Builder": {
        "Base Building": 0.36,
        "Story": 0.14,
        "Survey": 0.12,
        "Exploration": 0.16,
        "Trade": 0.10,
        "Combat": 0.12,
    },
    "Trader": {
        "Trade": 0.38,
        "Exploration": 0.12,
        "Survey": 0.10,
        "Story": 0.14,
        "Combat": 0.10,
        "Base Building": 0.16,
    },
    "Casual": {
        "Story": 0.28,
        "Exploration": 0.20,
        "Trade": 0.12,
        "Survey": 0.12,
        "Base Building": 0.14,
        "Combat": 0.14,
    },
    "Hardcore": {
        "Combat": 0.32,
        "Story": 0.18,
        "Exploration": 0.16,
        "Trade": 0.10,
        "Survey": 0.08,
        "Base Building": 0.16,
    },
}

DIFFICULTY_WEIGHTS: dict[str, dict[str, float]] = {
    "Explorer": {"Relaxed": 0.16, "Normal": 0.56, "Survival": 0.22, "Permadeath": 0.06},
    "Builder": {"Relaxed": 0.22, "Normal": 0.58, "Survival": 0.16, "Permadeath": 0.04},
    "Trader": {"Relaxed": 0.12, "Normal": 0.60, "Survival": 0.22, "Permadeath": 0.06},
    "Casual": {"Relaxed": 0.34, "Normal": 0.54, "Survival": 0.10, "Permadeath": 0.02},
    "Hardcore": {"Relaxed": 0.02, "Normal": 0.34, "Survival": 0.40, "Permadeath": 0.24},
}

SHIP_CLASS_WEIGHTS: dict[str, dict[str, float]] = {
    "Explorer": {
        "Explorer": 0.38,
        "Shuttle": 0.16,
        "Solar": 0.18,
        "Fighter": 0.12,
        "Hauler": 0.10,
        "Sentinel": 0.06,
    },
    "Builder": {
        "Hauler": 0.30,
        "Shuttle": 0.24,
        "Explorer": 0.18,
        "Solar": 0.10,
        "Fighter": 0.10,
        "Sentinel": 0.08,
    },
    "Trader": {
        "Hauler": 0.34,
        "Solar": 0.24,
        "Shuttle": 0.14,
        "Explorer": 0.10,
        "Fighter": 0.08,
        "Sentinel": 0.10,
    },
    "Casual": {
        "Shuttle": 0.34,
        "Explorer": 0.18,
        "Solar": 0.18,
        "Hauler": 0.14,
        "Fighter": 0.10,
        "Sentinel": 0.06,
    },
    "Hardcore": {
        "Fighter": 0.32,
        "Sentinel": 0.24,
        "Solar": 0.16,
        "Explorer": 0.10,
        "Hauler": 0.10,
        "Shuttle": 0.08,
    },
}

MULTIPLAYER_PROBABILITIES: dict[str, float] = {
    "Explorer": 0.24,
    "Builder": 0.31,
    "Trader": 0.28,
    "Casual": 0.19,
    "Hardcore": 0.36,
}


def export_session_facts(
    player_frame: pd.DataFrame,
    behaviour_frame: pd.DataFrame,
    config: SimulationConfig,
    output_path: Path,
    scenario_calendar: pd.DataFrame | None = None,
) -> int:
    """Generate and export gameplay sessions to CSV, returning the row count."""
    _validate_player_frame(player_frame)
    _validate_behaviour_frame(behaviour_frame)

    session_player_frame = player_frame.merge(
        behaviour_frame,
        on=["PlayerID", "Player Type"],
        how="inner",
        validate="one_to_one",
    )
    session_player_frame["RegistrationDate"] = pd.to_datetime(
        session_player_frame["RegistrationDate"]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    session_count = 0
    header_written = False
    next_session_id = 1

    for session_batch in _iter_session_batches(
        session_player_frame,
        config,
        scenario_calendar=scenario_calendar,
    ):
        if session_batch.empty:
            continue

        batch_size = len(session_batch)
        session_batch.insert(
            0,
            "SessionID",
            np.arange(next_session_id, next_session_id + batch_size, dtype=np.int64),
        )
        session_batch.to_csv(
            output_path,
            mode="a" if header_written else "w",
            header=not header_written,
            index=False,
        )

        header_written = True
        next_session_id += batch_size
        session_count += batch_size

    if not header_written:
        _empty_session_frame().to_csv(output_path, index=False)

    return session_count


def build_session_player_frame(
    player_frame: pd.DataFrame,
    behaviour_frame: pd.DataFrame,
) -> pd.DataFrame:
    """Build the merged player-behaviour frame used by the session engine."""
    _validate_player_frame(player_frame)
    _validate_behaviour_frame(behaviour_frame)

    session_player_frame = player_frame.merge(
        behaviour_frame,
        on=["PlayerID", "Player Type"],
        how="inner",
        validate="one_to_one",
    )
    session_player_frame["RegistrationDate"] = pd.to_datetime(
        session_player_frame["RegistrationDate"]
    )
    return session_player_frame


def derive_player_active_end_dates(
    player_frame: pd.DataFrame,
    behaviour_frame: pd.DataFrame,
    config: SimulationConfig,
    scenario_calendar: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Rebuild the deterministic churn cut-off date for each player."""
    session_player_frame = build_session_player_frame(player_frame, behaviour_frame)
    rng = np.random.default_rng(config.random_seed + 2)
    active_end_dates = _sample_active_end_dates(
        session_player_frame,
        config,
        rng,
        scenario_calendar=scenario_calendar,
    )
    return pd.DataFrame(
        {
            "PlayerID": session_player_frame["PlayerID"].to_numpy(dtype=np.int64),
            "ActiveEndDate": pd.to_datetime(active_end_dates).strftime("%Y-%m-%d"),
        }
    )


def _iter_session_batches(
    session_player_frame: pd.DataFrame,
    config: SimulationConfig,
    scenario_calendar: pd.DataFrame | None = None,
):
    rng = np.random.default_rng(config.random_seed + 2)
    simulation_dates = pd.date_range(
        config.simulation_start_date,
        config.simulation_end_date,
        freq="D",
    )

    registration_dates = session_player_frame["RegistrationDate"].to_numpy(
        dtype="datetime64[D]"
    )
    active_end_dates = _sample_active_end_dates(
        session_player_frame,
        config,
        rng,
        scenario_calendar=scenario_calendar,
    )

    login_probabilities = session_player_frame["DailyLoginProbability"].to_numpy(
        dtype=np.float64
    )
    player_ids = session_player_frame["PlayerID"].to_numpy(dtype=np.int64)
    player_types = session_player_frame["Player Type"].to_numpy(dtype=object)
    average_session_lengths = session_player_frame[
        "AverageSessionLengthMinutes"
    ].to_numpy(dtype=np.float64)
    mission_completion_probabilities = session_player_frame[
        "MissionCompletionProbability"
    ].to_numpy(dtype=np.float64)
    event_by_date = _build_event_lookup(config)
    scenario_by_date = _build_scenario_lookup(config, scenario_calendar)

    for current_day in simulation_dates:
        current_day64 = np.datetime64(current_day.date())
        active_mask = (
            (registration_dates <= current_day64)
            & (current_day64 <= active_end_dates)
        )
        if not np.any(active_mask):
            continue

        active_event = event_by_date.get(current_day.date())
        active_scenario = scenario_by_date.get(current_day.date())
        login_draws = rng.random(active_mask.sum())
        day_login_probabilities = login_probabilities[active_mask].copy()
        if active_event is not None:
            day_login_probabilities = np.clip(
                day_login_probabilities * active_event.login_lift,
                0.0,
                0.98,
            )
        if active_scenario is not None:
            day_login_probabilities = np.clip(
                day_login_probabilities * float(active_scenario["LoginLift"]),
                0.0,
                0.98,
            )
        session_mask = login_draws < day_login_probabilities
        if not np.any(session_mask):
            continue

        active_indices = np.flatnonzero(active_mask)[session_mask]
        yield _build_session_batch(
            active_indices,
            current_day,
            average_session_lengths[active_indices],
            mission_completion_probabilities[active_indices],
            player_ids[active_indices],
            player_types[active_indices],
            active_event,
            active_scenario,
            rng,
        )


def _build_session_batch(
    active_indices: np.ndarray,
    current_day: pd.Timestamp,
    average_session_lengths: np.ndarray,
    mission_completion_probabilities: np.ndarray,
    player_ids: np.ndarray,
    player_types: np.ndarray,
    active_event: LiveServiceEventConfig | None,
    active_scenario: pd.Series | None,
    rng: np.random.Generator,
) -> pd.DataFrame:
    session_count = len(active_indices)
    scenario_session_length_lift = (
        float(active_scenario["SessionLengthLift"])
        if active_scenario is not None
        else 1.0
    )
    session_lengths = _sample_session_lengths(
        average_session_lengths,
        rng,
        session_length_lift=(
            (active_event.session_length_lift if active_event is not None else 1.0)
            * scenario_session_length_lift
        ),
    )
    session_hours = session_lengths / 60.0

    login_offsets = _sample_login_offsets(player_types, session_lengths, rng)
    login_times = current_day + pd.to_timedelta(login_offsets, unit="m")
    logout_times = login_times + pd.to_timedelta(session_lengths, unit="m")

    planets_visited = _sample_count_by_type(
        player_types,
        PLANET_VISIT_RATES,
        session_hours,
        rng,
        minimum=1,
    )
    missions_started = _sample_count_by_type(
        player_types,
        MISSION_START_RATES,
        session_hours,
        rng,
        minimum=0,
    )

    missions_completed = np.zeros(session_count, dtype=np.int32)
    positive_mission_mask = missions_started > 0
    if np.any(positive_mission_mask):
        missions_completed[positive_mission_mask] = rng.binomial(
            missions_started[positive_mission_mask],
            mission_completion_probabilities[positive_mission_mask],
        )

    resources_collected = _sample_resources(
        player_types,
        session_hours,
        planets_visited,
        rng,
    )
    deaths = _sample_count_by_type(
        player_types,
        DEATH_RATES,
        session_hours,
        rng,
        minimum=0,
    )
    base_pieces_placed = _sample_count_by_type(
        player_types,
        BASE_PIECE_RATES,
        session_hours,
        rng,
        minimum=0,
    )
    biomes = _sample_categorical_by_type(player_types, BIOME_WEIGHTS, rng)
    mission_types = _sample_categorical_by_type(player_types, MISSION_TYPE_WEIGHTS, rng)
    mission_types = np.where(missions_started > 0, mission_types, "No Mission")
    difficulties = _sample_categorical_by_type(player_types, DIFFICULTY_WEIGHTS, rng)
    ship_classes = _sample_categorical_by_type(player_types, SHIP_CLASS_WEIGHTS, rng)
    multiplayer_sessions = _sample_multiplayer_sessions(player_types, rng)
    active_event_id = active_event.event_id if active_event is not None else pd.NA
    active_event_name = active_event.event_name if active_event is not None else ""
    active_event_type = active_event.event_type if active_event is not None else ""
    active_scenario_id = (
        int(active_scenario["ScenarioID"])
        if active_scenario is not None and pd.notna(active_scenario["ScenarioID"])
        else pd.NA
    )
    active_scenario_name = (
        str(active_scenario["ScenarioName"]) if active_scenario is not None else ""
    )
    active_scenario_type = (
        str(active_scenario["ScenarioType"]) if active_scenario is not None else ""
    )

    return pd.DataFrame(
        {
            "PlayerID": player_ids,
            "LoginTime": login_times.strftime("%Y-%m-%d %H:%M:%S"),
            "LogoutTime": logout_times.strftime("%Y-%m-%d %H:%M:%S"),
            "SessionLength": session_lengths,
            "EventID": pd.Series([active_event_id] * session_count, dtype="Int64"),
            "EventName": pd.Series([active_event_name] * session_count, dtype="string"),
            "EventType": pd.Series([active_event_type] * session_count, dtype="string"),
            "ScenarioID": pd.Series([active_scenario_id] * session_count, dtype="Int64"),
            "ScenarioName": pd.Series([active_scenario_name] * session_count, dtype="string"),
            "ScenarioType": pd.Series([active_scenario_type] * session_count, dtype="string"),
            "Biome": biomes,
            "MissionType": mission_types,
            "Difficulty": difficulties,
            "MultiplayerSession": multiplayer_sessions,
            "ShipClass": ship_classes,
            "PlanetsVisited": planets_visited,
            "MissionsStarted": missions_started,
            "MissionsCompleted": missions_completed,
            "ResourcesCollected": resources_collected,
            "Deaths": deaths,
            "BasePiecesPlaced": base_pieces_placed,
        }
    )


def _sample_active_end_dates(
    session_player_frame: pd.DataFrame,
    config: SimulationConfig,
    rng: np.random.Generator,
    scenario_calendar: pd.DataFrame | None = None,
) -> np.ndarray:
    registration_dates = session_player_frame["RegistrationDate"].to_numpy(
        dtype="datetime64[D]"
    )
    simulation_end = np.datetime64(config.simulation_end_date)
    monthly_churn_probabilities = session_player_frame["ChurnProbability"].to_numpy(
        dtype=np.float64
    )
    daily_churn_hazard = 1.0 - np.power(1.0 - monthly_churn_probabilities, 1.0 / 30.0)
    daily_churn_hazard = np.clip(daily_churn_hazard, 1e-6, 1 - 1e-6)
    acquisition_churn_lifts = _build_registration_churn_lifts(
        session_player_frame,
        config,
        scenario_calendar,
    )
    adjusted_daily_hazard = np.clip(
        daily_churn_hazard * acquisition_churn_lifts,
        1e-6,
        1 - 1e-6,
    )

    active_end_dates = np.full(
        len(session_player_frame),
        simulation_end,
        dtype="datetime64[D]",
    )
    active_status = np.zeros(len(session_player_frame), dtype=bool)
    churned_status = np.zeros(len(session_player_frame), dtype=bool)
    scenario_lookup = _build_scenario_lookup(config, scenario_calendar)

    for current_day in pd.date_range(
        config.simulation_start_date,
        config.simulation_end_date,
        freq="D",
    ):
        current_day64 = np.datetime64(current_day.date())
        active_status |= registration_dates <= current_day64
        candidate_mask = active_status & (~churned_status)
        if not np.any(candidate_mask):
            continue

        active_scenario = scenario_lookup.get(current_day.date())
        churn_multiplier = (
            float(active_scenario["ChurnLift"])
            if active_scenario is not None
            else 1.0
        )
        daily_hazard = np.clip(
            adjusted_daily_hazard[candidate_mask] * churn_multiplier,
            1e-6,
            1 - 1e-6,
        )
        churn_draws = rng.random(candidate_mask.sum())
        churn_mask = churn_draws < daily_hazard
        if not np.any(churn_mask):
            continue

        candidate_indices = np.flatnonzero(candidate_mask)
        churn_indices = candidate_indices[churn_mask]
        active_end_dates[churn_indices] = current_day64
        churned_status[churn_indices] = True

    return active_end_dates


def _sample_session_lengths(
    average_session_lengths: np.ndarray,
    rng: np.random.Generator,
    session_length_lift: float = 1.0,
) -> np.ndarray:
    lifted_session_lengths = average_session_lengths * session_length_lift
    standard_deviation = np.maximum(average_session_lengths * 0.35, 8.0)
    shape = np.square(lifted_session_lengths / standard_deviation)
    scale = np.square(standard_deviation) / lifted_session_lengths
    sampled_lengths = rng.gamma(shape=shape, scale=scale)
    clipped_lengths = np.clip(np.rint(sampled_lengths), a_min=5, a_max=360)
    return clipped_lengths.astype(np.int32)


def _sample_login_offsets(
    player_types: np.ndarray,
    session_lengths: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    login_offsets = np.empty(len(player_types), dtype=np.int32)

    for player_type, shape in LOGIN_TIME_SHAPES.items():
        player_mask = player_types == player_type
        if not np.any(player_mask):
            continue

        alpha, beta = shape
        batch_size = int(player_mask.sum())
        latest_start = 1439 - session_lengths[player_mask]
        sampled_offsets = np.floor(
            rng.beta(alpha, beta, size=batch_size) * latest_start
        ).astype(np.int32)
        login_offsets[player_mask] = np.clip(sampled_offsets, a_min=0, a_max=None)

    return login_offsets


def _sample_count_by_type(
    player_types: np.ndarray,
    rates: dict[str, float],
    session_hours: np.ndarray,
    rng: np.random.Generator,
    minimum: int,
) -> np.ndarray:
    sampled_counts = np.empty(len(player_types), dtype=np.int32)

    for player_type, rate in rates.items():
        player_mask = player_types == player_type
        if not np.any(player_mask):
            continue

        expected_count = np.maximum(rate * session_hours[player_mask], minimum)
        sampled_counts[player_mask] = np.maximum(
            rng.poisson(expected_count).astype(np.int32),
            minimum,
        )

    return sampled_counts


def _sample_resources(
    player_types: np.ndarray,
    session_hours: np.ndarray,
    planets_visited: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    resources_collected = np.empty(len(player_types), dtype=np.int32)

    for player_type, base_rate in RESOURCE_COLLECTION_RATES.items():
        player_mask = player_types == player_type
        if not np.any(player_mask):
            continue

        expected_resources = (
            base_rate * session_hours[player_mask]
            + planets_visited[player_mask] * 24.0
        )
        resources_collected[player_mask] = rng.poisson(
            np.maximum(expected_resources, 10.0)
        ).astype(np.int32)

    return resources_collected


def _sample_categorical_by_type(
    player_types: np.ndarray,
    weights_by_type: dict[str, dict[str, float]],
    rng: np.random.Generator,
) -> np.ndarray:
    sampled_values = np.empty(len(player_types), dtype=object)

    for player_type, weights in weights_by_type.items():
        player_mask = player_types == player_type
        if not np.any(player_mask):
            continue

        categories = np.array(list(weights.keys()), dtype=object)
        probabilities = np.array(list(weights.values()), dtype=np.float64)
        sampled_values[player_mask] = rng.choice(
            categories,
            size=int(player_mask.sum()),
            p=probabilities,
        )

    return sampled_values


def _sample_multiplayer_sessions(
    player_types: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    multiplayer_sessions = np.zeros(len(player_types), dtype=bool)

    for player_type, probability in MULTIPLAYER_PROBABILITIES.items():
        player_mask = player_types == player_type
        if not np.any(player_mask):
            continue

        multiplayer_sessions[player_mask] = (
            rng.random(int(player_mask.sum())) < probability
        )

    return multiplayer_sessions


def _build_event_lookup(
    config: SimulationConfig,
) -> dict[object, LiveServiceEventConfig]:
    event_lookup: dict[object, LiveServiceEventConfig] = {}
    for event in config.live_service_events:
        event_dates = pd.date_range(event.start_date, event.end_date, freq="D")
        for event_date in event_dates:
            event_lookup[event_date.date()] = event
    return event_lookup


def _build_scenario_lookup(
    config: SimulationConfig,
    scenario_calendar: pd.DataFrame | None,
) -> dict[object, pd.Series]:
    calendar_frame = scenario_calendar
    if calendar_frame is None:
        calendar_frame = build_scenario_calendar(config)

    lookup_frame = calendar_frame.copy()
    lookup_frame["Date"] = pd.to_datetime(lookup_frame["Date"])
    return {
        date_value.date(): row
        for date_value, row in lookup_frame.set_index("Date").iterrows()
        if pd.notna(row["ScenarioID"])
    }


def _build_registration_churn_lifts(
    session_player_frame: pd.DataFrame,
    config: SimulationConfig,
    scenario_calendar: pd.DataFrame | None,
) -> np.ndarray:
    if "AcquisitionScenarioID" in session_player_frame.columns:
        acquisition_scenarios = session_player_frame["AcquisitionScenarioID"].astype(
            "Int64"
        )
        scenario_calendar_frame = scenario_calendar
        if scenario_calendar_frame is None:
            scenario_calendar_frame = build_scenario_calendar(config)
        cohort_lift_lookup = (
            scenario_calendar_frame.dropna(subset=["ScenarioID"])
            .drop_duplicates(subset=["ScenarioID"])
            .set_index("ScenarioID")["CohortChurnLift"]
            .to_dict()
        )
        lifts = acquisition_scenarios.map(cohort_lift_lookup).fillna(1.0)
        return lifts.to_numpy(dtype=np.float64)

    registration_dates = pd.to_datetime(session_player_frame["RegistrationDate"])
    scenario_lookup = _build_scenario_lookup(config, scenario_calendar)
    lifts = np.ones(len(session_player_frame), dtype=np.float64)
    for index, registration_date in enumerate(registration_dates):
        active_scenario = scenario_lookup.get(registration_date.date())
        if active_scenario is None:
            continue
        lifts[index] = float(active_scenario["CohortChurnLift"])
    return lifts


def _empty_session_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "SessionID",
            "PlayerID",
            "LoginTime",
            "LogoutTime",
            "SessionLength",
            "EventID",
            "EventName",
            "EventType",
            "ScenarioID",
            "ScenarioName",
            "ScenarioType",
            "Biome",
            "MissionType",
            "Difficulty",
            "MultiplayerSession",
            "ShipClass",
            "PlanetsVisited",
            "MissionsStarted",
            "MissionsCompleted",
            "ResourcesCollected",
            "Deaths",
            "BasePiecesPlaced",
        ]
    )


def _validate_player_frame(player_frame: pd.DataFrame) -> None:
    required_columns = {"PlayerID", "RegistrationDate", "Player Type"}
    missing_columns = required_columns.difference(player_frame.columns)
    if missing_columns:
        missing_list = ", ".join(sorted(missing_columns))
        msg = f"player_frame is missing required columns: {missing_list}"
        raise ValueError(msg)


def _validate_behaviour_frame(behaviour_frame: pd.DataFrame) -> None:
    required_columns = {
        "PlayerID",
        "Player Type",
        "DailyLoginProbability",
        "AverageSessionLengthMinutes",
        "ChurnProbability",
        "MissionCompletionProbability",
    }
    missing_columns = required_columns.difference(behaviour_frame.columns)
    if missing_columns:
        missing_list = ", ".join(sorted(missing_columns))
        msg = f"behaviour_frame is missing required columns: {missing_list}"
        raise ValueError(msg)
