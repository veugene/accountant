import re
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
from dash import dash_table
from fuzzywuzzy import fuzz
from plotly.graph_objects import Figure

from database import Database, Transaction


def compute_similarity(df):
    return df.apply(lambda col: [fuzz.ratio(col.name, x) for x in col.index])


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

    def set_year(self, year: str):
        if year is not None:
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"
        else:
            start_date = end_date = None
        self.set_date_range(start_date, end_date)

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
        self.compute_name_similarity_matrix()
        self.update()

    def compute_name_similarity_matrix(self):
        with Database(self.db_path) as db:
            db_hash = db.hash()
            all_names = db.cursor.execute(
                f"SELECT name FROM {db.table_name}"
            ).fetchall()
        name_mapping = {
            re.sub(r"[\W\d]+", "", name[0].lower()): name[0]
            for name in all_names
        }

        # Load from cache if exists, else compute and save cache.
        cache_dir = Path(self.db_path).parent.joinpath(".similarity_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir.joinpath(f"{db_hash}")
        if cache_path.exists():
            ct = pd.read_csv(cache_path).set_index("key")
            print("Loaded name similarities from cache")
        else:
            df = pd.DataFrame(
                zip(name_mapping.keys(), name_mapping.values()),
                columns=["key", "name"],
            )
            ct = pd.crosstab(df["key"], df["key"])
            ct_split = np.array_split(ct, cpu_count())
            with Pool(cpu_count()) as pool:
                print("Computing name similarities ...")
                ct = pd.concat(pool.map(compute_similarity, ct_split))
                print("DONE")
            ct.to_csv(cache_path)

        self.name_similarity = ct
        self.name_mapping = name_mapping

    def get_categories(self) -> List[str]:
        return sorted(self.category_list)

    def get_name_to_process(self) -> Tuple[str, int, Transaction, int, int]:
        if self._idx >= len(self.uncategorized_names):
            self.reset()
            raise StopIteration
        self._current_name = self.uncategorized_names[self._idx]
        while self._current_name[0] in self._history:
            self._idx += 1
            self._current_name = self.uncategorized_names[self._idx]

        # Get one example of a matching transaction.
        name, count = self._current_name
        with Database(self.db_path) as db:
            result = db.cursor.execute(
                f"SELECT * FROM {db.table_name} WHERE name=? LIMIT 1",
                (name,),
            ).fetchall()
            tx_example = Transaction(*result[0])

        # Count progress.
        n_done = len(self._history)
        n_total = len(self.uncategorized_names)

        # Identify similar names.
        similar_names = self.get_similar_names(name)

        return name, similar_names, count, tx_example, n_done, n_total

    def get_similar_names(self, name: str):
        key = re.sub(r"[\W\d]+", "", name.lower())
        df = self.name_similarity[key].sort_values(ascending=False)
        similar_keys = list(df[df > 75].index)
        similar_names = [self.name_mapping[key] for key in similar_keys]
        return similar_names[1:]  # Skip self match

    def set_category(
        self,
        category: str,
        similar_names: Optional[List[str]] = None,
    ):
        if similar_names is None:
            similar_names = []
        name, count = self._current_name
        with Database(self.db_path) as db:
            db.set_name_category(name, category)
            for s_name in similar_names:
                db.set_name_category(s_name, category)
        self._history[name] = (category, count, similar_names)
        self._idx += 1
        self.update()

    def skip(self):
        name, count = self._current_name
        self._history[name] = ("__UNKNOWN__", count, [])
        self._idx += 1

    def undo(self):
        if len(self._history) == 0:
            return

        previous_name = list(self._history.keys())[-1]
        category, count, similar_names = self._history.pop(previous_name)
        if self._idx > 0:
            self._idx -= 1
        self._current_name = (previous_name, count)
        with Database(self.db_path) as db:
            db.set_name_category(previous_name, "__UNKNOWN__")
            for s_name in similar_names:
                db.set_name_category(s_name, "__UNKNOWN__")
        self.update()


class Table:
    def __init__(
        self,
        db_path: str,
        table_id: str = "table",
        group_by_name: bool = False,
        row_selectable: str = "multi",
    ):
        self.db_path = db_path
        self.table_id = table_id
        self.group_by_name = group_by_name
        self.row_selectable = row_selectable
        self.start_date = None
        self.end_date = None
        self.records = None
        self.table = None
        self.reset()

    def reset(self):
        self.category = "*"
        self.regex_query = ""
        self.update()

    def set_category(self, category: str) -> None:
        if category == self.category:
            return
        self.category = category
        self.update()

    def set_date_range(self, start_date: str, end_date: str):
        self.start_date = start_date
        self.end_date = end_date
        self.update()

    def set_year(self, year: str):
        if year is not None:
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"
        else:
            start_date = end_date = None
        self.set_date_range(start_date, end_date)

    def update(self):
        # Query
        if self.category == "*":
            category_query = "category IS NOT NULL"
        elif self.category is None:
            category_query = "category IS NULL"
        else:
            category_query = f'category="{self.category}"'
        if self.start_date is not None:
            category_query += f" AND date >= '{self.start_date}'"
        if self.end_date is not None:
            category_query += f" AND date <= '{self.end_date}'"
        with Database(self.db_path) as db:
            category_list = db.get_all_categories()
            if self.group_by_name:
                db.connection.create_function(
                    "REGEXP", 2, lambda x, y: 1 if re.search(x, y) else 0
                )
                df = pd.read_sql_query(
                    f"SELECT name, COUNT(*), category FROM {db.table_name} "
                    f"WHERE {category_query} "
                    f"AND name REGEXP '{self.regex_query}' "
                    "GROUP BY name ORDER BY COUNT(*) DESC",
                    db.connection,
                )
            else:
                df = pd.read_sql_query(
                    f"SELECT * FROM {db.table_name} WHERE {category_query} "
                    "ORDER BY date DESC",
                    db.connection,
                )

        # Create a table where the 'category' column is editable and has a
        # dropdown menu to select the category.
        category_options = [c for c in category_list]
        dropdown_options = [{"label": i, "value": i} for i in category_options]
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
            id=self.table_id,
            data=df.to_dict("records"),
            columns=columns,
            row_selectable=self.row_selectable,
            dropdown={"category": {"options": dropdown_options}},
            css=[
                {
                    "selector": ".Select-menu-outer",
                    "rule": "display: block !important",
                }
            ],  # github.com/plotly/dash-table/issues/221
        )
        self.records = df.to_dict("records")
        self.table = table

    def get_table(self):
        return self.table

    def set_regex_query(self, query: str):
        self.regex_query = query
        self.update()

    def diff(self, data):
        """
        Compares the entries dash table to those in this table. Returns the
        first entry for which the category differs.
        """
        assert self.records is not None
        assert len(data) == len(self.records)
        for new, old in zip(data, self.records):
            if new["category"] != old["category"]:
                return new
