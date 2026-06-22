# FakeGameStudio - SyntheticDataGenerator Overview and Run Guide

## What This Program Does

The program generates a synthetic business intelligence dataset for a fictional live-service game studio.

The goal is not just to create random rows. The project simulates believable business behavior so the data can support portfolio dashboards and analysis in tools such as Tableau, Power BI, SQL, and Python.

The generated data is designed to help answer questions such as:

- Why did DAU increase during a specific period?
- Which marketing campaigns brought in the most valuable players?
- Why did revenue rise while retention stayed flat?
- What happened after a major update, promotion, or outage?
- Which events improved engagement and which ones increased churn?

## Simple Summary Of How It Works

At a high level, the program works like this:

1. The configuration file defines the simulation period, player volume, behaviour distributions, live-service events, and business scenarios.
2. The scenario engine turns those business scenarios into day-by-day business conditions such as stronger acquisition, lower retention, better review sentiment, or reduced revenue.
3. The marketing generator uses those daily conditions to create campaigns and registration patterns.
4. The player generator creates players and links each player to the campaign and business scenario that acquired them.
5. The behaviour engine gives each player their own probabilities for logging in, playing longer sessions, purchasing, completing missions, and churning.
6. The session generator uses the players, behaviours, and scenario calendar to simulate daily gameplay activity.
7. The purchase and review generators use session history to create monetisation and sentiment data.
8. The finance generator aggregates purchase revenue and combines it with operating, infrastructure, and marketing costs.
9. The validation layer checks that the outputs are internally consistent.

The result is a connected BI dataset where business events affect multiple downstream tables in a believable way.

## What It Generates

Running the generator creates CSV files in the `output/` folder, including:

- `dim_date.csv`
- `dim_business_events.csv`
- `dim_business_scenario.csv`
- `dim_live_event.csv`
- `dim_player.csv`
- `fact_marketing.csv`
- `fact_sessions.csv`
- `fact_purchases.csv`
- `fact_reviews.csv`
- `fact_finance.csv`
- `validation_checks.csv`
- `summary_statistics.csv`

## What Each Output File Contains

Use this as a quick reference when opening the generated files or loading them into a warehouse.

- `dim_date.csv`
  - One row per date in the simulation window
  - Includes `DateKey`, `FullDate`, day, week, month, quarter, year, and weekend flags
  - Marks the active business scenario and live event for each day
  - Useful for time-series analysis, daily joins, and event-impact charts

- `dim_business_events.csv`
  - Analyst-friendly event dimension
  - Includes event ID, event name, event type, start and end dates, description, and expected business impact
  - Useful for dashboard labels and narrative annotations

- `dim_business_scenario.csv`
  - Full simulation scenario table
  - Stores scenario name, scenario type, date range, ramp settings, KPI effect parameters, and the metrics each scenario is intended to influence
  - Useful for explaining why acquisition, engagement, churn, or revenue changed

- `dim_live_event.csv`
  - Metadata for live-service events such as updates, seasonal drops, and promotions
  - Includes event type, event window, and the login, session length, and purchase lift values applied while the event is active
  - Useful for event comparisons and before/after analysis

- `dim_player.csv`
  - One row per simulated player
  - Includes registration date, country, age, platform, campaign, acquisition channel, acquisition scenario, and player type
  - Acts as the main dimension for all player-level fact tables

- `fact_marketing.csv`
  - Campaign-level acquisition fact table
  - Includes campaign metadata plus spend, impressions, clicks, installs, and registrations
  - Useful for CAC, conversion, and campaign ROI analysis

- `fact_sessions.csv`
  - One row per gameplay session
  - Includes player ID, login and logout times, session length, gameplay activity, and product fields such as biome, mission type, difficulty, multiplayer flag, and ship class
  - Also includes scenario and live-event attribution
  - Useful for DAU, engagement, retention, and product analytics

- `fact_purchases.csv`
  - One row per purchase transaction
  - Includes player ID, item, quantity, price, revenue, and purchase date
  - Useful for monetization, basket size, and item-mix analysis

- `fact_reviews.csv`
  - One row per player review
  - Includes player ID, hours played, recommended flag, review score, and review date
  - Useful for sentiment analysis and for comparing reviews across events or updates

- `fact_finance.csv`
  - Daily finance fact table
  - Includes revenue from purchases, operating costs, infrastructure costs, marketing costs, forecast revenue, and budget
  - Useful for margin, variance, and financial planning analysis

- `validation_checks.csv`
  - Data-quality output from the validation layer
  - Records each check name, pass/fail status, and supporting details for the result
  - Useful for confirming the dataset is internally consistent before loading it into BI tools

- `summary_statistics.csv`
  - High-level KPI summary output
  - Includes metric names and values for DAU, MAU, revenue, retention, churn, ARPU, and average session length
  - Useful as a quick health check after generation

## How the Simulation Works

The project combines several layers:

