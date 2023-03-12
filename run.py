# Run this app with `python run.py` and
# visit http://127.0.0.1:8050/ in your web browser.


import base64
import io

import dash
import dash_bootstrap_components as dbc
from dash import Dash, dash_table, dcc, html, no_update
from dash.dependencies import Input, Output, State

from database import Database
from parsing import parse_csv
from state import Basic, Plot, Table, Uncategorized

# Database path is hardcoded.
DB_PATH = "/home/eugene/.local/bank_records/db.sql"

# State is kept here.
state_basic = Basic(DB_PATH)
state_table = Table(DB_PATH, table_id="transaction_table")
state_table_modal = Table(
    DB_PATH, table_id="query_table", group_by_name=True, row_selectable="multi"
)
state_plot = Plot(DB_PATH)
state_uncategorized = Uncategorized(DB_PATH)


# Modal dialogue uses state.
def get_next_modal_body():
    try:
        (
            name,
            similar_names,
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
                    "Ex: "
                    f"[{tx_example.date}, "
                    f"{tx_example.name}, "
                    f"{tx_example.amount}]",
                    html.Br(),
                    html.Br(),
                    f"Name {n_done} / {n_total}; {count} occurrences.",
                ]
            ),
        ]
        options = state_basic.get_categories()
        options = [c for c in options if c != "__UNKNOWN__"]
    return message, similar_names, options


