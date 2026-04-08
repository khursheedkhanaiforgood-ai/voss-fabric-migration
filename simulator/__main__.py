"""
Entry point: python -m simulator

Usage:
  cd /Users/khukhan/voss-fabric-migration
  python -m simulator

Optional: set ANTHROPIC_API_KEY environment variable for AI explanations.
"""

import os
from .services.simulation_engine import SimulationEngine


def main():
    engine = SimulationEngine()
    engine.run()


if __name__ == "__main__":
    main()
