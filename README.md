# FakeGameStudio - SyntheticDataGenerator

`GameStudioBI` is a Python 3.12+ project for simulating the internal business intelligence database of a fictional game studio inspired by large-scale procedural space exploration games.

The project currently includes:

- a date dimension generator for warehouse time analysis
- a business scenario engine for intentional KPI stories and anomalies
- a live-service event dimension and event-driven engagement lifts
- configurable simulation settings
- a configurable player dimension generator
- a campaign-level marketing fact generator linked to acquired players
- a probabilistic behaviour engine keyed by player type
- a daily session fact generator driven by player behaviour
- purchase and review fact generators derived from session history
- a daily finance fact generator derived from purchases, sessions, and marketing
- validation outputs and KPI summaries for the generated dataset
- output, SQL, and docs directories

## Structure

- `config/` - configuration files and loader utilities
- `generators/` - future synthetic data generators
- `simulation/` - future simulation orchestration code
- `output/` - generated export destination
- `sql/` - future BI schema and query files
- `docs/` - project documentation

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

Edit [`config/simulation_config.toml`](/Users/neophytoskouphou/Desktop/Python%20Courses/fake_games_comp/config/simulation_config.toml) to change:

- `player_count`
- `simulation_start_date`
- `simulation_end_date`
- `random_seed`
- country, platform, acquisition channel, player type, and age-band distributions
- the registration date curve shape
- per-player-type behaviour distributions for login, session length, purchase, churn, and mission completion

## Current status

Running `python3 data_gen.py` generates `output/dim_date.csv`, `output/dim_business_events.csv`, `output/dim_business_scenario.csv`, `output/dim_live_event.csv`, and `output/dim_player.csv` with the configured dimensions.

The scenario engine in [`generators/scenario_generator.py`](/Users/neophytoskouphou/Desktop/Python%20Courses/fake_games_comp/generators/scenario_generator.py) creates day-level business stories with defined start and end dates, smooth ramp-up and ramp-down effects, and multi-KPI impacts across acquisition, engagement, monetisation, churn, and reviews.

The marketing generator in [`generators/marketing_generator.py`](/Users/neophytoskouphou/Desktop/Python%20Courses/fake_games_comp/generators/marketing_generator.py) exports `output/fact_marketing.csv`. Players in `dim_player.csv` are linked to their acquisition campaign via `CampaignID`, and acquisitions also carry scenario attribution through `AcquisitionScenarioID`.

The behaviour engine in [`simulation/behaviour_engine.py`](/Users/neophytoskouphou/Desktop/Python%20Courses/fake_games_comp/simulation/behaviour_engine.py) assigns probabilistic per-player behaviour values from the configured player-type profiles.

The session generator in [`generators/session_generator.py`](/Users/neophytoskouphou/Desktop/Python%20Courses/fake_games_comp/generators/session_generator.py) exports `output/fact_sessions.csv` by simulating daily player sessions across the configured date range.

`fact_sessions.csv` now also includes richer gameplay dimensions for product analytics:

- `Biome`
- `MissionType`
- `Difficulty`
- `MultiplayerSession`
- `ShipClass`

Configured live-service events apply lifts to login probability, session length, and purchase probability during active event windows. Sessions generated during an event include:

- `EventID`
- `EventName`
- `EventType`

The commerce generator in [`generators/commerce_generator.py`](/Users/neophytoskouphou/Desktop/Python%20Courses/fake_games_comp/generators/commerce_generator.py) exports:

- `output/fact_purchases.csv`
- `output/fact_reviews.csv`

Reviews are only generated for players whose accumulated playtime passes the minimum review threshold, and both purchase behaviour and review sentiment now react to configured business scenarios.

The finance generator in [`generators/finance_generator.py`](/Users/neophytoskouphou/Desktop/Python%20Courses/fake_games_comp/generators/finance_generator.py) exports `output/fact_finance.csv`. Revenue is aggregated directly from purchase records, while marketing cost is allocated from campaign spend over player registration dates.

The validation generator in [`generators/validation_generator.py`](/Users/neophytoskouphou/Desktop/Python%20Courses/fake_games_comp/generators/validation_generator.py) exports:

- `output/validation_checks.csv`
- `output/summary_statistics.csv`

It validates key relationships and produces headline metrics including DAU, MAU, revenue, retention, churn, ARPU, and average session length.

## Output Files

The generator writes the following CSV files to `output/`:

- `dim_date.csv` - date dimension with `DateKey`, `FullDate`, day, week, month, quarter, year, weekend, and active event/scenario fields for each day in the simulation window.
- `dim_business_events.csv` - analyst-facing event table with event names, types, start and end dates, narrative descriptions, and expected business impact notes.
- `dim_business_scenario.csv` - detailed scenario metadata with scenario type, date range, ramp periods, KPI effect settings, and the metrics each scenario is intended to move.
- `dim_live_event.csv` - live-service event dimension with event names, event type, start and end dates, and the login, session length, and purchase lifts applied during the window.
- `dim_player.csv` - player dimension with registration date, demographic fields, platform, campaign, acquisition channel, acquisition scenario, and player type.
- `fact_marketing.csv` - campaign-level acquisition fact with campaign metadata plus spend, impressions, clicks, installs, and registrations.
- `fact_sessions.csv` - daily gameplay sessions with login and logout times, session length, gameplay context fields, and scenario/event attribution.
- `fact_purchases.csv` - purchase fact with player ID, item, quantity, price, revenue, and purchase timestamp.
- `fact_reviews.csv` - review fact with player ID, hours played, recommendation flag, review score, and review date.
- `fact_finance.csv` - daily finance fact with revenue, operating costs, infrastructure costs, marketing costs, forecast revenue, and budget values.
- `validation_checks.csv` - data quality checks with pass/fail status and details for integrity rules such as foreign keys, churn behavior, and revenue reconciliation.
- `summary_statistics.csv` - headline BI metrics such as DAU, MAU, retention, churn, ARPU, revenue, and average session length.
