"""Business scenario generation and daily scenario calendar construction."""

from __future__ import annotations

from math import cos, pi
from pathlib import Path

import pandas as pd

from config import BusinessScenarioConfig, SimulationConfig


SCENARIO_MULTIPLIER_COLUMNS = [
    "AcquisitionLift",
    "MarketingEfficiencyLift",
    "MarketingSpendLift",
    "LoginLift",
    "SessionLengthLift",
    "PurchaseLift",
    "PurchasePriceLift",
    "CosmeticPurchaseLift",
    "ChurnLift",
    "CohortChurnLift",
]

SCENARIO_SHIFT_COLUMNS = [
    "ReviewScoreShift",
    "ReviewRecommendationShift",
]


def build_scenario_frame(config: SimulationConfig) -> pd.DataFrame:
    """Build a business scenario dimension from config."""
    return pd.DataFrame(
        [
            {
                "ScenarioID": scenario.scenario_id,
                "ScenarioName": scenario.scenario_name,
                "ScenarioType": scenario.scenario_type,
                "StartDate": scenario.start_date.isoformat(),
                "EndDate": scenario.end_date.isoformat(),
                "RampUpDays": scenario.ramp_up_days,
                "RampDownDays": scenario.ramp_down_days,
                "Description": scenario.description,
                "ExpectedImpact": scenario.expected_impact,
                "AffectedMetrics": ", ".join(scenario.affected_metrics),
                "PrimaryChannel": scenario.primary_channel or "",
                "AcquisitionLift": scenario.acquisition_lift,
                "MarketingEfficiencyLift": scenario.marketing_efficiency_lift,
                "MarketingSpendLift": scenario.marketing_spend_lift,
                "LoginLift": scenario.login_lift,
                "SessionLengthLift": scenario.session_length_lift,
                "PurchaseLift": scenario.purchase_lift,
                "PurchasePriceLift": scenario.purchase_price_lift,
                "CosmeticPurchaseLift": scenario.cosmetic_purchase_lift,
                "ChurnLift": scenario.churn_lift,
                "CohortChurnLift": scenario.cohort_churn_lift,
                "ReviewScoreShift": scenario.review_score_shift,
                "ReviewRecommendationShift": scenario.review_recommendation_shift,
            }
            for scenario in config.business_scenarios
        ]
    )


def build_business_event_frame(config: SimulationConfig) -> pd.DataFrame:
    """Build an analyst-facing business event dimension from scenario config."""
    return pd.DataFrame(
        [
            {
                "EventID": scenario.scenario_id,
                "EventName": scenario.scenario_name,
                "EventType": scenario.scenario_type,
                "StartDate": scenario.start_date.isoformat(),
                "EndDate": scenario.end_date.isoformat(),
                "Description": scenario.description,
                "ExpectedBusinessImpact": scenario.expected_impact,
            }
            for scenario in config.business_scenarios
        ]
    )


def export_scenario_frame(scenario_frame: pd.DataFrame, output_path: Path) -> Path:
    """Export the business scenario dimension to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scenario_frame.to_csv(output_path, index=False)
    return output_path


def export_business_event_frame(
    business_event_frame: pd.DataFrame,
    output_path: Path,
) -> Path:
    """Export the business event dimension to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    business_event_frame.to_csv(output_path, index=False)
    return output_path


