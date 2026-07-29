import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "signals" / "evaluate_shadow_signals.py"
spec = importlib.util.spec_from_file_location("evaluate_shadow_signals", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules["evaluate_shadow_signals"] = mod
spec.loader.exec_module(mod)


def _passing():
    return {"20D": {
        "data_audit_passed": True, "top_decile_excess_after_cost": 0.012,
        "precision_at_5": 0.62, "technical_precision_at_5": 0.52,
        "n_buys": 40, "coverage": 0.08, "folds_positive_frac": 0.75,
        "max_drawdown": -0.18, "turnover": 0.4, "sector_hhi": 0.2,
        "calibration_ece": 0.05, "large_loss_rate": 0.08, "dsr": 0.97, "pbo": 0.3,
    }}


def test_gate_passes_and_never_enables_fusion():
    g = mod.build_gate(_passing())
    assert g["model_validated"] is True
    assert g["fusion_enabled"] is False          # ALWAYS false
    assert all(g["checks"].values())


def test_gate_blocks_on_dsr_but_fusion_still_false():
    m = _passing(); m["20D"]["dsr"] = 0.80
    g = mod.build_gate(m)
    assert g["model_validated"] is False
    assert g["fusion_enabled"] is False
    assert g["checks"]["dsr_significant"] is False


def test_gate_blocks_when_holdout_already_evaluated():
    g = mod.build_gate(_passing(), holdout_manifest={"result": "EVALUATED"})
    assert g["checks"]["holdout_fresh"] is False
    assert g["model_validated"] is False
