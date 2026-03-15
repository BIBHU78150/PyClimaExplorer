import urllib.request
import os

# Create a demo_datasets directory
output_dir = "demo_datasets"
os.makedirs(output_dir, exist_ok=True)

# List of URLs for small NetCDF files (often used in tutorials or examples)
# These are publicly available THREDDS/OPeNDAP servers or direct links.

datasets = {
    # NCEP Reanalysis 1 - Surface Pressure (Monthly Long Term Mean) - Very Small
    "ncep_surface_pressure_ltm.nc": "https://downloads.psl.noaa.gov/Datasets/ncep.reanalysis.derived/surface/pres.sfc.mon.ltm.nc",
    
    # NCEP Reanalysis - Air Temperature at surface (Daily for a single year - 2023) - ~30MB
    "ncep_air_temp_2023.nc": "https://downloads.psl.noaa.gov/Datasets/ncep.reanalysis.dailyavgs/surface/air.sig995.2023.nc",
    
    # NCEP Sea Level Pressure (Daily for 2023) - ~15MB
    "ncep_slp_2023.nc": "https://downloads.psl.noaa.gov/Datasets/ncep.reanalysis.dailyavgs/surface/slp.2023.nc"
}

for filename, url in datasets.items():
    output_path = os.path.join(output_dir, filename)
    print(f"Downloading {filename} from {url}...")
    try:
        urllib.request.urlretrieve(url, output_path)
        print(f"Successfully downloaded to {output_path}")
        print(f"Size: {os.path.getsize(output_path) / (1024*1024):.2f} MB")
        print("-" * 40)
    except Exception as e:
        print(f"Failed to download {filename}. Error: {e}")

print("Download script finished.")
