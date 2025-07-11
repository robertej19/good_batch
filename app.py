import dash
from dash import dcc, html, Input, Output, State, callback_context, no_update
import pandas as pd
import os
import subprocess
from chart import create_price_trend_chart, create_value_pie_chart, create_bingo_scatter
import plotly.express as px
from dash.dependencies import Input, Output
from plotly.graph_objs import Figure
import plotly.graph_objects as go
import numpy as np


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
try:
    download_and_clean_csv(CLONES_CSV_FILENAME, EXPECTED_COLUMNS, sheet_gid="0")  # First sheet (clones)
    download_and_clean_csv(MANDALORIANS_CSV_FILENAME, EXPECTED_COLUMNS, sheet_gid="1730506931")  # Second sheet (mandalorians)
except Exception as e:
    print(f"Warning: Could not download CSV files: {e}")

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
try:
    clones_df = load_and_clean_df(CLONES_CSV_FILENAME)
    mandalorians_df = load_and_clean_df(MANDALORIANS_CSV_FILENAME)
except Exception as e:
    print(f"Warning: Could not load CSV files: {e}")
    # Create empty DataFrames as fallback
    clones_df = pd.DataFrame(columns=EXPECTED_COLUMNS)
    mandalorians_df = pd.DataFrame(columns=EXPECTED_COLUMNS)

# Create combined dataset
all_df = pd.concat([clones_df, mandalorians_df], ignore_index=True)

# Create a sorted DataFrame for the grid (descending by value, reindexed)
all_grid_df = all_df.sort_values("Cost (BrickEconomy)", ascending=False).reset_index(drop=True)

# Combine all SW IDs for scraping
all_sw_ids = []
all_sw_ids.extend(clones_df["SW ID"].dropna().unique().tolist())
all_sw_ids.extend(mandalorians_df["SW ID"].dropna().unique().tolist())
all_sw_ids = list(set(all_sw_ids))  # Remove duplicates

