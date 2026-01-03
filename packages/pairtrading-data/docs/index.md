# pairtrading-data Documentation

A Python library for market data collection and validation, designed for pair trading strategies.

## Overview

`pairtrading-data` is the data layer for a pair trading framework. It provides:

- **Data Collection**: Fetch market data from Massive API (formerly Polygon)
- **Caching**: CSV-based caching to avoid re-downloading data
- **Stock Universes**: Manage symbol lists (S&P 500, sectors, custom)
- **Bias Prevention**: Tools to prevent look-ahead and survivorship bias
- **Data Validation**: Quality checks for gaps, outliers, corporate actions

## Architecture

This library is designed to be used as a dependency by:

1. **pairtrading-engine**: Backtest engine with on_bar() callbacks
2. **Strategy projects**: Individual strategy implementations (GGR, Cointegration, etc.)

```
┌─────────────────────┐
│  pairtrading-data   │  ← This library
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ pairtrading-engine  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Strategy Projects  │
└─────────────────────┘
```

## Quick Links

- [Quick Start](quickstart.md) - Get up and running
- [Data Providers](providers.md) - Fetching market data
- [Validation](validation.md) - Bias prevention and data quality

## Installation

```bash
# Development install
pip install -e .

# From Git
pip install git+https://github.com/dylanstrijker/pairtrading-data.git
```

## Requirements

- Python 3.11+
- pandas >= 2.0
- numpy >= 1.24
- httpx >= 0.25
- pydantic >= 2.0

## API Key

You'll need a Massive API key (formerly Polygon) for fetching market data:

```bash
export MASSIVE_API_KEY="your_api_key_here"
```
