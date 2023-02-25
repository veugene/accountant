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

    def exists(self) -> bool:
        check = self.cursor.execute(
            "SELECT name "
            "FROM sqlite_master "
            "WHERE type='table' "
            f"AND name='{self.table_name}'"
        )
        db_exists = len(check.fetchall())
        assert db_exists in [0, 1]
        return bool(db_exists)
    
    def create(self) -> None:
        if self.exists():
            raise Exception(
                'Database already exists. Will not create a new one.'
            )
        self.cursor.execute(
            f"CREATE TABLE {self.table_name}({','.join(self.columns)})"
        )

    def add_transactions(self, transaction_list: List[Transaction]) -> None:
        for tx in transaction_list:
            assert isinstance(tx, Transaction)
        
        # Match each transaction to a category, if known.
        transactions_with_categories = self.match_transactions_to_categories(
            transaction_list
        )
        
        # After matching each transaction to a category, add them to db.
        self.cursor.executemany(
            f"INSERT INTO {self.table_name} VALUES (?, ?, ?, ?)",
            transactions_with_categories
        )
        self.connection.commit()
    
    def match_transactions_to_categories(
        self, transaction_list: List[Transaction]
    ) -> List[Transaction]:
        transactions_with_categories = []
        for tx in transaction_list:
            category = self.get_category_by_name(tx.name)
            if category is not None:
                if tx.category is None:
                    category = category_by_name[tx.name]
                elif tx.category != category:
                    raise ValueError(
                        f"Transaction with name '{tx.name}' passed to the "
                        f"database with category '{tx.category}' but this name "
                        f"is already associated with category '{category}'."
                    )
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
            f"SELECT category FROM bank_records WHERE name='name'"
        ).fetchall()
        if len(category_list) == 0:
            return None
        assert len(set(category_list)) == 1
        return category_list[0]
        