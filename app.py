import dash
from dash import dcc, html, Input, Output
import pandas as pd
import os
import subprocess
from chart import create_price_trend_chart, create_value_pie_chart, create_bingo_scatter
from dash.dependencies import Input, Output
from plotly.graph_objs import Figure
import plotly.graph_objects as go


# Constants
CLONES_CSV_FILENAME = "clones.csv"
MANDALORIANS_CSV_FILENAME = "mandalorians.csv"
CSV_URL = "https://docs.google.com/spreadsheets/d/1Z6n9yeqg0PPREqmOnJAapWa7o4K1byQ1Pu3pHtWFY10/export?format=csv"

EXPECTED_COLUMNS = [
    "Owned",
    "Picture",
    "Name of Clone",
    "SW ID",
    "Cost (BrickEconomy)"
]

def download_and_clean_csv(filename, expected_columns, sheet_gid=None):
    """Download and clean CSV from Google Sheets"""
    if not os.path.exists(filename):
        print(f"Downloading and cleaning {filename}...")
        
        # Construct URL with specific sheet if needed
        url = CSV_URL
        if sheet_gid:
            url = f"{CSV_URL}&gid={sheet_gid}"
            
        df_downloaded = pd.read_csv(url)
        
        # Clean column names
        df_downloaded.columns = [col.strip() for col in df_downloaded.columns]
        
        # Map expected → actual columns (case-insensitive)
        column_mapping = {}
        for expected in expected_columns:
            match = next((col for col in df_downloaded.columns if col.strip().lower() == expected.lower()), None)
            if match:
                column_mapping[expected] = match
            else:
                print(f"Warning: Expected column '{expected}' not found in Google Sheet.")
                print(f"Available columns: {list(df_downloaded.columns)}")
                continue
        
        if not column_mapping:
            raise ValueError(f"No expected columns found for {filename}")
            
        df_cleaned = df_downloaded[list(column_mapping.values())].rename(columns={v: k for k, v in column_mapping.items()})
        df_cleaned.to_csv(filename, index=False)
        print(f"Saved {filename}")
    else:
        print(f"Using cached file: {filename}")

# Download and clean both datasets
download_and_clean_csv(CLONES_CSV_FILENAME, EXPECTED_COLUMNS, sheet_gid="0")  # First sheet (clones)
download_and_clean_csv(MANDALORIANS_CSV_FILENAME, EXPECTED_COLUMNS, sheet_gid="1730506931")  # Second sheet (mandalorians)

def load_and_clean_df(filename):
    """Load and clean a dataframe"""
    df = pd.read_csv(filename)
    df.columns = [col.strip() for col in df.columns]
    
    # Clean and convert "Cost (BrickEconomy)"
    df["Cost (BrickEconomy)"] = (
        df["Cost (BrickEconomy)"]
        .astype(str)
        .str.replace(r"[^0-9\.]", "", regex=True)
        .astype(float)
    )
    
    # Ensure "Owned" is integer
    df["Owned"] = df["Owned"].fillna(0).astype(int)
    
    return df

# Load both datasets
clones_df = load_and_clean_df(CLONES_CSV_FILENAME)
mandalorians_df = load_and_clean_df(MANDALORIANS_CSV_FILENAME)

# Create combined dataset
all_df = pd.concat([clones_df, mandalorians_df], ignore_index=True)

# Combine all SW IDs for scraping
all_sw_ids = []
all_sw_ids.extend(clones_df["SW ID"].dropna().unique().tolist())
all_sw_ids.extend(mandalorians_df["SW ID"].dropna().unique().tolist())
all_sw_ids = list(set(all_sw_ids))  # Remove duplicates

# Ensure minifig value sales CSV exists
MINIFIG_VALUE_SALES_CSV = "all_minifig_value_sales.csv"
if not os.path.exists(MINIFIG_VALUE_SALES_CSV):
    print(f"{MINIFIG_VALUE_SALES_CSV} not found. Scraping value sales data...")
    subprocess.run([
        "python3", "scrap_script.py", *all_sw_ids
    ], check=True)
else:
    print(f"Using cached file: {MINIFIG_VALUE_SALES_CSV}")