# The app accesses and updates the state.
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.layout = html.Div(
    children=[
        html.Div(id="hidden_refresh1", style={"display": "none"}),
        html.Div(id="hidden_refresh2", style={"display": "none"}),
        html.Div(id="hidden_refresh3", style={"display": "none"}),
        html.Div(id="hidden_refresh4", style={"display": "none"}),
        html.Div(id="hidden_refresh5", style={"display": "none"}),
        html.Div(id="hidden_refresh6", style={"display": "none"}),
        html.Div(id="hidden_refresh7", style={"display": "none"}),
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
                    "Regex query",
                    id="button_query",
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
                                html.Div(
                                    [
                                        dcc.RadioItems(
                                            state_basic.get_categories(),
                                            labelStyle={"display": "block"},
                                            id="modal_categorize_radio_items",
                                        ),
                                        dcc.Input(
                                            type="text",
                                            debounce=True,
                                            id="modal_categorize_text",
                                        ),
                                    ],
                                    style={
                                        "width": "28%",
                                        "margin": "1%",
                                        "float": "left",
                                    },
                                ),
                                html.Div(
                                    [
                                        html.B("Select similar names:"),
                                        dcc.Checklist(
                                            id="checklist_similar_names",
                                            labelStyle={"display": "block"},
                                            options=[],
                                        ),
                                    ],
                                    style={
                                        "width": "68%",
                                        "margin": "1%",
                                        "float": "right",
                                    },
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
                dbc.Modal(
                    [
                        dbc.ModalHeader(
                            [
                                html.B("Categorization by regex name query"),
                            ]
                        ),
                        dbc.ModalBody(
                            id="modal_query_body",
                            children=[
                                html.Div(
                                    [
                                        html.B("Name query (regex)"),
                                        dcc.Input(
                                            type="text",
                                            debounce=True,
                                            id="modal_query_text",
                                            style={
                                                "overflow": "auto",
                                                "width": "100%",
                                            },
                                        ),
                                    ],
                                    style={
                                        "width": "32%",
                                        "margin": "1%",
                                        "float": "left",
                                    },
                                ),
                                html.Div(
                                    [
                                        html.Button(
                                            "Convert",
                                            id="button_convert",
                                            style={
                                                "width": "98%",
                                                "height": "98%",
                                                "lineHeight": "60px",
                                                "borderWidth": "2px",
                                                "borderStyle": "solid",
                                                "borderRadius": "5px",
                                                "textAlign": "center",
                                                "margin": "1%",
                                                "float": "center",
                                            },
                                        ),
                                    ],
                                    style={
                                        "width": "8%",
                                        "margin": "1%",
                                        "float": "right",
                                    },
                                ),
                                html.Div(
                                    [
                                        html.B("Create category"),
                                        dcc.Input(
                                            type="text",
                                            debounce=False,
                                            id="input_create_category",
                                            style={"width": "100%"},
                                        ),
                                    ],
                                    style={
                                        "width": "16%",
                                        "margin": "1%",
                                        "float": "right",
                                    },
                                ),
                                html.Div(
                                    [
                                        html.B("Target category"),
                                        dcc.Dropdown(
                                            id="modal_query_target_dropdown",
                                            options=state_basic.get_categories(),
                                            clearable=True,
                                            style={
                                                "width": "100%",
                                            },
                                        ),
                                    ],
                                    style={
                                        "width": "16%",
                                        "margin": "1%",
                                        "float": "right",
                                    },
                                ),
                                html.Div(
                                    [
                                        html.B("Source category"),
                                        dcc.Dropdown(
                                            id="modal_query_source_dropdown",
                                            value="*",
                                            options=["*"]
                                            + state_basic.get_categories(),
                                            clearable=True,
                                            style={
                                                "width": "100%",
                                            },
                                        ),
                                    ],
                                    style={
                                        "width": "16%",
                                        "margin": "1%",
                                        "float": "right",
                                    },
                                ),
                            ],
                        ),
                        dbc.ModalFooter(
                            [
                                dcc.Checklist(
                                    id="select_all_checklist",
                                    options=["Select all"],
                                    style={"float": "left"},
                                ),
                                html.Div(
                                    [state_table_modal.get_table()],
                                    style={
                                        "width": "100%",
                                        "float": "center",
                                    },
                                    id="modal_query_container",
                                ),
                            ],
                        ),
                    ],
                    id="modal_query",
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
                html.Div(
                    [
                        html.B("Date range"),
                        html.Br(),
                        dcc.DatePickerRange(
                            id="date_picker_range",
                            clearable=True,
                        ),
                    ],
                    style={"float": "left", "margin": "1%"},
                ),
                html.Div(
                    [
                        html.B("Year"),
                        html.Br(),
                        dcc.Dropdown(
                            id="year_dropdown",
                            options=state_basic.get_year_list(),
                            clearable=True,
                        ),
                    ],
                    style={"float": "left", "width": "10%", "margin": "1%"},
                ),
                html.Div(
                    [
                        html.B("Interval"),
                        html.Br(),
                        dcc.RadioItems(
                            ["Annual", "Monthly"],
                            value="Annual",
                            labelStyle={"display": "block"},
                            id="radio_interval",
                        ),
                    ],
                    style={"float": "left", "width": "10%", "margin": "1%"},
                ),
                html.Div(
                    [
                        html.B("Filter categories"),
                        html.Br(),
                        html.Button("Select", id="button_select_categories"),
                    ],
                    style={"float": "left", "width": "10%", "margin": "1%"},
                ),
                html.Div(
                    [
                        html.B("Extrapolate final year"),
                        html.Br(),
                        dcc.Checklist(
                            id="checklist_extrapolate_year",
                            options=["Extrapolate"],
                            style={"float": "left"},
                        ),
                    ],
                    style={"float": "left", "width": "10%", "margin": "1%"},
                ),
            ],
            style={"float": "left", "width": "100%", "margin": "1%"},
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(
                    [
                        html.B("Select categories to display"),
                    ]
                ),
                dbc.ModalBody(
                    dcc.Checklist(
                        id="select_all_categories_checklist",
                        options=["Select all"],
                        value=["Select all"],
                        style={"float": "left"},
                    ),
                ),
                dbc.ModalFooter(
                    [
                        html.Div(
                            dcc.Checklist(
                                options=state_basic.get_categories(),
                                value=state_basic.get_categories(),
                                labelStyle={"display": "block"},
                                id="modal_checklist_category_selection",
                            ),
                            style={
                                "width": "100%",
                                "float": "center",
                            },
                        ),
                    ],
                ),
            ],
            id="modal_select_categories",
            is_open=False,
            size="sm",
        ),
        html.Br(),
        html.Div(
            [
                html.Div(
                    html.B("No category selected"),
                    id="transaction_table_category",
                ),
                html.Div(
                    # dash_table.DataTable(
                    # id="transaction_table",
                    # columns=[{"name": "empty", "id": "empty"}],
                    # ),
                    state_table.get_table(),
                    id="transaction_table_container",
                ),
            ],
            style={"width": "100%", "float": "left", "margin": "1%"},
        ),
    ],
)


@app.callback(
    Output("year_dropdown", "options"),
    Output("hidden_refresh6", "children"),
    Input("upload_csv", "contents"),
    prevent_initial_call=True,
)
def upload_csv_callback(contents_list):
    if contents_list is None:
        return no_update, None

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

    # Get the list of years in the DB.
    return state_basic.get_year_list(), None


