from dash import html

# ---------------------------------------------------------------- design tokens
INK = "#1F2937"
SURFACE = "#FFFFFF"
PAPER = "#F7F5F0"
BORDER = "#E7E5E0"
MUTED = "#6B7280"
TEAL = "#0F766E"
TEAL_LIGHT = "#DDF4EF"
CORAL = "#B45309"
CORAL_LIGHT = "#FFEDD5"
SLATE = "#4B5563"
SHADOW = "0 4px 14px rgba(17, 24, 39, 0.06)"
RADIUS = "16px"
FONT = "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"


def _style(**kw):
    return kw


def metric_card(label: str, value, note: str = "", accent: str = TEAL):
    return html.Div(
        [
            html.Div(label, style={
                "fontSize": "12px",
                "fontWeight": "600",
                "color": MUTED,
                "letterSpacing": "0.04em",
                "textTransform": "uppercase",
                "marginBottom": "8px",
            }),
            html.Div(str(value), style={
                "fontSize": "34px",
                "fontWeight": "800",
                "color": INK,
                "marginTop": "4px",
                "letterSpacing": "-0.02em",
            }),
            html.Div(note, style={
                "fontSize": "11px",
                "color": SLATE,
                "marginTop": "6px",
            }),
        ],
        style={
            "background": SURFACE,
            "padding": "20px 18px",
            "borderRadius": RADIUS,
            "border": f"1px solid {BORDER}",
            "boxShadow": SHADOW,
            "minWidth": "150px",
            "display": "flex",
            "flexDirection": "column",
            "gap": "4px",
        },
    )


def stat_row(items: list[dict]):
    """A row of metric cards."""
    return html.Div(
        [
            metric_card(
                item.get("label", ""),
                item.get("value", 0),
                item.get("note", ""),
                item.get("accent", TEAL),
            )
            for item in items
        ],
        style={
            "display": "grid",
            "gridTemplateColumns": "repeat(auto-fit, minmax(150px, 1fr))",
            "gap": "14px",
            "width": "100%",
        },
    )


def section_title(text: str, subtitle: str = ""):
    return html.Div(
        [
            html.Div(text, style={
                "fontSize": "17px",
                "fontWeight": "700",
                "color": INK,
                "marginBottom": "4px",
            }),
            html.Div(subtitle, style={
                "fontSize": "12px",
                "color": MUTED,
            }) if subtitle else None,
        ],
        style={"marginBottom": "14px"},
    )


def panel(children, style=None):
    return html.Div(
        children,
        style={
            "background": SURFACE,
            "borderRadius": RADIUS,
            "border": f"1px solid {BORDER}",
            "boxShadow": SHADOW,
            "padding": "24px",
            **(style or {}),
        },
    )


def paper_card(paper: dict):
    score = round(float(paper.get("ranking_score", 0)) * 100, 1)
    authors = paper.get("authors") or "Authors not identified"
    year = paper.get("year") or "Year not identified"
    abstract = paper.get("abstract") or "Tavily did not return an abstract/snippet."
    paper_id = paper.get("paper_id", "")
    views_by_me = paper.get("views_by_me", 0)
    views_by_others = paper.get("views_by_others", paper.get("views", 0) - views_by_me)

    return html.Div(
        [
            html.Div(
                [
                    html.Span(f"#{paper.get('rank', '-')}", style={
                        "background": TEAL_LIGHT,
                        "color": TEAL,
                        "padding": "4px 10px",
                        "borderRadius": "20px",
                        "fontWeight": "700",
                        "fontSize": "11px",
                    }),
                    html.Span(f"Relevance {score}%", style={
                        "background": CORAL_LIGHT,
                        "color": CORAL,
                        "padding": "4px 10px",
                        "borderRadius": "20px",
                        "fontWeight": "700",
                        "fontSize": "11px",
                        "marginLeft": "8px",
                    }),
                ],
                style={"marginBottom": "12px", "display": "flex", "gap": "8px", "flexWrap": "wrap"},
            ),
            html.H3(paper.get("title", "Untitled paper"), style={
                "fontSize": "17px",
                "lineHeight": "1.4",
                "margin": "0 0 8px",
                "color": INK,
                "fontWeight": "700",
            }),
            html.Div(f"{authors}  ·  {year}  ·  {paper.get('domain', '')}", style={
                "fontSize": "12px",
                "color": MUTED,
                "marginBottom": "10px",
            }),
            html.P(abstract[:650], style={
                "fontSize": "13px",
                "lineHeight": "1.6",
                "color": SLATE,
                "margin": "0 0 14px",
            }),
            html.Div(
                [
                    html.A(
                        "Open source ↗",
                        href=paper.get("url", "#"),
                        target="_blank",
                        rel="noopener noreferrer",
                        id={"type": "paper-open", "index": paper_id},
                        n_clicks=0,
                        style={
                            "color": TEAL,
                            "fontWeight": "700",
                            "fontSize": "12px",
                            "textDecoration": "none",
                            "padding": "6px 12px",
                            "border": f"1px solid {TEAL}",
                            "borderRadius": "8px",
                            "display": "inline-flex",
                            "alignItems": "center",
                            "gap": "6px",
                        },
                    ),
                    html.Span(
                        f"{views_by_others} read by others · {views_by_me} by you",
                        style={"color": MUTED, "fontSize": "11px", "marginLeft": "10px"},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "gap": "10px", "flexWrap": "wrap"},
            ),
        ],
        style={
            "background": SURFACE,
            "padding": "20px",
            "borderRadius": RADIUS,
            "border": f"1px solid {BORDER}",
            "marginBottom": "14px",
        },
    )


def empty_state(message: str, hint: str = ""):
    return html.Div(
        [
            html.P(message, style={"fontSize": "14px", "color": MUTED, "margin": "0"}),
            html.P(hint, style={"fontSize": "12px", "color": SLATE, "marginTop": "4px"}) if hint else None,
        ],
        style={"textAlign": "center", "padding": "30px", "color": MUTED},
    )


def list_item(children, style=None):
    return html.Div(
        children,
        style={
            "background": SURFACE,
            "borderRadius": "12px",
            "border": f"1px solid {BORDER}",
            "padding": "16px",
            "marginBottom": "10px",
            **(style or {}),
        },
    )
