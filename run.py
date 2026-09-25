"""진입점 스크립트. 예: python run.py data/sample_incident_1.json"""
import sys
from incident_copilot.cli import run

if __name__ == "__main__":
    sys.exit(run())