1. Player generation:
   creates players with registration dates, country, age, platform, acquisition channel, campaign, and player type.

2. Behaviour generation:
   assigns each player probabilistic gameplay and monetisation tendencies based on player type.

3. Business scenarios:
   injects intentional stories such as strong campaigns, successful updates, promotions, outages, expansions, and poor patches.

4. Session, purchase, review, marketing, and finance generation:
   produces downstream facts that respond consistently to those scenarios.

5. Validation:
   checks foreign keys, churn behavior, campaign links, and revenue reconciliation.

## How The Files Connect To Each Other

The project is designed as one pipeline, not as separate random scripts.

### Configuration layer

- `config/simulation_config.toml`
  defines the rules for the whole simulation
- `config/settings.py`
  loads and validates those rules

Everything else depends on this configuration.

### Scenario and date layer

- `generators/scenario_generator.py`
  creates the business scenario metadata and the daily scenario calendar
- `generators/event_generator.py`
  exports the live-service event metadata
- `generators/date_generator.py`
  creates the date dimension and marks which events and scenarios are active on each day

These files provide the time-based context used by the rest of the simulation.

### Acquisition and player layer

- `generators/marketing_generator.py`
  creates campaign-level marketing data using the scenario calendar
- `generators/player_generator.py`
  creates players and links them to campaigns and acquisition scenarios

This means player growth is tied directly to campaign and scenario activity.

### Behaviour and gameplay layer

- `simulation/behaviour_engine.py`
  assigns per-player probabilities based on player type
- `generators/session_generator.py`
  uses player data, behaviour data, and scenario effects to generate gameplay sessions

This is where retention, churn, engagement, and gameplay activity are simulated.

### Monetisation and sentiment layer

- `generators/commerce_generator.py`
  uses session history to generate purchases and reviews

Purchases depend on session activity and purchase probability.
Reviews depend on accumulated playtime and are influenced by scenario conditions.

### Finance and QA layer

- `generators/finance_generator.py`
  derives daily finance data from purchases, sessions, and marketing costs
- `generators/validation_generator.py`
  checks whether the generated data is valid and produces summary KPIs

This is where the program confirms that the dataset makes sense as a BI model.

### Pipeline entry point

- `data_gen.py`
  runs the entire pipeline in the correct order

It ties everything together by calling each generator in sequence and saving the final CSVs into `output/`.

## Dependency Flow

This is the simplest way to think about the relationships:

`simulation_config.toml`
-> scenario and event metadata
-> marketing campaigns
-> players
-> player behaviours
-> sessions
-> purchases and reviews
-> finance
-> validation and summary statistics

So if an earlier layer changes, later layers change as well.

For example:

- a stronger marketing scenario changes campaign output
- that changes player acquisition timing
- that changes session volume
- that changes purchases
- that changes revenue
- that changes finance and KPI summaries

That is what makes the project useful for business analysis instead of just data generation.

## Requirements

- Python `3.12+`
- `pandas`
- `numpy`
- `Faker`

These dependencies are already declared in `pyproject.toml`.

## How To Run Everything

Run these commands from the project root.

### 1. Create a virtual environment

```bash
python3.12 -m venv .venv
```

If `python3.12` is not available on your machine, use the Python 3.12+ executable you have installed.

### 2. Activate the virtual environment

On macOS or Linux:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -e .
```

### 4. Review or adjust the simulation settings

Edit:

`config/simulation_config.toml`

Important settings include:

- `player_count`
- `simulation_start_date`
- `simulation_end_date`
- `random_seed`
- live-service events
- business scenarios
- player and acquisition distributions

### 5. Run the generator

```bash
python data_gen.py
```

This will generate all configured CSV outputs in:

`output/`

## What To Check After Running

After execution, confirm that these files exist in `output/`:

- `dim_player.csv`
- `fact_sessions.csv`
- `fact_purchases.csv`
- `fact_reviews.csv`
- `fact_marketing.csv`
- `fact_finance.csv`
- `validation_checks.csv`
- `summary_statistics.csv`

The two most useful QA files are:

- `validation_checks.csv`: confirms key integrity and reconciliation rules
- `summary_statistics.csv`: provides headline metrics such as DAU, MAU, revenue, retention, churn, ARPU, and average session length

## Optional: Load the Data Into MySQL

If you want to build the warehouse and connect Tableau:

1. Generate the CSVs with `python data_gen.py`
2. Run `sql/01_create_star_schema.sql`
3. Run `sql/02_load_from_csv.sql`
4. Run `sql/03_create_kpi_views.sql`
5. Optionally use `sql/04_kpi_pack.sql`

## Practical Notes

- `fact_sessions.csv` is the heaviest output and can take the longest to generate.
- If you want faster development runs, reduce `player_count` or shorten the simulation date range.
- The default portfolio-oriented configuration is meant to be realistic enough for dashboards without becoming unnecessarily large.