def calculate_stats(df):
    """Calculate statistics for a dataframe"""
    owned = df[df["Owned"] == True]
    not_owned = df[df["Owned"] == False]
    
    owned_sum = owned["Cost (BrickEconomy)"].sum()
    not_owned_sum = not_owned["Cost (BrickEconomy)"].sum()
    
    total_count = len(df)
    owned_count = len(owned)
    not_owned_count = len(not_owned)
    percent_owned = 100 * owned_count / total_count if total_count else 0
    
    owned_avg = owned["Cost (BrickEconomy)"].mean() if owned_count else 0
    not_owned_avg = not_owned["Cost (BrickEconomy)"].mean() if not_owned_count else 0
    
    most_exp_owned = owned.sort_values("Cost (BrickEconomy)", ascending=False).iloc[0] if owned_count else None
    most_exp_not_owned = not_owned.sort_values("Cost (BrickEconomy)", ascending=False).iloc[0] if not_owned_count else None
    
    return {
        'owned_sum': owned_sum,
        'not_owned_sum': not_owned_sum,
        'total_count': total_count,
        'owned_count': owned_count,
        'not_owned_count': not_owned_count,
        'percent_owned': percent_owned,
        'owned_avg': owned_avg,
        'not_owned_avg': not_owned_avg,
        'most_exp_owned': most_exp_owned,
        'most_exp_not_owned': most_exp_not_owned,
        'owned': owned,
        'not_owned': not_owned
    }

# Calculate stats for all datasets
clones_stats = calculate_stats(clones_df)
mandalorians_stats = calculate_stats(mandalorians_df)
all_stats = calculate_stats(all_df)

# Initialize app
app = dash.Dash(__name__)
app.title = "Lego Minifig Prices"

DARK_BG = "#181c20"
DARK_CARD = "#23272b"
DARK_ACCENT = "#2d333b"
DARK_TEXT = "#f3f6fa"
DARK_SUBTEXT = "#b0b8c1"
DARK_BORDER = "#444b53"
DARK_SHADOW = "0 2px 12px #111"
DARK_PIE_COLORS = [
    "#8ecae6", "#219ebc", "#023047", "#ffb703", "#fb8500", "#ff006e", "#8338ec", "#3a86ff", "#ffbe0b", "#ff006e"
]
DARK_GREEN = "#1b5e20"
DARK_RED = "#8b0000"

def smart_truncate_name(name, max_len=32):
    # If name is short, return as is
    if len(name) <= max_len:
        return name
    # Try to keep the first part and the most unique/important part (e.g., after a dash or comma)
    parts = [p.strip() for p in name.replace('–', '-').replace('—', '-').split('-')]
    if len(parts) > 1:
        # Keep first and last part
        short = parts[0]
        if len(short) + len(parts[-1]) + 3 <= max_len:
            return f"{short} - {parts[-1][:max_len-len(short)-3]}..."
        else:
            return f"{short[:max_len-3]}..."
    # If comma-separated, try to keep first and last
    parts = [p.strip() for p in name.split(',')]
    if len(parts) > 1:
        short = parts[0]
        if len(short) + len(parts[-1]) + 3 <= max_len:
            return f"{short}, {parts[-1][:max_len-len(short)-3]}..."
        else:
            return f"{short[:max_len-3]}..."
    # Fallback: just truncate
    return name[:max_len-3] + '...'

def get_top5_cards(df, owned=True):
    top5 = df.sort_values("Cost (BrickEconomy)", ascending=False).head(5)
    cards = []
    for _, row in top5.iterrows():
        swid = row["SW ID"]
        name = smart_truncate_name(row["Name of Clone"])
        value = row["Cost (BrickEconomy)"]
        img_path = f"/assets/images/{swid}.png"
        cards.append(html.Div([
            html.Div([
                html.Img(src=img_path, style={
                    "maxWidth": "180px",
                    "maxHeight": "180px",
                    "display": "block",
                    "margin": "auto",
                }),
            ], style={
                "width": "200px",
                "height": "200px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "background": "#fff",
                "borderRadius": "18px",
                "border": f"3px solid {DARK_BORDER}",
                "margin": "0 auto"
            }),
            html.Div(name, style={"fontWeight": "bold", "fontSize": "1.7em", "marginTop": "1.2em", "color": DARK_TEXT}),
            html.Div(f"${value:,.2f}", style={"color": DARK_SUBTEXT, "fontSize": "1.3em", "marginTop": "0.4em"})
        ], style={"display": "inline-block", "width": "260px", "margin": "0 24px", "textAlign": "center", "verticalAlign": "top", "background": DARK_CARD, "borderRadius": "22px", "boxShadow": DARK_SHADOW, "padding": "18px 8px", "border": f"2px solid {DARK_BORDER}"}))
    return cards

