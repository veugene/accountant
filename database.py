from pathlib import Path
import sqlite3
from typing import List, NamedTuple, Optional, Union
import warnings


class Transaction(NamedTuple):
    date: str
    name: str
    amount: float
    category: Optional[str] = '__UNKNOWN__'


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
            return False    # Re-raise exception.


class _Database:
    def __init__(self, database_file_path):
        self.database_file_path = Path(database_file_path)
        self.database_file_path.parent.mkdir(parents=True, exist_ok=True)    
        self.connection = sqlite3.connect(database_file_path)
        self.cursor = self.connection.cursor()
        self.table_name = 'bank_records'

        # Create the table if it does not yet exist.
        check = self.cursor.execute(
            'SELECT name '
            'FROM sqlite_master '
            'WHERE type="table" '
            f'AND name="{self.table_name}"'
        )
        db_exists = len(check.fetchall())
        assert db_exists in [0, 1]
        if not db_exists:
            self.cursor.execute(
                f'CREATE TABLE {self.table_name}('
                    'date TEXT,'
                    'name TEXT,'
                    'amount FLOAT,'
                    'category TEXT,'
                    'UNIQUE(date, name, amount)'
                ')'
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
                    f'INSERT INTO {self.table_name} VALUES (?, ?, ?, ?)',
                    tx
                )
            except sqlite3.IntegrityError:
                # UNIQUE constraint failed. Entry already exists. Don't add.
                msg = (
                    f'Entry date, name, and amount already exists: {tx}. '
                    'Will not add this transaction to the database.'
                )
                if raise_on_duplicate:
                    print(msg)
                    raise
                else:
                    warnings.warn(msg)
            except:
                print(f'Error when adding transaction: {tx}')
                raise
        self.connection.commit()
    
    def match_transactions_to_categories(
        self, transaction_list: List[Transaction]
    ) -> List[Transaction]:
        transactions_with_categories = []
        for tx in transaction_list:
            category = self.get_category_by_name(tx.name)
            if tx.category is not None and category is not None:
                if tx.category != category:
                    raise ValueError(
                        f'Transaction with name "{tx.name}" passed to the '
                        f'database with category "{tx.category}" but this name '
                        f'is already associated with category "{category}".'
                    )
            if category is None:
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
            f'SELECT DISTINCT category FROM {self.table_name} '
            f'WHERE name="{name}"'
        ).fetchall()
        if len(category_list) == 0:
            return None
        assert len(set(category_list)) == 1
        return category_list[0][0]
    
    def get_uncategorized_names(self) -> List[Transaction]:
        result = self.cursor.execute(
            f"SELECT DISTINCT name FROM {self.table_name} "
            "WHERE category = '__UNKNOWN__'"
        )
        retval = [val[0] for val in result.fetchall()]
        return retval
    
    def set_name_category(self, name, category) -> None:
        self.cursor.execute(
            f'UPDATE {self.table_name} '
            f'SET category="{category}" WHERE name="{name}"'
        )
        self.connection.commit()
    
    def get_all_categories(self) -> List[Union[None, str]]:
        result = self.cursor.execute(
            f'SELECT DISTINCT category FROM {self.table_name}'
        )
        retval = [val[0] for val in result.fetchall() if val[0] is not None]
        return retval
