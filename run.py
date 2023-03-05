# Run this app with `python run.py` and
# visit http://127.0.0.1:8050/ in your web browser.


import base64
import datetime
import io

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from dash import Dash, dash_table, dcc, html
from dash.dependencies import Input, Output, State

from database import Database, Transaction
from parsing import parse_csv

DB_PATH = "/home/eugene/.local/bank_records/db.sql"


with Database(DB_PATH) as db:
    df = pd.read_sql_query(f"SELECT * FROM {db.table_name}", db.connection)
    fig = px.pie(df, values="amount", names="name")


class PieChart:
    def __init__(self):
        self.category = None
        self.df = None
        self.fig = None
        self.get_df("*")
        self.get_fig("*")

    def get_df(self, category: str = "*"):
        if category == self.category:
            # Return cached dataframe
            return self.df

        with Database(DB_PATH) as db:
            if category == "NULL":
                query = f"SELECT * FROM {db.table_name} WHERE category IS NULL"
            elif category == "*":
                query = f"SELECT * FROM {db.table_name}"
            else:
                query = (
                    f"SELECT * FROM {db.table_name} WHERE category={category}"
                )
            df = pd.read_sql_query(query, db.connection)

        self.category = category
        self.df = df  # Cache
        return df

    def get_fig(self, category: str = "*"):
        if category == self.category:
            # Returned cached fig
            return self.fig

        df = self.get_df(category)
        fig = pix.pie(df, values="amount", names="name")
        self.fig = fig  # Cache
        return fig


app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])


app.layout = html.Div(
    children=[
        html.Div(
            [
                dcc.Upload(
                    id="upload_csv",
                    children=html.Div(
                        ["Import CSV files (click or drag and drop)"]
                    ),
                    style={
                        "width": "47%",
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
                        "width": "47%",
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
                        dbc.ModalHeader("HEADER"),
                        dbc.ModalBody("BODY OF MODAL"),
                        dbc.ModalFooter(
                            dbc.Button(
                                "CLOSE BUTTON",
                                id="button_close_modal_categorize",
                                className="ms-auto",
                            )
                        ),
                    ],
                    id="modal_categorize",
                ),
            ],
            style={"height": "80px"},
        ),
        html.Div(id="csv_output"),
        dcc.Graph(
            id="pie_chart",
            figure=fig,
        ),
    ],
)


@app.callback(Output("csv_output", "children"), Input("upload_csv", "contents"))
def update_csv(contents_list):
    if contents_list is not None:
        df_list = [pd.DataFrame(columns=Transaction._fields)]
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
                df = pd.DataFrame.from_records(
                    transaction_list, columns=Transaction._fields
                )
                df_list.append(df)
        df = pd.concat(df_list)
        children = html.Div(
            [
                dash_table.DataTable(
                    df.to_dict("records"),
                    [{"name": i, "id": i} for i in df.columns],
                ),
            ],
        )
        return children


@app.callback(
    Output("modal_categorize", "is_open"),
    [
        Input("button_categorize", "n_clicks"),
        Input("button_close_modal_categorize", "n_clicks"),
    ],
    [State("modal_categorize", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open


if __name__ == "__main__":
    app.run_server(debug=True)
