import argparse
from pathlib import Path

from . import install_monitor

parser = argparse.ArgumentParser(description="Install the Tiel hardware sensor overlay.")
parser.add_argument("polystrata", type=Path, help="PolyStrata checkout")
args = parser.parse_args()
try:
    install_monitor(args.polystrata)
except (OSError, RuntimeError) as error:
    parser.exit(1, f"{error}\n")
