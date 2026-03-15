import streamlit as st
import xarray as xr
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import io
import urllib.request

# --- Configuration ---
st.set_page_config(page_title="PyClimaExplorer", layout="wide", page_icon="🌍")

# --- Styling ---
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: 700;
        background: -webkit-linear-gradient(45deg, #1E88E5, #00ACC1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #555;
        margin-bottom: 2rem;
    }
    .stApp {
        background-color: #f8f9fa;
    }
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e0e0e0;
    }
    div.block-container {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Title ---
st.markdown('<h1 class="main-header">PyClimaExplorer</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Interactive visualizer for climate model data.</p>', unsafe_allow_html=True)

# --- Session State & Query Params Sync ---
# We sync session state with query parameters so the tour survives a page refresh
# If 'tour_completed' is not in the URL, we auto-start the tour for new users.
is_tour_completed = st.query_params.get("tour_completed", "false").lower() == "true"
is_tour_mode = st.query_params.get("tour_mode", "false").lower() == "true"

if 'tour_completed' not in st.session_state:
    st.session_state.tour_completed = is_tour_completed

if 'tour_mode' not in st.session_state:
    # Auto-start condition: if not completed and not explicitly set to false in URL
    if not st.session_state.tour_completed and st.query_params.get("tour_mode") is None:
        st.session_state.tour_mode = True
    else:
        st.session_state.tour_mode = is_tour_mode
        
if 'tour_step' not in st.session_state:
    st.session_state.tour_step = int(st.query_params.get("tour_step", 1))

# Helper to update both state and URL
def update_tour_state(mode: bool, step: int = 1, completed: bool = False):
    st.session_state.tour_mode = mode
    st.session_state.tour_step = step
    if completed:
        st.session_state.tour_completed = True
        
    if mode:
        st.query_params["tour_mode"] = "true"
        st.query_params["tour_step"] = str(step)
    else:
        st.query_params.pop("tour_mode", None)
        st.query_params.pop("tour_step", None)
        
    if st.session_state.tour_completed:
        st.query_params["tour_completed"] = "true"

# --- Data Loading ---
@st.cache_data
def load_demo_data(dataset_name):
    """Loads either the tutorial dataset or a pre-downloaded demo dataset."""
    try:
        if dataset_name == "Tutorial (Air Temperature)":
            return xr.tutorial.open_dataset("air_temperature").load()
        elif dataset_name == "NCEP Air Temp 2023":
            return xr.open_dataset("demo_datasets/ncep_air_temp_2023.nc").load()
        elif dataset_name == "NCEP Sea Level Pressure 2023":
            return xr.open_dataset("demo_datasets/ncep_slp_2023.nc").load()
        elif dataset_name == "NCEP Surface Pressure LTM":
            return xr.open_dataset("demo_datasets/ncep_surface_pressure_ltm.nc").load()
    except Exception as e:
        st.error(f"Error loading {dataset_name}: {e}")
        return None

def process_uploaded_data(uploaded_file):
    """Processes an uploaded NetCDF file."""
    try:
        # Save uploaded file to memory, xarray can read from bytes via h5netcdf or netcdf4 sometimes, 
        # but often it's easier to write to a temp file or read directly.
        # Alternatively, we can use xarray open_dataset with a file-like object and engine='h5netcdf'
        # For simplicity and robust stream handling in Streamlit, we read the bytes and load.
        file_content = uploaded_file.read()
        ds = xr.open_dataset(file_content, engine="h5netcdf").load()
        return ds
    except Exception as e:
        st.error(f"Error parsing uploaded NetCDF file: {e}")
        return None

# --- Sidebar Controls ---
st.sidebar.header("Data Source")

# If tour mode is active, lock the data source to the tutorial and hide the radio buttons
if st.session_state.tour_mode:
    data_source = "Demo Datasets"
    demo_selection = "Tutorial (Air Temperature)"
    # The view mode depends on the tour step
    if st.session_state.tour_step == 3:
        view_mode = "Comparison View"
    else:
        view_mode = "Single View"
    
    st.sidebar.info("Tour Mode Active: Controls are locked.")
    if st.sidebar.button("Exit Tour", use_container_width=True):
        update_tour_state(False, completed=True)
        st.rerun()
else:
    data_source = st.sidebar.radio("Select Data Source", ["Demo Datasets", "Upload NetCDF File"])
    
    if data_source == "Demo Datasets":
        demo_selection = st.sidebar.selectbox("Select a Demo Dataset", [
            "Tutorial (Air Temperature)",
            "NCEP Air Temp 2023",
            "NCEP Sea Level Pressure 2023",
            "NCEP Surface Pressure LTM"
        ])
        
    view_mode = st.sidebar.radio("View Mode", ["Single View", "Comparison View"])

ds = None
if data_source == "Demo Datasets":
    with st.spinner(f"Loading {demo_selection}..."):
        ds = load_demo_data(demo_selection)
else:
    uploaded_file = st.sidebar.file_uploader("Upload a .nc file", type=["nc"])
    if uploaded_file is not None:
        with st.spinner("Loading uploaded dataset..."):
            ds = process_uploaded_data(uploaded_file)
    else:
        st.info("Please upload a .nc file to proceed.")

if ds:
    # --- Data Extraction ---
    st.sidebar.header("Configuration")
    
    # Identify variables, dims, coordinates
    variables = list(ds.data_vars.keys())
    if not variables:
        variables = list(ds.variables.keys()) # Fallback
        
    # Assume standard names for spatial and temporal dims for simplicity
    dim_names = list(ds.dims)
    time_dim = next((d for d in dim_names if d.lower() in ['time', 't']), None)
    lat_dim = next((d for d in dim_names if d.lower() in ['lat', 'latitude', 'y']), None)
    lon_dim = next((d for d in dim_names if d.lower() in ['lon', 'longitude', 'x']), None)

    if not (time_dim and lat_dim and lon_dim):
        st.warning(f"Could not automatically identify standard dimensions (time, lat, lon). Found: {dim_names}")
    else:
        # Extract coordinate values
        times = pd.to_datetime(ds[time_dim].values)
        lats = ds[lat_dim].values
        lons = ds[lon_dim].values
        
        # --- Tour Mode Overlay ---
        if st.session_state.tour_mode:
            tour_container = st.container()
            with tour_container:
                st.info("🧭 **Guided Tour Active**")
                col_text, col_nav = st.columns([3, 1])
                
                with col_text:
                    if st.session_state.tour_step == 1:
                        st.markdown("### Step 1: Spatial Overview\nWelcome! This is the **Spatial View**. It shows a 2D geographical map of the selected variable. Here, we are looking at **air temperature** during a cold winter day in North America (January 2013). Notice the deep purple colors representing sub-zero temperatures.")
                    elif st.session_state.tour_step == 2:
                        st.markdown("### Step 2: Temporal Drill-down\nSwitch to the **Temporal View** tab! This line chart tracks the temperature over the entire year for a specific coordinate. Notice the clear seasonal sine-wave pattern, dipping low in January and peaking in July.")
                    elif st.session_state.tour_step == 3:
                        st.markdown("### Step 3: 3D Comparison\nSwitch to the **3D Map Viewer** tab! We are now in **Comparison View**. On the left is the cold January data, and on the right is warm July data. You can interactively pan and tilt these PyDeck 3D column maps to compare the temperature elevation differences side-by-side!")

                with col_nav:
                    col_prev, col_next = st.columns(2)
                    with col_prev:
                        if st.session_state.tour_step > 1:
                            if st.button("⬅️ Previous"):
                                update_tour_state(True, st.session_state.tour_step - 1)
                                st.rerun()
                    with col_next:
                        if st.session_state.tour_step < 3:
                            if st.button("Next ➡️"):
                                update_tour_state(True, st.session_state.tour_step + 1)
                                st.rerun()
                        else:
                            if st.button("Finish Tour 🎉"):
                                update_tour_state(False, completed=True)
                                st.rerun()
            st.divider()

        # Variable selection (lock to 'air' in tour mode)
        if st.session_state.tour_mode:
            selected_var = "air"
        else:
            selected_var = st.sidebar.selectbox("Select Variable", variables)
            
        # --- Tour Mode Overrides & General Selection ---
        if st.session_state.tour_mode:
            # Bypass sidebar and manually set variables based on the step
            
            # Step 1 & 2: Show single data point (Jan 1, 2013)
            # Step 3: Compare Jan 1, 2013 with July 1, 2013
            # In the tutorial dataset (air_temperature), 2013 starts at index 0
            
            # Example coordinates for something distinctive (North America winter)
            lat_idx_target = list(lats).index(45.0) if 45.0 in lats else len(lats)//2
            lon_idx_target = list(lons).index(265.0) if 265.0 in lons else len(lons)//2 # 265 is approx US longitude in 0-360 system
            
            selected_lat_idx = lat_idx_target
            selected_lon_idx = lon_idx_target
            selected_lat = lats[selected_lat_idx]
            selected_lon = lons[selected_lon_idx]

            if st.session_state.tour_step in [1, 2]:
                time_index = 0 # Jan 1, 2013
                selected_time = times[time_index]
            else: # Step 3 (Comparison)
                # Ensure we have these dates or fallback
                # Jan index = 0, July index is roughly 4 * 180 (4 per day roughly) = ~720
                time_index_1 = 0 
                selected_time_1 = times[time_index_1]
                
                time_index_2 = min(730, len(times) - 1)  # Approx July
                selected_time_2 = times[time_index_2]
                
                ds_1 = ds
                ds_2 = ds

        else:
            # --- Dataset Date/Time Filtering ---
            min_date = times.min().date()
            max_date = times.max().date()
    
            if view_mode == "Single View":
                st.sidebar.subheader("Filter Dataset by Date")
                date_range = st.sidebar.date_input("Select Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
                
                if isinstance(date_range, tuple) and len(date_range) == 2:
                    ds = ds.sel({time_dim: slice(str(date_range[0]), str(date_range[1]))})
                    times = pd.to_datetime(ds[time_dim].values)
                    if len(times) == 0:
                        st.sidebar.warning("No data available for the selected date range.")
                        st.stop()
                elif isinstance(date_range, tuple) and len(date_range) < 2:
                     st.sidebar.info("Please select an end date to apply the filter.")
                     st.stop()
                     
                st.sidebar.subheader("Temporal Selection")
                time_index = st.sidebar.slider("Select Time index", 0, len(times) - 1, 0)
                selected_time = times[time_index]
                st.sidebar.write(f"**Current Date:** {selected_time.strftime('%Y-%m-%d %H:%M')}")
                
            else: # Comparison View
                st.sidebar.subheader("Filter Dataset 1 by Date")
                date_range_1 = st.sidebar.date_input("Select Date Range 1", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="dr1")
                if isinstance(date_range_1, tuple) and len(date_range_1) == 2:
                    ds_1 = ds.sel({time_dim: slice(str(date_range_1[0]), str(date_range_1[1]))})
                    times_1 = pd.to_datetime(ds_1[time_dim].values)
                    if len(times_1) == 0:
                        st.sidebar.warning("No data available for Date Range 1.")
                        st.stop()
                else:
                    st.sidebar.info("Please select an end date for Dataset 1.")
                    st.stop()
                    
                st.sidebar.subheader("Filter Dataset 2 by Date")
                date_range_2 = st.sidebar.date_input("Select Date Range 2", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="dr2")
                if isinstance(date_range_2, tuple) and len(date_range_2) == 2:
                    ds_2 = ds.sel({time_dim: slice(str(date_range_2[0]), str(date_range_2[1]))})
                    times_2 = pd.to_datetime(ds_2[time_dim].values)
                    if len(times_2) == 0:
                        st.sidebar.warning("No data available for Date Range 2.")
                        st.stop()
                else:
                    st.sidebar.info("Please select an end date for Dataset 2.")
                    st.stop()
                    
                st.sidebar.subheader("Temporal Selection")
                time_index_1 = st.sidebar.slider("Select Time 1 index", 0, len(times_1) - 1, 0)
                selected_time_1 = times_1[time_index_1]
                st.sidebar.write(f"**Time 1:** {selected_time_1.strftime('%Y-%m-%d %H:%M')}")
                
                time_index_2 = st.sidebar.slider("Select Time 2 index", 0, len(times_2) - 1, len(times_2) - 1)
                selected_time_2 = times_2[time_index_2]
                st.sidebar.write(f"**Time 2:** {selected_time_2.strftime('%Y-%m-%d %H:%M')}")
            
            # Location selection
            st.sidebar.subheader("Spatial Selection (for temporal view)")
            col1, col2 = st.sidebar.columns(2)
            with col1:
                selected_lat_idx = st.selectbox("Latitude Index", range(len(lats)), index=len(lats)//2)
            with col2:
                selected_lon_idx = st.selectbox("Longitude Index", range(len(lons)), index=len(lons)//2)
                
            selected_lat = lats[selected_lat_idx]
            selected_lon = lons[selected_lon_idx]
        
        # Helper function to extract data
        def extract_map_data(ds, selected_var, time_idx, time_dim, lat_dim, lon_dim):
            da_time_slice = ds[selected_var].isel(**{time_dim: time_idx})
            df = da_time_slice.to_dataframe().reset_index()
            df = df.rename(columns={lat_dim: 'lat', lon_dim: 'lon'})
            if df['lon'].max() > 180:
                df['lon'] = (df['lon'] + 180) % 360 - 180
            return df

        if view_mode == "Single View":
            df_map = extract_map_data(ds, selected_var, time_index, time_dim, lat_dim, lon_dim)
        else:
            df_map_1 = extract_map_data(ds_1, selected_var, time_index_1, time_dim, lat_dim, lon_dim)
            df_map_2 = extract_map_data(ds_2, selected_var, time_index_2, time_dim, lat_dim, lon_dim)
            # Find global min/max for consistent comparison scales
            global_min = min(df_map_1[selected_var].min(), df_map_2[selected_var].min())
            global_max = max(df_map_1[selected_var].max(), df_map_2[selected_var].max())

        # --- Main Layout ---
        tab1, tab2, tab3 = st.tabs(["🗺️ Spatial View", "📈 Temporal View", "🌐 3D Map Viewer"])
        
        with tab1:
            if view_mode == "Single View":
                st.subheader(f"Global Distribution of {selected_var} on {selected_time.strftime('%Y-%m-%d')}")
                try:
                    fig_map = px.scatter_geo(
                        df_map, lat="lat", lon="lon", color=selected_var,
                        hover_name=selected_var, size_max=15, projection="natural earth",
                        color_continuous_scale=px.colors.sequential.Plasma,
                        title=f"{selected_var} Distribution"
                    )
                    fig_map.update_layout(margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_map, use_container_width=True)
                except Exception as e:
                     st.error(f"Error generating map: {e}")
            else:
                st.subheader("Comparison: Spatial Distribution")
                col_map1, col_map2 = st.columns(2)
                
                with col_map1:
                    st.write(f"**{selected_time_1.strftime('%Y-%m-%d')}**")
                    try:
                        fig_map1 = px.scatter_geo(
                            df_map_1, lat="lat", lon="lon", color=selected_var,
                            hover_name=selected_var, size_max=15, projection="natural earth",
                            color_continuous_scale=px.colors.sequential.Plasma,
                            range_color=[global_min, global_max]
                        )
                        fig_map1.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig_map1, use_container_width=True)
                    except Exception as e:
                        st.error(f"Error: {e}")
                        
                with col_map2:
                    st.write(f"**{selected_time_2.strftime('%Y-%m-%d')}**")
                    try:
                        fig_map2 = px.scatter_geo(
                            df_map_2, lat="lat", lon="lon", color=selected_var,
                            hover_name=selected_var, size_max=15, projection="natural earth",
                            color_continuous_scale=px.colors.sequential.Plasma,
                            range_color=[global_min, global_max]
                        )
                        fig_map2.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig_map2, use_container_width=True)
                    except Exception as e:
                        st.error(f"Error: {e}")

        with tab2:
            st.subheader(f"Time Series for {selected_var} at Lat: {selected_lat:.2f}, Lon: {selected_lon:.2f}")
            
            if view_mode == "Single View":
                # Extract time series for the specific point
                da_timeseries = ds[selected_var].isel(**{lat_dim: selected_lat_idx, lon_dim: selected_lon_idx})
                df_ts = da_timeseries.to_dataframe().reset_index()
                
                fig_ts = px.line(
                    df_ts, 
                    x=time_dim, 
                    y=selected_var,
                    title=f"{selected_var} over time",
                    template="plotly_white"
                )
                fig_ts.update_layout(xaxis_title="Time", yaxis_title=selected_var, hovermode="x unified")
                
                # Add vertical line for selected time robustly using scatter trace
                y_min = df_ts[selected_var].min()
                y_max = df_ts[selected_var].max()
                
                fig_ts.add_trace(go.Scatter(x=[selected_time, selected_time], y=[y_min, y_max], 
                                            mode="lines", name="Current Date", line=dict(color="red", dash="dash", width=2)))
                st.plotly_chart(fig_ts, use_container_width=True)
                
            else:
                st.subheader("Comparison: Temporal Series")
                col_ts1, col_ts2 = st.columns(2)
                
                da_ts_1 = ds_1[selected_var].isel(**{lat_dim: selected_lat_idx, lon_dim: selected_lon_idx})
                df_ts_1 = da_ts_1.to_dataframe().reset_index()
                
                da_ts_2 = ds_2[selected_var].isel(**{lat_dim: selected_lat_idx, lon_dim: selected_lon_idx})
                df_ts_2 = da_ts_2.to_dataframe().reset_index()
                
                with col_ts1:
                    st.write(f"**{selected_time_1.strftime('%Y-%m-%d')}**")
                    fig_ts1 = px.line(df_ts_1, x=time_dim, y=selected_var, template="plotly_white")
                    fig_ts1.update_layout(xaxis_title="Time", yaxis_title=selected_var, hovermode="x unified", margin=dict(l=0, r=0, t=0, b=0))
                    y_min_1 = df_ts_1[selected_var].min()
                    y_max_1 = df_ts_1[selected_var].max()
                    fig_ts1.add_trace(go.Scatter(x=[selected_time_1, selected_time_1], y=[y_min_1, y_max_1], 
                                                mode="lines", name="Time 1", line=dict(color="red", dash="dash", width=2)))
                    st.plotly_chart(fig_ts1, use_container_width=True)
                    
                with col_ts2:
                    st.write(f"**{selected_time_2.strftime('%Y-%m-%d')}**")
                    fig_ts2 = px.line(df_ts_2, x=time_dim, y=selected_var, template="plotly_white")
                    fig_ts2.update_layout(xaxis_title="Time", yaxis_title=selected_var, hovermode="x unified", margin=dict(l=0, r=0, t=0, b=0))
                    y_min_2 = df_ts_2[selected_var].min()
                    y_max_2 = df_ts_2[selected_var].max()
                    fig_ts2.add_trace(go.Scatter(x=[selected_time_2, selected_time_2], y=[y_min_2, y_max_2], 
                                                mode="lines", name="Time 2", line=dict(color="blue", dash="dash", width=2)))
                    st.plotly_chart(fig_ts2, use_container_width=True)
            
        with tab3:
            if view_mode == "Single View":
                st.subheader("3D Interactive Map Render")
                st.markdown("A 3D visualization using PyDeck.")
                
                # Sample a subset of data if it's too large for webgl
                sample_frac = min(1.0, 10000 / len(df_map))
                df_pydeck = df_map.sample(frac=sample_frac).dropna(subset=[selected_var, 'lat', 'lon'])
                
                # Normalize variable for elevation and color
                var_min = df_pydeck[selected_var].min()
                var_max = df_pydeck[selected_var].max()
                df_pydeck['norm_val'] = (df_pydeck[selected_var] - var_min) / (var_max - var_min + 1e-6)
                
                # Colors: blue to red gradient based on normalized value
                df_pydeck['color_r'] = (df_pydeck['norm_val'] * 255).astype(int)
                df_pydeck['color_g'] = 50
                df_pydeck['color_b'] = ((1 - df_pydeck['norm_val']) * 255).astype(int)
                
                try:
                    layer = pdk.Layer(
                        "ColumnLayer", df_pydeck, get_position=["lon", "lat"],
                        get_elevation="norm_val * 500000", elevation_scale=1, radius=50000,
                        get_fill_color=["color_r", "color_g", "color_b", 200],
                        pickable=True, auto_highlight=True,
                    )
                    view_state = pdk.ViewState(
                        latitude=float(df_pydeck['lat'].mean()) if not df_pydeck.empty else 0.0,
                        longitude=float(df_pydeck['lon'].mean()) if not df_pydeck.empty else 0.0,
                        zoom=2, pitch=45,
                    )
                    r = pdk.Deck(
                        layers=[layer], initial_view_state=view_state,
                        tooltip={"text": f"Lat: {{lat}}\nLon: {{lon}}\n{selected_var}: {{{selected_var}}}"},
                        map_provider='carto', map_style='dark',
                    )
                    st.pydeck_chart(r)
                except Exception as e:
                    st.error(f"Error rendering 3D view: {e}")
            else:
                st.subheader("Comparison: 3D Interactive Map")
                col_globe1, col_globe2 = st.columns(2)
                
                sample_frac = min(1.0, 10000 / len(df_map_1))
                df_pydeck_1 = df_map_1.sample(frac=sample_frac).dropna(subset=[selected_var, 'lat', 'lon']).copy()
                df_pydeck_2 = df_map_2.sample(frac=sample_frac).dropna(subset=[selected_var, 'lat', 'lon']).copy()
                
                # Normalize using global min/max for true comparison
                df_pydeck_1['norm_val'] = (df_pydeck_1[selected_var] - global_min) / (global_max - global_min + 1e-6)
                df_pydeck_1['color_r'] = (df_pydeck_1['norm_val'] * 255).astype(int)
                df_pydeck_1['color_g'] = 50
                df_pydeck_1['color_b'] = ((1 - df_pydeck_1['norm_val']) * 255).astype(int)

                df_pydeck_2['norm_val'] = (df_pydeck_2[selected_var] - global_min) / (global_max - global_min + 1e-6)
                df_pydeck_2['color_r'] = (df_pydeck_2['norm_val'] * 255).astype(int)
                df_pydeck_2['color_g'] = 50
                df_pydeck_2['color_b'] = ((1 - df_pydeck_2['norm_val']) * 255).astype(int)

                with col_globe1:
                    st.write(f"**{selected_time_1.strftime('%Y-%m-%d')}**")
                    try:
                        layer1 = pdk.Layer(
                            "ColumnLayer", df_pydeck_1, get_position=["lon", "lat"],
                            get_elevation="norm_val * 500000", elevation_scale=1, radius=50000,
                            get_fill_color=["color_r", "color_g", "color_b", 200], pickable=True, auto_highlight=True,
                        )
                        view_state = pdk.ViewState(
                            latitude=float(df_pydeck_1['lat'].mean()) if not df_pydeck_1.empty else 0.0,
                            longitude=float(df_pydeck_1['lon'].mean()) if not df_pydeck_1.empty else 0.0,
                            zoom=2, pitch=45,
                        )
                        r1 = pdk.Deck(
                            layers=[layer1], initial_view_state=view_state,
                            tooltip={"text": f"Lat: {{lat}}\nLon: {{lon}}\n{selected_var}: {{{selected_var}}}"},
                            map_provider='carto', map_style='dark',
                        )
                        st.pydeck_chart(r1)
                    except Exception as e:
                        st.error(f"Error: {e}")

                with col_globe2:
                    st.write(f"**{selected_time_2.strftime('%Y-%m-%d')}**")
                    try:
                        layer2 = pdk.Layer(
                            "ColumnLayer", df_pydeck_2, get_position=["lon", "lat"],
                            get_elevation="norm_val * 500000", elevation_scale=1, radius=50000,
                            get_fill_color=["color_r", "color_g", "color_b", 200], pickable=True, auto_highlight=True,
                        )
                        view_state = pdk.ViewState(
                            latitude=float(df_pydeck_2['lat'].mean()) if not df_pydeck_2.empty else 0.0,
                            longitude=float(df_pydeck_2['lon'].mean()) if not df_pydeck_2.empty else 0.0,
                            zoom=2, pitch=45,
                        )
                        r2 = pdk.Deck(
                            layers=[layer2], initial_view_state=view_state,
                            tooltip={"text": f"Lat: {{lat}}\nLon: {{lon}}\n{selected_var}: {{{selected_var}}}"},
                            map_provider='carto', map_style='dark',
                        )
                        st.pydeck_chart(r2)
                    except Exception as e:
                        st.error(f"Error: {e}")

else:
    # Initial state screen, maybe some project info
    st.markdown("""
    ### Welcome to PyClimaExplorer!
    Explore complex climate model data easily.
    
    1. Select a data source from the sidebar. 
    2. Try the built-in tutorial dataset to get started right away.
    3. Choose variables, time slices, and specific geographic points to analyze.
    """)
    if st.button("🚀 Start Guided Tour", type="primary"):
        update_tour_state(True, 1)
        st.rerun()
