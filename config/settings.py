"""Load and validate simulation configuration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isclose
from pathlib import Path
import tomllib


DEFAULT_CONFIG_PATH = Path(__file__).with_name("simulation_config.toml")


@dataclass(frozen=True, slots=True)
class LiveServiceEventConfig:
    event_id: int
    event_name: str
    event_type: str
    start_date: date
    end_date: date
    login_lift: float
    session_length_lift: float
    purchase_lift: float

    def validate(self, label: str) -> "LiveServiceEventConfig":
        if self.event_id <= 0:
            msg = f"{label}.event_id must be greater than 0"
            raise ValueError(msg)
        if self.start_date > self.end_date:
            msg = f"{label}.start_date must be on or before end_date"
            raise ValueError(msg)
        for field_name, field_value in (
            ("login_lift", self.login_lift),
            ("session_length_lift", self.session_length_lift),
            ("purchase_lift", self.purchase_lift),
        ):
            if field_value <= 0:
                msg = f"{label}.{field_name} must be greater than 0"
                raise ValueError(msg)
        return self


@dataclass(frozen=True, slots=True)
class BusinessScenarioConfig:
    scenario_id: int
    scenario_name: str
    scenario_type: str
    start_date: date
    end_date: date
    ramp_up_days: int
    ramp_down_days: int
    description: str
    expected_impact: str
    affected_metrics: tuple[str, ...]
    primary_channel: str | None
    acquisition_lift: float
    marketing_efficiency_lift: float
    marketing_spend_lift: float
    login_lift: float
    session_length_lift: float
    purchase_lift: float
    purchase_price_lift: float
    cosmetic_purchase_lift: float
    churn_lift: float
    cohort_churn_lift: float
    review_score_shift: float
    review_recommendation_shift: float

    def validate(self, label: str) -> "BusinessScenarioConfig":
        if self.scenario_id <= 0:
            msg = f"{label}.scenario_id must be greater than 0"
            raise ValueError(msg)
        if self.start_date > self.end_date:
            msg = f"{label}.start_date must be on or before end_date"
            raise ValueError(msg)
        if self.ramp_up_days < 0 or self.ramp_down_days < 0:
            msg = f"{label}.ramp_up_days and ramp_down_days must be non-negative"
            raise ValueError(msg)
        if not self.description.strip():
            msg = f"{label}.description must not be empty"
            raise ValueError(msg)
        if not self.expected_impact.strip():
            msg = f"{label}.expected_impact must not be empty"
            raise ValueError(msg)
        if not self.affected_metrics:
            msg = f"{label}.affected_metrics must not be empty"
            raise ValueError(msg)
        for field_name, field_value in (
            ("acquisition_lift", self.acquisition_lift),
            ("marketing_efficiency_lift", self.marketing_efficiency_lift),
            ("marketing_spend_lift", self.marketing_spend_lift),
            ("login_lift", self.login_lift),
            ("session_length_lift", self.session_length_lift),
            ("purchase_lift", self.purchase_lift),
            ("purchase_price_lift", self.purchase_price_lift),
            ("cosmetic_purchase_lift", self.cosmetic_purchase_lift),
            ("churn_lift", self.churn_lift),
            ("cohort_churn_lift", self.cohort_churn_lift),
        ):
            if field_value <= 0:
                msg = f"{label}.{field_name} must be greater than 0"
                raise ValueError(msg)
        return self


@dataclass(frozen=True, slots=True)
class ProbabilityDistributionConfig:
    alpha: float
    beta: float

    def validate(self, label: str) -> "ProbabilityDistributionConfig":
        if self.alpha <= 0 or self.beta <= 0:
            msg = f"{label} alpha and beta must be greater than 0"
            raise ValueError(msg)
        return self


@dataclass(frozen=True, slots=True)
class SessionLengthDistributionConfig:
    mean_minutes: float
    std_dev_minutes: float

    def validate(self, label: str) -> "SessionLengthDistributionConfig":
        if self.mean_minutes <= 0:
            msg = f"{label} mean_minutes must be greater than 0"
            raise ValueError(msg)
        if self.std_dev_minutes <= 0:
            msg = f"{label} std_dev_minutes must be greater than 0"
            raise ValueError(msg)
        return self


@dataclass(frozen=True, slots=True)
class PlayerTypeBehaviourProfile:
    daily_login_probability: ProbabilityDistributionConfig
    average_session_length_minutes: SessionLengthDistributionConfig
    purchase_probability: ProbabilityDistributionConfig
    churn_probability: ProbabilityDistributionConfig
    mission_completion_probability: ProbabilityDistributionConfig

    def validate(self, player_type: str) -> "PlayerTypeBehaviourProfile":
        self.daily_login_probability.validate(
            f"{player_type}.daily_login_probability"
        )
        self.average_session_length_minutes.validate(
            f"{player_type}.average_session_length_minutes"
        )
        self.purchase_probability.validate(f"{player_type}.purchase_probability")
        self.churn_probability.validate(f"{player_type}.churn_probability")
        self.mission_completion_probability.validate(
            f"{player_type}.mission_completion_probability"
        )
        return self


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    player_count: int
    simulation_start_date: date
    simulation_end_date: date
    random_seed: int
    registration_curve_alpha: float
    registration_curve_beta: float
    country_weights: dict[str, float]
    platform_weights: dict[str, float]
    acquisition_channel_weights: dict[str, float]
    player_type_weights: dict[str, float]
    age_band_weights: dict[str, float]
    behaviour_profiles: dict[str, PlayerTypeBehaviourProfile]
    live_service_events: tuple[LiveServiceEventConfig, ...]
    business_scenarios: tuple[BusinessScenarioConfig, ...]

    def validate(self) -> "SimulationConfig":
        if self.player_count <= 0:
            msg = "player_count must be greater than 0"
            raise ValueError(msg)
        if self.simulation_start_date > self.simulation_end_date:
            msg = "simulation_start_date must be on or before simulation_end_date"
            raise ValueError(msg)
        if self.registration_curve_alpha <= 0 or self.registration_curve_beta <= 0:
            msg = "registration curve alpha and beta must be greater than 0"
            raise ValueError(msg)

        _validate_weights("country_weights", self.country_weights)
        _validate_weights("platform_weights", self.platform_weights)
        _validate_weights(
            "acquisition_channel_weights",
            self.acquisition_channel_weights,
        )
        _validate_weights("player_type_weights", self.player_type_weights)
        _validate_weights("age_band_weights", self.age_band_weights)

        for band_label in self.age_band_weights:
            _parse_age_band(band_label)

        if set(self.behaviour_profiles) != set(self.player_type_weights):
            msg = "behaviour_profiles must match the configured player types exactly"
            raise ValueError(msg)
        for player_type, profile in self.behaviour_profiles.items():
            profile.validate(player_type)
        _validate_live_service_events(
            self.live_service_events,
            self.simulation_start_date,
            self.simulation_end_date,
        )
        _validate_business_scenarios(
            self.business_scenarios,
            self.simulation_start_date,
            self.simulation_end_date,
        )
        return self


def load_simulation_config(config_path: Path | None = None) -> SimulationConfig:
    path = config_path or DEFAULT_CONFIG_PATH
    with path.open("rb") as config_file:
        raw_config = tomllib.load(config_file)

    simulation = raw_config["simulation"]
    distributions = raw_config["distributions"]
    registration_curve = distributions["registration_curve"]
    behaviour_profiles = raw_config["behaviour_profiles"]
    live_service_events = raw_config.get("live_service_events", [])
    business_scenarios = raw_config.get("business_scenarios", [])

    return SimulationConfig(
        player_count=int(simulation["player_count"]),
        simulation_start_date=date.fromisoformat(simulation["simulation_start_date"]),
        simulation_end_date=date.fromisoformat(simulation["simulation_end_date"]),
        random_seed=int(simulation.get("random_seed", 42)),
        registration_curve_alpha=float(registration_curve["alpha"]),
        registration_curve_beta=float(registration_curve["beta"]),
        country_weights=_normalize_weights(distributions["country"]),
        platform_weights=_normalize_weights(distributions["platform"]),
        acquisition_channel_weights=_normalize_weights(
            distributions["acquisition_channel"]
        ),
        player_type_weights=_normalize_weights(distributions["player_type"]),
        age_band_weights=_normalize_weights(distributions["age_band"]),
        behaviour_profiles=_load_behaviour_profiles(behaviour_profiles),
        live_service_events=_load_live_service_events(live_service_events),
        business_scenarios=_load_business_scenarios(business_scenarios),
    ).validate()


def _normalize_weights(raw_weights: dict[str, float]) -> dict[str, float]:
    total = float(sum(float(weight) for weight in raw_weights.values()))
    if total <= 0:
        msg = "distribution weights must sum to a positive value"
        raise ValueError(msg)

    return {
        str(key): float(weight) / total
        for key, weight in raw_weights.items()
    }


def _validate_weights(name: str, weights: dict[str, float]) -> None:
    if not weights:
        msg = f"{name} must not be empty"
        raise ValueError(msg)
    if any(weight <= 0 for weight in weights.values()):
        msg = f"{name} must contain only positive values"
        raise ValueError(msg)
    if not isclose(sum(weights.values()), 1.0, rel_tol=1e-9, abs_tol=1e-9):
        msg = f"{name} must sum to 1.0 after normalization"
        raise ValueError(msg)


def _parse_age_band(band_label: str) -> tuple[int, int]:
    try:
        lower_bound_text, upper_bound_text = band_label.split("-", maxsplit=1)
        lower_bound = int(lower_bound_text)
        upper_bound = int(upper_bound_text)
    except ValueError as exc:
        msg = f"Invalid age band '{band_label}'. Expected format like '21-25'."
        raise ValueError(msg) from exc

    if lower_bound < 0 or upper_bound < lower_bound:
        msg = f"Invalid age band '{band_label}'."
        raise ValueError(msg)
    return lower_bound, upper_bound


def _load_behaviour_profiles(
    raw_profiles: dict[str, dict[str, dict[str, float]]],
) -> dict[str, PlayerTypeBehaviourProfile]:
    return {
        player_type: PlayerTypeBehaviourProfile(
            daily_login_probability=_load_probability_distribution(
                profile["daily_login_probability"]
            ),
            average_session_length_minutes=_load_session_length_distribution(
                profile["average_session_length_minutes"]
            ),
            purchase_probability=_load_probability_distribution(
                profile["purchase_probability"]
            ),
            churn_probability=_load_probability_distribution(
                profile["churn_probability"]
            ),
            mission_completion_probability=_load_probability_distribution(
                profile["mission_completion_probability"]
            ),
        )
        for player_type, profile in raw_profiles.items()
    }


def _load_probability_distribution(
    raw_distribution: dict[str, float],
) -> ProbabilityDistributionConfig:
    return ProbabilityDistributionConfig(
        alpha=float(raw_distribution["alpha"]),
        beta=float(raw_distribution["beta"]),
    )


def _load_session_length_distribution(
    raw_distribution: dict[str, float],
) -> SessionLengthDistributionConfig:
    return SessionLengthDistributionConfig(
        mean_minutes=float(raw_distribution["mean_minutes"]),
        std_dev_minutes=float(raw_distribution["std_dev_minutes"]),
    )


def _load_live_service_events(
    raw_events: list[dict[str, object]],
) -> tuple[LiveServiceEventConfig, ...]:
    return tuple(
        LiveServiceEventConfig(
            event_id=int(raw_event["event_id"]),
            event_name=str(raw_event["event_name"]),
            event_type=str(raw_event["event_type"]),
            start_date=date.fromisoformat(str(raw_event["start_date"])),
            end_date=date.fromisoformat(str(raw_event["end_date"])),
            login_lift=float(raw_event["login_lift"]),
            session_length_lift=float(raw_event["session_length_lift"]),
            purchase_lift=float(raw_event["purchase_lift"]),
        )
        for raw_event in raw_events
    )


def _load_business_scenarios(
    raw_scenarios: list[dict[str, object]],
) -> tuple[BusinessScenarioConfig, ...]:
    return tuple(
        BusinessScenarioConfig(
            scenario_id=int(raw_scenario["scenario_id"]),
            scenario_name=str(raw_scenario["scenario_name"]),
            scenario_type=str(raw_scenario["scenario_type"]),
            start_date=date.fromisoformat(str(raw_scenario["start_date"])),
            end_date=date.fromisoformat(str(raw_scenario["end_date"])),
            ramp_up_days=int(raw_scenario.get("ramp_up_days", 0)),
            ramp_down_days=int(raw_scenario.get("ramp_down_days", 0)),
            description=str(raw_scenario["description"]),
            expected_impact=str(raw_scenario["expected_impact"]),
            affected_metrics=tuple(
                str(metric) for metric in raw_scenario.get("affected_metrics", [])
            ),
            primary_channel=(
                str(raw_scenario["primary_channel"])
                if raw_scenario.get("primary_channel") is not None
                else None
            ),
            acquisition_lift=float(raw_scenario.get("acquisition_lift", 1.0)),
            marketing_efficiency_lift=float(
                raw_scenario.get("marketing_efficiency_lift", 1.0)
            ),
            marketing_spend_lift=float(
                raw_scenario.get("marketing_spend_lift", 1.0)
            ),
            login_lift=float(raw_scenario.get("login_lift", 1.0)),
            session_length_lift=float(
                raw_scenario.get("session_length_lift", 1.0)
            ),
            purchase_lift=float(raw_scenario.get("purchase_lift", 1.0)),
            purchase_price_lift=float(
                raw_scenario.get("purchase_price_lift", 1.0)
            ),
            cosmetic_purchase_lift=float(
                raw_scenario.get("cosmetic_purchase_lift", 1.0)
            ),
            churn_lift=float(raw_scenario.get("churn_lift", 1.0)),
            cohort_churn_lift=float(
                raw_scenario.get("cohort_churn_lift", 1.0)
            ),
            review_score_shift=float(raw_scenario.get("review_score_shift", 0.0)),
            review_recommendation_shift=float(
                raw_scenario.get("review_recommendation_shift", 0.0)
            ),
        )
        for raw_scenario in raw_scenarios
    )


def _validate_live_service_events(
    events: tuple[LiveServiceEventConfig, ...],
    simulation_start_date: date,
    simulation_end_date: date,
) -> None:
    event_ids: set[int] = set()
    ordered_events = sorted(events, key=lambda event: (event.start_date, event.end_date))
    previous_end_date: date | None = None

    for index, event in enumerate(ordered_events, start=1):
        event.validate(f"live_service_events[{index}]")
        if event.event_id in event_ids:
            msg = "live_service_events must use unique event_id values"
            raise ValueError(msg)
        event_ids.add(event.event_id)

        if event.start_date < simulation_start_date or event.end_date > simulation_end_date:
            msg = "live_service_events must be fully contained within the simulation date range"
            raise ValueError(msg)

        if previous_end_date is not None and event.start_date <= previous_end_date:
            msg = "live_service_events must not overlap"
            raise ValueError(msg)
        previous_end_date = event.end_date


def _validate_business_scenarios(
    scenarios: tuple[BusinessScenarioConfig, ...],
    simulation_start_date: date,
    simulation_end_date: date,
) -> None:
    scenario_ids: set[int] = set()
    ordered_scenarios = sorted(
        scenarios,
        key=lambda scenario: (scenario.start_date, scenario.end_date),
    )
    previous_end_date: date | None = None

    for index, scenario in enumerate(ordered_scenarios, start=1):
        scenario.validate(f"business_scenarios[{index}]")
        if scenario.scenario_id in scenario_ids:
            msg = "business_scenarios must use unique scenario_id values"
            raise ValueError(msg)
        scenario_ids.add(scenario.scenario_id)

        if (
            scenario.start_date < simulation_start_date
            or scenario.end_date > simulation_end_date
        ):
            msg = (
                "business_scenarios must be fully contained within the simulation "
                "date range"
            )
            raise ValueError(msg)

        if previous_end_date is not None and scenario.start_date <= previous_end_date:
            msg = "business_scenarios must not overlap"
            raise ValueError(msg)
        previous_end_date = scenario.end_date
