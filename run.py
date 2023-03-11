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
from ui.state import Plot, Table, Uncategorized

# Database path is hardcoded.
DB_PATH = "/home/eugene/.local/bank_records/db.sql"

# State is kept here.
state_table = Table(DB_PATH)
state_plot = Plot(DB_PATH)
state_uncategorized = Uncategorized(DB_PATH)
state_table.set_category_options(state_uncategorized.get_categories())


# Modal dialogue uses state.
def get_next_modal_body():
    try:
        (
            name,
            count,
            tx_example,
            n_done,
            n_total,
        ) = state_uncategorized.get_name_to_process()
    except StopIteration:
        message = "No uncategorized transactions"
        options = []
    else:
        message = [
            html.P(
                [
                    html.I(name),
                    html.Br(),
                    html.Br(),
                    f"Name {n_done} / {n_total}; {count} occurrences. "
                    f"Example transaction amount: {tx_example.amount}",
                ]
            ),
        ]
        options = state_uncategorized.get_categories()
    return message, options


# The app accesses and updates the state.
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.layout = html.Div(
    children=[
        html.Div(id="dummy_checklist_output", style={"display": "none"}),
        html.Div(id="dummy_table_output", style={"display": "none"}),
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
                                dcc.Input(
                                    type="text",
                                    debounce=True,
                                    id="modal_categorize_text",
                                ),
                            ],
                        ),
                        dbc.ModalFooter(
                            html.Div(
                                [
                                    dbc.Button(
                                        "Skip",
                                        id="button_skip_modal_categorize",
                                        className="ms-auto",
                                        style={
                                            "margin": "1%",
                                            "float": "right",
                                        },
                                    ),
                                    dbc.Button(
                                        "Undo",
                                        id="button_undo_modal_categorize",
                                        className="ms-auto",
                                        style={
                                            "margin": "1%",
                                            "float": "right",
                                        },
                                    ),
                                    dbc.Button(
                                        "Ignore",
                                        id="button_ignore_modal_categorize",
                                        className="ms-auto",
                                        color="danger",
                                        style={
                                            "margin": "1%",
                                            "float": "right",
                                        },
                                    ),
                                ],
                                style={"width": "100%"},
                            ),
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
            style={"float": "right"},
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
                    id="date_picker_range",
                    clearable=True,
                ),
                dcc.Dropdown(
                    id="year_dropdown",
                    options=state_plot.get_year_list(),
                    clearable=True,
                ),
                dcc.Checklist(id="checklist_annual", options=["Annual"]),
            ],
            style={"float": "left", "margin": "1%"},
        ),
        html.Div(
            id="category_contents",
            children=[
                html.B("No category selected", id="transaction_table_category"),
                dash_table.DataTable(
                    id="editable_transaction_table",
                    columns=[{"name": "empty", "id": "empty"}],
                )
            ],
            style={"width": "31%", "float": "left", "margin": "1%"},
        ),
    ],
)


@app.callback(
    Output("year_dropdown", "options"),
    Input("upload_csv", "contents"),
    State("year_dropdown", "options"),
    prevent_initial_call=True,
)
def upload_csv_callback(contents_list, year_options):
    if contents_list is None:
        return year_options

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

    # Update year options in dropdown.
    state_plot.update()
    year_options = state_plot.get_year_list()

    return year_options


@app.callback(
    Output("pie_chart", "figure"),
    Output("line_plot", "figure"),
    Input("button_plot", "n_clicks"),
    prevent_initial_call=True,
)
def button_plot_callback(n_clicks):
    # Update figure.
    if n_clicks is not None:
        state_plot.update()
    return state_plot.get_fig_pie(), state_plot.get_fig_line()


