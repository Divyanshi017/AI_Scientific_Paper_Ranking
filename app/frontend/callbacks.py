from dash import Input, Output, State, ALL, ctx, html, no_update
import plotly.graph_objects as go

from app.frontend.components import (
    paper_card,
    empty_state,
    list_item,
    TEAL,
    MUTED,
    INK
)
from app.services.tavily_search import search_papers
from app.services.paper_ranking import rank_papers
from app.services.rag import answer_from_papers
from app.storage import memory_store


def _empty_chart():
    fig = go.Figure()
    fig.update_layout(
        template="plotly_white",
        height=300,
        margin=dict(l=20, r=20, t=10, b=20),
        xaxis_title="",
        yaxis_title="Views",
    )
    return fig


def _views_lookup() -> dict:
    """Map paper_id -> {views_by_me, views_by_others} from in-memory store."""
    lookup = {}
    for paper in memory_store.get_papers():
        pid = paper.get("paper_id")
        viewers = paper.get("viewers", {}) or {}
        me = memory_store.current_viewer_id()
        lookup[pid] = {
            "views_by_me": viewers.get(me, 0),
            "views_by_others": sum(v for k, v in viewers.items() if k != me),
        }
    return lookup


def _enrich_with_views(papers: list[dict]) -> list[dict]:
    lookup = _views_lookup()
    for paper in papers:
        pid = paper.get("paper_id")
        data = lookup.get(pid, {"views_by_me": 0, "views_by_others": 0})
        paper["views_by_me"] = data["views_by_me"]
        paper["views_by_others"] = data["views_by_others"]
        paper["views"] = data["views_by_me"] + data["views_by_others"]
    return papers