@app.callback(
    Output("pie_chart", "figure"),
    Output("line_plot", "figure"),
    Output("transaction_table_container", "children"),
    Output("modal_checklist_category_selection", "options"),
    Input("modal_categorize", "is_open"),  # Wait for callback
    Input("modal_query", "is_open"),  # Wait for callback
    Input("modal_select_categories", "is_open"),  # Wait for callback
    State("modal_checklist_category_selection", "value"),
    Input("date_picker_range", "start_date"),  # Wait for callback
    Input("date_picker_range", "end_date"),  # Wait for callback
    Input("year_dropdown", "value"),  # Wait for callback
    Input("transaction_table_category", "children"),  # Wait for callback
    Input("year_dropdown", "options"),  # Wait for upload csv callback
    Input("hidden_refresh2", "children"),  # Wait for callback
    Input("hidden_refresh1", "children"),  # Wait for callback
    Input("hidden_refresh6", "children"),  # Wait for callback
    Input("hidden_refresh7", "children"),  # Wait for callback
    prevent_initial_call=True,
)
def refresh_all_callback(
    categorize_modal_open,
    query_modal_open,
    select_modal_open,
    category_selection,
    *args,
    **kwargs,
):
    trigger_id = dash.callback_context.triggered[0]["prop_id"].split(".")[0]

    if trigger_id == "modal_categorize" and categorize_modal_open is True:
        # Update only when the modal is closed, not when it is opened.
        return no_update, no_update, no_update, no_update

    if trigger_id == "modal_query" and query_modal_open is True:
        # Update only when the modal is closed, not when it is opened.
        return no_update, no_update, no_update, no_update

    if trigger_id == "modal-select_categories" and select_modal_open is True:
        # Update only when the modal is closed, not when it is opened.
        return no_update, no_update, no_update, no_update

    # Update all states.
    state_basic.update()
    state_table.update()
    state_table_modal.update()
    state_plot.update()
    state_uncategorized.update()

    # Update category selection.
    state_plot.set_category_list(category_selection)

    return (
        state_plot.get_fig_pie(),
        state_plot.get_fig_line(),
        [state_table.get_table()],
        state_basic.get_categories(),
    )


@app.callback(
    Output("modal_categorize", "is_open"),
    Output("modal_categorize_message", "children"),
    Output("checklist_similar_names", "options"),
    Output("modal_categorize_radio_items", "options"),
    Output("modal_categorize_radio_items", "value"),
    Output("modal_categorize_text", "value"),
    Input("button_categorize", "n_clicks"),
    Input("button_ignore_modal_categorize", "n_clicks"),
    Input("button_undo_modal_categorize", "n_clicks"),
    Input("button_skip_modal_categorize", "n_clicks"),
    Input("modal_categorize_radio_items", "value"),
    Input("modal_categorize_text", "value"),
    State("modal_categorize", "is_open"),
    State("checklist_similar_names", "value"),
    prevent_initial_call=True,
)
def categorize_callback(
    n_clicks_open,
    n_clicks_ignore,
    n_clicks_undo,
    n_clicks_skip,
    category,
    new_category,
    is_open,
    selected_similar_names,
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
        state_uncategorized.set_category(None, selected_similar_names)

    # Undo previous action.
    elif trigger_id == "button_undo_modal_categorize":
        state_uncategorized.undo()

    # Skip button pressed. Skip to next iteration by doing nothing on this one.
    elif trigger_id == "button_skip_modal_categorize":
        state_uncategorized.skip()

    # If a radio item is selected within the modal dialog.
    elif trigger_id == "modal_categorize_radio_items":
        state_uncategorized.set_category(category, selected_similar_names)

    # Entered a new category.
    elif trigger_id == "modal_categorize_text":
        if new_category != "":
            # Avoid empty string category. Do nothing.
            state_uncategorized.set_category(
                new_category, selected_similar_names
            )

    # Initial null trigger on app start.
    elif len(trigger_id) == 0:
        pass

    # This should never happen.
    else:
        raise Exception(f"Unexpected callback trigger: {trigger_id}")

    # Update the message and radio items options.
    message, similar_names, options = get_next_modal_body()

    return set_is_open, message, similar_names, options, None, ""


@app.callback(
    Output("modal_query", "is_open"),
    Input("button_query", "n_clicks"),
    State("modal_query", "is_open"),
    prevent_initial_call=True,
)
def query_callback(
    n_clicks_open,
    is_open,
):
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    set_is_open = is_open

    # If the modal dialog is toggled.
    if trigger_id == "button_query":
        if n_clicks_open:
            set_is_open = not set_is_open

    return set_is_open


@app.callback(
    Output("transaction_table_category", "children"),
    Input(component_id="pie_chart", component_property="clickData"),
    Input("date_picker_range", "start_date"),
    Input("date_picker_range", "end_date"),
    Input("year_dropdown", "value"),
    prevent_initial_call=True,
)
def click_pie_chart_callback(click_data, start_date, end_date, year):
    trigger_id = dash.callback_context.triggered[0]["prop_id"].split(".")[0]
    if trigger_id == "pie_chart":
        category = click_data["points"][0]["label"]
        state_table.set_category(category)
    if trigger_id == "date_picker_range":
        state_table.set_date_range(start_date, end_date)
    if trigger_id == "year_dropdown":
        state_table.set_year(year)
    return html.B(state_table.category)


@app.callback(
    Output("hidden_refresh1", "children"),
    Input("radio_interval", "value"),
    prevent_initial_call=True,
)
def radio_interval_callback(value):
    if value == "Annual":
        state_plot.set_interval("YS")
    elif value == "Monthly":
        state_plot.set_interval("MS")


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
    Output("hidden_refresh2", "children"),
    Input("transaction_table", "data"),
    prevent_initial_call=True,
)
def transaction_table_change_callback(data):
    if data is None:
        return
    diff = state_table.diff(data)
    if diff is not None:
        with Database(DB_PATH) as db:
            db.set_name_category(
                name=diff["name"],
                category=diff["category"],
            )
        state_table.update()
    return


