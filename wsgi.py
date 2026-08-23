import sys
import os

# Set the project root directory
project_home = os.path.dirname(__file__)
sys.path.insert(0, project_home)

# Set Python interpreter to your venv
INTERP = os.path.join(project_home, "venv", "bin", "python3")
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

# Import the app factory and create the application instance
from app import create_app

application = create_app()