def create_stats_section(stats, title):
    """Create statistics section for a dataset"""
    return html.Div([
        html.H3(title, style={"fontSize": "1.8em", "marginBottom": "0.5em", "color": DARK_TEXT}),
        html.H3(f"Total Value (Owned): ${stats['owned_sum']:,.2f}", style={"fontSize": "1.5em", "margin": "0.2em", "color": DARK_TEXT}),
        html.H3(f"Total Value (Not Owned): ${stats['not_owned_sum']:,.2f}", style={"fontSize": "1.5em", "margin": "0.2em", "color": DARK_TEXT}),
        html.P(f"Total Minifigures: {stats['total_count']}", style={"fontSize": "1.2em", "margin": "0.2em", "color": DARK_TEXT}),
        html.P(f"Owned: {stats['owned_count']} ({stats['percent_owned']:.1f}%)", style={"fontSize": "1.2em", "margin": "0.2em", "color": DARK_TEXT}),
        html.P(f"Not Owned: {stats['not_owned_count']} ({100-stats['percent_owned']:.1f}%)", style={"fontSize": "1.2em", "margin": "0.2em", "color": DARK_TEXT}),
        html.P(f"Average Value (Owned): ${stats['owned_avg']:,.2f}", style={"fontSize": "1.2em", "margin": "0.2em", "color": DARK_TEXT}),
        html.P(f"Average Value (Not Owned): ${stats['not_owned_avg']:,.2f}", style={"fontSize": "1.2em", "margin": "0.2em", "color": DARK_TEXT}),
        html.P(f"Most Expensive Owned: {smart_truncate_name(stats['most_exp_owned']['Name of Clone'])} (${stats['most_exp_owned']['Cost (BrickEconomy)']:,.2f})" if stats['most_exp_owned'] is not None else "Most Expensive Owned: N/A", style={"fontSize": "1.2em", "margin": "0.2em", "color": DARK_TEXT}),
        html.P(f"Most Expensive Not Owned: {smart_truncate_name(stats['most_exp_not_owned']['Name of Clone'])} (${stats['most_exp_not_owned']['Cost (BrickEconomy)']:,.2f})" if stats['most_exp_not_owned'] is not None else "Most Expensive Not Owned: N/A", style={"fontSize": "1.2em", "margin": "0.2em", "color": DARK_TEXT}),
    ], style={"textAlign": "center", "marginBottom": "2em", "background": DARK_CARD, "borderRadius": "18px", "padding": "1.2em 0", "boxShadow": DARK_SHADOW, "border": f"2px solid {DARK_BORDER}"})

def create_dataset_tab(df, stats, dataset_name):
    """Create a complete tab for a dataset"""
    return html.Div([
        create_stats_section(stats, f"{dataset_name} Statistics"),
        dcc.Graph(
            id=f"{dataset_name.lower()}-bingo-graph",
            style={"margin": "2em 0 2em 0", "width": "100%", "maxWidth": "1200px", "marginLeft": "auto", "marginRight": "auto"}
        ),
        html.Div([
            html.H4(f"Top 5 Most Expensive Owned {dataset_name}", style={"fontSize": "1.3em", "margin": "0.5em 0 0.2em 0", "color": DARK_TEXT}),
            html.Div(get_top5_cards(stats['owned'], owned=True), style={"marginBottom": "2em"}),
            html.H4(f"Top 5 Most Expensive Not Owned {dataset_name}", style={"fontSize": "1.3em", "margin": "0.5em 0 0.2em 0", "color": DARK_TEXT}),
            html.Div(get_top5_cards(stats['not_owned'], owned=False)),
        ], style={"textAlign": "center", "marginBottom": "2em", "background": DARK_CARD, "borderRadius": "18px", "padding": "1.2em 0", "boxShadow": DARK_SHADOW, "border": f"2px solid {DARK_BORDER}"}),
        html.Div([
            html.Div([
                dcc.Graph(
                    id=f"{dataset_name.lower()}-value-pie-chart",
                    figure=create_value_pie_chart(df, title=f"Percentage of Total Value by {dataset_name}", dark_mode=True),
                    style={"height": "600px"}
                )
            ], style={"width": "50%", "display": "inline-block", "verticalAlign": "top", "padding": "0 1em"}),
            html.Div(
                id=f"{dataset_name.lower()}-pie-hover-image-container",
                style={"width": "50%", "display": "inline-block", "verticalAlign": "top", "padding": "0 1em", "height": "600px", "boxSizing": "border-box", "display": "flex", "alignItems": "center", "justifyContent": "center"}
            ),
        ], style={"display": "flex", "flexDirection": "row", "justifyContent": "center", "alignItems": "stretch", "marginBottom": "2em", "background": DARK_CARD, "borderRadius": "18px", "padding": "1.2em 0", "boxShadow": DARK_SHADOW, "border": f"2px solid {DARK_BORDER}"}),
        dcc.Graph(
            id=f"{dataset_name.lower()}-owned-bar-chart", 
            figure=create_price_trend_chart(y_scale="linear", dark_mode=True), 
            style={"height": "700px"}
        ),
    ])