def build_scenario_calendar(config: SimulationConfig) -> pd.DataFrame:
    """Build a day-level scenario calendar with gradual KPI effects."""
    scenario_dates = pd.date_range(
        config.simulation_start_date,
        config.simulation_end_date,
        freq="D",
    )
    calendar = pd.DataFrame({"Date": scenario_dates})
    calendar["ScenarioID"] = pd.Series(pd.NA, index=calendar.index, dtype="Int64")
    calendar["ScenarioName"] = pd.Series("", index=calendar.index, dtype="string")
    calendar["ScenarioType"] = pd.Series("", index=calendar.index, dtype="string")
    calendar["ScenarioIntensity"] = 0.0
    calendar["Description"] = pd.Series("", index=calendar.index, dtype="string")
    calendar["ExpectedImpact"] = pd.Series("", index=calendar.index, dtype="string")
    calendar["AffectedMetrics"] = pd.Series("", index=calendar.index, dtype="string")
    calendar["PrimaryChannel"] = pd.Series("", index=calendar.index, dtype="string")

    for column in SCENARIO_MULTIPLIER_COLUMNS:
        calendar[column] = 1.0
    for column in SCENARIO_SHIFT_COLUMNS:
        calendar[column] = 0.0

    for scenario in config.business_scenarios:
        scenario_mask = (
            (calendar["Date"] >= pd.Timestamp(scenario.start_date))
            & (calendar["Date"] <= pd.Timestamp(scenario.end_date))
        )
        if not scenario_mask.any():
            continue

        scenario_dates = calendar.loc[scenario_mask, "Date"]
        intensities = scenario_dates.apply(
            lambda value: _scenario_day_intensity(value, scenario)
        ).to_numpy(dtype=float)
        calendar.loc[scenario_mask, "ScenarioID"] = scenario.scenario_id
        calendar.loc[scenario_mask, "ScenarioName"] = scenario.scenario_name
        calendar.loc[scenario_mask, "ScenarioType"] = scenario.scenario_type
        calendar.loc[scenario_mask, "ScenarioIntensity"] = intensities
        calendar.loc[scenario_mask, "Description"] = scenario.description
        calendar.loc[scenario_mask, "ExpectedImpact"] = scenario.expected_impact
        calendar.loc[scenario_mask, "AffectedMetrics"] = ", ".join(
            scenario.affected_metrics
        )
        calendar.loc[scenario_mask, "PrimaryChannel"] = scenario.primary_channel or ""

        _apply_multiplier(calendar, scenario_mask, intensities, "AcquisitionLift", scenario.acquisition_lift)
        _apply_multiplier(
            calendar,
            scenario_mask,
            intensities,
            "MarketingEfficiencyLift",
            scenario.marketing_efficiency_lift,
        )
        _apply_multiplier(
            calendar,
            scenario_mask,
            intensities,
            "MarketingSpendLift",
            scenario.marketing_spend_lift,
        )
        _apply_multiplier(calendar, scenario_mask, intensities, "LoginLift", scenario.login_lift)
        _apply_multiplier(
            calendar,
            scenario_mask,
            intensities,
            "SessionLengthLift",
            scenario.session_length_lift,
        )
        _apply_multiplier(
            calendar,
            scenario_mask,
            intensities,
            "PurchaseLift",
            scenario.purchase_lift,
        )
        _apply_multiplier(
            calendar,
            scenario_mask,
            intensities,
            "PurchasePriceLift",
            scenario.purchase_price_lift,
        )
        _apply_multiplier(
            calendar,
            scenario_mask,
            intensities,
            "CosmeticPurchaseLift",
            scenario.cosmetic_purchase_lift,
        )
        _apply_multiplier(
            calendar,
            scenario_mask,
            intensities,
            "ChurnLift",
            scenario.churn_lift,
        )
        _apply_multiplier(
            calendar,
            scenario_mask,
            intensities,
            "CohortChurnLift",
            scenario.cohort_churn_lift,
        )
        _apply_shift(
            calendar,
            scenario_mask,
            intensities,
            "ReviewScoreShift",
            scenario.review_score_shift,
        )
        _apply_shift(
            calendar,
            scenario_mask,
            intensities,
            "ReviewRecommendationShift",
            scenario.review_recommendation_shift,
        )

    calendar["Date"] = calendar["Date"].dt.strftime("%Y-%m-%d")
    return calendar


def _apply_multiplier(
    calendar: pd.DataFrame,
    mask: pd.Series,
    intensities: pd.Series | list[float] | pd.Index | pd.array,
    column: str,
    target_lift: float,
) -> None:
    calendar.loc[mask, column] = 1.0 + (
        target_lift - 1.0
    ) * pd.Series(intensities, index=calendar.index[mask])


def _apply_shift(
    calendar: pd.DataFrame,
    mask: pd.Series,
    intensities: pd.Series | list[float] | pd.Index | pd.array,
    column: str,
    target_shift: float,
) -> None:
    calendar.loc[mask, column] = target_shift * pd.Series(
        intensities,
        index=calendar.index[mask],
    )


def _scenario_day_intensity(
    current_day: pd.Timestamp,
    scenario: BusinessScenarioConfig,
) -> float:
    start_day = pd.Timestamp(scenario.start_date)
    end_day = pd.Timestamp(scenario.end_date)
    total_days = (end_day - start_day).days + 1
    day_index = (current_day - start_day).days
    if day_index < 0 or day_index >= total_days:
        return 0.0

    intensity = 1.0
    if scenario.ramp_up_days > 0 and day_index < scenario.ramp_up_days:
        intensity = min(
            intensity,
            _eased_progress((day_index + 1) / scenario.ramp_up_days),
        )

    days_remaining = total_days - day_index
    if scenario.ramp_down_days > 0 and days_remaining <= scenario.ramp_down_days:
        intensity = min(
            intensity,
            _eased_progress(days_remaining / scenario.ramp_down_days),
        )
    return float(max(intensity, 0.15))


def _eased_progress(progress: float) -> float:
    bounded_progress = min(max(progress, 0.0), 1.0)
    return 0.15 + 0.85 * 0.5 * (1.0 - cos(pi * bounded_progress))
