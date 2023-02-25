from pathlib import Path
import sqlite3


class database:
    def __init__(self, database_file_path):
        self.database_file_path = Path(database_file_path)
        self.database_file_path.parent.mkdir(parents=True, exist_ok=True)    
        self.connection = sqlite3.connect(database_file_path)
        self.cursor = self.connection.cursor()
        self.db_name = 'bank_records'
        self.columns = ['category', 'name', 'date', 'credit', 'debit']

    def exists(self):
        check = self.cursor.execute(
            "SELECT name "
            "FROM sqlite_master "
            "WHERE type='table' "
            f"AND name='{self.db_name}'"
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
            f"CREATE TABLE {self.db_name}({','.join(self.columns)})"
        )
