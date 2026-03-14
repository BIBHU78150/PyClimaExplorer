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

# --- Data Loading ---
@st.cache_data
def load_tutorial_data():
    """Loads a default tutorial dataset (air temperature)."""
    try:
        ds = xr.tutorial.open_dataset("air_temperature").load()
        return ds
    except Exception as e:
        st.error(f"Error loading tutorial dataset: {e}")
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
data_source = st.sidebar.radio("Select Data Source", ["Tutorial Dataset (air_temperature)", "Upload NetCDF File"])

ds = None
if data_source == "Tutorial Dataset (air_temperature)":
    with st.spinner("Loading tutorial data..."):
        ds = load_tutorial_data()
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
        # Variable selection
        selected_var = st.sidebar.selectbox("Select Variable", variables)
        
        # Extract coordinate values
        times = pd.to_datetime(ds[time_dim].values)
        lats = ds[lat_dim].values
        lons = ds[lon_dim].values
        
        # Time selection
        st.sidebar.subheader("Temporal Selection")
        time_index = st.sidebar.slider("Select Time index", 0, len(times) - 1, 0)
        selected_time = times[time_index]
        st.sidebar.write(f"**Current Date:** {selected_time.strftime('%Y-%m-%d %H:%M')}")
        
        # Location selection
        st.sidebar.subheader("Spatial Selection (for temporal view)")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            selected_lat_idx = st.selectbox("Latitude Index", range(len(lats)), index=len(lats)//2)
        with col2:
            selected_lon_idx = st.selectbox("Longitude Index", range(len(lons)), index=len(lons)//2)
            
        selected_lat = lats[selected_lat_idx]
        selected_lon = lons[selected_lon_idx]
        
        # Convert Xarray data format for plotly
        # Slice for the current time
        da_time_slice = ds[selected_var].isel(**{time_dim: time_index})
        
        # Create a dataframe for the map
        df_map = da_time_slice.to_dataframe().reset_index()
        
        # Ensure correct column names for plotly
        df_map = df_map.rename(columns={lat_dim: 'lat', lon_dim: 'lon'})

        # Handle longitudes 0 to 360 vs -180 to 180
        if df_map['lon'].max() > 180:
            df_map['lon'] = (df_map['lon'] + 180) % 360 - 180

        # --- Main Layout ---
        tab1, tab2, tab3 = st.tabs(["🗺️ Spatial View", "📈 Temporal View", "🌐 3D Map Viewer"])
        
        with tab1:
            st.subheader(f"Global Distribution of {selected_var} on {selected_time.strftime('%Y-%m-%d')}")
            
            # Use Plotly Density Mapbox or Scattergeo
            try:
                fig_map = px.scatter_geo(
                    df_map, 
                    lat="lat", 
                    lon="lon", 
                    color=selected_var,
                    hover_name=selected_var, 
                    size_max=15,
                    projection="natural earth",
                    color_continuous_scale=px.colors.sequential.Plasma,
                    title=f"{selected_var} Distribution"
                )
                fig_map.update_layout(
                    margin=dict(l=0, r=0, t=30, b=0),
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_map, use_container_width=True)
            except Exception as e:
                 st.error(f"Error generating map: {e}")

        with tab2:
            st.subheader(f"Time Series for {selected_var} at Lat: {selected_lat:.2f}, Lon: {selected_lon:.2f}")
            
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
            fig_ts.update_layout(
                xaxis_title="Time",
                yaxis_title=selected_var,
                hovermode="x unified"
            )
            st.plotly_chart(fig_ts, use_container_width=True)
            
        with tab3:
            st.subheader("3D Interactive Map Render")
            st.markdown("A 3D visualization using PyDeck.")
            
            # Simple PyDeck implementation (HexagonLayer or ScatterplotLayer)
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
                    "ColumnLayer",
                    df_pydeck,
                    get_position=["lon", "lat"],
                    get_elevation="norm_val * 500000",
                    elevation_scale=1,
                    radius=50000,
                    get_fill_color=["color_r", "color_g", "color_b", 200],
                    pickable=True,
                    auto_highlight=True,
                )

                view_state = pdk.ViewState(
                    latitude=df_pydeck['lat'].mean() if not df_pydeck.empty else 0,
                    longitude=df_pydeck['lon'].mean() if not df_pydeck.empty else 0,
                    zoom=2,
                    pitch=45,
                )

                r = pdk.Deck(
                    layers=[layer],
                    initial_view_state=view_state,
                    tooltip={"text": f"Lat: {{lat}}\nLon: {{lon}}\n{selected_var}: {{{selected_var}}}"},
                    map_provider='carto',
                    map_style='dark',
                )
                
                # Render
                st.pydeck_chart(r)
            except Exception as e:
                st.error(f"Error rendering 3D view: {e}")

else:
    # Initial state screen, maybe some project info
    st.markdown("""
    ### Welcome to PyClimaExplorer!
    Explore complex climate model data easily.
    
    1. Select a data source from the sidebar. 
    2. Try the built-in tutorial dataset to get started right away.
    3. Choose variables, time slices, and specific geographic points to analyze.
    """)