def register_callbacks(dash_app):
    @dash_app.callback(
        Output("dashboard-panel", "style"),
        Output("search-panel", "style"),
        Output("chat-panel", "style"),
        Output("history-panel", "style"),
        Input("main-tabs", "value"),
    )
    def switch_tab(tab):
        visible = {"paddingTop": "0"}
        hidden = {"display": "none", "paddingTop": "0"}
        return (
            visible if tab == "dashboard" else hidden,
            visible if tab == "search" else hidden,
            visible if tab == "chat" else hidden,
            visible if tab == "history" else hidden,
        )

    @dash_app.callback(
        Output("search-status", "children"),
        Output("top-five-results", "children"),
        Output("all-paper-results", "children"),
        Input("search-button", "n_clicks"),
        State("search-question", "value"),
        prevent_initial_call=True,
    )
    def run_search(n_clicks, question):
        question = (question or "").strip()
        if len(question) < 5:
            return (
                "Please enter a research question with at least 5 characters.",
                [],
                [],
            )

        try:
            papers = search_papers(question)
            ranked = rank_papers(question, papers)
            ranked = _enrich_with_views(ranked)
            memory_store.save_search(question, ranked)

            top_cards = [paper_card(paper) for paper in ranked[:5]]
            all_cards = [
                html.Div(
                    [
                        html.Div(f"#{paper['rank']} · {paper['title']}", style={"fontWeight": "600"}),
                        html.Div(
                            f"Score: {paper['ranking_score']:.3f} · {paper.get('domain', '')}",
                            style={"fontSize": "12px", "color": MUTED, "marginTop": "5px"},
                        ),
                    ],
                    style={"padding": "10px 0", "borderBottom": "1px solid #EDF0EE"},
                )
                for paper in ranked
            ]
            status = (
                f"Retrieved {len(ranked)} unique academic-paper candidates. "
                f"Showing the five highest-ranked results."
            )
            return status, top_cards, all_cards
        except Exception as error:
            return f"Search failed: {error}", [], []

    @dash_app.callback(
        Output("chat-status", "children"),
        Output("chat-answer", "children"),
        Output("chat-sources", "children"),
        Input("chat-button", "n_clicks"),
        State("chat-question", "value"),
        prevent_initial_call=True,
    )
    def run_chat(n_clicks, question):
        question = (question or "").strip()
        if len(question) < 3:
            return "Enter a question first.", "", ""
        try:
            result = answer_from_papers(question)
            source_items = [
                html.Li(
                    html.A(
                        source["title"],
                        href=source["url"],
                        target="_blank",
                        rel="noopener noreferrer",
                        style={"color": TEAL, "textDecoration": "none", "fontWeight": "600"},
                    )
                )
                for source in result["sources"]
            ]
            return (
                f"Generated with {result['model']} · {result['retrieved_passages']} passages retrieved.",
                result["answer"] + "\n\n" + result["content_note"],
                html.Div(
                    [html.H4("Sources", style={"fontSize": "15px", "fontWeight": "700", "marginBottom": "6px"}), html.Ul(source_items)]
                ),
            )
        except Exception as error:
            return f"Could not generate an answer: {error}", "", ""

    @dash_app.callback(
        Output("dashboard-metrics", "children"),
        Output("views-chart", "figure"),
        Output("popular-papers", "children"),
        Input("dashboard-refresh", "n_intervals"),
        Input("main-tabs", "value"),
    )
    def refresh_dashboard(_interval, _tab):
        data = memory_store.analytics_summary()

        # Remove the count cards; the dashboard is chart-focused.
        metrics = html.Div()

        # Bar chart: each paper's total views; hover shows title + breakdown.
        chart = data.get("paper_chart", [])[:20]
        fig = go.Figure()
        if chart:
            fig.add_trace(
                go.Bar(
                    x=[p["title"] for p in chart],
                    y=[p["views_by_others"] + p["views_by_me"] for p in chart],
                    marker_color=TEAL,
                    hovertemplate=(
                        "<b>%{x}</b><br>"
                        "Views by other people: %{customdata[0]}<br>"
                        "Views by you: %{customdata[1]}<br>"
                        "Distinct readers: %{customdata[2]}<extra></extra>"
                    ),
                    customdata=[
                        [p["views_by_others"], p["views_by_me"], p["distinct_readers"]]
                        for p in chart
                    ],
                    name="Views",
                )
            )
        fig.update_layout(
            template="plotly_white",
            height=420,
            margin=dict(l=40, r=20, t=10, b=140),
            yaxis_title="Total views",
            xaxis_title="Paper",
            showlegend=False,
            xaxis={"tickangle": -35, "tickfont": {"size": 10}},
        )

        if data["top_papers"]:
            popular = [
                list_item(
                    [
                        html.Div(paper["title"], style={"fontSize": "13px", "fontWeight": "700", "color": INK}),
                        html.Div(
                            f"{paper['views_by_others']} read by others · {paper['views_by_me']} by you",
                            style={"fontSize": "12px", "color": MUTED, "marginTop": "4px"},
                        ),
                    ]
                )
                for paper in data["top_papers"][:5]
            ]
        else:
            popular = empty_state(
                "No papers read by others yet.",
                "Open a paper from Search & Ranking to start tracking.",
            )

        return metrics, fig, popular

    @dash_app.callback(
        Output("history-list", "children"),
        Input("dashboard-refresh", "n_intervals"),
        Input("main-tabs", "value"),
    )
    def refresh_history(_interval, _tab):
        history = memory_store.get_search_history()
        if not history:
            return empty_state("No searches in this running session yet.")

        return [
            list_item(
                [
                    html.Div(item["question"], style={"fontWeight": "700", "color": INK}),
                    html.Div(
                        f"{item['paper_count']} papers · {item['created_at']}",
                        style={"fontSize": "12px", "color": MUTED, "marginTop": "6px"},
                    ),
                ]
            )
            for item in history
        ]

    @dash_app.callback(
        Output("dashboard-refresh", "disabled"),
        Input({"type": "paper-open", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def track_paper_open(clicks):
        triggered = ctx.triggered_id
        if not isinstance(triggered, dict):
            return no_update
        paper_id = triggered.get("index")
        if paper_id:
            try:
                memory_store.record_view(paper_id)
            except KeyError:
                pass
        return no_update
