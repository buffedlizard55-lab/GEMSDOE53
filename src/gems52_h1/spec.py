"""Pinned specification of the DOE GEMS Prize grid, band taxonomy, and SHA-256 pins.

Every geometry constant and band description below was verified directly from the
restored GeoTIFF headers in data/training_features.tif, data/labels.tif, and
data/sample_submission.tif.

Official Competition References:
- Overview: https://www.drivendata.org/competitions/306/competition-doe-gems/
- Problem Description & DTI Metric: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
- About & Resources: https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/
- Data Tab: https://www.drivendata.org/competitions/306/competition-doe-gems/data/
- Leaderboard: https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/
- NREL/DOE GEMS Prize Rules PDF: https://docs.nlr.gov/docs/fy26osti/96647.pdf
- DOE GDR Submission 1391 (INGENIOUS): https://gdr.openei.org/submissions/1391
- USGS GeoDAWN Airborne Survey: https://doi.org/10.5066/P93LGLVQ
- Blum & Mitchell (COLT '98): https://doi.org/10.1145/279943.279962
"""
from __future__ import annotations

# --- Grid Geometry (Verified from sample_submission.tif & training_features.tif) ---
EPSG = 32611
CRS_STRING = "EPSG:32611"
PIXEL_SIZE_M = 100.0
WIDTH = 3292
HEIGHT = 3730
SHAPE = (HEIGHT, WIDTH)
ORIGIN_X = 243350.0
ORIGIN_Y = 4508550.0
TRANSFORM_TUPLE = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
BOUNDS = (243350.0, 4135550.0, 572550.0, 4508550.0)
TOTAL_PIXELS = HEIGHT * WIDTH  # 12,279,160

# --- Measured Pixel Counts ---
FOOTPRINT_PIXELS = 5_167_373
NODATA_OUTSIDE_PIXELS = 7_111_787
CATALOGUE_POSITIVE_PIXELS = 60_988

# --- Sentinels ---
FEATURE_SENTINEL = -3.4028234663852886e38
FEATURE_INVALID_BELOW = -1e38
LABEL_NODATA = -1

# --- Official DTI Metric Constants ---
ALPHA = 0.2
BETA = 0.8
RADIUS_M = 300.0
RADIUS_PX = 3.0
EPS_METRIC = 1e-12

# --- All 19 Official Bands in training_features.tif (1-based index, name, category, description) ---
OFFICIAL_BANDS: list[tuple[int, str, str, str]] = [
    (1, "mag_anom", "magnetic_data", "Magnetic anomaly - deviation from expected Earth's magnetic field"),
    (2, "rtp", "magnetic_data", "Reduced to pole magnetic data - magnetic anomaly corrected for latitude effects"),
    (3, "tmi_hg", "magnetic_data", "Total magnetic intensity horizontal gradient - rate of change in horizontal direction"),
    (4, "geod_2ndinv", "geodetic_strain", "Geodetic second invariant - measure of strain rate tensor magnitude"),
    (5, "iso_grav_anom_slope", "gravity_data", "Isostatic gravity anomaly slope - gradient of gravity after isostatic correction"),
    (6, "tc", "magnetic_data", "Tilt angle or total curvature - magnetic field derivative for edge detection"),
    (7, "geod_shearrate", "geodetic_strain", "Geodetic shear rate - rate of angular deformation from GPS/InSAR"),
    (8, "geod_dilaterate", "geodetic_strain", "Geodetic dilatation rate - rate of volumetric strain (expansion/contraction)"),
    (9, "tmi_vg", "magnetic_data", "Total magnetic intensity vertical gradient - rate of change in vertical direction"),
    (10, "deq_n100a15", "seismic", "Distance to earthquake (n=100km radius, a=15° azimuth parameters)"),
    (11, "iso_grav_anom_vg", "gravity_data", "Isostatic gravity anomaly vertical gradient - vertical rate of change"),
    (12, "det_elev", "topographic", "Detrended elevation - topography with regional trends removed"),
    (13, "iso_grav_anom", "gravity_data", "Isostatic gravity anomaly - gravity after compensating for topographic mass"),
    (14, "tmi", "magnetic_data", "Total magnetic intensity - total strength of magnetic field"),
    (15, "depth_to_base_surf", "subsurface", "Depth to basement surface - thickness of sedimentary cover"),
    (16, "ieq_n100a15", "seismic", "Earthquake intensity or density (n=100km radius, a=15° parameters)"),
    (17, "cond_surf", "subsurface", "Conductivity surface - electrical conductivity of subsurface"),
    (18, "iso_grav_anom_hg", "gravity_data", "Isostatic gravity anomaly horizontal gradient - horizontal rate of change"),
    (19, "det_elev_slope", "topographic", "Detrended elevation slope - gradient of elevation after detrending"),
]

BAND_NAME_TO_IDX = {name: idx for idx, name, _, _ in OFFICIAL_BANDS}

# View A: Potential-field and subsurface (gravity, magnetics, strain, seismicity, basement/conductivity)
VIEW_A_BAND_NAMES: tuple[str, ...] = (
    "mag_anom",
    "rtp",
    "tmi_hg",
    "geod_2ndinv",
    "iso_grav_anom_slope",
    "tc",
    "geod_shearrate",
    "geod_dilaterate",
    "tmi_vg",
    "deq_n100a15",
    "iso_grav_anom_vg",
    "iso_grav_anom",
    "tmi",
    "depth_to_base_surf",
    "ieq_n100a15",
    "cond_surf",
    "iso_grav_anom_hg",
)

# View B: Surface (DEM-derived curvature and slope, plus any radiometric bands)
# NOTE (IR-52-01): training_features.tif contains 0 radiometric bands (Band 6 'tc' is
# magnetic_data: "Tilt angle or total curvature - magnetic field derivative for edge detection").
# True airborne gamma-ray radiometrics (K, Th, U, TC) are in data/external/geodawn_rad_u8.tif
# from the USGS GeoDAWN release (DOI: 10.5066/P93LGLVQ).
VIEW_B_BAND_NAMES: tuple[str, ...] = (
    "det_elev",
    "det_elev_slope",
)
