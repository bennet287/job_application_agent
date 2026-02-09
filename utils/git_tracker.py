import subprocess
from pathlib import Path


def init_cv_repo(cv_versions_dir: Path):
    if not cv_versions_dir.exists():
        cv_versions_dir.mkdir(parents=True)
    
    git_dir = cv_versions_dir / '.git'
    if git_dir.exists():
        print("CV repo already initialized.")
        return
    
    subprocess.run(['git', 'init'], cwd=cv_versions_dir, check=True)
    subprocess.run(['git', 'checkout', '-b', 'cv-history'], cwd=cv_versions_dir, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Job Agent'], cwd=cv_versions_dir, check=True)
    subprocess.run(['git', 'config', 'user.email', 'agent@local'], cwd=cv_versions_dir, check=True)
    
    readme = cv_versions_dir / 'README.md'
    readme.write_text("# CV Versions\n\nImmutable history of tailored CVs.\n")
    subprocess.run(['git', 'add', 'README.md'], cwd=cv_versions_dir, check=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=cv_versions_dir, check=True)
    
    print(f"CV repo initialized at {cv_versions_dir}")