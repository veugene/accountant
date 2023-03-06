from typing import List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure

from database import Database, Transaction


class Plot:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.category = "*"
        self.interval = "MS"
        self.start_date = None
        self.end_date = None
        self.update()

    def set_category(self, category: str) -> None:
        if category == self.category:
            return
        self.category = category
        self.update()

    def set_interval(self, interval: str) -> None:
        assert interval in ["MS", "YS"]
        self.interval = interval
        self.fig_line = self.make_line()

    def set_date_range(self, start_date: str, end_date: str):
        self.start_date = start_date
        self.end_date = end_date
        self.update()

    def get_category(self) -> str:
        return self.category

    def update(self) -> None:
        with Database(self.db_path) as db:
            if self.category == "*":
                query = (
                    f"SELECT * FROM {db.table_name} WHERE category IS NOT NULL"
                )
            else:
                query = (
                    f"SELECT * FROM {db.table_name} "
                    f"WHERE category={self.category}"
                )
            if self.start_date is not None:
                query += f" AND date >= '{self.start_date}'"
            if self.end_date is not None:
                query += f" AND date <= '{self.end_date}'"
            self.df = pd.read_sql_query(query, db.connection)
            self.df["date"] = pd.to_datetime(self.df.date, format="%Y-%m-%d")
        self.fig_pie = px.pie(self.df, values="amount", names="category")
        self.fig_line = self.make_line()

    def make_line(self) -> Figure:
        assert self.interval in ["MS", "YS"]

        # Empty figure.
        if len(self.df) == 0:
            return px.line(self.df, x="date", y=[])

        # Group amounts by category, interpolate index by time interval, and
        # within each interval, sum all the amounts of each category.
        df = (
            self.df.fillna("null")
            .set_index("date")
            .groupby([pd.Grouper(freq=self.interval), "category"])
            .agg({"amount": "sum"})
            .unstack()
            .fillna(0)
            .resample(self.interval)
            .sum()
        )

        # Simplify MultiIndex columns (amount, <category>) to just category names.
        df.columns = df.columns.get_level_values(1)
        fig = px.line(df, x=df.index, y=df.columns)
        if self.interval == "MS":
            fig.update_layout(
                xaxis={"tickangle": 90, "dtick": "M1", "tickformat": "%b %Y"}
            )
        elif self.interval == "YS":
            fig.update_layout(
                xaxis={"tickangle": 90, "dtick": "M12", "tickformat": "%Y"}
            )
        else:
            AssertionError(f"interval={self.interval} not in ['M', 'Y']")
        return fig

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

    def get_year_list(self) -> List[int]:
        return list(self.df.groupby(self.df.date.dt.year)["date"].max().index)


class Uncategorized:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._current_name = None
        self._history = {}
        self.reset()

    def update(self):
        with Database(self.db_path) as db:
            self.uncategorized_names = db.get_uncategorized_names()
            self.category_list = db.get_all_categories()
            self._idx = 0

    def reset(self):
        self._current_name = None
        self._history = {}
        self.update()

    def get_names(self) -> List[str]:
        return self.uncategorized_names

    def get_categories(self) -> List[str]:
        category_list = [c for c in self.category_list if c != "__UNKNOWN__"]
        return category_list

    def get_name_to_process(self) -> Tuple[str, Transaction]:
        if self._idx >= len(self.uncategorized_names):
            raise StopIteration
        self._current_name = self.uncategorized_names[self._idx]
        while self._current_name in self._history:
            self._idx += 1
            self._current_name = self.uncategorized_names[self._idx]

        # Get one example of a matching transaction.
        with Database(self.db_path) as db:
            print(
                "DEBUG",
                f"SELECT * FROM {db.table_name} "
                f"WHERE name='{self._current_name}' LIMIT 1",
            )
            result = db.cursor.execute(
                f"SELECT * FROM {db.table_name} WHERE name=? LIMIT 1",
                (self._current_name,),
            ).fetchall()
            tx_example = Transaction(*result[0])

        return self._current_name, tx_example

    def set_category(self, category: str):
        with Database(self.db_path) as db:
            db.set_name_category(self._current_name, category)
        self._history[self._current_name] = category
        self._idx += 1
        self.update()

    def skip(self):
        self._history[self._current_name] = "__UNKNOWN__"
        self._idx += 1

    def undo(self):
        if len(self._history) == 0:
            return

        previous_name = list(self._history.keys())[-1]
        category = self._history.pop(previous_name)
        if self._idx > 0:
            self._idx -= 1
        self._current_name = previous_name
        with Database(self.db_path) as db:
            db.set_name_category(self._current_name, "__UNKNOWN__")
        self.update()
