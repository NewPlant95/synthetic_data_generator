"""Marketing campaign fact generation for GameStudioBI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from config import SimulationConfig


CHANNEL_CAMPAIGN_COUNTS: dict[str, int] = {
    "Organic Search": 4,
    "Steam Wishlist": 5,
    "Platform Store Feature": 4,
    "Seasonal Sale": 4,
    "Creator/Streamer": 5,
    "Friend Referral": 3,
    "Paid User Acquisition": 5,
}

CHANNEL_PARAMETERS: dict[str, dict[str, tuple[float, float]]] = {
    "Organic Search": {
        "ctr": (0.035, 0.070),
        "install_rate": (0.38, 0.58),
        "registration_rate": (0.74, 0.90),
        "cpc": (0.35, 0.85),
    },
    "Steam Wishlist": {
        "ctr": (0.045, 0.090),
        "install_rate": (0.44, 0.68),
        "registration_rate": (0.82, 0.95),
        "cpc": (0.40, 1.10),
    },
    "Platform Store Feature": {
        "ctr": (0.050, 0.095),
        "install_rate": (0.40, 0.63),
        "registration_rate": (0.78, 0.92),
        "cpc": (0.55, 1.30),
    },
    "Seasonal Sale": {
        "ctr": (0.055, 0.110),
        "install_rate": (0.46, 0.72),
        "registration_rate": (0.84, 0.96),
        "cpc": (0.60, 1.45),
    },
    "Creator/Streamer": {
        "ctr": (0.030, 0.065),
        "install_rate": (0.34, 0.54),
        "registration_rate": (0.76, 0.90),
        "cpc": (0.70, 1.80),
    },
    "Friend Referral": {
        "ctr": (0.060, 0.130),
        "install_rate": (0.52, 0.78),
        "registration_rate": (0.88, 0.98),
        "cpc": (0.20, 0.70),
    },
    "Paid User Acquisition": {
        "ctr": (0.020, 0.050),
        "install_rate": (0.25, 0.44),
        "registration_rate": (0.68, 0.84),
        "cpc": (1.10, 2.90),
    },
}

CHANNEL_NAME_TOKENS: dict[str, list[str]] = {
    "Organic Search": ["Atlas", "Signal", "Nebula", "Frontier", "Waypoint"],
    "Steam Wishlist": ["Wishlist", "Voyager", "Launch", "Update", "Expedition"],
    "Platform Store Feature": ["Featured", "Orbit", "Showcase", "Constellation", "Prime"],
    "Seasonal Sale": ["Summer", "Autumn", "Holiday", "Anniversary", "Solstice"],
    "Creator/Streamer": ["Creator", "Broadcast", "Galaxy", "Pulse", "Relay"],
    "Friend Referral": ["Referral", "Squad", "Co-Op", "Beacon", "Alliance"],
    "Paid User Acquisition": ["Prospecting", "Growth", "Acquisition", "Orbit", "Reach"],
}


@dataclass(frozen=True, slots=True)
class MarketingArtifacts:
    campaign_frame: pd.DataFrame
    campaign_day_frame: pd.DataFrame


def build_marketing_artifacts(
    config: SimulationConfig,
    scenario_calendar: pd.DataFrame,
) -> MarketingArtifacts:
    """Build campaign facts plus the day-level allocation used by player acquisition."""
    rng = np.random.default_rng(config.random_seed + 5)
    campaign_catalog = _build_campaign_catalog(config, rng)
    daily_registrations = _build_daily_registration_targets(config, scenario_calendar, rng)
    campaign_day_frame = _build_campaign_day_frame(
        config,
        scenario_calendar,
        campaign_catalog,
        daily_registrations,
        rng,
    )
    campaign_frame = _aggregate_campaign_day_frame(campaign_day_frame)
    return MarketingArtifacts(
        campaign_frame=campaign_frame,
        campaign_day_frame=campaign_day_frame,
    )


def build_marketing_frame(
    config: SimulationConfig,
    scenario_calendar: pd.DataFrame,
) -> pd.DataFrame:
    """Compatibility wrapper returning only the aggregated marketing fact."""
    return build_marketing_artifacts(config, scenario_calendar).campaign_frame


def export_marketing_frame(marketing_frame: pd.DataFrame, output_path: Path) -> Path:
    """Export the marketing fact table to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    marketing_frame.to_csv(output_path, index=False)
    return output_path


