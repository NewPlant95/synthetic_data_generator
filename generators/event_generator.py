"""Live-service event dimension generation for GameStudioBI."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import SimulationConfig


def build_event_frame(config: SimulationConfig) -> pd.DataFrame:
    """Build a live-service event dimension from config."""
    return pd.DataFrame(
        [
            {
                "EventID": event.event_id,
                "EventName": event.event_name,
                "EventType": event.event_type,
                "StartDate": event.start_date.isoformat(),
                "EndDate": event.end_date.isoformat(),
                "LoginLift": event.login_lift,
                "SessionLengthLift": event.session_length_lift,
                "PurchaseLift": event.purchase_lift,
            }
            for event in config.live_service_events
        ]
    )


def export_event_frame(event_frame: pd.DataFrame, output_path: Path) -> Path:
    """Export the live-service event dimension to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    event_frame.to_csv(output_path, index=False)
    return output_path
