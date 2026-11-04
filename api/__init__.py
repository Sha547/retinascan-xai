import sys
from pathlib import Path

# ml/ modules import each other by bare name (from common import ...), the way they
# run on Kaggle, so ml/ itself has to be importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