def _build_campaign_catalog(
    config: SimulationConfig,
    rng: np.random.Generator,
) -> pd.DataFrame:
    campaign_rows: list[dict[str, object]] = []
    campaign_id = 1
    simulation_start = config.simulation_start_date.isoformat()
    simulation_end = config.simulation_end_date.isoformat()

    for channel in config.acquisition_channel_weights:
        tokens = CHANNEL_NAME_TOKENS[channel]
        for index in range(CHANNEL_CAMPAIGN_COUNTS.get(channel, 3)):
            parameters = CHANNEL_PARAMETERS[channel]
            campaign_rows.append(
                {
                    "CampaignID": campaign_id,
                    "CampaignName": f"{channel} {tokens[index % len(tokens)]} {index + 1}",
                    "Channel": channel,
                    "CampaignKind": "Always On",
                    "CampaignStartDate": simulation_start,
                    "CampaignEndDate": simulation_end,
                    "ScenarioID": pd.NA,
                    "ScenarioName": "",
                    "ScenarioType": "",
                    "PriorityWeight": 1.0 + 0.05 * index,
                    "CTR": float(rng.uniform(*parameters["ctr"])),
                    "InstallRate": float(rng.uniform(*parameters["install_rate"])),
                    "RegistrationRate": float(
                        rng.uniform(*parameters["registration_rate"])
                    ),
                    "CPC": float(rng.uniform(*parameters["cpc"])),
                }
            )
            campaign_id += 1

    for scenario in config.business_scenarios:
        if not scenario.primary_channel:
            continue
        channel = scenario.primary_channel
        tokens = CHANNEL_NAME_TOKENS.get(channel, ["Story"])
        parameters = CHANNEL_PARAMETERS[channel]
        campaign_rows.append(
            {
                "CampaignID": campaign_id,
                "CampaignName": (
                    f"{scenario.scenario_name} {tokens[(campaign_id - 1) % len(tokens)]}"
                ),
                "Channel": channel,
                "CampaignKind": "Scenario Burst",
                "CampaignStartDate": scenario.start_date.isoformat(),
                "CampaignEndDate": scenario.end_date.isoformat(),
                "ScenarioID": scenario.scenario_id,
                "ScenarioName": scenario.scenario_name,
                "ScenarioType": scenario.scenario_type,
                "PriorityWeight": 2.6,
                "CTR": float(rng.uniform(*parameters["ctr"])),
                "InstallRate": float(rng.uniform(*parameters["install_rate"])),
                "RegistrationRate": float(rng.uniform(*parameters["registration_rate"])),
                "CPC": float(rng.uniform(*parameters["cpc"])),
            }
        )
        campaign_id += 1

    return pd.DataFrame(campaign_rows)


