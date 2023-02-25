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
        self.cursor.executemany(
            f"INSERT INTO {self.table_name} VALUES (?, ?, ?, ?)",
            transaction_list
        )
        self.connection.commit()
    