import sqlite3
from pathlib import Path


class MigrationManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.migrations_dir = Path(__file__).parent
    
    def get_current_version(self, conn: sqlite3.Connection) -> int:
        try:
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            return cursor.fetchone()[0] or 0
        except sqlite3.OperationalError:
            return 0
    
    def apply_pending(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        
        current = self.get_current_version(conn)
        migrations = sorted(self.migrations_dir.glob('[0-9][0-9][0-9]_*.sql'))
        
        for migration_file in migrations:
            version = int(migration_file.stem.split('_')[0])
            
            if version > current:
                print(f"Applying migration {version}: {migration_file.name}")
                
                with open(migration_file, 'r') as f:
                    sql = f.read()
                
                try:
                    conn.executescript(sql)
                    conn.commit()
                    current = version
                except sqlite3.Error as e:
                    conn.rollback()
                    raise RuntimeError(f"Migration {version} failed: {e}")
        
        conn.close()
        print(f"Schema at version {current}")
    
    def verify_integrity(self):
        conn = sqlite3.connect(self.db_path)
        
        try:
            versions = conn.execute(
                "SELECT version FROM schema_version ORDER BY version"
            ).fetchall()
        except sqlite3.OperationalError:
            conn.close()
            return False
        
        conn.close()
        
        versions = [v[0] for v in versions]
        if not versions:
            return True
        
        expected = list(range(1, max(versions) + 1))
        missing = set(expected) - set(versions)
        
        if missing:
            raise RuntimeError(f"Missing migrations: {missing}")
        
        return True