@app.callback(
    Output("modal_categorize", "is_open"),
    Output("modal_categorize_message", "children"),
    Output("modal_categorize_radio_items", "options"),
    Output("modal_categorize_radio_items", "value"),
    Output("modal_categorize_text", "value"),
    Input("button_categorize", "n_clicks"),
    Input("button_ignore_modal_categorize", "n_clicks"),
    Input("button_undo_modal_categorize", "n_clicks"),
    Input("button_skip_modal_categorize", "n_clicks"),
    State("modal_categorize", "is_open"),
    Input("modal_categorize_radio_items", "value"),
    Input("modal_categorize_text", "value"),
    prevent_initial_call=True,
)
def button_categorize_callback(
    n_clicks_open,
    n_clicks_ignore,
    n_clicks_undo,
    n_clicks_skip,
    is_open,
    category,
    new_category,
):
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    set_is_open = is_open

    # If the modal dialog is toggled.
    if trigger_id == "button_categorize":
        if n_clicks_open:
            set_is_open = not set_is_open

    # Ignore button pressed. Set a None category.
    elif trigger_id == "button_ignore_modal_categorize":
        state_uncategorized.set_category(None)

    # Undo previous action.
    elif trigger_id == "button_undo_modal_categorize":
        state_uncategorized.undo()

    # Skip button pressed. Skip to next iteration by doing nothing on this one.
    elif trigger_id == "button_skip_modal_categorize":
        state_uncategorized.skip()

    # If a radio item is selected within the modal dialog.
    elif trigger_id == "modal_categorize_radio_items":
        state_uncategorized.set_category(category)

    # Entered a new category.
    elif trigger_id == "modal_categorize_text":
        if new_category != "":
            # Avoid empty string category. Do nothing.
            state_uncategorized.set_category(new_category)

    # Initial null trigger on app start.
    elif len(trigger_id) == 0:
        pass

    # This should never happen.
    else:
        raise Exception(f"Unexpected callback trigger: {trigger_id}")

    # When closing this modal, update category list for table.
    if set_is_open == False:
        state_table.set_category_options(state_uncategorized.get_categories())

    # Update the message and radio items options.
    message, options = get_next_modal_body()

    return set_is_open, message, options, None, ""


@app.callback(
    Output("category_contents", "children"),
    Input(component_id="pie_chart", component_property="clickData"),
    Input("date_picker_range", "start_date"),
    Input("date_picker_range", "end_date"),
    Input("year_dropdown", "value"),
    prevent_initial_call=True,
)
def click_pie_chart_callback(click_data, start_date, end_date, year):
    trigger_id = dash.callback_context.triggered[0]["prop_id"].split(".")[0]
    if trigger_id == "pie_chart":
        if click_data is None:
            state_table.reset()
        else:
            category = click_data["points"][0]["label"]
            state_table.set_category(category)
    if trigger_id == "date_picker_range":
        state_table.set_date_range(start_date, end_date)
    if trigger_id == "year_dropdown":
        state_table.set_year(year)
    return state_table.get_table()


@app.callback(
    Output("dummy_checklist_output", "children"),
    Input("checklist_annual", "value"),
    prevent_initial_call=True,
)
def checklist_annual_callback(value):
    if value is not None:
        if len(value):
            state_plot.set_interval("YS")
        else:
            state_plot.set_interval("MS")
    return None


@app.callback(
    Output("date_picker_range", "start_date"),
    Output("date_picker_range", "end_date"),
    Output("year_dropdown", "value"),
    Input("date_picker_range", "start_date"),
    Input("date_picker_range", "end_date"),
    Input("year_dropdown", "value"),
    prevent_initial_call=True,
)
def date_picker_range_callback(start_date, end_date, year):
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if trigger_id == "date_picker_range":
        state_plot.set_date_range(start_date, end_date)
        year = None
    if trigger_id == "year_dropdown":
        state_plot.set_year(year)
    return state_plot.start_date, state_plot.end_date, year


@app.callback(
    Output("dummy_table_output", "children"),
    Input("editable_transaction_table", "data"),
    prevent_initial_call=True,
)
def transaction_table_category_change_callback(data):
    if data is None:
        return
    diff = state_table.diff(data)
    if diff is not None:
        with Database(DB_PATH) as db:
            db.set_name_category(
                name=diff["name"],
                category=diff["category"],
            )
    return


if __name__ == "__main__":
    # Make a backup.
    with Database(DB_PATH) as db:
        db.backup()

    # Run app.
    app.run_server(debug=True)