# Layout with tabs
app.layout = html.Div([
    html.H1("Lego Minifigure Price Trends", style={"textAlign": "center", "fontSize": "2.7em", "marginBottom": "0.2em", "color": DARK_TEXT}),
    dcc.Store(id="page-width-store"),
    dcc.Interval(id="interval", interval=1000, n_intervals=0, max_intervals=1),
    
    # Tabs
    dcc.Tabs([
        dcc.Tab(
            label="Clones", 
            children=create_dataset_tab(clones_df, clones_stats, "Clones"),
            style={"backgroundColor": DARK_CARD, "color": DARK_TEXT, "border": f"2px solid {DARK_BORDER}"},
            selected_style={"backgroundColor": DARK_ACCENT, "color": DARK_TEXT, "border": f"2px solid {DARK_BORDER}"}
        ),
        dcc.Tab(
            label="Mandalorians", 
            children=create_dataset_tab(mandalorians_df, mandalorians_stats, "Mandalorians"),
            style={"backgroundColor": DARK_CARD, "color": DARK_TEXT, "border": f"2px solid {DARK_BORDER}"},
            selected_style={"backgroundColor": DARK_ACCENT, "color": DARK_TEXT, "border": f"2px solid {DARK_BORDER}"}
        ),
        dcc.Tab(
            label="All", 
            children=create_dataset_tab(all_df, all_stats, "All"),
            style={"backgroundColor": DARK_CARD, "color": DARK_TEXT, "border": f"2px solid {DARK_BORDER}"},
            selected_style={"backgroundColor": DARK_ACCENT, "color": DARK_TEXT, "border": f"2px solid {DARK_BORDER}"}
        ),
    ], style={"backgroundColor": DARK_BG, "color": DARK_TEXT}),
], style={"fontFamily": "Segoe UI, Arial, sans-serif", "background": DARK_BG, "padding": "0", "margin": "0", "minHeight": "100vh"})

# Responsive bingo grid callbacks for both datasets
app.clientside_callback(
    """
    function(n_intervals) {
        return window.innerWidth;
    }
    """,
    Output("page-width-store", "data"),
    Input("interval", "n_intervals"),
)

