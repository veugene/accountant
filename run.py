# Run this app with `python run.py` and
# visit http://127.0.0.1:8050/ in your web browser.


import base64
import datetime
import io

import dash
from dash import Dash, html, dash_table, dcc
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px

from database import Database, Transaction
from parsing import parse_csv


app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])


app.layout = html.Div(children=[
    html.Div(
        [
            dcc.Upload(
                id='upload_csv',
                children=html.Div(['Import CSV files.']),
                style={
                    'width': '50%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px'
                },
                # Allow multiple files to be uploaded
                multiple=True
            ),
            dbc.Button('Categorize unknown', id='button_categorize'),
            dbc.Modal(
                [
                    dbc.ModalHeader("HEADER"),
                    dbc.ModalBody("BODY OF MODAL"),
                    dbc.ModalFooter(
                        dbc.Button("CLOSE BUTTON", id="button_close_modal_categorize", className="ml-auto")
                    ),
                ],
                id="modal_categorize",
            ),
        ],
    ),
    html.Div(id='csv_output'),
])


@app.callback(
    Output('csv_output', 'children'),
    Input('upload_csv', 'contents')
)
def update_csv(contents_list):
    if contents_list is not None:
        df_list = [pd.DataFrame(columns=Transaction._fields)]
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
                df = pd.DataFrame.from_records(
                    transaction_list, columns=Transaction._fields
                )
                df_list.append(df)
        df = pd.concat(df_list)
        children = html.Div(
            [
                dash_table.DataTable(
                    df.to_dict('records'),
                    [{'name': i, 'id': i} for i in df.columns]
                ),
            ],
        )
        return children

@app.callback(
    Output("modal_categorize", "is_open"),
    [Input("button_categorize", "n_clicks"), Input("button_close_modal_categorize", "n_clicks")],
    [State("modal_categorize", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

if __name__ == '__main__':
    app.run_server(debug=True)
 
