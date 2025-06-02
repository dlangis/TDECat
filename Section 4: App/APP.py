# Import packages
from dash import Dash, html, dash_table, dcc, callback, Output, Input
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import os

# ---------------------------------------------------------------
# Additional Functions for UVOT Conversion
# ---------------------------------------------------------------

def AB_magnitude_to_flux(mag, err):
    """
    Convert AB magnitudes to flux density in Jy.
    """
    mag = np.array(mag)
    err = np.array(err)
    flux = 3631 * 10**(-0.4 * mag)
    flux_err = flux * np.log(10) * 0.4 * err
    return flux, flux_err

# New Swift zero-points (Breeveld et al.)
zeropoints_new = {
    'vv': {'vega': 17.89, 'ab': 17.88},
    'bb': {'vega': 19.11, 'ab': 18.98},
    'uu': {'vega': 18.34, 'ab': 19.36},
    'w1': {'vega': 17.44, 'ab': 18.95},
    'm2': {'vega': 16.85, 'ab': 18.54},
    'w2': {'vega': 17.38, 'ab': 19.11},
}

def swift_vega_to_ab(m_vega, filt):
    """
    Convert a Swift UVOT Vega magnitude to an AB magnitude.
    """
    offset = zeropoints_new[filt]['ab'] - zeropoints_new[filt]['vega']
    return m_vega + offset

# Define the UVOT filter order, colors, markers, and vertical offsets.
uvot_filters  = ["w2", "m2", "w1", "uu", "bb", "vv"]
uvot_colors   = {
    "w2": "violet",
    "m2": "purple",
    "w1": "blue",
    "uu": "green",
    "bb": "orange",
    "vv": "red"
}
uvot_markers  = {
    "w2": "circle",
    "m2": "square",
    "w1": "diamond",
    "uu": "triangle-up",
    "bb": "triangle-down",
    "vv": "pentagon"
}
uvot_offsets  = {
    "w2": 0.0,
    "m2": 1.25,
    "w1": 2.5,
    "uu": 4,
    "bb": 5.5,
    "vv": 7
}

# ---------------------------------------------------------------
# Data Loading and Preparation
# ---------------------------------------------------------------

# Read in the catalogue CSV
df = pd.read_csv('TDE_catalogue_all.csv', delimiter=',')

# Save plain versions for AT and ZTF names.
# If the 'AT name' column is empty, then use the 'Alternative name' column.
df['AT_name_plain'] = df.apply(
    lambda row: row['AT name'].strip().replace("AT ", "AT")
                if pd.notna(row['AT name']) and row['AT name'].strip() != ""
                else (row['Alternative name'].strip() if pd.notna(row['Alternative name']) and row['Alternative name'].strip() != "" else ""),
    axis=1
)
df['ZTF_name_plain'] = df['ZTF name'].str.strip()

# Extract identifiers (for generating URL links in the table)
def extract_identifier(name):
    if pd.notna(name) and name.strip() != "":
        return name.split()[-1]
    else:
        return None

df['identifier']  = df['AT name'].apply(extract_identifier)
df['identifier2'] = df['ZTF name'].apply(extract_identifier)
df['identifier3'] = df['Gaia alert name'].apply(extract_identifier)

# Generate markdown links for display in the table
base_url_at   = "https://www.wis-tns.org/object/"
base_url_ztf  = "https://alerce.online/object/"
base_url_gaia = "http://gsaweb.ast.cam.ac.uk/alerts/alert/"

df['AT name'] = '[' + df['AT name'] + ']' + '(' + base_url_at + df['identifier'] + ')'
df['ZTF name'] = '[' + df['ZTF name'] + ']' + '(' + base_url_ztf + df['identifier2'] + ')'
df['Gaia alert name'] = '[' + df['Gaia alert name'] + ']' + '(' + base_url_gaia + df['identifier3'] + ')'

# ---------------------------------------------------------------
# Data Directories
# ---------------------------------------------------------------
data_dir_bhtom = 'OPTICAL_INFRARED'  # Optical/Infrared photometry folder
data_dir_sp    = 'OPTICAL_SPECTRA'           # Spectrum folder
data_dir_uvot  = 'UV'              # UVOT light curve folder
data_dir_xray  = 'X-RAYS'#'X-rays'            # X-ray light curve folder