@app.callback(
    Output("clones-bingo-graph", "figure"),
    Input("page-width-store", "data")
)
def update_clones_bingo_grid(page_width):
    try:
        columns = max(2, int(page_width // 130)) if page_width else 12
        fig = create_bingo_scatter(clones_df, columns=columns, dark_mode=True)
        if fig is None or not isinstance(fig, Figure):
            raise ValueError("Invalid figure returned")
        return fig
    except Exception as e:
        fig = go.Figure()
        fig.update_layout(
            title=f"Error loading clones bingo grid: {e}",
            paper_bgcolor="#181c20",
            plot_bgcolor="#181c20",
            font_color="#f3f6fa"
        )
        return fig

@app.callback(
    Output("mandalorians-bingo-graph", "figure"),
    Input("page-width-store", "data")
)
def update_mandalorians_bingo_grid(page_width):
    try:
        columns = max(2, int(page_width // 130)) if page_width else 12
        fig = create_bingo_scatter(mandalorians_df, columns=columns, dark_mode=True)
        if fig is None or not isinstance(fig, Figure):
            raise ValueError("Invalid figure returned")
        return fig
    except Exception as e:
        fig = go.Figure()
        fig.update_layout(
            title=f"Error loading mandalorians bingo grid: {e}",
            paper_bgcolor="#181c20",
            plot_bgcolor="#181c20",
            font_color="#f3f6fa"
        )
        return fig

@app.callback(
    Output("all-bingo-graph", "figure"),
    Input("page-width-store", "data")
)
def update_all_bingo_grid(page_width):
    try:
        columns = max(2, int(page_width // 130)) if page_width else 12
        fig = create_bingo_scatter(all_df, columns=columns, dark_mode=True)
        if fig is None or not isinstance(fig, Figure):
            raise ValueError("Invalid figure returned")
        return fig
    except Exception as e:
        fig = go.Figure()
        fig.update_layout(
            title=f"Error loading all bingo grid: {e}",
            paper_bgcolor="#181c20",
            plot_bgcolor="#181c20",
            font_color="#f3f6fa"
        )
        return fig

# Pie chart hover callbacks for both datasets
@app.callback(
    Output("clones-pie-hover-image-container", "children"),
    Input("clones-value-pie-chart", "hoverData")
)
def display_clones_pie_hover_image(hoverData):
    if hoverData and 'label' in hoverData['points'][0]:
        minifig_name = hoverData['points'][0]['label']
        swid = None
        if 'customdata' in hoverData['points'][0]:
            swid = hoverData['points'][0]['customdata'][0]
        # Fallback: try to find SW ID from clones_df
        if not swid:
            row = clones_df[clones_df["Name of Clone"] == minifig_name]
            if not row.empty:
                swid = row.iloc[0]["SW ID"]
        img_path = f"/assets/images/{swid}.png" if swid else None
        short_name = smart_truncate_name(minifig_name)
        return html.Div([
            html.Div([
                html.Img(src=img_path, style={
                    "maxWidth": "180px",
                    "maxHeight": "180px",
                    "display": "block",
                    "margin": "auto",
                }) if img_path else None,
            ], style={
                "width": "200px",
                "height": "200px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "background": "#fff",
                "borderRadius": "18px",
                "border": f"3px solid {DARK_BORDER}",
                "margin": "0 auto"
            }),
            html.H3(short_name, style={"marginTop": "1.5em", "fontSize": "2em", "color": DARK_TEXT})
        ], style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"})
    return html.Div("Hover over a slice to see the minifigure image.", style={"color": DARK_SUBTEXT, "textAlign": "center"})

@app.callback(
    Output("mandalorians-pie-hover-image-container", "children"),
    Input("mandalorians-value-pie-chart", "hoverData")
)
def display_mandalorians_pie_hover_image(hoverData):
    if hoverData and 'label' in hoverData['points'][0]:
        minifig_name = hoverData['points'][0]['label']
        swid = None
        if 'customdata' in hoverData['points'][0]:
            swid = hoverData['points'][0]['customdata'][0]
        # Fallback: try to find SW ID from mandalorians_df
        if not swid:
            row = mandalorians_df[mandalorians_df["Name of Clone"] == minifig_name]
            if not row.empty:
                swid = row.iloc[0]["SW ID"]
        img_path = f"/assets/images/{swid}.png" if swid else None
        short_name = smart_truncate_name(minifig_name)
        return html.Div([
            html.Div([
                html.Img(src=img_path, style={
                    "maxWidth": "180px",
                    "maxHeight": "180px",
                    "display": "block",
                    "margin": "auto",
                }) if img_path else None,
            ], style={
                "width": "200px",
                "height": "200px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "background": "#fff",
                "borderRadius": "18px",
                "border": f"3px solid {DARK_BORDER}",
                "margin": "0 auto"
            }),
            html.H3(short_name, style={"marginTop": "1.5em", "fontSize": "2em", "color": DARK_TEXT})
        ], style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"})
    return html.Div("Hover over a slice to see the minifigure image.", style={"color": DARK_SUBTEXT, "textAlign": "center"})

@app.callback(
    Output("all-pie-hover-image-container", "children"),
    Input("all-value-pie-chart", "hoverData")
)
def display_all_pie_hover_image(hoverData):
    if hoverData and 'label' in hoverData['points'][0]:
        minifig_name = hoverData['points'][0]['label']
        swid = None
        if 'customdata' in hoverData['points'][0]:
            swid = hoverData['points'][0]['customdata'][0]
        # Fallback: try to find SW ID from all_df
        if not swid:
            row = all_df[all_df["Name of Clone"] == minifig_name]
            if not row.empty:
                swid = row.iloc[0]["SW ID"]
        img_path = f"/assets/images/{swid}.png" if swid else None
        short_name = smart_truncate_name(minifig_name)
        return html.Div([
            html.Div([
                html.Img(src=img_path, style={
                    "maxWidth": "180px",
                    "maxHeight": "180px",
                    "display": "block",
                    "margin": "auto",
                }) if img_path else None,
            ], style={
                "width": "200px",
                "height": "200px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "background": "#fff",
                "borderRadius": "18px",
                "border": f"3px solid {DARK_BORDER}",
                "margin": "0 auto"
            }),
            html.H3(short_name, style={"marginTop": "1.5em", "fontSize": "2em", "color": DARK_TEXT})
        ], style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"})
    return html.Div("Hover over a slice to see the minifigure image.", style={"color": DARK_SUBTEXT, "textAlign": "center"})

# Run
if __name__ == "__main__":
    app.run(debug=True)
