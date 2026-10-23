"""Run the Week 1 TrackEval known-answer script under pytest."""
import importlib.util

from conftest import ROOT


def test_trackeval_known_answers():
    spec = importlib.util.spec_from_file_location("ka", ROOT / "tests/known_answer/test_identity_swap.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main() == 0