# ---------------------------------------------------------------
# App Layout
# ---------------------------------------------------------------
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

app.layout = dbc.Container([
    # Title and logo
    dbc.Row([
        dbc.Col(html.Img(src="assets/TDECat2.png", height="150px"), width="auto"),
        dbc.Col(html.H2('Welcome to the Tidal Disruption Event catalogue (aka TDECat) for events up until 2024'))
    ], align="center"),
    
    html.Hr(),
    
    # Catalogue DataTable (with markdown links)
    dash_table.DataTable(
        data=df.to_dict('records'),
        page_size=10,
        columns=[{'id': x, 'name': x, 'presentation': 'markdown'} if x in ['AT name','ZTF name','Gaia alert name'] 
                 else {'id': x, 'name': x} for x in df.columns]
    ),
    
    html.H4('Global histograms'),
    html.Hr(),
    html.P('Select parameter:'),
    dcc.Dropdown(
        id="controls-and-radio-item",
        options=["Redshift", "Discovery date (UT)", "Discovery mag/flux"],
        value="Redshift",
        clearable=False,
    ),
    dcc.Graph(figure={}, id='controls-and-graph'),
    
    html.H4('Individual Light Curves and Spectrum'),
    html.Hr(),
    # Single target-selection dropdown (uses plain AT names)
    dcc.Dropdown(
        id='target-dropdown',
        options=[{'label': at, 'value': idx} for idx, at in enumerate(df['AT_name_plain'].tolist())],
        placeholder="Type to search for AT name...",
        searchable=True,
        clearable=True,
    ),
    html.H5('Optical/Infrared Light Curve'),
    dcc.Graph(id='optical-plot', figure={}),
    
    html.H5('UVOT Light Curve'),
    dcc.Graph(id='uvot-plot', figure={}),

    html.H5('X-ray Light Curve'),

    # ── Add SNR threshold input here ────────────────────────────────────────
    html.Div([
        html.Label("SNR threshold:"),
        dcc.Input(
            id='snr-input',
            type='number',
            value=3,         # default SNR = 3
            min=0,
            step=0.1,
            style={'width': '80px'}
        )
    ], style={'margin-bottom': '10px'}),

    dcc.Graph(id='xray-plot', figure={}),
    
    html.H5('Spectrum'),
    dcc.Graph(id='spectrum-plot', figure={}),
    
    html.Hr(),
    html.P('©Dimitrios-Alkinoos Langis (alkinooslangis@gmail.com)')
], fluid=True)

# ---------------------------------------------------------------
# Callback: Global Histogram (unchanged)
# ---------------------------------------------------------------
@callback(
    Output('controls-and-graph', 'figure'),
    Input('controls-and-radio-item', 'value')
)
def update_graph(col_chosen):
    if col_chosen == "Discovery mag/flux":
        # 1) Take the raw column as strings
        raw_mag = df['Discovery mag/flux'].astype(str)
        # 2) Remove any “(vega)” (and surrounding whitespace)
        mag_clean = raw_mag.str.replace(r'\s*\(vega\)\s*', '', regex=True)
        # 3) Convert to numeric, drop non‐numeric
        mag_vals = pd.to_numeric(mag_clean, errors='coerce').dropna()
        # 4) Build the histogram from mag_vals
        fig = px.histogram(
            mag_vals,
            nbins=30
        )
        return fig

    # default for all other columns:
    fig = px.histogram(df, x=col_chosen, histfunc='count')
    return fig