def _build_daily_registration_targets(
    config: SimulationConfig,
    scenario_calendar: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    day_count = len(scenario_calendar)
    day_positions = (np.arange(day_count, dtype=np.float64) + 0.5) / day_count
    base_curve = np.power(day_positions, config.registration_curve_alpha - 1.0) * np.power(
        1.0 - day_positions,
        config.registration_curve_beta - 1.0,
    )
    weighted_curve = base_curve * scenario_calendar["AcquisitionLift"].to_numpy(
        dtype=np.float64
    )
    daily_weights = weighted_curve / weighted_curve.sum()
    daily_registrations = rng.multinomial(config.player_count, daily_weights)

    registration_plan = scenario_calendar.loc[
        :,
        ["Date", "ScenarioID", "ScenarioName", "ScenarioType", "PrimaryChannel"],
    ].copy()
    registration_plan["Registrations"] = daily_registrations.astype(np.int64)
    return registration_plan


def _build_campaign_day_frame(
    config: SimulationConfig,
    scenario_calendar: pd.DataFrame,
    campaign_catalog: pd.DataFrame,
    daily_registrations: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    scenario_lookup = scenario_calendar.copy()
    scenario_lookup["Date"] = pd.to_datetime(scenario_lookup["Date"])
    scenario_lookup = scenario_lookup.set_index("Date")

    campaign_day_rows: list[dict[str, object]] = []
    campaign_catalog = campaign_catalog.copy()
    campaign_catalog["CampaignStartDate"] = pd.to_datetime(
        campaign_catalog["CampaignStartDate"]
    )
    campaign_catalog["CampaignEndDate"] = pd.to_datetime(
        campaign_catalog["CampaignEndDate"]
    )

    for registration_row in daily_registrations.itertuples(index=False):
        registration_count = int(registration_row.Registrations)
        if registration_count <= 0:
            continue

        activity_date = pd.Timestamp(registration_row.Date)
        scenario_row = scenario_lookup.loc[activity_date]
        active_campaigns = campaign_catalog[
            (campaign_catalog["CampaignStartDate"] <= activity_date)
            & (activity_date <= campaign_catalog["CampaignEndDate"])
        ].copy()
        if active_campaigns.empty:
            continue

        channel_weights = _build_daily_channel_weights(
            config,
            scenario_row,
        )
        channel_order = list(config.acquisition_channel_weights)
        channel_counts = rng.multinomial(
            registration_count,
            [channel_weights[channel] for channel in channel_order],
        )

        for channel, channel_count in zip(channel_order, channel_counts, strict=True):
            if channel_count == 0:
                continue

            channel_campaigns = active_campaigns[
                active_campaigns["Channel"] == channel
            ].copy()
            if channel_campaigns.empty:
                continue

            campaign_weights = channel_campaigns["PriorityWeight"].to_numpy(dtype=float)
            campaign_weights = campaign_weights / campaign_weights.sum()
            campaign_counts = rng.multinomial(channel_count, campaign_weights)
            for campaign_row, campaign_registrations in zip(
                channel_campaigns.itertuples(index=False),
                campaign_counts,
                strict=True,
            ):
                if campaign_registrations == 0:
                    continue

                funnel_metrics = _calculate_funnel_metrics(
                    int(campaign_registrations),
                    campaign_row,
                    scenario_row,
                )
                campaign_day_rows.append(
                    {
                        "ActivityDate": activity_date.strftime("%Y-%m-%d"),
                        "CampaignID": int(campaign_row.CampaignID),
                        "CampaignName": str(campaign_row.CampaignName),
                        "Channel": str(campaign_row.Channel),
                        "CampaignKind": str(campaign_row.CampaignKind),
                        "CampaignStartDate": campaign_row.CampaignStartDate.strftime(
                            "%Y-%m-%d"
                        ),
                        "CampaignEndDate": campaign_row.CampaignEndDate.strftime(
                            "%Y-%m-%d"
                        ),
                        "ScenarioID": campaign_row.ScenarioID,
                        "ScenarioName": str(campaign_row.ScenarioName),
                        "ScenarioType": str(campaign_row.ScenarioType),
                        "Registrations": int(campaign_registrations),
                        **funnel_metrics,
                    }
                )

    if not campaign_day_rows:
        return pd.DataFrame(
            columns=[
                "ActivityDate",
                "CampaignID",
                "CampaignName",
                "Channel",
                "CampaignKind",
                "CampaignStartDate",
                "CampaignEndDate",
                "ScenarioID",
                "ScenarioName",
                "ScenarioType",
                "Spend",
                "Impressions",
                "Clicks",
                "Installs",
                "Registrations",
            ]
        )

    return pd.DataFrame(campaign_day_rows).sort_values(
        ["ActivityDate", "Channel", "CampaignID"],
        kind="mergesort",
    ).reset_index(drop=True)


def _build_daily_channel_weights(
    config: SimulationConfig,
    scenario_row: pd.Series,
) -> dict[str, float]:
    channel_weights = dict(config.acquisition_channel_weights)
    primary_channel = str(scenario_row["PrimaryChannel"])
    acquisition_lift = float(scenario_row["AcquisitionLift"])
    scenario_type = str(scenario_row["ScenarioType"])

    if primary_channel:
        focus_multiplier = 1.0 + max(acquisition_lift - 1.0, 0.0) * 1.9
        if primary_channel in channel_weights:
            channel_weights[primary_channel] *= focus_multiplier

    if scenario_type == "Viral Campaign":
        for channel_name in ("Creator/Streamer", "Friend Referral"):
            if channel_name in channel_weights:
                channel_weights[channel_name] *= 1.35
    elif scenario_type == "Marketing Campaign":
        for channel_name in ("Creator/Streamer", "Paid User Acquisition"):
            if channel_name in channel_weights:
                channel_weights[channel_name] *= 1.18
    elif scenario_type == "Major Update":
        for channel_name in ("Steam Wishlist", "Platform Store Feature"):
            if channel_name in channel_weights:
                channel_weights[channel_name] *= 1.12

    total_weight = float(sum(channel_weights.values()))
    return {
        channel_name: weight / total_weight
        for channel_name, weight in channel_weights.items()
    }


def _calculate_funnel_metrics(
    registrations: int,
    campaign_row,
    scenario_row: pd.Series,
) -> dict[str, int | float]:
    marketing_efficiency_lift = float(scenario_row["MarketingEfficiencyLift"])
    marketing_spend_lift = float(scenario_row["MarketingSpendLift"])

    effective_ctr = np.clip(
        float(campaign_row.CTR) * marketing_efficiency_lift**0.35,
        0.005,
        0.24,
    )
    effective_install_rate = np.clip(
        float(campaign_row.InstallRate) * marketing_efficiency_lift**0.25,
        0.08,
        0.98,
    )
    effective_registration_rate = np.clip(
        float(campaign_row.RegistrationRate) * marketing_efficiency_lift**0.18,
        0.20,
        0.99,
    )

    installs = int(np.ceil(registrations / effective_registration_rate))
    clicks = int(np.ceil(installs / effective_install_rate))
    impressions = int(np.ceil(clicks / effective_ctr))
    spend = round(
        clicks
        * float(campaign_row.CPC)
        * marketing_spend_lift
        / max(marketing_efficiency_lift**0.10, 0.7),
        2,
    )

    return {
        "Spend": spend,
        "Impressions": impressions,
        "Clicks": clicks,
        "Installs": installs,
    }


def _aggregate_campaign_day_frame(campaign_day_frame: pd.DataFrame) -> pd.DataFrame:
    if campaign_day_frame.empty:
        return campaign_day_frame

    aggregated = (
        campaign_day_frame.groupby(
            [
                "CampaignID",
                "CampaignName",
                "Channel",
                "CampaignKind",
                "CampaignStartDate",
                "CampaignEndDate",
                "ScenarioID",
                "ScenarioName",
                "ScenarioType",
            ],
            dropna=False,
            as_index=False,
        )[["Spend", "Impressions", "Clicks", "Installs", "Registrations"]]
        .sum()
        .sort_values(["Channel", "CampaignID"], kind="mergesort")
        .reset_index(drop=True)
    )
    aggregated["Spend"] = aggregated["Spend"].round(2)
    aggregated["ScenarioID"] = aggregated["ScenarioID"].astype("Int64")
    return aggregated