@app.callback(
    Output("hidden_refresh3", "children"),
    Input("modal_query_text", "value"),
    Input("modal_query_source_dropdown", "value"),
    prevent_initial_call=True,
)
def query_table_callback(query, source_category):
    trigger_id = dash.callback_context.triggered[0]["prop_id"].split(".")[0]
    if trigger_id == "modal_query_text":
        if query is None:
            query = ""
        state_table_modal.set_regex_query(query)
    if trigger_id == "modal_query_source_dropdown":
        state_table_modal.set_category(source_category)
    return


@app.callback(
    Output("query_table", "selected_rows"),
    Input("select_all_checklist", "value"),
    State("query_table", "data"),
    prevent_initial_call=True,
)
def select_all_callback(select_all, table_data):
    selected_rows = []
    if select_all:
        selected_rows = list(range(len(table_data)))
    return selected_rows


@app.callback(
    Output("hidden_refresh4", "children"),
    Input("query_table", "data"),
    prevent_initial_call=True,
)
def query_table_change_callback(data):
    if data is None:
        return
    diff = state_table_modal.diff(data)
    if diff is not None:
        with Database(DB_PATH) as db:
            db.set_name_category(
                name=diff["name"],
                category=diff["category"],
            )
        state_table_modal.update()
    return


@app.callback(
    Output("hidden_refresh5", "children"),
    Input("button_convert", "n_clicks"),
    State("modal_query_target_dropdown", "value"),
    State("input_create_category", "value"),
    State("query_table", "selected_rows"),
    State("query_table", "data"),
    prevent_initial_call=True,
)
def convert_button_callback(
    n_clicks, category_dropdown, category_create, selected_rows, rows
):
    if len(selected_rows) == 0:
        return
    if category_create is not None and category_create != "":
        category = category_create
    else:
        category = category_dropdown
    for idx in selected_rows:
        with Database(DB_PATH) as db:
            db.set_name_category(
                name=rows[idx]["name"],
                category=category,
            )
    return


@app.callback(
    Output("modal_query_target_dropdown", "value"),
    Output("input_create_category", "value"),
    Input("modal_query_target_dropdown", "value"),
    Input("input_create_category", "value"),
    prevent_initial_call=True,
)
def clear_dropdown_or_input_field(dropdown_value, input_value):
    trigger_id = dash.callback_context.triggered[0]["prop_id"].split(".")[0]
    if trigger_id == "modal_query_target_dropdown":
        return no_update, ""
    if trigger_id == "input_create_category":
        return None, no_update


@app.callback(
    Output("modal_query_container", "children"),
    Output("modal_query_target_dropdown", "options"),
    Output("modal_query_source_dropdown", "options"),
    Output("select_all_checklist", "value"),
    Input("hidden_refresh3", "children"),
    Input("hidden_refresh4", "children"),
    Input("hidden_refresh5", "children"),
    prevent_initial_call=True,
)
def refresh_query_table(*args, **kwargs):
    state_table_modal.update()
    state_uncategorized.update()
    categories = state_basic.get_categories()
    return (
        [state_table_modal.get_table()],
        categories,
        ["*"] + categories,
        [],
    )


@app.callback(
    Output("modal_select_categories", "is_open"),
    Input("button_select_categories", "n_clicks"),
    State("modal_categorize", "is_open"),
    prevent_initial_call=True,
)
def categorize_callback(
    n_clicks_open,
    is_open,
):
    if n_clicks_open:
        return not is_open
    return is_open


@app.callback(
    Output("modal_checklist_category_selection", "value"),
    Input("select_all_categories_checklist", "value"),
    State("modal_checklist_category_selection", "options"),
    prevent_initial_call=True,
)
def select_all_callback(select_all, options):
    if select_all:
        return options
    return []


@app.callback(
    Output("hidden_refresh7", "children"),
    Input("checklist_extrapolate_year", "value"),
)
def extrapolate_year_callback(extrapolate_value):
    if extrapolate_value == ["Extrapolate"]:
        state_plot.set_extrapolate(True)
    else:
        state_plot.set_extrapolate(False)


if __name__ == "__main__":
    # Make a backup.
    with Database(DB_PATH) as db:
        db.backup()

    # Run app.
    app.run_server(debug=True)