# ---------------------------------------------------------------
# Callback: Update Individual Plots 
# ---------------------------------------------------------------
@callback(
    Output('optical-plot', 'figure'),
    Output('uvot-plot', 'figure'),
    Output('xray-plot', 'figure'),
    Output('spectrum-plot', 'figure'),
    Input('target-dropdown', 'value'),
    Input('snr-input', 'value')   #SNR threshold
)
def update_individual_plots(selected_index, snr_threshold):
    # Create empty figures for each panel.
    optical_fig  = go.Figure()
    uvot_fig     = go.Figure()
    xray_fig     = go.Figure()
    spectrum_fig = go.Figure()
    
    if selected_index is None:
        # Return empty figures if no target is selected.
        return optical_fig, uvot_fig, xray_fig, spectrum_fig
    
    # Look up the target row by DataFrame index.
    row = df.loc[selected_index]
    # Use AT_name_plain if available; otherwise, fall back to ZTF_name_plain.
    name_for_file = (row['AT_name_plain'] if pd.notna(row['AT_name_plain']) and row['AT_name_plain'].strip() != ""
                     else row['ZTF_name_plain'])
    
    # -----------------------------
    # 1. Optical/Infrared Light Curve
    optical_file = os.path.join(data_dir_bhtom, "target_" + name_for_file + "_photometry.csv")
    if os.path.exists(optical_file):
        try:
            dfl_opt = pd.read_csv(optical_file, delimiter=';')
            for filt, group in dfl_opt.groupby('Filter'):
                optical_fig.add_trace(go.Scatter(
                    x=group['MJD'],
                    y=group['Magnitude'],
                    error_y=dict(type='data', array=group['Error'], visible=True),
                    mode='markers',
                    name=f"{filt}"
                ))
        except Exception as e:
            print(f"Error reading optical file {optical_file}: {e}")
            optical_fig.add_annotation(text="Error loading Optical/Infrared data")
    else:
        optical_fig.add_annotation(text="No Optical/Infrared data available")
    optical_fig.update_xaxes(title="Modified Julian Date")
    optical_fig.update_yaxes(title="Magnitude")
    optical_fig.update_yaxes(autorange="reversed")
    optical_fig.update_layout(title="", legend_title="Filter")
    
    # -----------------------------
    # 2. UVOT Light Curve
    uvot_file = os.path.join(data_dir_uvot, name_for_file + "_uvot_lightcurve.csv")
    if os.path.exists(uvot_file):
        try:
            dfl_uvot = pd.read_csv(uvot_file)  # assuming comma delimiter
            for flt in uvot_filters:
                mag_col = f"mag_{flt}_src"
                err_col = f"magerr_{flt}_src"
                if mag_col in dfl_uvot.columns and err_col in dfl_uvot.columns:
                    # Convert from Vega to AB.
                    AB_MAG = swift_vega_to_ab(dfl_uvot[mag_col], flt)
                    uvot_fig.add_trace(go.Scatter(
                        x=dfl_uvot["mjd"],
                        y=AB_MAG,
                        error_y=dict(type='data', array=dfl_uvot[err_col], visible=True),
                        mode='markers',
                        marker=dict(symbol=uvot_markers[flt],
                                    color=uvot_colors[flt],
                                    size=8,
                                    line=dict(color='black')),
                        name=f"UVOT {flt.upper()}"
                    ))
            uvot_fig.update_yaxes(autorange="reversed")
        except Exception as e:
            print(f"Error reading UVOT file {uvot_file}: {e}")
            uvot_fig.add_annotation(text="Error loading UVOT data")
    else:
        uvot_fig.add_annotation(text="No UVOT data available")
    uvot_fig.update_xaxes(title="Modified Julian Date")
    uvot_fig.update_yaxes(title="AB Magnitude")
    uvot_fig.update_layout(title="", legend_title="Filter")
    
    # -----------------------------
    # 3. X-ray Light Curve (SNR‐controlled)
    xray_file = os.path.join(data_dir_xray, name_for_file + "_xray_lightcurve.csv")
    if os.path.exists(xray_file):
        try:
            dfl_xray = pd.read_csv(xray_file)
    
            # Compute mid‐MJD
            dfl_xray['MJD'] = (dfl_xray['mjd_start'] + dfl_xray['mjd_stop']) / 2.0
    
            # Extract arrays (or default to zeros if missing)
            src_flux    = dfl_xray['src_flux'].values
            src_err_lo  = dfl_xray['src_flux_errinf'].values
            src_err_hi  = dfl_xray['src_flux_errsup'].values
            src_snr     = dfl_xray['src_flux_SNR'].values if 'src_flux_SNR' in dfl_xray.columns else np.zeros(len(dfl_xray))
            src_ul_vals = dfl_xray['src_flux_UL'].values if 'src_flux_UL' in dfl_xray.columns else np.zeros(len(dfl_xray))
    
            flux_fit_pl   = dfl_xray.get('flux_fit_pl', pd.Series(0, index=dfl_xray.index)).values
            fit_pl_err_lo = dfl_xray.get('flux_fit_pl_errinf', pd.Series(0, index=dfl_xray.index)).values
            fit_pl_err_hi = dfl_xray.get('flux_fit_pl_errsup', pd.Series(0, index=dfl_xray.index)).values
    
            flux_fit_bb   = dfl_xray.get('flux_fit_bb', pd.Series(0, index=dfl_xray.index)).values
            fit_bb_err_lo = dfl_xray.get('flux_fit_bb_errinf', pd.Series(0, index=dfl_xray.index)).values
            fit_bb_err_hi = dfl_xray.get('flux_fit_bb_errsup', pd.Series(0, index=dfl_xray.index)).values
    
            best_model_raw = (
                dfl_xray['best_model']
                .fillna("")
                .astype(str)
                .str.upper()
                .str.strip()
                .values
            )
            mjd_vals = dfl_xray['MJD'].values
    
            # Masks based on SNR threshold (anything with low SNR → treat as UL)
            ul_mask  = (src_flux == 0) | (src_snr < snr_threshold)  # upper limits
            det_mask = (src_snr >= snr_threshold) & (~ul_mask)      # detections
    
            # Among detections, split into PL vs. BB vs. “no fit provided”
            pl_mask = det_mask & (best_model_raw == 'PL')
            bb_mask = det_mask & (best_model_raw == 'BB')
            src_det_mask = det_mask & (best_model_raw == '')  
    
            # --- PL‐fitted points ---
            mjd_pl    = mjd_vals[pl_mask]
            flux_pl   = flux_fit_pl[pl_mask]
            errlo_pl  = fit_pl_err_lo[pl_mask]
            errhi_pl  = fit_pl_err_hi[pl_mask]
    
            # --- BB‐fitted points ---
            mjd_bb    = mjd_vals[bb_mask]
            flux_bb   = flux_fit_bb[bb_mask]
            errlo_bb  = fit_bb_err_lo[bb_mask]
            errhi_bb  = fit_bb_err_hi[bb_mask]
    
            # --- “Raw” detections (no model) if any ---
            mjd_src    = mjd_vals[src_det_mask]
            flux_src   = src_flux[src_det_mask]
            errlo_src  = src_err_lo[src_det_mask]
            errhi_src  = src_err_hi[src_det_mask]
    
            # --- Upper‐limits (including low‐SNR) ---
            mjd_ulims = mjd_vals[ul_mask]
            ulims     = src_ul_vals[ul_mask]
    
            # Plot
            # 1) “Raw” detections, blue circles
            if len(mjd_src):
                xray_fig.add_trace(go.Scatter(
                    x=mjd_src,
                    y=flux_src,
                    error_y=dict(
                        type='data',
                        symmetric=False,
                        array=errhi_src,
                        arrayminus=errlo_src,
                        visible=True
                    ),
                    mode='markers',
                    marker=dict(color='blue', symbol='circle', size=8),
                    name='Detection (raw src_flux)'
                ))
    
            # 2) PL‐fit detections, green squares
            if len(mjd_pl):
                xray_fig.add_trace(go.Scatter(
                    x=mjd_pl,
                    y=flux_pl,
                    error_y=dict(
                        type='data',
                        symmetric=False,
                        array=errhi_pl,
                        arrayminus=errlo_pl,
                        visible=True
                    ),
                    mode='markers',
                    marker=dict(color='green', symbol='square', size=8),
                    name='Detection (PL fit)'
                ))
    
            # 3) BB‐fit detections, orange diamonds
            if len(mjd_bb):
                xray_fig.add_trace(go.Scatter(
                    x=mjd_bb,
                    y=flux_bb,
                    error_y=dict(
                        type='data',
                        symmetric=False,
                        array=errhi_bb,
                        arrayminus=errlo_bb,
                        visible=True
                    ),
                    mode='markers',
                    marker=dict(color='orange', symbol='diamond', size=8),
                    name='Detection (BB fit)'
                ))
    
            # 4) Upper limits (red triangle‐down)
            if len(mjd_ulims):
                xray_fig.add_trace(go.Scatter(
                    x=mjd_ulims,
                    y=ulims,
                    mode='markers',
                    marker=dict(color='red', symbol='triangle-down', size=10),
                    name='Upper limits'
                ))
    
        except Exception as e:
            print(f"Error processing X-ray file {xray_file}: {e}")
            xray_fig.add_annotation(text="Error loading X-ray data")
    else:
        xray_fig.add_annotation(text="No X-ray data available")
    
    # Ensure legend always appears
    xray_fig.update_xaxes(title="Modified Julian Date")
    xray_fig.update_yaxes(title_text='Flux (erg/s/cm^-2)')
    xray_fig.update_layout(
        title="",
        legend_title="Data Type / Best‐Fit Model",
        showlegend=True
    )
    
    # -----------------------------
    # 4. Spectrum Plot (redshift‐corrected to rest frame)
    # Determine the folder name using name_for_file first; if empty, use AT or Alternative
    if pd.notna(name_for_file) and name_for_file.strip() != "":
        spec_name = name_for_file
    elif pd.notna(row['AT name']) and row['AT name'].strip() != "":
        spec_name = row['AT name'].strip().replace("AT ", "AT")
    elif pd.notna(row['Alternative name']) and row['Alternative name'].strip() != "":
        spec_name = row['Alternative name'].strip()
    else:
        spec_name = name_for_file
    
    spec_folder = os.path.join(data_dir_sp, f"{spec_name}_ascii_files")
    
    # Get redshift (default to 0 if missing/invalid)
    try:
        z = float(row['Redshift']) if pd.notna(row['Redshift']) else 0.0
    except:
        z = 0.0
    
    all_y_vals = []
    
    if os.path.exists(spec_folder):
        try:
            matching_files = [f for f in os.listdir(spec_folder) if not f.startswith('.')]
            if not matching_files:
                spectrum_fig.add_annotation(text="No spectrum files found")
            else:
                for file in matching_files:
                    file_path = os.path.join(spec_folder, file)
                    try:
                        df_spec = pd.read_csv(file_path, delim_whitespace=True, comment='#', header=None)
                    except Exception as e:
                        print(f"Error reading spectrum file {file_path}: {e}")
                        continue
    
                    if df_spec.empty or df_spec.shape[1] < 2:
                        continue
    
                    wavelength_obs = df_spec.iloc[:, 0].values
                    intensity       = df_spec.iloc[:, 1].values
    
                    # Convert observed wavelength to rest‐frame
                    wavelength_rest = wavelength_obs / (1.0 + z)
    
                    all_y_vals.extend(intensity.tolist())
                    spectrum_fig.add_trace(go.Scatter(
                        x=wavelength_rest,
                        y=intensity,
                        mode='lines',
                        name=file,
                        showlegend=True
                    ))
    
                if not spectrum_fig.data:
                    spectrum_fig.add_annotation(text="No valid spectrum traces found")
                if all_y_vals:
                    spectrum_fig.update_xaxes(title="Rest Wavelength (Å)")
    
                    # -----------------------------------------------------------------
                    # ADD REST‐FRAME H α, H β, He II (4686 Å) MARKERS WITH LABELS BELOW AXIS
                    # Dictionary of rest‐frame line wavelengths (in Å)
                    rest_lines = {
                        "H α": 6562.8,
                        "H β": 4861.3,
                        "He II": 4686.0
                    }
    
                    for label, wl_rest in rest_lines.items():
                        spectrum_fig.add_shape(
                            type="line",
                            xref="x",
                            yref="paper",
                            x0=wl_rest,
                            x1=wl_rest,
                            y0=0,
                            y1=1,
                            line=dict(color="magenta", dash="dash"),
                            layer="below"
                        )
                        spectrum_fig.add_annotation(
                            x=wl_rest,
                            y=0,
                            xref="x",
                            yref="paper",
                            text=label,
                            showarrow=False,
                            yshift=-20, 
                            font=dict(size=12, color="magenta")
                        )
    
        except Exception as e:
            print(f"Error processing spectrum folder {spec_folder}: {e}")
            spectrum_fig.add_annotation(text="Error loading spectrum")
    else:
        spectrum_fig.add_annotation(text="No spectrum folder found")
    
    spectrum_fig.update_layout(
        title="",
        legend_title="File names",
        showlegend=True,
        legend=dict(
            orientation="h",
            x=0.5,
            y=1.15,
            xanchor="center",
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="black",
            borderwidth=1
        ),
        margin=dict(t=120, b=80)
    )
    return optical_fig, uvot_fig, xray_fig, spectrum_fig



# ---------------------------------------------------------------
# Run the app
# ---------------------------------------------------------------
if __name__ == '__main__':
    app.server.run(port=8000, host='127.0.0.1', debug=True)
