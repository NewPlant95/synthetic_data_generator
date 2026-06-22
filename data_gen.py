"""Project entry point for the GameStudioBI scaffold."""

from __future__ import annotations

from pathlib import Path

from config import load_simulation_config
from generators.commerce_generator import export_purchase_facts, export_review_facts
from generators.date_generator import build_date_frame, export_date_frame
from generators.event_generator import build_event_frame, export_event_frame
from generators.finance_generator import export_finance_facts
from generators.marketing_generator import build_marketing_artifacts, export_marketing_frame
from generators.player_generator import build_player_frame, export_player_frame
from generators.scenario_generator import (
    build_business_event_frame,
    build_scenario_calendar,
    build_scenario_frame,
    export_business_event_frame,
    export_scenario_frame,
)
from generators.session_generator import export_session_facts
from generators.validation_generator import export_validation_artifacts
from simulation.behaviour_engine import assign_player_behaviours


OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DATE_OUTPUT_PATH = OUTPUT_DIR / "dim_date.csv"
EVENT_OUTPUT_PATH = OUTPUT_DIR / "dim_live_event.csv"
BUSINESS_EVENT_OUTPUT_PATH = OUTPUT_DIR / "dim_business_events.csv"
SCENARIO_OUTPUT_PATH = OUTPUT_DIR / "dim_business_scenario.csv"
MARKETING_OUTPUT_PATH = OUTPUT_DIR / "fact_marketing.csv"
PLAYER_OUTPUT_PATH = OUTPUT_DIR / "dim_player.csv"
SESSION_OUTPUT_PATH = OUTPUT_DIR / "fact_sessions.csv"
PURCHASE_OUTPUT_PATH = OUTPUT_DIR / "fact_purchases.csv"
REVIEW_OUTPUT_PATH = OUTPUT_DIR / "fact_reviews.csv"
FINANCE_OUTPUT_PATH = OUTPUT_DIR / "fact_finance.csv"
VALIDATION_CHECKS_PATH = OUTPUT_DIR / "validation_checks.csv"
SUMMARY_STATISTICS_PATH = OUTPUT_DIR / "summary_statistics.csv"


def main() -> None:
    config = load_simulation_config()
    scenario_calendar = build_scenario_calendar(config)
    scenario_frame = build_scenario_frame(config)
    business_event_frame = build_business_event_frame(config)
    scenario_export_path = export_scenario_frame(scenario_frame, SCENARIO_OUTPUT_PATH)
    business_event_export_path = export_business_event_frame(
        business_event_frame,
        BUSINESS_EVENT_OUTPUT_PATH,
    )
    date_frame = build_date_frame(config, scenario_calendar=scenario_calendar)
    date_export_path = export_date_frame(date_frame, DATE_OUTPUT_PATH)
    event_frame = build_event_frame(config)
    event_export_path = export_event_frame(event_frame, EVENT_OUTPUT_PATH)
    marketing_artifacts = build_marketing_artifacts(config, scenario_calendar)
    marketing_frame = marketing_artifacts.campaign_frame
    marketing_export_path = export_marketing_frame(marketing_frame, MARKETING_OUTPUT_PATH)
    player_frame = build_player_frame(
        config,
        marketing_frame=marketing_frame,
        campaign_day_frame=marketing_artifacts.campaign_day_frame,
    )
    player_export_path = export_player_frame(player_frame, PLAYER_OUTPUT_PATH)
    behaviour_frame = assign_player_behaviours(player_frame, config)
    session_count = export_session_facts(
        player_frame,
        behaviour_frame,
        config,
        SESSION_OUTPUT_PATH,
        scenario_calendar=scenario_calendar,
    )
    purchase_count = export_purchase_facts(
        SESSION_OUTPUT_PATH,
        player_frame,
        behaviour_frame,
        config,
        PURCHASE_OUTPUT_PATH,
        scenario_calendar=scenario_calendar,
    )
    review_count = export_review_facts(
        SESSION_OUTPUT_PATH,
        player_frame,
        behaviour_frame,
        config,
        REVIEW_OUTPUT_PATH,
        scenario_calendar=scenario_calendar,
    )
    finance_count = export_finance_facts(
        PURCHASE_OUTPUT_PATH,
        SESSION_OUTPUT_PATH,
        player_frame,
        marketing_frame,
        config,
        FINANCE_OUTPUT_PATH,
    )
    validation_check_count, summary_stat_count = export_validation_artifacts(
        player_frame,
        marketing_frame,
        config,
        OUTPUT_DIR,
        SESSION_OUTPUT_PATH,
        PURCHASE_OUTPUT_PATH,
        REVIEW_OUTPUT_PATH,
        FINANCE_OUTPUT_PATH,
    )

    print("GameStudioBI date dimension generated")
    print(f"rows: {len(date_frame)}")
    print(f"output: {date_export_path}")
    print("GameStudioBI business scenario dimension generated")
    print(f"rows: {len(scenario_frame)}")
    print(f"output: {scenario_export_path}")
    print("GameStudioBI business event dimension generated")
    print(f"rows: {len(business_event_frame)}")
    print(f"output: {business_event_export_path}")
    print("GameStudioBI live-service event dimension generated")
    print(f"rows: {len(event_frame)}")
    print(f"output: {event_export_path}")
    print("GameStudioBI marketing fact generated")
    print(f"rows: {len(marketing_frame)}")
    print(f"output: {marketing_export_path}")
    print("GameStudioBI player dimension generated")
    print(f"rows: {len(player_frame)}")
    print(f"output: {player_export_path}")
    print("GameStudioBI session fact generated")
    print(f"rows: {session_count}")
    print(f"output: {SESSION_OUTPUT_PATH}")
    print("GameStudioBI purchase fact generated")
    print(f"rows: {purchase_count}")
    print(f"output: {PURCHASE_OUTPUT_PATH}")
    print("GameStudioBI review fact generated")
    print(f"rows: {review_count}")
    print(f"output: {REVIEW_OUTPUT_PATH}")
    print("GameStudioBI finance fact generated")
    print(f"rows: {finance_count}")
    print(f"output: {FINANCE_OUTPUT_PATH}")
    print("GameStudioBI validation checks generated")
    print(f"rows: {validation_check_count}")
    print(f"output: {VALIDATION_CHECKS_PATH}")
    print("GameStudioBI summary statistics generated")
    print(f"rows: {summary_stat_count}")
    print(f"output: {SUMMARY_STATISTICS_PATH}")


if __name__ == "__main__":
    main()
