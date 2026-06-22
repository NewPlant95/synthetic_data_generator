"""Date dimension generation for GameStudioBI."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import SimulationConfig
from generators.scenario_generator import build_scenario_calendar


def build_date_frame(
    config: SimulationConfig,
    scenario_calendar: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build a date dimension covering the simulation date range."""
    scenario_frame = scenario_calendar
    if scenario_frame is None:
        scenario_frame = build_scenario_calendar(config)

    dates = pd.date_range(
        config.simulation_start_date,
        config.simulation_end_date,
        freq="D",
    )
    date_frame = pd.DataFrame({"FullDate": dates})
    date_frame["ActiveEventID"] = pd.Series(pd.NA, index=date_frame.index, dtype="Int64")
    date_frame["ActiveEventName"] = pd.Series("", index=date_frame.index, dtype="string")
    date_frame["ActiveEventType"] = pd.Series("", index=date_frame.index, dtype="string")
    date_frame["ActiveScenarioID"] = pd.Series(pd.NA, index=date_frame.index, dtype="Int64")
    date_frame["ActiveScenarioName"] = pd.Series("", index=date_frame.index, dtype="string")
    date_frame["ActiveScenarioType"] = pd.Series("", index=date_frame.index, dtype="string")

    for event in config.live_service_events:
        event_mask = (
            (date_frame["FullDate"] >= pd.Timestamp(event.start_date))
            & (date_frame["FullDate"] <= pd.Timestamp(event.end_date))
        )
        date_frame.loc[event_mask, "ActiveEventID"] = event.event_id
        date_frame.loc[event_mask, "ActiveEventName"] = event.event_name
        date_frame.loc[event_mask, "ActiveEventType"] = event.event_type

    scenario_lookup = scenario_frame.copy()
    scenario_lookup["Date"] = pd.to_datetime(scenario_lookup["Date"])
    scenario_lookup = scenario_lookup.set_index("Date")
    date_frame["ActiveScenarioID"] = scenario_lookup["ScenarioID"].reindex(
        date_frame["FullDate"]
    ).to_numpy()
    date_frame["ActiveScenarioName"] = scenario_lookup["ScenarioName"].reindex(
        date_frame["FullDate"]
    ).to_numpy()
    date_frame["ActiveScenarioType"] = scenario_lookup["ScenarioType"].reindex(
        date_frame["FullDate"]
    ).to_numpy()

    iso_calendar = date_frame["FullDate"].dt.isocalendar()

    date_frame["DateKey"] = date_frame["FullDate"].dt.strftime("%Y%m%d").astype(int)
    date_frame["DayOfMonth"] = date_frame["FullDate"].dt.day.astype(int)
    date_frame["DayOfWeekNumber"] = date_frame["FullDate"].dt.dayofweek.add(1).astype(int)
    date_frame["DayName"] = date_frame["FullDate"].dt.day_name()
    date_frame["WeekOfYear"] = iso_calendar.week.astype(int)
    date_frame["MonthNumber"] = date_frame["FullDate"].dt.month.astype(int)
    date_frame["MonthName"] = date_frame["FullDate"].dt.month_name()
    date_frame["QuarterNumber"] = date_frame["FullDate"].dt.quarter.astype(int)
    date_frame["YearNumber"] = date_frame["FullDate"].dt.year.astype(int)
    date_frame["IsWeekend"] = date_frame["DayOfWeekNumber"].isin([6, 7])
    date_frame["MonthStartDate"] = date_frame["FullDate"].dt.to_period("M").dt.start_time
    date_frame["QuarterStartDate"] = (
        date_frame["FullDate"].dt.to_period("Q").dt.start_time
    )
    date_frame["FullDate"] = date_frame["FullDate"].dt.strftime("%Y-%m-%d")
    date_frame["MonthStartDate"] = date_frame["MonthStartDate"].dt.strftime("%Y-%m-%d")
    date_frame["QuarterStartDate"] = date_frame["QuarterStartDate"].dt.strftime(
        "%Y-%m-%d"
    )

    return date_frame.loc[
        :,
        [
            "DateKey",
            "FullDate",
            "DayOfMonth",
            "DayOfWeekNumber",
            "DayName",
            "WeekOfYear",
            "MonthNumber",
            "MonthName",
            "QuarterNumber",
            "YearNumber",
            "IsWeekend",
            "ActiveEventID",
            "ActiveEventName",
            "ActiveEventType",
            "ActiveScenarioID",
            "ActiveScenarioName",
            "ActiveScenarioType",
            "MonthStartDate",
            "QuarterStartDate",
        ],
    ]


def export_date_frame(date_frame: pd.DataFrame, output_path: Path) -> Path:
    """Export the date dimension to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    date_frame.to_csv(output_path, index=False)
    return output_path
