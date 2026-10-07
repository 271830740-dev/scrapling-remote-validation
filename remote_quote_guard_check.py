"""Remote-only synthetic rejection checks; no travel requests or real prices."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import importlib.metadata
import json
from pathlib import Path
import platform

from scrapling.parser import Selector
from guarded_extraction import extract_candidate_amount


def main():
    version = importlib.metadata.version("scrapling")
    if version != "0.4.15":
        raise RuntimeError(f"Expected 0.4.15, got {version}")
    expected = {"supplier_id": "supplier-A", "hotel_id": "hotel-A", "room_id": "00042", "rate_id": "rate-A"}
    checks = []

    def require(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    def card(ids=None, name="Fixture King", price="321.00", currency="CNY", price_html=None):
        ids = expected if ids is None else ids
        attributes = " ".join(
            f'data-{key.replace("_", "-")}="{escape(value, quote=True)}"'
            for key, value in ids.items()
        )
        amount_html = f'<span class="price">{escape(price)}</span>' if price_html is None else price_html
        return f'<article class="room" {attributes} data-currency="{escape(currency)}"><h3>{escape(name)}</h3>{amount_html}</article>'

    def extract(markup, expected_ids=None, name="Fixture King", currency="CNY"):
        candidates = Selector(f"<main>{markup}</main>").css("article.room")
        return extract_candidate_amount(candidates, expected if expected_ids is None else expected_ids, name, currency)

    valid = extract(card())
    require("valid_candidate_amount_preserved", valid is not None and valid["candidate_amount"] == "321.00")
    require("leading_zero_source_id_preserved", valid["room_id"] == "00042")
    require("candidate_never_counts_as_strict_quote", valid["strict_quote_accepted"] is False)
    require("candidate_currency_is_not_request_binding_proof", valid["request_currency_binding_verified"] is False)
    redesigned_card = card().replace('class="room"', 'class="room redesigned"')
    redesigned = f"<section><div>{redesigned_card}</div></section>"
    require("wrapper_and_class_change_preserve_exact_source", extract(redesigned) == valid)
    require("no_card_rejected", extract("") is None)
    require("duplicate_identical_cards_rejected", extract(card() + card()) is None)
    for field in expected:
        changed = {**expected, field: "different-source"}
        require(f"same_name_wrong_{field}_rejected", extract(card(changed)) is None)
        missing = {key: value for key, value in expected.items() if key != field}
        require(f"missing_source_{field}_rejected", extract(card(missing)) is None)
        missing_expected = deepcopy(expected)
        missing_expected.pop(field)
        require(f"missing_expected_{field}_rejected", extract(card(), missing_expected) is None)
    require("same_source_wrong_name_rejected", extract(card(name="Fixture Twin")) is None)
    require("duplicate_room_names_rejected", extract(card().replace("</h3>", "</h3><h3>Fixture King</h3>")) is None)
    require("empty_expected_name_rejected", extract(card(), name="") is None)
    require("numeric_source_id_rejected", extract(card(), {**expected, "room_id": 42}) is None)
    require("leading_zero_ids_not_collapsed", extract(card({**expected, "room_id": "42"})) is None)
    require("unverified_expected_currency_rejected", extract(card(), currency="") is None)
    require("wrong_currency_rejected", extract(card(currency="USD")) is None)
    require("missing_currency_rejected", extract(card(currency="")) is None)
    require("missing_price_rejected", extract(card(price_html="")) is None)
    require("ordinary_and_member_prices_not_collapsed", extract(card(price_html='<span class="price">321.00</span><span class="price">299.00</span>')) is None)
    require("identical_duplicate_prices_not_collapsed", extract(card(price_html='<span class="price">321.00</span><span class="price">321.00</span>')) is None)
    require("nested_price_parts_not_concatenated", extract(card(price_html='<span class="price"><b>321</b>.00</span>')) is None)
    for index, amount in enumerate(["", "0", "0.00", "-1", "NaN", "Infinity", "1e2", "321,00", "from 321", "321 CNY", "321/room", "321..00"]):
        require(f"invalid_amount_{index}_rejected", extract(card(price=amount)) is None)
    precise = extract(card(price="321.0000000000000000000000001"))
    require("decimal_precision_not_rounded_or_float_cast", precise is not None and precise["candidate_amount"] == "321.0000000000000000000000001")
    print(json.dumps({
        "status": "passed", "scope": "synthetic_candidate_extraction_guard_only",
        "scrapling_version": version, "python_version": platform.python_version(),
        "operating_system": platform.system(), "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "implementation_sha256": sha256(Path(__file__).resolve().with_name("guarded_extraction.py").read_bytes()).hexdigest(),
        "checks": checks, "real_ctrip_quotes": 0, "travel_requests": 0,
        "strict_quote_accepted": False, "fixtures_are_fictional": True,
        "limitations": valid["remaining_verification"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
