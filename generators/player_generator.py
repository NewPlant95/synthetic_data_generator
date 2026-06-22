"""Player dimension generator for GameStudioBI."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

from config import SimulationConfig


def build_player_frame(
    config: SimulationConfig,
    marketing_frame: pd.DataFrame | None = None,
    campaign_day_frame: pd.DataFrame | None = None,
    faker: Faker | None = None,
) -> pd.DataFrame:
    """Build a configurable player dimension dataset."""
    fake = faker or Faker()
    fake.seed_instance(config.random_seed)
    rng = np.random.default_rng(config.random_seed)

    player_count = config.player_count
    countries = _sample_weighted(fake, config.country_weights, player_count)
    platforms = _sample_weighted(fake, config.platform_weights, player_count)
    player_types = _sample_weighted(fake, config.player_type_weights, player_count)
    ages = _build_ages(config, fake, rng)
    (
        registration_dates,
        campaign_ids,
        acquisition_channels,
        acquisition_scenario_ids,
        acquisition_scenario_names,
        acquisition_scenario_types,
    ) = _build_registration_assignments(
        config,
        marketing_frame,
        campaign_day_frame,
        rng,
        fake,
    )

    player_frame = pd.DataFrame(
        {
            "RegistrationDate": registration_dates,
            "Country": countries,
            "Age": ages,
            "Platform": platforms,
            "CampaignID": campaign_ids,
            "Acquisition Channel": acquisition_channels,
            "AcquisitionScenarioID": acquisition_scenario_ids,
            "AcquisitionScenarioName": acquisition_scenario_names,
            "AcquisitionScenarioType": acquisition_scenario_types,
            "Player Type": player_types,
        }
    ).sort_values(
        by="RegistrationDate",
        kind="mergesort",
    ).reset_index(drop=True)

    player_frame.insert(
        0,
        "PlayerID",
        np.arange(1, player_count + 1, dtype=np.int64),
    )
    player_frame["RegistrationDate"] = player_frame["RegistrationDate"].dt.strftime(
        "%Y-%m-%d"
    )
    return player_frame


def export_player_frame(player_frame: pd.DataFrame, output_path: Path) -> Path:
    """Export the player dimension dataset to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    player_frame.to_csv(output_path, index=False)
    return output_path


def _build_ages(
    config: SimulationConfig,
    fake: Faker,
    rng: np.random.Generator,
) -> np.ndarray:
    age_band_labels = np.array(
        _sample_weighted(fake, config.age_band_weights, config.player_count),
        dtype=object,
    )
    ages = np.empty(config.player_count, dtype=np.int16)

    for band_label in config.age_band_weights:
        lower_bound, upper_bound = _parse_age_band(band_label)
        band_mask = age_band_labels == band_label
        band_size = int(band_mask.sum())
        if band_size == 0:
            continue
        ages[band_mask] = rng.integers(
            lower_bound,
            upper_bound + 1,
            size=band_size,
        )

    return ages


def _build_registration_assignments(
    config: SimulationConfig,
    marketing_frame: pd.DataFrame | None,
    campaign_day_frame: pd.DataFrame | None,
    rng: np.random.Generator,
    fake: Faker,
) -> tuple[pd.Series, np.ndarray, list[str], pd.Series, pd.Series, pd.Series]:
    if campaign_day_frame is not None:
        return _build_assignments_from_campaign_days(config, campaign_day_frame, rng)

    if marketing_frame is None:
        registration_dates = _build_registration_dates(config, rng)
        acquisition_channels = _sample_weighted(
            fake,
            config.acquisition_channel_weights,
            config.player_count,
        )
        campaign_ids = np.zeros(config.player_count, dtype=np.int64)
        acquisition_scenario_ids = pd.Series(
            pd.array([pd.NA] * config.player_count, dtype="Int64")
        )
        acquisition_scenario_names = pd.Series([""] * config.player_count, dtype="string")
        acquisition_scenario_types = pd.Series([""] * config.player_count, dtype="string")
        return (
            registration_dates,
            campaign_ids,
            acquisition_channels,
            acquisition_scenario_ids,
            acquisition_scenario_names,
            acquisition_scenario_types,
        )

    required_columns = {"CampaignID", "Channel", "Registrations"}
    missing_columns = required_columns.difference(marketing_frame.columns)
    if missing_columns:
        missing_list = ", ".join(sorted(missing_columns))
        msg = f"marketing_frame is missing required columns: {missing_list}"
        raise ValueError(msg)

    registration_dates = _build_registration_dates(config, rng)
    campaign_ids = np.repeat(
        marketing_frame["CampaignID"].to_numpy(dtype=np.int64),
        marketing_frame["Registrations"].to_numpy(dtype=np.int64),
    )
    acquisition_channels = np.repeat(
        marketing_frame["Channel"].to_numpy(dtype=object),
        marketing_frame["Registrations"].to_numpy(dtype=np.int64),
    )
    if len(campaign_ids) != config.player_count:
        msg = "marketing_frame registrations must sum to player_count"
        raise ValueError(msg)

    permutation = rng.permutation(config.player_count)
    shuffled_campaign_ids = campaign_ids[permutation]
    shuffled_channels = acquisition_channels[permutation].tolist()
    acquisition_scenario_ids = pd.Series(
        pd.array([pd.NA] * config.player_count, dtype="Int64")
    )
    acquisition_scenario_names = pd.Series([""] * config.player_count, dtype="string")
    acquisition_scenario_types = pd.Series([""] * config.player_count, dtype="string")
    return (
        registration_dates,
        shuffled_campaign_ids,
        shuffled_channels,
        acquisition_scenario_ids,
        acquisition_scenario_names,
        acquisition_scenario_types,
    )


