import sys
from pathlib import Path

# Permet aux tests d'importer depuis src.*
sys.path.insert(0, str(Path(__file__).parent))
