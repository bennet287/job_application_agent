#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Setting up Job Application Agent..."

# Create asset directories
mkdir -p "$PROJECT_DIR/assets/cv_versions"
mkdir -p "$PROJECT_DIR/assets/cover_letters"
mkdir -p "$PROJECT_DIR/assets/decisions"

# Check for master CV
if [ ! -f "$PROJECT_DIR/assets/master_cv.docx" ]; then
    echo "WARNING: Place your CV at $PROJECT_DIR/assets/master_cv.docx"
    echo "Setup cannot continue without your CV file."
    exit 1
fi

# Run Python setup
python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')

from utils.permissions import PermissionManager
from utils.git_tracker import init_cv_repo
from config import settings
from database.migrations import MigrationManager

# Set permissions
pm = PermissionManager('$PROJECT_DIR')
pm.setup()

# Init git repo for CVs
init_cv_repo(settings.CV_VERSIONS_DIR)

# Run DB migrations
mg = MigrationManager(str(settings.DB_PATH))
mg.apply_pending()

print('Setup complete!')
"

echo ""
echo "Next steps:"
echo "1. Configure settings in: config/settings.py"
echo "2. Run: python main.py process 'https://company.com/job'"