import sqlite3
import warnings
from pathlib import Path
from shutil import copy
from typing import Dict, List, NamedTuple, Optional, Tuple, Union
from zlib import crc32


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
            except Exception:
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

    def get_uncategorized_names(self) -> Dict[str, int]:
        """
        Sorts the distinct names according to how often they appear.
        """
        result = self.cursor.execute(
            "SELECT name, COUNT(*) "
            f"FROM {self.table_name} "
            "WHERE category=? "
            "GROUP BY name "
            "ORDER BY COUNT(*) ASC, SUM(amount) ASC, name DESC",
            ("__UNKNOWN__",),
        )
        return dict(result.fetchall())

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

    def hash(self):
        result = self.cursor.execute(
            f"SELECT * FROM {self.table_name}"
        ).fetchall()
        transaction_string_list = []
        for tx in result:
            transaction_string_list.append("".join([str(v) for v in tx]))
        db_string = "\n".join(sorted(transaction_string_list))
        db_hash_dec = crc32(db_string.encode("utf-8"))
        db_hash = hex(db_hash_dec)[2:]  # Skip initial '0x'; doesn't change
        return db_hash

    def backup(self):
        """
        If a backup with the same hash does not already exist, create one.

        Format: "{filename}.backup_{hash}"

        Example: "db.sql.backup_d7f030ec"
        """
        hash_db = self.hash()
        backup_fn = f"{self.database_file_path.name}.backup_{hash_db}"
        backup_path = Path(self.database_file_path.parent, backup_fn)
        if not backup_path.exists():
            copy(
                self.database_file_path,
                backup_path,
            )
