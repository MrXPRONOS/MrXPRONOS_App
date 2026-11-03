"""Predeployment check for 2025 extra market validation."""
import json
from bsd_archive import MATCHES_FILE, _read_json
from bsd_v2_core import V2History, fit_rho_2024
from bsd_v2_new_market_model import fit_extra_market_model
def main():
    hist = _read_json(MATCHES_FILE, [])
    if not hist:
        raise ValueError("Missing history")
    index = V2History(hist)
    rho, _ = fit_rho_2024(index)
    model = fit_extra_market_model(index, rho=rho)
    report = model.to_dict()
    assert report["train_2025_jan_aug_games"] > 0
    assert report["validation_2025_sep_dec_games"] > 0
    print("BSD_MARKET_HOLDOUT_REPORT", json.dumps(report, ensure_ascii=False))
if __name__ == "__main__":
    main()
