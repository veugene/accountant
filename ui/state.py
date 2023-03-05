import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure

from database import Database


class PieChart:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.category = None
        self.df = None
        self.fig = None
        self.get_df("*")
        self.get_fig("*")

    def get_df(self, category: str = "*") -> pd.DataFrame:
        if category == self.category and self.df is not None:
            # Return cached dataframe
            return self.df

        with Database(self.db_path) as db:
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

    def get_fig(self, category: str = "*") -> Figure:
        if category == self.category and self.fig is not None:
            # Returned cached fig
            return self.fig

        df = self.get_df(category)
        fig = px.pie(df, values="amount", names="name")
        self.fig = fig  # Cache
        return fig 
