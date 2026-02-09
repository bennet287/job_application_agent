import os
import stat
from pathlib import Path


class PermissionManager:
    RESTRICTED_READ = 0o600
    RESTRICTED_EXEC = 0o700
    STANDARD_READ = 0o644
    STANDARD_EXEC = 0o755
    
    def __init__(self, project_root: str):
        self.root = Path(project_root)
    
    def setup(self):
        self._chmod(self.root, self.RESTRICTED_EXEC)
        
        for dir_name in ['core', 'database', 'cli', 'utils', 'config']:
            path = self.root / dir_name
            self._chmod_recursive(path, self.STANDARD_READ, self.STANDARD_EXEC)
        
        self._chmod(self.root / 'config' / 'settings.py', self.RESTRICTED_READ)
        
        assets = self.root / 'assets'
        self._chmod(assets, self.RESTRICTED_EXEC)
        
        for subdir in ['cv_versions', 'cover_letters', 'decisions']:
            path = assets / subdir
            path.mkdir(exist_ok=True)
            self._chmod_recursive(path, self.RESTRICTED_READ, self.RESTRICTED_EXEC)
        
        master_cv = assets / 'master_cv.docx'
        if master_cv.exists():
            self._chmod(master_cv, self.RESTRICTED_READ)
        
        db_path = self.root / 'applications.db'
        if db_path.exists():
            self._chmod(db_path, self.RESTRICTED_READ)
        
        self._chmod(self.root / 'main.py', self.STANDARD_EXEC)
        
        print("Permissions hardened.")
    
    def _chmod_recursive(self, path: Path, file_mode: int, dir_mode: int):
        if not path.exists():
            path.mkdir(parents=True, mode=dir_mode)
            return
        
        for item in path.rglob('*'):
            if item.is_dir():
                self._chmod(item, dir_mode)
            elif item.is_file():
                self._chmod(item, file_mode)
        
        self._chmod(path, dir_mode)
    
    def _chmod(self, path: Path, mode: int):
        os.chmod(path, mode)
        actual = stat.S_IMODE(os.stat(path).st_mode)
        if actual != mode:
            raise PermissionError(f"Permission fail: {path}")
        