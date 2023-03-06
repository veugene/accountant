# Run this app with `python run.py` and
# visit http://127.0.0.1:8050/ in your web browser.


import base64
import datetime
import io

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Dash, dash_table, dcc, html
from dash.dependencies import Input, Output, State

from database import Database, Transaction
from parsing import parse_csv
from ui.state import Plot, Uncategorized

# Database path is hardcoded.
DB_PATH = "/home/eugene/.local/bank_records/db.sql"

# State is kept here.
state_plot = Plot(DB_PATH)
state_uncategorized = Uncategorized(DB_PATH)


# Modal dialogue uses state.
def get_modal_body():
    try:
        name = next(state_uncategorized)
    except StopIteration:
        message = "No uncategorized transactions"
        options = []
    else:
        message = html.I(name)
        options = state_uncategorized.get_categories()
    return message, options


# The app accesses and updates the state.
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.layout = html.Div(
    children=[
        html.Div(id="dummy_upload_csv_output", style={"display": "none"}),
        html.Div(
            id="dummy_button_categorize_output", style={"display": "none"}
        ),
        html.Div(id="dummy_button_plot_output", style={"display": "none"}),
        html.Div(
            [
                dcc.Upload(
                    id="upload_csv",
                    children=html.Div(
                        ["Import CSV files (click or drag and drop)"]
                    ),
                    style={
                        "width": "31%",
                        "height": "60px",
                        "lineHeight": "60px",
                        "borderWidth": "1px",
                        "borderStyle": "dashed",
                        "borderRadius": "5px",
                        "textAlign": "center",
                        "margin": "1%",
                        "float": "left",
                    },
                    # Allow multiple files to be uploaded
                    multiple=True,
                ),
                html.Button(
                    "Categorize unknown",
                    id="button_categorize",
                    style={
                        "width": "31%",
                        "height": "60px",
                        "lineHeight": "60px",
                        "borderWidth": "2px",
                        "borderStyle": "solid",
                        "borderRadius": "5px",
                        "textAlign": "center",
                        "margin": "1%",
                        "float": "left",
                    },
                ),
                html.Button(
                    "Plot",
                    id="button_plot",
                    style={
                        "width": "31%",
                        "height": "60px",
                        "lineHeight": "60px",
                        "borderWidth": "2px",
                        "borderStyle": "solid",
                        "borderRadius": "5px",
                        "textAlign": "center",
                        "margin": "1%",
                        "float": "left",
                    },
                ),
                dbc.Modal(
                    [
                        dbc.ModalHeader(html.B("Set a category")),
                        dbc.ModalBody(
                            id="modal_categorize_body",
                            children=[
                                html.Div("", id="modal_categorize_message"),
                                dcc.RadioItems(
                                    [],
                                    labelStyle={"display": "block"},
                                    id="modal_categorize_radio_items",
                                ),
                            ],
                        ),
                        dbc.ModalFooter(
                            dbc.Button(
                                "Close",
                                id="button_close_modal_categorize",
                                className="ms-auto",
                            )
                        ),
                    ],
                    id="modal_categorize",
                    is_open=False,
                    size="xl",
                ),
            ],
            style={"height": "80px"},
        ),
        dcc.Graph(
            id="pie_chart",
            figure=state_plot.get_fig_pie(),
            style={"float": "left"},
        ),
        dcc.Graph(
            id="line_plot",
            figure=state_plot.get_fig_line(),
            style={"float": "left"},
        ),
        html.Div(
            style={
                "width": "100%",
                "float": "left",
            }
        ),
        html.Div(
            [
                dcc.DatePickerRange(
                    clearable=True,
                ),
                dcc.Dropdown(
                    ["2020", "2021", "2022"],
                    clearable=True,
                ),
            ],
            style={"float": "left", "margin": "1%"},
        ),
        html.Div(
            id="category_contents",
            style={"width": "31%", "float": "left", "margin": "1%"},
        ),
    ],
)


@app.callback(
    Output("dummy_upload_csv_output", "children"),
    Input("upload_csv", "contents"),
)
def upload_csv_callback(contents_list):
    if contents_list is None:
        return None

    # Parse all transactions from csv files.
    transaction_import_list = []
    for contents in contents_list:
        content_type, content_string = contents.split(",")
        if content_type != "data:text/csv;base64":
            continue
        try:
            decoded_string = io.StringIO(
                base64.b64decode(content_string).decode("utf-8")
            )
            transaction_list = parse_csv(decoded_string)
        except Exception as e:
            print(e)
            pass
        else:
            transaction_import_list.extend(transaction_list)

    # Add transactions to database. This skips transactions that already
    # exist in the database.
    with Database(DB_PATH) as db:
        db.add_transactions(transaction_import_list)

    return None


@app.callback(
    Output("pie_chart", "figure"),
    Input("button_plot", "n_clicks"),
)
def button_plot_callback(n_clicks):
    # Update figure.
    if n_clicks is not None:
        state_plot.update()
    return state_plot.get_fig_pie()


@app.callback(
    Output("modal_categorize", "is_open"),
    Output("modal_categorize_message", "children"),
    Output("modal_categorize_radio_items", "options"),
    Output("modal_categorize_radio_items", "value"),
    Input("button_categorize", "n_clicks"),
    Input("button_close_modal_categorize", "n_clicks"),
    State("modal_categorize", "is_open"),
    Input("modal_categorize_radio_items", "value"),
)
def button_categorize_callback(
    n_clicks_open, n_clicks_close, is_open, category
):
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    set_is_open = is_open
    state_uncategorized.update()

    # If the modal dialog is toggled.
    if trigger_id in ["button_categorize", "button_close_modal_categorize"]:
        if n_clicks_open or n_clicks_close:
            set_is_open = not set_is_open

    # If a radio item is selected within the modal dialog.
    elif trigger_id == "modal_categorize_radio_items":
        state_uncategorized.set_category(category)
        state_uncategorized.update()

    # Initial null trigger on app start.
    elif len(trigger_id) == 0:
        pass

    # This should never happen.
    else:
        raise Exception(f"Unexpected callback trigger: {trigger_id}")

    # Update the message and radio items options.
    message, options = get_modal_body()

    return set_is_open, message, options, None


@app.callback(
    Output("category_contents", "children"),
    Input(component_id="pie_chart", component_property="clickData"),
)
def click_pie_chart_callback(click_data):
    if click_data is None:
        return []

    category = click_data["points"][0]["label"]
    if category == "null":
        category_query = "category IS NULL"
    else:
        category_query = f'category="{category}"'
    with Database(DB_PATH) as db:
        df = pd.read_sql_query(
            f"SELECT * FROM {db.table_name} WHERE {category_query} "
            "ORDER BY date DESC",
            db.connection,
        )
    table = dash_table.DataTable(
        df.to_dict("records"), [{"name": i, "id": i} for i in df.columns]
    )
    return [table]


if __name__ == "__main__":
    app.run_server(debug=True)