# Ensure minifig value sales CSV exists
MINIFIG_VALUE_SALES_CSV = "all_minifig_value_sales.csv"
if not os.path.exists(MINIFIG_VALUE_SALES_CSV):
    print(f"{MINIFIG_VALUE_SALES_CSV} not found. Scraping value sales data...")
    try:
        subprocess.run([
            "python3", "information_scraper.py", *all_sw_ids
        ], check=True)
    except Exception as e:
        print(f"Warning: Could not scrape value sales data: {e}")
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
server = app.server  # THIS is needed!

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
DARK_BLACK = "#000000"

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
        html.Div(
            dcc.Graph(
                id=f"{dataset_name.lower()}-bingo-graph",
                style={"margin": "2em 0 2em 0", "width": "100%", "maxWidth": "1200px", "marginLeft": "auto", "marginRight": "auto"},
                config={"responsive": True}
            ),
            id=f"{dataset_name.lower()}-bingo-graph-container",
            style={"paddingLeft": 32, "paddingRight": 32}  # default, will be overridden in callback for mobile
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

def make_minifig_grid(df, grid_id_prefix="minifig"):  # grid_id_prefix allows for multiple grids if needed
    df = df.sort_values("Cost (BrickEconomy)", ascending=False).reset_index(drop=True)
    return html.Div(
        [
            html.Div([
                html.Img(
                    src=f"/assets/images_bg_removed/{row['SW ID']}.png",
                    style={
                        "width": "100%",
                        "borderRadius": "10px",
                        "background": "transparent",
                        "display": "block",
                    },
                ),
            ],
                id={"type": f"{grid_id_prefix}-img", "index": i},
                n_clicks=0,
                style={
                    "aspectRatio": "1/1",
                    "background": ("#222" if row.get("Owned", False) else "#8b0000"),
                    "padding": "2px",
                    "margin": "2px",
                    "display": "inline-block",
                    "boxSizing": "border-box",
                    "cursor": "pointer",
                    "transition": "box-shadow 0.2s",
                    "position": "relative",
                    "overflow": "hidden",
                },
                tabIndex=0  # for accessibility
            )
            for i, row in df.iterrows()
        ],
        id=f"{grid_id_prefix}-grid",
        style={
            # Remove 'padding', 'width', and 'maxWidth' so CSS can control it
            "display": "flex",
            "flexWrap": "wrap",
            "justifyContent": "center",
            "gap": "2px",
            "margin": "0",
        }
    )

# Helper to create a price history chart for a single minifig
def create_single_minifig_price_chart(swid, dark_mode=True, line_width=2, chart_height=220):
    try:
        df = pd.read_csv("all_minifig_value_sales.csv", parse_dates=["Date"])
    except FileNotFoundError:
        # Return empty figure if file doesn't exist
        return go.Figure()
    minifig_df = df[df["SW_ID"] == swid].sort_values("Date")
    if minifig_df.empty:
        return go.Figure()
    # Apply rolling window smoothing (12 months)
    window = 12
    minifig_df = minifig_df.set_index("Date")
    minifig_df["Q1_smooth"] = minifig_df["Q1"].rolling(window=window, min_periods=1, center=True).mean()
    minifig_df["Q3_smooth"] = minifig_df["Q3"].rolling(window=window, min_periods=1, center=True).mean()
    minifig_df = minifig_df.reset_index()
    fig = go.Figure()
    # Only show a 50% transparent blue band between smoothed Q1 and Q3, no bounding lines
    fig.add_traces([
        go.Scatter(
            x=minifig_df["Date"],
            y=minifig_df["Q3_smooth"],
            mode="lines",
            line=dict(color="rgba(33, 150, 243, 0.5)", width=0),  # No visible line
            fill=None,
            showlegend=False,
            hoverinfo="skip",
        ),
        go.Scatter(
            x=minifig_df["Date"],
            y=minifig_df["Q1_smooth"],
            mode="lines",
            line=dict(color="rgba(33, 150, 243, 0.5)", width=0),  # No visible line
            fill='tonexty',
            fillcolor="rgba(33, 150, 243, 0.5)",
            showlegend=False,
            hoverinfo="skip",
        ),
    ])
    fig.update_layout(
        title="Price History (Q1–Q3 Band, Smoothed)",
        xaxis_title="Date",
        yaxis_title="Value ($)",
        margin=dict(l=10, r=10, t=40, b=10),
        height=chart_height,
        font={"size": 10},
        showlegend=False,
    )
    if dark_mode:
        fig.update_layout(
            plot_bgcolor=DARK_BG,
            paper_bgcolor=DARK_BG,
            font_color=DARK_TEXT,
            xaxis=dict(gridcolor=DARK_BORDER, zerolinecolor=DARK_BORDER),
            yaxis=dict(gridcolor=DARK_BORDER, zerolinecolor=DARK_BORDER),
        )
    return fig

# Helper to create a sum-over-time Q3 chart for a group of minifigs

def create_group_q3_sum_chart(swid_list, chart_height=320):
    try:
        df = pd.read_csv("all_minifig_value_sales.csv", parse_dates=["Date"])
    except FileNotFoundError:
        # Return empty figure if file doesn't exist
        return go.Figure()
    group_df = df[df["SW_ID"].isin(swid_list)]
    # Only keep data from 2021 onwards
    group_df = group_df[group_df["Date"] >= pd.Timestamp("2021-01-01")]
    if group_df.empty:
        return go.Figure()
    # For each date, for each minifig, get the most recent Q3 value up to that date
    all_dates = group_df["Date"].sort_values().unique()
    all_swids = group_df["SW_ID"].unique()
    value_by_date = []
    count_by_date = []
    for date in all_dates:
        # For each minifig, get the most recent Q3 value up to this date
        sub = group_df[group_df["Date"] <= date]
        latest_q3 = sub.sort_values("Date").groupby("SW_ID").tail(1)
        value_sum = latest_q3["Q3"].sum()
        value_by_date.append(value_sum)
        count_by_date.append(len(latest_q3))
    import numpy as np
    fig = go.Figure()
    # Total Q3 value (left y-axis)
    fig.add_trace(go.Scatter(
        x=all_dates,
        y=value_by_date,
        mode="lines",
        line=dict(color="#2196f3", width=3),
        fill="tozeroy",
        fillcolor="rgba(33, 150, 243, 0.18)",
        name="Total Q3 Value",
        yaxis="y1",
    ))
    # Number of minifigs (right y-axis)
    fig.add_trace(go.Scatter(
        x=all_dates,
        y=count_by_date,
        mode="lines+markers",
        line=dict(color="#ffbe0b", width=2, dash="dot"),
        marker=dict(size=6, color="#ffbe0b"),
        name="# Minifigs",
        yaxis="y2",
    ))
    fig.update_layout(
        title="Value and Quantity",
        title_x=0.5,
        xaxis_title="Date",
        yaxis=dict(
            title="Collection Value ($)",
            showgrid=True,
            gridcolor=DARK_BORDER,
            zerolinecolor=DARK_BORDER,
            tickformat="~s",
            ticksuffix="",
        ),
        yaxis2=dict(
            title=dict(text="# Minifigs", font=dict(color="#ffbe0b")),
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=dict(color="#ffbe0b"),
        ),
        margin=dict(l=10, r=10, t=40, b=10),
        height=chart_height,
        font={"size": 11},
        showlegend=False,
        plot_bgcolor=DARK_BG,
        paper_bgcolor=DARK_BG,
        font_color=DARK_TEXT,
        xaxis=dict(gridcolor=DARK_BORDER, zerolinecolor=DARK_BORDER),
    )
    return fig

# Remove Clones, Mandalorians, and All tabs, keep only the Grid tab
app.layout = html.Div([
    html.H1("Lego Star Wars Collection", style={"textAlign": "center", "fontSize": "2.7em", "marginBottom": "0.2em", "color": DARK_TEXT}),
    dcc.Store(id="page-width-store"),
    dcc.Interval(id="interval", interval=1000, n_intervals=0, max_intervals=1),
    dcc.Tabs(
        id="minifig-tabs",
        value="all",
        children=[
            dcc.Tab(label="Clones", value="clones",
                style={
                    "backgroundColor": DARK_CARD,
                    "color": DARK_TEXT,
                    "border": f"2px solid {DARK_BORDER}",
                    "fontWeight": "bold",
                    "fontSize": "1.1em",
                    "padding": "0.5em 1em",
                    "marginRight": "0.2em",
                    "borderRadius": "12px 12px 0 0",
                },
                selected_style={
                    "backgroundColor": DARK_ACCENT,
                    "color": DARK_TEXT,
                    "border": f"2px solid {DARK_BORDER}",
                    "fontWeight": "bold",
                    "fontSize": "1.1em",
                    "padding": "0.5em 1em",
                    "marginRight": "0.2em",
                    "borderRadius": "12px 12px 0 0",
                },
            ),
            dcc.Tab(label="Mandalorians", value="mandalorians",
                style={
                    "backgroundColor": DARK_CARD,
                    "color": DARK_TEXT,
                    "border": f"2px solid {DARK_BORDER}",
                    "fontWeight": "bold",
                    "fontSize": "1.1em",
                    "padding": "0.5em 1em",
                    "marginRight": "0.2em",
                    "borderRadius": "12px 12px 0 0",
                },
                selected_style={
                    "backgroundColor": DARK_ACCENT,
                    "color": DARK_TEXT,
                    "border": f"2px solid {DARK_BORDER}",
                    "fontWeight": "bold",
                    "fontSize": "1.1em",
                    "padding": "0.5em 1em",
                    "marginRight": "0.2em",
                    "borderRadius": "12px 12px 0 0",
                },
            ),
            dcc.Tab(label="All", value="all",
                style={
                    "backgroundColor": DARK_CARD,
                    "color": DARK_TEXT,
                    "border": f"2px solid {DARK_BORDER}",
                    "fontWeight": "bold",
                    "fontSize": "1.1em",
                    "padding": "0.5em 1em",
                    "marginRight": "0.2em",
                    "borderRadius": "12px 12px 0 0",
                },
                selected_style={
                    "backgroundColor": DARK_ACCENT,
                    "color": DARK_TEXT,
                    "border": f"2px solid {DARK_BORDER}",
                    "fontWeight": "bold",
                    "fontSize": "1.1em",
                    "padding": "0.5em 1em",
                    "marginRight": "0.2em",
                    "borderRadius": "12px 12px 0 0",
                },
            ),
        ],
        style={"maxWidth": "600px", "margin": "0 auto 1.5em auto", "borderBottom": f"2px solid {DARK_BORDER}", "display": "flex", "flexDirection": "row", "backgroundColor": DARK_BG},
        parent_className="custom-tabs",
        className="custom-tabs-container",
        colors={"background": DARK_BG, "border": DARK_BORDER, "primary": DARK_ACCENT},
        vertical=False,
    ),
    html.Div(id="minifig-stats-summary", style={"maxWidth": "700px", "margin": "0 auto 1.5em auto"}),
    html.Div(id="minifig-grid-container"),
                # Modal overlay for minifig popout
                html.Div(
                    id="minifig-modal-overlay",
                    style={
                        "display": "none",
                        "position": "fixed",
                        "top": 0,
                        "left": 0,
                        "width": "100vw",
                        "height": "100vh",
                        "background": "transparent",  # No gray overlay
                        "zIndex": 1000,
                        "justifyContent": "center",
                        "alignItems": "flex-start",
                        "pointerEvents": "none",  # Allow clicks to pass through except modal content
                    },
                    children=[
                        html.Div(
                            id="minifig-modal-content",
                            style={
                                "margin": "5vh auto 0 auto",
                                "position": "relative",
                                "top": "5vh",
                                "width": "min(40vw, 98vw)",
                                "background": DARK_CARD,
                                "borderRadius": "18px",
                                "boxShadow": DARK_SHADOW,
                                "padding": "1.5em 1em 1em 1em",
                                "textAlign": "center",
                                "color": DARK_TEXT,
                                "zIndex": 1001,
                                "pointerEvents": "auto",  # Only modal content is clickable
                                "fontSize": "1em",
                            },
                            children=[
                                html.Button("×", id="minifig-modal-close", n_clicks=0, style={
                                    "position": "absolute",
                                    "top": "0.7em",
                                    "right": "1.1em",
                                    "fontSize": "2em",
                                    "background": "none",
                                    "border": "none",
                                    "color": DARK_TEXT,
                                    "cursor": "pointer",
                                    "zIndex": 1002,
                                }),
                                html.Div(id="minifig-modal-body")
                            ]
                        )
                    ]
                ),
], style={"fontFamily": "Segoe UI, Arial, sans-serif", "background": DARK_BG, "padding": "0", "margin": "0", "minHeight": "100vh"})

# Callback to update the stats summary and grid based on selected tab
@app.callback(
    [Output("minifig-stats-summary", "children"), Output("minifig-grid-container", "children")],
    [Input("minifig-tabs", "value"), Input("page-width-store", "data")],
)
def update_minifig_stats_and_grid(tab_value, page_width):
    if tab_value == "clones":
        df = clones_df.sort_values("Cost (BrickEconomy)", ascending=False).reset_index(drop=True)
        label = "Clones"
    elif tab_value == "mandalorians":
        df = mandalorians_df.sort_values("Cost (BrickEconomy)", ascending=False).reset_index(drop=True)
        label = "Mandalorians"
    else:
        df = all_grid_df
        label = "All Minifigs"
    owned = df[df["Owned"] == 1]
    not_owned = df[df["Owned"] == 0]
    owned_sum = owned["Cost (BrickEconomy)"].sum()
    not_owned_sum = not_owned["Cost (BrickEconomy)"].sum()
    owned_count = len(owned)
    not_owned_count = len(not_owned)
    # Chart: sum Q3 values over time for all minifigs in this group
    swid_list = df["SW ID"].dropna().unique().tolist()
    chart = dcc.Graph(
        figure=create_group_q3_sum_chart(swid_list),
        config={"displayModeBar": False},
        style={"height": "320px", "width": "100%", "margin": "0 auto"}
    )
    # Responsive layout
    mobile = page_width is not None and page_width < 700
    if mobile:
        text_style = {"fontSize": "0.98em", "padding": "0 0.5em", "marginBottom": "1em", "color": DARK_TEXT, "width": "100%", "textAlign": "center"}
        stats_section = html.Div([
            html.Div([
                html.H3(f"{label} Statistics", style={"fontSize": "1.1em", "marginBottom": "0.4em", "color": DARK_TEXT, "textAlign": "center"}),
                html.P(f"Total Value (Owned): ${owned_sum:,.2f}", style=text_style),
                html.P(f"Total Value (Not Owned): ${not_owned_sum:,.2f}", style=text_style),
                html.P(f"Owned: {owned_count}", style=text_style),
                html.P(f"Not Owned: {not_owned_count}", style=text_style),
            ], style={"width": "100%", "padding": "0", "marginBottom": "0.5em"}),
            html.Div(chart, style={"width": "100%", "minWidth": "0", "maxWidth": "100%", "overflow": "hidden", "display": "flex", "alignItems": "center", "justifyContent": "center"}),
        ], style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "width": "90%", "margin": "0 auto", "background": DARK_CARD, "borderRadius": "14px", "padding": "0.7em 0", "boxShadow": DARK_SHADOW, "border": f"2px solid {DARK_BORDER}"})
    else:
        stats_section = html.Div([
            html.Div([
                html.H3(f"{label} Statistics", style={"fontSize": "1.3em", "marginBottom": "0.5em", "color": DARK_TEXT}),
                html.P(f"Total Value (Owned): ${owned_sum:,.2f}", style={"fontSize": "1.1em", "margin": "0.2em", "color": DARK_TEXT}),
                html.P(f"Total Value (Not Owned): ${not_owned_sum:,.2f}", style={"fontSize": "1.1em", "margin": "0.2em", "color": DARK_TEXT}),
                html.P(f"Owned: {owned_count}", style={"fontSize": "1.1em", "margin": "0.2em", "color": DARK_TEXT}),
                html.P(f"Not Owned: {not_owned_count}", style={"fontSize": "1.1em", "margin": "0.2em", "color": DARK_TEXT}),
            ], style={"flex": "0 0 auto", "minWidth": "0", "maxWidth": "100%", "padding": "0 1.5em", "display": "flex", "flexDirection": "column", "justifyContent": "center", "alignItems": "flex-start"}),
            html.Div(chart, style={"flex": "1 1 0", "minWidth": "0", "maxWidth": "100%", "overflow": "hidden", "display": "flex", "alignItems": "center", "justifyContent": "center"}),
        ], style={"display": "flex", "flexDirection": "row", "alignItems": "stretch", "justifyContent": "center", "width": "100%", "gap": "1.5em", "background": DARK_CARD, "borderRadius": "14px", "padding": "1.1em 0", "boxShadow": DARK_SHADOW, "border": f"2px solid {DARK_BORDER}", "flexWrap": "wrap"})
    return stats_section, make_minifig_grid(df)

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

