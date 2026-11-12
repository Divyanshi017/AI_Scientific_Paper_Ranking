from dash import dcc, html
from app.frontend.components import TEAL, CORAL, INK, MUTED, PAPER, BORDER, RADIUS, SHADOW, FONT

PAGE_STYLE = {
    "background": PAPER,
    "minHeight": "100vh",
    "padding": "28px",
    "fontFamily": FONT,
    "color": INK,
}

HEADER_STYLE = {
    "background": "linear-gradient(120deg, #0F766E, #155E75)",
    "color": "white",
    "padding": "32px",
    "borderRadius": "24px",
    "boxShadow": "0 12px 30px rgba(15, 118, 110, 0.18)",
    "marginBottom": "26px",
}

PANEL_STYLE = {"paddingTop": "0"}

TABS_STYLE = {"marginTop": "0"}


def dashboard_panel():
    return html.Div(
        [
            html.Div(id="dashboard-metrics"),

            html.Div(
                [
                    html.Div(
                        ["Paper views by other people"],
                        style={"fontSize": "16px", "fontWeight": "700", "color": INK, "marginBottom": "10px"},
                    ),
                    dcc.Graph(id="views-chart", config={"displayModeBar": False}),
                ],
                style={"width": "100%"},
            ),
            html.Div(
                [
                    html.Div(
                        ["Most read by other people"],
                        style={"fontSize": "16px", "fontWeight": "700", "color": INK, "marginBottom": "10px"},
                    ),
                    html.Div(id="popular-papers"),
                ],
                style={"width": "100%", "marginTop": "18px"},
            ),
            html.P(
                "Views are counted when a paper source link is opened. "
                "The chart shows papers read by other people (not your own views). "
                "Hover a bar to see the paper title. Analytics are temporary because this version uses in-memory storage.",
                style={"fontSize": "12px", "color": MUTED, "marginTop": "14px"},
            ),
        ],
        id="dashboard-panel",
        style=PANEL_STYLE,
    )


def search_panel():
    return html.Div(
        [
            html.H2("Find research papers", style={"fontSize": "22px", "margin": "0 0 6px 0", "fontWeight": "700"}),
            html.P(
                "Enter a focused research question. Tavily searches the web for academic-paper candidates.",
                style={"color": MUTED, "fontSize": "13px", "margin": "0 0 16px 0"},
            ),
            dcc.Textarea(
                id="search-question",
                placeholder="Example: How does retrieval-augmented generation reduce hallucinations in large language models?",
                style={
                    "width": "100%",
                    "height": "100px",
                    "padding": "14px",
                    "borderRadius": "12px",
                    "border": f"1px solid {BORDER}",
                    "fontSize": "14px",
                    "fontFamily": FONT,
                    "resize": "vertical",
                },
            ),
            html.Button(
                "Search and rank papers",
                id="search-button",
                n_clicks=0,
                style={
                    "background": TEAL,
                    "color": "white",
                    "border": "0",
                    "borderRadius": "10px",
                    "padding": "12px 20px",
                    "fontWeight": "700",
                    "marginTop": "14px",
                    "cursor": "pointer",
                    "fontSize": "14px",
                },
            ),
            html.Div(id="search-status", style={"marginTop": "14px", "color": MUTED, "fontSize": "13px"}),
            html.H3("Top 5 ranked papers", style={"marginTop": "26px", "fontSize": "17px", "fontWeight": "700"}),
            html.Div(id="top-five-results"),
            html.Details(
                [
                    html.Summary("View all retrieved candidates", style={"cursor": "pointer", "fontWeight": "700"}),
                    html.Div(id="all-paper-results", style={"marginTop": "14px"}),
                ],
                style={"marginTop": "12px"},
            ),
        ],
        id="search-panel",
        style={"display": "none", **PANEL_STYLE},
    )


def chat_panel():
    return html.Div(
        [
            html.H2("Ask the research assistant", style={"fontSize": "22px", "margin": "0 0 6px 0", "fontWeight": "700"}),
            html.P(
                "Answers are grounded in passages extracted from the top five papers in your latest search.",
                style={"fontSize": "13px", "color": MUTED, "margin": "0 0 16px 0"},
            ),
            dcc.Textarea(
                id="chat-question",
                placeholder="What methods do these papers use to evaluate RAG?",
                style={
                    "width": "100%",
                    "height": "85px",
                    "padding": "14px",
                    "borderRadius": "12px",
                    "border": f"1px solid {BORDER}",
                    "fontSize": "14px",
                    "fontFamily": FONT,
                    "resize": "vertical",
                },
            ),
            html.Button(
                "Ask question",
                id="chat-button",
                n_clicks=0,
                style={
                    "background": CORAL,
                    "color": "white",
                    "border": "0",
                    "borderRadius": "10px",
                    "padding": "12px 20px",
                    "fontWeight": "700",
                    "marginTop": "14px",
                    "cursor": "pointer",
                    "fontSize": "14px",
                },
            ),
            html.Div(id="chat-status", style={"marginTop": "16px"}),
            html.Div(id="chat-answer", style={
                "background": "white",
                "padding": "20px",
                "borderRadius": "14px",
                "marginTop": "12px",
                "lineHeight": "1.7",
                "whiteSpace": "pre-wrap",
                "border": f"1px solid {BORDER}",
            }),
            html.Div(id="chat-sources", style={"marginTop": "12px"}),
        ],
        id="chat-panel",
        style={"display": "none", **PANEL_STYLE},
    )


def history_panel():
    return html.Div(
        [
            html.H2("Search history", style={"fontSize": "22px", "margin": "0 0 8px 0", "fontWeight": "700"}),
            html.P("Previous searches held in this running application instance.", style={"color": MUTED}),
            html.Div(id="history-list"),
        ],
        id="history-panel",
        style={"display": "none", **PANEL_STYLE},
    )


def build_layout():
    return html.Div(
        [
            html.Div(
                [
                    html.Div("RESEARCH COMPASS", style={
                        "fontSize": "11px",
                        "fontWeight": "800",
                        "letterSpacing": "2px",
                        "opacity": "0.9",
                        "marginBottom": "8px",
                    }),
                    html.H1("Research Paper Assistant", style={"fontSize": "30px", "margin": "4px 0", "fontWeight": "800"}),
                    html.P(
                        "Discover relevant research. Compare evidence. Ask better questions.",
                        style={"fontSize": "14px", "margin": "0", "opacity": "0.9"},
                    ),
                ],
                style=HEADER_STYLE,
            ),
            dcc.Tabs(
                id="main-tabs",
                value="dashboard",
                children=[
                    dcc.Tab(label="Dashboard", value="dashboard"),
                    dcc.Tab(label="Search & Ranking", value="search"),
                    dcc.Tab(label="RAG Assistant", value="chat"),
                    dcc.Tab(label="Search History", value="history"),
                ],
                style=TABS_STYLE,
            ),
            dashboard_panel(),
            search_panel(),
            chat_panel(),
            history_panel(),
            dcc.Interval(id="dashboard-refresh", interval=15000, n_intervals=0),
        ],
        style=PAGE_STYLE,
    )
