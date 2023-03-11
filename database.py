import sqlite3
import warnings
from datetime import date
from pathlib import Path
from shutil import copy
from typing import List, NamedTuple, Optional, Tuple, Union

from natsort import natsorted


class Transaction(NamedTuple):
    date: str
    name: str
    amount: float
    category: Optional[str] = "__UNKNOWN__"


class Database:
    def __init__(self, database_file_path):
        self.database_file_path = database_file_path
        self.connection = None

    def __enter__(self):
        db = _Database(self.database_file_path)
        self.connection = db.connection
        return db

    def __exit__(self, exception_type, exception_value, exception_traceback):
        if self.connection is not None:
            self.connection.close()
        if exception_type is not None:
            return False  # Re-raise exception.


class _Database:
    def __init__(self, database_file_path):
        self.database_file_path = Path(database_file_path)
        self.database_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database_file_path)
        self.cursor = self.connection.cursor()
        self.table_name = "bank_records"

        # Create the table if it does not yet exist.
        check = self.cursor.execute(
            "SELECT name "
            "FROM sqlite_master "
            'WHERE type="table" '
            f'AND name="{self.table_name}"'
        )
        db_exists = len(check.fetchall())
        assert db_exists in [0, 1]
        if not db_exists:
            self.cursor.execute(
                f"CREATE TABLE {self.table_name}("
                "date TEXT,"
                "name TEXT,"
                "amount FLOAT,"
                "category TEXT,"
                "UNIQUE(date, name, amount)"
                ")"
            )

    def add_transactions(
        self,
        transaction_list: List[Transaction],
        raise_on_duplicate=False,
    ) -> None:
        for tx in transaction_list:
            assert isinstance(tx, Transaction)

        # Match each transaction to a category, if known.
        transactions_with_categories = self.match_transactions_to_categories(
            transaction_list
        )

        # After matching each transaction to a category, add them to db.
        for tx in transactions_with_categories:
            try:
                self.cursor.execute(
                    f"INSERT INTO {self.table_name} VALUES (?, ?, ?, ?)", tx
                )
            except sqlite3.IntegrityError:
                # UNIQUE constraint failed. Entry already exists. Don't add.
                msg = (
                    f"Entry date, name, and amount already exists: {tx}. "
                    "Will not add this transaction to the database."
                )
                if raise_on_duplicate:
                    print(msg)
                    raise
                else:
                    warnings.warn(msg)
            except:
                print(f"Error when adding transaction: {tx}")
                raise
        self.connection.commit()

    def match_transactions_to_categories(
        self, transaction_list: List[Transaction]
    ) -> List[Transaction]:
        transactions_with_categories = []
        for tx in transaction_list:
            category = self.get_category_by_name(tx.name)
            if tx.category != "__UNKNOWN__" and category != "__UNKNOWN__":
                if tx.category != category:
                    raise ValueError(
                        f'Transaction with name "{tx.name}" passed to the '
                        f'database with category "{tx.category}" but this name '
                        f'is already associated with category "{category}".'
                    )
            if category == "__UNKNOWN__":
                category = tx.category
            transaction = Transaction(
                date=tx.date,
                name=tx.name,
                amount=tx.amount,
                category=category,
            )
            transactions_with_categories.append(transaction)
        return transactions_with_categories

    def get_category_by_name(self, name: str) -> Optional[str]:
        category_list = self.cursor.execute(
            f"SELECT DISTINCT category FROM {self.table_name} WHERE name=?",
            (name,),
        ).fetchall()
        if len(category_list) == 0:
            return "__UNKNOWN__"
        assert len(set(category_list)) == 1
        return category_list[0][0]

    def get_uncategorized_names(self) -> List[Tuple[str, int]]:
        """
        Sorts the distinct names according to how often they appear.
        """
        result = self.cursor.execute(
            "SELECT name, COUNT(*) "
            f"FROM {self.table_name} "
            "WHERE category=? "
            "GROUP BY name "
            "ORDER BY COUNT(*) DESC",
            ("__UNKNOWN__",),
        )
        return result.fetchall()

    def set_name_category(self, name: str, category: Optional[str]) -> None:
        if category is None:
            set_to = "NULL"
        else:
            set_to = f"'{category}'"
        self.cursor.execute(
            f"UPDATE {self.table_name} SET category={set_to} WHERE name=?",
            (name,),
        )
        self.connection.commit()

    def get_all_categories(self) -> List[Union[None, str]]:
        result = self.cursor.execute(
            f"SELECT DISTINCT category FROM {self.table_name}"
        )
        retval = [val[0] for val in result.fetchall() if val[0] is not None]
        return retval

    def backup(self):
        """
        Find the last numbered backup file for the day and increment that
        number. Then save a backup.

        Format: "{filename}.backup_{date}_{number}"

        Example: "db.sql.backup_2023-03-06_0001"

        It is possible that a file may exist that matches up to 'number' but
        with a suffix that does not cast to a number. For this reason, loop
        over the file candidates to find the last matching backup file for
        the day.
        """
        date_string = date.today().strftime("%Y-%m-%d")
        name_root = f"{self.database_file_path.name}.backup_{date_string}_"
        backup_file_list = list(
            self.database_file_path.parent.glob(f"{name_root}*")
        )
        last_backup_num = 0
        for fn in natsorted(backup_file_list)[::-1]:
            suffix = str(fn.name).replace(name_root, "")
            try:
                last_backup_num = int(suffix)
            except ValueError:
                continue
            else:
                break
        backup_fn = f"{name_root}{last_backup_num + 1}"
        copy(
            self.database_file_path,
            Path(self.database_file_path.parent, backup_fn),
        )
