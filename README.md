# PyClimaExplorer

A rapid-prototype interactive visualizer for climate model data (NetCDF).

## Overview

PyClimaExplorer allows researchers and the public to slice, dice, and view multidimensional climate data interactively. It offers:
- **Spatial View**: A 2D globe map visualizing a variable for a specific time index.
- **Temporal View**: A time-series chart showing the historic trend of a variable at specific latitude/longitude coordinates.
- **3D Globe Render**: An interactive 3D representation using PyDeck.

## Pre-requisites

You need Python 3.8+ installed.

## Setup Instructions

1. **Change Directory:**
   ```bash
   cd PyClimaExplorer
   ```

2. **Install Dependencies:**
   It is recommended to use a virtual environment.
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Dashboard:**
   ```bash
   streamlit run app.py
   ```
   
   The application will open in your default browser at `http://localhost:8501`.

## Data Input

- **Built-in:** Uses Xarray's tutorial `air_temperature` dataset.
- **Custom Upload:** You can upload your own `.nc` (NetCDF) files. Ensure your standard geographical dimensions are roughly named `time`, `lat`, and `lon` for automatic detection.

## Sample Datasets
You can find more standard climate data sets containing historical outputs at the [CESM CVDP Data Repository](https://www.cesm.ucar.edu/projects/cvdp/data-repository).
