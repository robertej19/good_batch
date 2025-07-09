import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def create_price_trend_chart(csv_path="all_minifig_value_sales.csv", clones_csv="clones.csv", y_scale="linear", dark_mode=False):
    # Load datasets
    df = pd.read_csv(csv_path, parse_dates=["Date"])
    clones = pd.read_csv(clones_csv)
    # Build SW_ID to Name mapping
    swid_to_name = dict(zip(clones["SW ID"], clones["Name of Clone"]))

    # Filter to only minifigures where Owned is False
    not_owned_clones = clones[clones["Owned"] == False]
    not_owned_ids = not_owned_clones["SW ID"].dropna().unique()

    # Filter the main df to only those SW_IDs
    df_not_owned = df[df['SW_ID'].isin(not_owned_ids)].copy()
    # Add minifigure name and image path columns for hover
    df_not_owned["Minifig Name"] = df_not_owned["SW_ID"].map(swid_to_name)
    df_not_owned["Image Path"] = "/assets/images/" + df_not_owned["SW_ID"] + ".png"

    # Create line plot of Q1 (25th percentile) price over time, y-axis scale set by y_scale
    fig = px.line(
        df_not_owned,
        x="Date",
        y="Q1",
        color="SW_ID",
        labels={"Q1": "Value ($)", "Date": "Date", "SW_ID": "Minifig ID"},
        title="Minifigure Value Over Time (Q1) - Not Owned",
        hover_data={"Minifig Name": True, "Image Path": True, "SW_ID": False, "Date": False, "Q1": False}
    )

    # Show minifigure name and image on hover
    fig.update_traces(
        hovertemplate=(
            "Minifigure: %{customdata[0]}<br>"
            "<img src='%{customdata[1]}' style='width:80px;'><extra></extra>"
        )
    )
    # Set y-axis to the specified scale
    fig.update_yaxes(type=y_scale)

    if dark_mode:
        fig.update_layout(
            plot_bgcolor="#181c20",
            paper_bgcolor="#181c20",
            font_color="#f3f6fa",
            xaxis=dict(gridcolor="#23272b", zerolinecolor="#23272b"),
            yaxis=dict(gridcolor="#23272b", zerolinecolor="#23272b"),
        )

    fig.update_layout(
        hovermode="closest",  # Per-trace selection
        xaxis_title="Date",
        yaxis_title=f"Price (USD, {y_scale} scale)",
        legend_title="Minifigure",
        font={"size": 18},
    )

    return fig

def create_value_pie_chart(df, title="Percentage of Total Value by Minifigure", dark_mode=False):
    # Only include minifigs with a value > 0
    df = df[df["Cost (BrickEconomy)"] > 0].copy()
    # Assign color: white if owned, dark red if not owned
    color_map = {True: "#fff", False: "#8b0000"}
    df["Color"] = df["Owned"].map(color_map)
    fig = px.pie(
        df,
        names="Name of Clone",
        values="Cost (BrickEconomy)",
        title=title,
        hover_data=["SW ID"],
        hole=0.3,
        color="Name of Clone",
        color_discrete_map={row["Name of Clone"]: row["Color"] for _, row in df.iterrows()}
    )
    # Only show info on hover (no static labels)
    fig.update_traces(textinfo='none', textfont_size=16)
    fig.update_layout(
        showlegend=False,
        font={"size": 18},
        margin={"l": 20, "r": 20, "t": 60, "b": 20}
    )
    if dark_mode:
        fig.update_layout(
            plot_bgcolor="#181c20",
            paper_bgcolor="#181c20",
            font_color="#f3f6fa",
        )
    return fig

def create_bingo_scatter(df, columns=8, dark_mode=True, mobile=False, mobile_image_size=65):
    # Sort by value descending
    df = df.sort_values("Cost (BrickEconomy)", ascending=False).reset_index(drop=True)
    # Prepare grid positions
    n = len(df)
    rows = (n + columns - 1) // columns
    x = [(i % columns) for i in range(n)]
    y = [-(i // columns) for i in range(n)]  # negative so first row is at top
    # Color and hover info
    marker_colors = ["#000000" if owned else "#8b0000" for owned in df["Owned"]]
    hover_texts = [
        f"<b>{smart_truncate_name(row['Name of Clone'])}</b><br>${row['Cost (BrickEconomy)']:,.2f}" for _, row in df.iterrows()
    ]
    # Marker and image size for mobile/desktop
    if mobile:
        marker_size = mobile_image_size
        image_size = mobile_image_size / 130  # 130 is the desktop base size
    else:
        marker_size = 120
        image_size = 0.9
    # Scatter for colored backgrounds
    fig = go.Figure(go.Scatter(
        x=x,
        y=y,
        mode="markers",
        marker=dict(
            size=marker_size,
            color=marker_colors,
            symbol="square",
            line=dict(width=0),
            opacity=1,
        ),
        hoverinfo="text",
        hovertext=hover_texts,
        showlegend=False,
    ))
    # Overlay images (no SVG, just PNG path)
    for i, row in enumerate(df.itertuples()):
        img_url = f"/assets/images/{row._4}.png"
        fig.add_layout_image(
            dict(
                source=img_url,
                xref="x", yref="y",
                x=x[i], y=y[i],
                sizex=image_size, sizey=image_size,
                xanchor="center", yanchor="middle",
                layer="above"
            )
        )
    fig.update_xaxes(
        visible=False,
        range=[-0.5, columns-0.5],
        fixedrange=True
    )
    fig.update_yaxes(
        visible=False,
        range=[-rows+0.5, 0.5],
        fixedrange=True,
        scaleanchor="x",
        scaleratio=1
    )
    fig.update_layout(
        plot_bgcolor="#181c20" if dark_mode else "#fff",
        paper_bgcolor="#181c20" if dark_mode else "#fff",
        margin=dict(l=0, r=0, t=0, b=0),
        height=rows*mobile_image_size+40 if mobile else rows*130+40,
        width=columns*mobile_image_size+40 if mobile else columns*130+40,
        hoverlabel=dict(bgcolor="#23272b" if dark_mode else "#fff", font_size=18, font_color="#f3f6fa" if dark_mode else "#222"),
    )
    return fig

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