def _build_registration_dates(
    config: SimulationConfig,
    rng: np.random.Generator,
) -> pd.Series:
    start = np.datetime64(config.simulation_start_date)
    simulation_length_days = (
        config.simulation_end_date - config.simulation_start_date
    ).days
    day_offsets = np.floor(
        rng.beta(
            config.registration_curve_alpha,
            config.registration_curve_beta,
            size=config.player_count,
        )
        * (simulation_length_days + 1)
    ).astype(np.int32)

    registration_dates = start + day_offsets.astype("timedelta64[D]")
    return pd.Series(pd.to_datetime(registration_dates), copy=False)


def _build_assignments_from_campaign_days(
    config: SimulationConfig,
    campaign_day_frame: pd.DataFrame,
    rng: np.random.Generator,
) -> tuple[pd.Series, np.ndarray, list[str], pd.Series, pd.Series, pd.Series]:
    required_columns = {
        "ActivityDate",
        "CampaignID",
        "Channel",
        "Registrations",
        "ScenarioID",
        "ScenarioName",
        "ScenarioType",
    }
    missing_columns = required_columns.difference(campaign_day_frame.columns)
    if missing_columns:
        missing_list = ", ".join(sorted(missing_columns))
        msg = f"campaign_day_frame is missing required columns: {missing_list}"
        raise ValueError(msg)

    registration_dates = np.repeat(
        campaign_day_frame["ActivityDate"].to_numpy(dtype=object),
        campaign_day_frame["Registrations"].to_numpy(dtype=np.int64),
    )
    campaign_ids = np.repeat(
        campaign_day_frame["CampaignID"].to_numpy(dtype=np.int64),
        campaign_day_frame["Registrations"].to_numpy(dtype=np.int64),
    )
    acquisition_channels = np.repeat(
        campaign_day_frame["Channel"].to_numpy(dtype=object),
        campaign_day_frame["Registrations"].to_numpy(dtype=np.int64),
    )
    acquisition_scenario_ids = np.repeat(
        campaign_day_frame["ScenarioID"].astype("Int64").to_numpy(),
        campaign_day_frame["Registrations"].to_numpy(dtype=np.int64),
    )
    acquisition_scenario_names = np.repeat(
        campaign_day_frame["ScenarioName"].to_numpy(dtype=object),
        campaign_day_frame["Registrations"].to_numpy(dtype=np.int64),
    )
    acquisition_scenario_types = np.repeat(
        campaign_day_frame["ScenarioType"].to_numpy(dtype=object),
        campaign_day_frame["Registrations"].to_numpy(dtype=np.int64),
    )

    if len(campaign_ids) != config.player_count:
        msg = "campaign_day_frame registrations must sum to player_count"
        raise ValueError(msg)

    permutation = rng.permutation(config.player_count)
    return (
        pd.Series(pd.to_datetime(registration_dates[permutation]), copy=False),
        campaign_ids[permutation],
        acquisition_channels[permutation].tolist(),
        pd.Series(pd.array(acquisition_scenario_ids[permutation], dtype="Int64")),
        pd.Series(acquisition_scenario_names[permutation], dtype="string"),
        pd.Series(acquisition_scenario_types[permutation], dtype="string"),
    )


def _sample_weighted(
    fake: Faker,
    weights: dict[str, float],
    sample_size: int,
) -> list[str]:
    ordered_weights = OrderedDict(weights.items())
    return list(
        fake.random_elements(
            elements=ordered_weights,
            length=sample_size,
            unique=False,
            use_weighting=True,
        )
    )


def _parse_age_band(band_label: str) -> tuple[int, int]:
    lower_bound_text, upper_bound_text = band_label.split("-", maxsplit=1)
    return int(lower_bound_text), int(upper_bound_text)
