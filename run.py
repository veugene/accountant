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
from ui.state import PieChart, Uncategorized


# Database path is hardcoded.
DB_PATH = '/home/eugene/.local/bank_records/db.sql'

# State is kept here.
state_pie_chart = PieChart(DB_PATH)
state_uncategorized = Uncategorized(DB_PATH)

# The app accesses and updates the state.
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.layout = html.Div(
    children=[
        html.Div(
            [
                dcc.Upload(
                    id='upload_csv',
                    children=html.Div(
                        ['Import CSV files (click or drag and drop)']
                    ),
                    style={
                        'width': '47%',
                        'height': '60px',
                        'lineHeight': '60px',
                        'borderWidth': '1px',
                        'borderStyle': 'dashed',
                        'borderRadius': '5px',
                        'textAlign': 'center',
                        'margin': '1%',
                        'float': 'left',
                    },
                    # Allow multiple files to be uploaded
                    multiple=True,
                ),
                html.Button(
                    'Categorize unknown',
                    id='button_categorize',
                    style={
                        'width': '47%',
                        'height': '60px',
                        'lineHeight': '60px',
                        'borderWidth': '2px',
                        'borderStyle': 'solid',
                        'borderRadius': '5px',
                        'textAlign': 'center',
                        'margin': '1%',
                        'float': 'left',
                    },
                ),
                dbc.Modal(
                    [
                        dbc.ModalHeader(html.B('Set a category')),
                        dbc.ModalBody(id='modal_categorize_body', children=''),
                        dbc.ModalFooter(
                            dbc.Button(
                                'CLOSE BUTTON',
                                id='button_close_modal_categorize',
                                className='ms-auto',
                            )
                        ),
                    ],
                    id='modal_categorize',
                    is_open=False,
                    size='xl',
                ),
            ],
            style={'height': '80px'},
        ),
        dcc.Graph(
            id='pie_chart',
            figure=state_pie_chart.fig,
        ),
    ],
)


@app.callback(Output('pie_chart', 'figure'), Input('upload_csv', 'contents'))
def update_csv(contents_list):
    if contents_list is None:
        return state_pie_chart.fig

    # Parse all transactions from csv files.
    transaction_import_list = []
    for contents in contents_list:
        content_type, content_string = contents.split(',')
        if content_type != 'data:text/csv;base64':
            continue
        try:
            decoded_string = io.StringIO(
                base64.b64decode(content_string).decode('utf-8')
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
    
    # Update figure.
    pie_chart.update()
    fig = pie_chart.get_fig()

    return fig


@app.callback(
    Output('modal_categorize', 'is_open'),
    Output('modal_categorize_body', 'children'),
    Input('button_categorize', 'n_clicks'),
    Input('button_close_modal_categorize', 'n_clicks'),
    State('modal_categorize', 'is_open'),
)
def toggle_modal_catogorize(n_clicks_open, n_clicks_close, is_open):
    set_is_open = is_open
    if n_clicks_open or n_clicks_close:
        set_is_open = not set_is_open
    if set_is_open:
        state_uncategorized.update()
    try:
        name = next(state_uncategorized)
    except StopIteration:
        body = 'No uncategorized transactions'
    else:
        body = html.Div(children=[
            html.I(name),
            dcc.RadioItems(
                state_uncategorized.get_categories(),
                labelStyle={'display': 'block'},
                id='category_radio_items',
            )
        ])
    return set_is_open, body


if __name__ == '__main__':
    app.run_server(debug=True)
