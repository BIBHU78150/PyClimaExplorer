# PyClimaExplorer

A rapid-prototype interactive visualizer for climate model data (NetCDF).

## Overview

PyClimaExplorer allows researchers and the public to slice, dice, and view multidimensional climate data interactively. It offers:
- **Spatial View**: A 2D globe map visualizing a variable for a specific time index using Plotly.
- **Temporal View**: A time-series chart showing the historic trend of a variable at specific latitude/longitude coordinates.
- **3D Interactive Map**: An interactive 3D representation highlighting regional anomalies using PyDeck.

## Pre-requisites

You need Python 3.8+ installed.

## How to Run Locally

1. **Clone the repository:**
   ```bash
   git clone https://github.com/BIBHU78150/PyClimaExplorer.git
   cd PyClimaExplorer
   ```

2. **Create and activate a virtual environment (Recommended):**
   - **Windows:**
     ```bash
     python -m venv .venv
     .\.venv\Scripts\activate
     ```
   - **macOS/Linux:**
     ```bash
     python -m venv .venv
     source .venv/bin/activate
     ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the Dashboard:**
   ```bash
   streamlit run app.py
   ```
   The application will open in your default browser at `http://localhost:8501`.

## How to Deploy to Streamlit Community Cloud

Deploying this app to the public is free and easy with Streamlit Cloud:
1. Ensure your code is pushed to your GitHub repository.
2. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Click **"New app"**.
4. Select your repository (`BIBHU78150/PyClimaExplorer`), branch (`main`), and set the main file path to `app.py`.
5. Click **"Deploy!"** Your app will be live within minutes.

## Data Input & Sample Datasets

- **Built-in Tutorial:** By default, the app uses Xarray's tutorial `air_temperature` dataset to instantly demonstrate the visualizations.
- **Custom Upload:** You can upload your own `.nc` (NetCDF) files via the sidebar. Ensure your standard geographical dimensions are roughly named `time`, `lat`, and `lon` for automatic detection.

### Where to get more sample NetCDF data:
If you want to try uploading different climate datasets, you can freely download `.nc` files from these scientific repositories:
- **[Copernicus Climate Data Store (ERA5)](https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-single-levels?tab=overview):** Global hourly reanalysis data (e.g., 2m temperature, total precipitation). Highly recommended for high-quality data.
- **[CESM CVDP Data Repository](https://www.cesm.ucar.edu/projects/cvdp/data-repository):** Standard climate data sets containing historical outputs.
- **[NASA Earth Observations (NEO)](https://neo.gsfc.nasa.gov/):** Various planetary datasets.
- **[NOAA Physical Sciences Laboratory](https://psl.noaa.gov/data/gridded/):** Gridded climate datasets including NCEP Reanalysis.
