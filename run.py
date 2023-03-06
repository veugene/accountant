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
from ui.state import DiffTable, Plot, Uncategorized

# Database path is hardcoded.
DB_PATH = "/home/eugene/.local/bank_records/db.sql"

# State is kept here.
state_table = DiffTable()
state_plot = Plot(DB_PATH)
state_uncategorized = Uncategorized(DB_PATH)


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
        html.Div(id="dummy_upload_csv_output", style={"display": "none"}),
        html.Div(
            id="dummy_button_categorize_output", style={"display": "none"}
        ),
        html.Div(id="dummy_button_plot_output", style={"display": "none"}),
        html.Div(id="dummy_checklist_output", style={"display": "none"}),
        html.Div(id="dummy_picker_output", style={"display": "none"}),
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
    Output("line_plot", "figure"),
    Input("button_plot", "n_clicks"),
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

    # Update the message and radio items options.
    message, options = get_next_modal_body()

    return set_is_open, message, options, None, ""


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

    # Create a table where the 'category' column is editable and has a dropdown
    # menu to select the category.
    state_table.reset()  # Creating new table. Clear table cache.
    dropdown_options = [
        {"label": i, "value": i} for i in state_uncategorized.get_categories()
    ]
    columns = []
    for c in df.columns:
        if c == "category":
            columns.append(
                {
                    "name": c,
                    "id": c,
                    "editable": True,
                    "presentation": "dropdown",
                }
            )
        else:
            columns.append({"name": c, "id": c})
    table = dash_table.DataTable(
        id="editable_transaction_table",
        data=df.to_dict("records"),
        columns=columns,
        dropdown={"category": {"options": dropdown_options}},
        css=[
            {
                "selector": ".Select-menu-outer",
                "rule": "display: block !important",
            }
        ],  # github.com/plotly/dash-table/issues/221
    )
    return [table]


@app.callback(
    Output("dummy_checklist_output", "children"),
    Input("checklist_annual", "value"),
)
def checklist_annual_callback(value):
    if value is not None:
        if len(value):
            state_plot.set_interval("YS")
        else:
            state_plot.set_interval("MS")
    return None


@app.callback(
    Output("dummy_picker_output", "children"),
    Input("date_picker_range", "start_date"),
    Input("date_picker_range", "end_date"),
)
def date_picker_range_callback(start_date, end_date):
    state_plot.set_date_range(start_date, end_date)
    return None


@app.callback(
    Output("date_picker_range", "start_date"),
    Output("date_picker_range", "end_date"),
    Input("year_dropdown", "value"),
)
def date_picker_range_callback(value):
    if value is not None:
        start_date = f"{value}-01-01"
        end_date = f"{value}-12-31"
    else:
        start_date = end_date = None
    state_plot.set_date_range(start_date, end_date)
    return start_date, end_date


@app.callback(
    Output("dummy_table_output", "children"),
    Input("editable_transaction_table", "data"),
)
def transaction_table_category_change_callback(data):
    diff = state_table.diff(data)
    if diff is not None:
        with Database(DB_PATH) as db:
            db.set_name_category(
                name=diff["name"],
                category=diff["category"],
            )
    return None


if __name__ == "__main__":
    app.run_server(debug=True)
