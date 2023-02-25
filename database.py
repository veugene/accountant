from pathlib import Path
import sqlite3
from typing import List, NamedTuple, Optional


class Transaction(NamedTuple):
    date: str
    name: str
    amount: float
    category: Optional[str] = None


class database:
    def __init__(self, database_file_path):
        self.database_file_path = Path(database_file_path)
        self.database_file_path.parent.mkdir(parents=True, exist_ok=True)    
        self.connection = sqlite3.connect(database_file_path)
        self.cursor = self.connection.cursor()
        self.table_name = 'bank_records'
        self.columns = Transaction._fields

    def exists(self):
        check = self.cursor.execute(
            "SELECT name "
            "FROM sqlite_master "
            "WHERE type='table' "
            f"AND name='{self.table_name}'"
        )
        db_exists = len(check.fetchall())
        assert db_exists in [0, 1]
        return bool(db_exists)
    
    def create(self):
        if self.exists():
            raise Exception(
                'Database already exists. Will not create a new one.'
            )
        self.cursor.execute(
            f"CREATE TABLE {self.table_name}({','.join(self.columns)})"
        )

    def add_transactions(self, transaction_list: List[Transaction]):
        for tx in transaction_list:
            assert isinstance(tx, Transaction)
        
        # Match each transaction to a category, if known.
        # 
        # NOTE: this assumes that each name has a single category. If a name
        # has multiple categories, this will silently just choose one category.
        # Perhaps a sanity check should be added somewhere for this.
        category_by_name = dict(
            self.cursor.execute(
                "SELECT name, category FROM bank_records"
            )
        )
        transaction_list_with_categories = []
        for tx in transaction_list:
            category = None
            if tx.name in category_by_name:
                if tx.category is None:
                    category = category_by_name[tx.name]
                elif tx.category != category_by_name[tx.name]:
                    raise ValueError(
                        f"Transaction with name '{tx.name}' passed to the "
                        f"database with category '{tx.category}' but this name "
                        "is already associated with category "
                        f"'{category_by_name[tx.name]}'."
                    )
            transaction = Transaction(
                date=tx.date,
                name=tx.name,
                amount=tx.amount,
                category=category
            )
            transaction_list_with_categories.append(transaction)
        
        # After matching each transaction to a category, add them to db.
        self.cursor.executemany(
            f"INSERT INTO {self.table_name} VALUES (?, ?, ?, ?)",
            transaction_list_with_categories
        )
        self.connection.commit()
    