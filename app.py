import dash
from dash import dcc, html, Input, Output, State, callback_context
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
                html.Div(
                    [
                        html.Div(
                            row["Name of Clone"],
                            style={
                                "fontWeight": "bold",
                                "fontSize": "min(1.1em, 4vw)",  # Shrinks on small screens
                                "overflowWrap": "break-word",
                                "wordBreak": "break-word",
                                "whiteSpace": "normal",
                                "lineHeight": "1.1",
                                "maxHeight": "4.4em",  # Allow up to 4 lines
                                "overflow": "auto",
                                "width": "100%",
                                "margin": "0 auto",
                                "padding": "0 2px",
                            }
                        ),
                        html.Div(
                            f"${row['Cost (BrickEconomy)']:.2f}",
                            style={
                                "fontSize": "1em",
                                "textAlign": "center",
                                "width": "100%",
                                "marginTop": "0.3em"
                            }
                        ),
                    ],
                    id={"type": f"{grid_id_prefix}-overlay", "index": i},
                    style={
                        "position": "absolute",
                        "top": 0,
                        "left": 0,
                        "width": "100%",
                        "height": "100%",
                        "background": "rgba(24,28,32,0.97)",
                        "color": "#fff",
                        "display": "none",
                        "alignItems": "flex-start",  # Start near the top
                        "justifyContent": "flex-start",  # Start near the top
                        "flexDirection": "column",
                        "zIndex": 2,
                        "borderRadius": "10px",
                        "textAlign": "center",
                        "padding": "12px 6px",
                        "fontSize": "1.1em",
                        "boxShadow": "0 2px 12px #111",
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
    df = pd.read_csv("all_minifig_value_sales.csv", parse_dates=["Date"])
    minifig_df = df[df["SW_ID"] == swid]
    if minifig_df.empty:
        return go.Figure()
    fig = go.Figure()
    # Q1 line
    fig.add_trace(go.Scatter(
        x=minifig_df["Date"],
        y=minifig_df["Q1"],
        mode="lines",
        name="Q1 (25th %)",
        line=dict(color="#4fc3f7", width=line_width),
    ))
    # Q3 line
    fig.add_trace(go.Scatter(
        x=minifig_df["Date"],
        y=minifig_df["Q3"],
        mode="lines",
        name="Q3 (75th %)",
        line=dict(color="#1976d2", width=line_width),
        fill='tonexty',
        fillcolor="rgba(33, 150, 243, 0.18)",
    ))
    fig.update_layout(
        title="Price History (Q1–Q3 Band)",
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

# Add a new tab for the HTML/CSS grid
app.layout = html.Div([
    html.H1("Lego Minifigure Price Trends", style={"textAlign": "center", "fontSize": "2.7em", "marginBottom": "0.2em", "color": DARK_TEXT}),
    dcc.Store(id="page-width-store"),
    dcc.Interval(id="interval", interval=1000, n_intervals=0, max_intervals=1),
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
        dcc.Tab(
            label="Grid", 
            children=[
                html.H2("All Minifigs - Responsive Grid", style={"textAlign": "center", "color": DARK_TEXT, "marginTop": "1em"}),
                make_minifig_grid(all_grid_df),
                html.Div(id="minifig-info-panel", style={"marginTop": "2em", "color": DARK_TEXT, "textAlign": "center", "fontSize": "1.2em"}),
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
            ],
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
    Output("clones-bingo-graph-container", "style"),
    Output("clones-bingo-graph", "style"),
    Input("page-width-store", "data")
)
def update_clones_bingo_grid(page_width):
    try:
        mobile = page_width is not None and page_width < 700
        if mobile:
            container_style = {
                "width": "100vw",
                "display": "flex",
                "justifyContent": "center",
                "paddingLeft": 0,
                "paddingRight": 0,
                "margin": "0"
            }
            graph_style = {"width": "60vw", "minWidth": 0, "margin": "2em 0 2em 0"}
            available_width = int(page_width * 0.6)
            columns = 5
            max_img_size = int((available_width / 5) * 0.92) * 2
            max_img_size = max(40, min(220, max_img_size))
        else:
            side_padding = 32
            container_style = {"paddingLeft": side_padding, "paddingRight": side_padding}
            graph_style = {"margin": "2em 0 2em 0", "width": "100%", "maxWidth": "1200px", "marginLeft": "auto", "marginRight": "auto"}
            available_width = max(320, page_width - 2 * side_padding) if page_width else 320
            columns = max(2, int(page_width // 130)) if page_width else 12
            max_img_size = 130
        fig = create_bingo_scatter(clones_df, columns=columns, dark_mode=True, mobile=mobile, mobile_image_size=max_img_size)
        if fig is None or not isinstance(fig, Figure):
            raise ValueError("Invalid figure returned")
        return fig, container_style, graph_style
    except Exception as e:
        fig = go.Figure()
        fig.update_layout(
            title=f"Error loading clones bingo grid: {e}",
            paper_bgcolor="#181c20",
            plot_bgcolor="#181c20",
            font_color="#f3f6fa"
        )
        return fig, {"width": "100vw", "display": "flex", "justifyContent": "center", "paddingLeft": 0, "paddingRight": 0, "margin": "0"}, {"width": "60vw", "minWidth": 0, "margin": "2em 0 2em 0"}

@app.callback(
    Output("mandalorians-bingo-graph", "figure"),
    Output("mandalorians-bingo-graph-container", "style"),
    Output("mandalorians-bingo-graph", "style"),
    Input("page-width-store", "data")
)
def update_mandalorians_bingo_grid(page_width):
    try:
        mobile = page_width is not None and page_width < 700
        if mobile:
            container_style = {
                "width": "100vw",
                "display": "flex",
                "justifyContent": "center",
                "paddingLeft": 0,
                "paddingRight": 0,
                "margin": "0"
            }
            graph_style = {"width": "60vw", "minWidth": 0, "margin": "2em 0 2em 0"}
            available_width = int(page_width * 0.6)
            columns = 5
            max_img_size = int((available_width / 5) * 0.92) * 2
            max_img_size = max(40, min(220, max_img_size))
        else:
            side_padding = 32
            container_style = {"paddingLeft": side_padding, "paddingRight": side_padding}
            graph_style = {"margin": "2em 0 2em 0", "width": "100%", "maxWidth": "1200px", "marginLeft": "auto", "marginRight": "auto"}
            available_width = max(320, page_width - 2 * side_padding) if page_width else 320
            columns = max(2, int(page_width // 130)) if page_width else 12
            max_img_size = 130
        fig = create_bingo_scatter(mandalorians_df, columns=columns, dark_mode=True, mobile=mobile, mobile_image_size=max_img_size)
        if fig is None or not isinstance(fig, Figure):
            raise ValueError("Invalid figure returned")
        return fig, container_style, graph_style
    except Exception as e:
        fig = go.Figure()
        fig.update_layout(
            title=f"Error loading mandalorians bingo grid: {e}",
            paper_bgcolor="#181c20",
            plot_bgcolor="#181c20",
            font_color="#f3f6fa"
        )
        return fig, {"width": "100vw", "display": "flex", "justifyContent": "center", "paddingLeft": 0, "paddingRight": 0, "margin": "0"}, {"width": "60vw", "minWidth": 0, "margin": "2em 0 2em 0"}

@app.callback(
    Output("all-bingo-graph", "figure"),
    Output("all-bingo-graph-container", "style"),
    Output("all-bingo-graph", "style"),
    Input("page-width-store", "data")
)
def update_all_bingo_grid(page_width):
    try:
        mobile = page_width is not None and page_width < 700
        if mobile:
            container_style = {
                "width": "100vw",
                "display": "flex",
                "justifyContent": "center",
                "paddingLeft": 0,
                "paddingRight": 0,
                "margin": "0"
            }
            graph_style = {"width": "60vw", "minWidth": 0, "margin": "2em 0 2em 0"}
            available_width = int(page_width * 0.6)
            columns = 5
            max_img_size = int((available_width / 5) * 0.92) * 2
            max_img_size = max(40, min(220, max_img_size))
        else:
            side_padding = 32
            container_style = {"paddingLeft": side_padding, "paddingRight": side_padding}
            graph_style = {"margin": "2em 0 2em 0", "width": "100%", "maxWidth": "1200px", "marginLeft": "auto", "marginRight": "auto"}
            available_width = max(320, page_width - 2 * side_padding) if page_width else 320
            columns = max(2, int(page_width // 130)) if page_width else 12
            max_img_size = 130
        fig = create_bingo_scatter(all_df, columns=columns, dark_mode=True, mobile=mobile, mobile_image_size=max_img_size)
        if fig is None or not isinstance(fig, Figure):
            raise ValueError("Invalid figure returned")
        return fig, container_style, graph_style
    except Exception as e:
        fig = go.Figure()
        fig.update_layout(
            title=f"Error loading all bingo grid: {e}",
            paper_bgcolor="#181c20",
            plot_bgcolor="#181c20",
            font_color="#f3f6fa"
        )
        return fig, {"width": "100vw", "display": "flex", "justifyContent": "center", "paddingLeft": 0, "paddingRight": 0, "margin": "0"}, {"width": "60vw", "minWidth": 0, "margin": "2em 0 2em 0"}

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

# Info panel callback for grid
@app.callback(
    Output("minifig-info-panel", "children"),
    Output("minifig-modal-overlay", "style"),
    Output("minifig-modal-body", "children"),
    Input({"type": "minifig-img", "index": dash.ALL}, "n_clicks_timestamp"),
    State({"type": "minifig-img", "index": dash.ALL}, "id"),
    Input("minifig-modal-close", "n_clicks"),
    State("page-width-store", "data"),
    prevent_initial_call=True,
)
def show_minifig_info_and_modal(n_clicks_timestamps, ids, close_n_clicks, page_width):
    ctx = callback_context
    # If close button was clicked, hide modal
    if ctx.triggered and ctx.triggered[0]["prop_id"].startswith("minifig-modal-close"):
        return dash.no_update, {"display": "none"}, dash.no_update
    # Otherwise, show modal for the most recently clicked minifig
    if not n_clicks_timestamps or all(ts is None for ts in n_clicks_timestamps):
        return "Click an image to see details.", {"display": "none"}, dash.no_update
    idx = int(np.nanargmax([ts or 0 for ts in n_clicks_timestamps]))
    i = ids[idx]["index"]
    row = all_grid_df.iloc[i]

    # Determine if mobile
    mobile = page_width is not None and page_width < 700
    modal_width = "90vw" if mobile else "min(40vw, 98vw)"
    left_col_width = "90px" if mobile else "120px"
    img_max_width = "70px" if mobile else "110px"
    chart_line_width = 4 if mobile else 2
    chart_height = 180 if mobile else 220

    info_panel = html.Div([
        html.H3(row["Name of Clone"]),
        html.P(f"Price: ${row['Cost (BrickEconomy)']:.2f}"),
        html.Img(src=f"/assets/images/{row['SW ID']}.png", style={"width": "160px", "margin": "1em auto", "display": "block", "background": "#fff", "borderRadius": "10px"}),
    ])
    price_chart = dcc.Graph(
        figure=create_single_minifig_price_chart(row["SW ID"], line_width=chart_line_width, chart_height=chart_height),
        config={"displayModeBar": False},
        style={"height": f"{chart_height}px", "width": "100%", "marginTop": "0"}
    )
    modal_body = html.Div([
        html.Div([
            html.Img(src=f"/assets/images/{row['SW ID']}.png", style={"width": "80%", "maxWidth": img_max_width, "margin": "0 auto 0.7em auto", "display": "block", "background": "#fff", "borderRadius": "10px", "boxShadow": DARK_SHADOW}),
            html.H2(row["Name of Clone"], style={"marginTop": "0.3em", "fontSize": "0.95em", "lineHeight": "1.15"}),
            html.P(f"Current Price: ${row['Cost (BrickEconomy)']:.2f}", style={"fontSize": "0.85em", "marginTop": "0.3em"}),
        ], style={"flex": f"0 0 {left_col_width}", "minWidth": "0", "marginRight": "1.2em", "display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "flex-start"}),
        html.Div(price_chart, style={"flex": "1 1 0", "minWidth": "0", "maxWidth": "100%", "overflow": "hidden", "display": "flex", "alignItems": "center", "justifyContent": "center"}),
    ], style={"display": "flex", "flexDirection": "row", "alignItems": "flex-start", "justifyContent": "center", "width": "100%", "overflow": "hidden"})
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
    return info_panel, modal_style, modal_body

@app.callback(
    Output({"type": "minifig-overlay", "index": dash.ALL}, "style"),
    Input({"type": "minifig-img", "index": dash.ALL}, "n_clicks_timestamp"),
    State({"type": "minifig-overlay", "index": dash.ALL}, "style"),
    prevent_initial_call=True,
)
def show_minifig_overlay(n_clicks_timestamps, current_styles):
    print("Overlay callback fired!")
    print("n_clicks_timestamps:", n_clicks_timestamps)
    if not n_clicks_timestamps or all(ts is None for ts in n_clicks_timestamps):
        print("No image has been clicked yet.")
        # Hide all overlays
        return [dict(style, **{"display": "none"}) for style in current_styles]
    idx = int(np.nanargmax([ts or 0 for ts in n_clicks_timestamps]))
    print(f"Selected overlay index: {idx}")
    new_styles = []
    for i, style in enumerate(current_styles):
        if i == idx:
            # Show overlay for clicked image
            new_style = dict(style, **{"display": "flex"})
        else:
            new_style = dict(style, **{"display": "none"})
        new_styles.append(new_style)
    return new_styles

# Run
if __name__ == "__main__":
    app.run(debug=True)