# Modal popout callback for grid
@app.callback(
    Output("minifig-modal-overlay", "style"),
    Output("minifig-modal-content", "style"),
    Output("minifig-modal-body", "children"),
    Input({"type": "minifig-img", "index": dash.ALL}, "n_clicks_timestamp"),
    State({"type": "minifig-img", "index": dash.ALL}, "id"),
    Input("minifig-modal-close", "n_clicks"),
    State("page-width-store", "data"),
    prevent_initial_call=True,
)
def show_minifig_modal(n_clicks_timestamps, ids, close_n_clicks, page_width):
    ctx = callback_context
    # If close button was clicked, hide modal
    if ctx.triggered and ctx.triggered[0]["prop_id"].startswith("minifig-modal-close"):
        return {"display": "none"}, no_update, no_update
    # Otherwise, show modal for the most recently clicked minifig
    if not n_clicks_timestamps or all(ts is None for ts in n_clicks_timestamps):
        return {"display": "none"}, no_update, no_update
    idx = int(np.nanargmax([ts or 0 for ts in n_clicks_timestamps]))
    i = ids[idx]["index"]
    row = all_grid_df.iloc[i]

    # Determine if mobile
    mobile = page_width is not None and page_width < 700
    modal_width = "98vw" if mobile else "min(85vw, 98vw)"
    left_col_width = "25%" if mobile else "25%"
    img_max_width = "70px" if mobile else "110px"
    chart_line_width = 4 if mobile else 2
    chart_height = 180 if mobile else 220

    price_chart = dcc.Graph(
        figure=create_single_minifig_price_chart(row["SW ID"], line_width=chart_line_width, chart_height=chart_height),
        config={"displayModeBar": False},
        style={"height": f"{chart_height}px", "width": "100%", "marginTop": "0"}
    )
    modal_body = html.Div([
        html.Div([
            html.H2(row["Name of Clone"], style={
                "marginTop": "0",
                "marginBottom": "1em",
                "fontSize": "1.1em",
                "lineHeight": "1.2",
                "textAlign": "center",
                # No width or padding here; handled by parent div
            }),
        ], style={
            "width": "80%",
            "margin": "0 auto",
        }),
        html.Div([
            html.Div([
                html.Img(src=f"/assets/images/{row['SW ID']}.png", style={"width": "80%", "maxWidth": img_max_width, "margin": "0 auto 0.7em auto", "display": "block", "background": "#fff", "borderRadius": "10px", "boxShadow": DARK_SHADOW}),
                html.P(f"Current Price: ${row['Cost (BrickEconomy)']:.2f}", style={"fontSize": "0.85em", "marginTop": "0.3em", "textAlign": "center"}),
            ], style={"flex": f"0 0 {left_col_width}", "minWidth": "0", "marginRight": "1.2em", "display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "flex-start"}),
            html.Div(price_chart, style={"flex": "1 1 0", "minWidth": "0", "maxWidth": "100%", "overflow": "hidden", "display": "flex", "alignItems": "center", "justifyContent": "center"}),
        ], style={"display": "flex", "flexDirection": "row", "alignItems": "flex-start", "justifyContent": "center", "width": "100%", "overflow": "hidden"}),
    ], style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "flex-start", "width": "100%", "overflow": "hidden"})
    modal_style = {
        "display": "flex",
        "position": "fixed",
        "top": 0,
        "left": 0,
        "width": modal_width,
        "height": "100vh",
        "background": "transparent",
        "zIndex": 1000,
        "justifyContent": "center",
        "alignItems": "flex-start",
        "pointerEvents": "none",
    }
    modal_content_style = {
        "margin": "5vh auto 0 auto",
        "position": "relative",
        "top": "5vh",
        "width": modal_width,
        "background": DARK_CARD,
        "borderRadius": "18px",
        "boxShadow": DARK_SHADOW,
        "padding": "1.5em 1em 1em 1em",
        "textAlign": "center",
        "color": DARK_TEXT,
        "zIndex": 1001,
        "pointerEvents": "auto",
        "fontSize": "1em",
    }
    return modal_style, modal_content_style, modal_body

# Run
if __name__ == "__main__":
    app.run(debug=True)
