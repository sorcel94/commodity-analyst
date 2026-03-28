# Commodity Analyst

Natural gas market analysis dashboard for tracking EU storage levels, LNG imports, and price benchmarks.

## Features

- **Storage Overview** -- fill levels vs 5-year average and EU 90% target trajectory
- **Injection Analysis** -- injection pace and country breakdown
- **LNG Terminals** -- terminal rankings, send-out rates, and drill-down views
- **Market Benchmarks** -- TTF, Henry Hub, JKM prices and correlations
- **Imbalance Signals** -- composite scorecard summarizing supply/demand balance

## Setup

```bash
# Install dependencies
uv sync

# Create .env with your API keys
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your GIE_API_KEY and FRED_API_KEY

# Run the dashboard
uv run streamlit run src/commodity_analyst/dashboard/app.py
```

## Deployment (Streamlit Community Cloud)

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and create a new app
3. Set **Main file path** to `src/commodity_analyst/dashboard/app.py`
4. Add secrets in app Settings > Secrets:
   ```toml
   GIE_API_KEY = "your-key"
   FRED_API_KEY = "your-key"
   ```

## Tech Stack

Python 3.12 | Streamlit | Plotly | pandas | httpx | yfinance | fredapi
