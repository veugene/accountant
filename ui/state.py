from typing import List, Optional

import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure

from database import Database


class Plot:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.category = '*'
        self.interval = 'M'
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
            if self.category == 'NULL':
                query = f'SELECT * FROM {db.table_name} WHERE category IS NULL'
            elif self.category == '*':
                query = f'SELECT * FROM {db.table_name}'
            else:
                query = (
                    f'SELECT * FROM {db.table_name} WHERE category={self.category}'
                )
            self.df = pd.read_sql_query(query, db.connection)
            self.df['date'] = pd.to_datetime(self.df.date, format='%Y-%m-%d')
        self.fig_pie = px.pie(self.df, values='amount', names='category')
        self.fig_line = self.make_line(self.interval)
    
    def make_line(self, interval: str = 'M'):
        assert interval in ['M', 'Y']
        self.interval = interval
        
        # Group amounts by category, interpolate index by time interval, and
        # within each interval, sum all the amounts of each category.
        df = self.df.fillna(
            'null'
        ).set_index(
            'date'
        ).groupby(
            [pd.Grouper(freq='M'), 'category']
        ).agg(
            {'amount': 'sum'}
        ).unstack().fillna(0).resample(
            self.interval
        ).sum()
        
        # Simplify MultiIndex columns (amount, <category>) to just category names.
        df.columns = df.columns.get_level_values(1)
        return px.line(df, x=df.index, y=df.columns)

    def get_df(self, category: Optional[str] = None) -> pd.DataFrame:
        if category is not None and category != self.category:
            self.set_category(category)
        return self.df

    def get_fig_pie(self, category: Optional[str] = None) -> Figure:
        if category is not None and category != self.category:
            self.set_category(category)
        return self.fig_pie
    
    def get_fig_line(self, category: Optional[str] = None) -> Figure:
        if category is not None and category != self.category:
            self.set_category(category)
        return self.fig_line


class Uncategorized:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.update()
    
    def update(self):
        with Database(self.db_path) as db:
            self.uncategorized_names = db.get_uncategorized_names()
            self.category_list = db.get_all_categories()
            self._iter = iter(self.uncategorized_names)
    
    def get_names(self) -> List[str]:
        return self.uncategorized_names

    def get_categories(self) -> List[str]:
        return self.category_list
    
    def __next__(self):
        self._current_name = next(self._iter)
        return self._current_name
    
    def set_category(self, category: str):
        with Database(self.db_path) as db:
            db.set_name_category(self._current_name, category)
        self.update()
