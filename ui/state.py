from typing import Optional

import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure

from database import Database


class PieChart:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.category = '*'
        self.update()

    def set_category(self, category: str) -> None:
        if category == self.category:
            return
        self.category = category
        self.update()
    
    def get_category(self) -> str:
        return self.category

    def update(self) -> None:
        with Database(self.db_path) as db:
            if self.category == "NULL":
                query = f"SELECT * FROM {db.table_name} WHERE category IS NULL"
            elif self.category == "*":
                query = f"SELECT * FROM {db.table_name}"
            else:
                query = (
                    f"SELECT * FROM {db.table_name} WHERE category={self.category}"
                )
            self.df = pd.read_sql_query(query, db.connection)
        self.fig = px.pie(self.df, values="amount", names="name")

    def get_df(self, category: Optional[str] = None) -> pd.DataFrame:
        if category is not None and category != self.category:
            self.set_category(category)
        return self.df

    def get_fig(self, category: Optional[str] = None) -> Figure:
        if category is not None and category != self.category:
            self.set_category(category)
        return self.fig
