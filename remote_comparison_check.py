"""Public fictional comparison fixtures; no live hotel, request or account."""
from copy import deepcopy
import json
import os
from quote_comparison import compare_normalized_quotes

if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
    raise RuntimeError("Remote GitHub-hosted execution required")


def fixture(platform, amount):
    return {
        "source": {"platform": platform, "hotel_id": platform+"-hotel", "room_id": platform+"-room",
                   "rate_id": platform+"-rate", "request_id": platform+"-request", "response_id": platform+"-response",
                   "evidence_ref": "fictional-source", "observed_at": "2030-01-01T00:00:00Z",
                   "request_binding_verified": True, "available": True},
        "conditions": {"property_key": "fictional-property", "physical_room_key": "fictional-room",
                       "check_in": "2030-01-02", "check_out": "2030-01-04",
                       "rooms": [{"adults": 2, "children_ages": [7]}],
                       "meal_state": "verified_schedule",
                       "meal_schedule": [{"date": "2030-01-03", "room_index": 0, "kind": "breakfast", "servings": 3},
                                         {"date": "2030-01-04", "room_index": 0, "kind": "breakfast", "servings": 3}],
                       "payment_timing": "prepaid", "audience_key": "public-ordinary", "market": "CN", "device": "desktop",
                       "other_terms": [], "complete_verified": True, "evidence_ref": "fictional-conditions",
                       "cancellation_policy": {"complete_verified": True, "intervals": [
                           {"start_at": None, "end_at": "2030-01-01T18:00:00+08:00", "penalty": {"kind": "none"}},
                           {"start_at": "2030-01-01T18:00:00+08:00", "end_at": None,
                            "penalty": {"kind": "percent", "value": "100", "basis": "stay_total"}}]}},
        "price": {"role": "customer_payable", "basis": "all_rooms_full_stay_all_mandatory_charges",
                  "currency": "CNY", "stay_total": amount, "coverage_verified": True, "evidence_ref": "fictional-total"}}


checks = []
base_a, base_b = fixture("platform-a", "200.10"), fixture("platform-b", "220.30")


def compare(a, b, **kwargs):
    return compare_normalized_quotes(a, b, now_utc="2030-01-01T00:01:00Z",
                                     max_age_seconds=120, max_skew_seconds=30, **kwargs)


def check(name, result):
    assert result, name
    checks.append({"name": name, "passed": True})


def reject_change(name, path, value):
    changed = deepcopy(base_b)
    target = changed
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    check(name, compare(base_a, changed)["status"] == "not_comparable")


result = compare(base_a, base_b)
check("different platform and source IDs allowed", result["status"] == "candidate_comparison")
check("exact negative price difference", result["difference_our_minus_other"] == "-20.20" and result["lower_price_side"] == "our")
check("candidate never accepted as live quote", result["strict_quote_accepted"] is False)
reverse = compare(base_b, base_a)
check("positive difference and competitor lower", reverse["difference_our_minus_other"] == "20.20" and reverse["lower_price_side"] == "other")
equal = compare(base_a, fixture("platform-b", "200.1"))
check("decimal scale does not change equality", equal["lower_price_side"] == "equal")
utc = deepcopy(base_b)
utc["conditions"]["cancellation_policy"]["intervals"][0]["end_at"] = "2030-01-01T10:00:00Z"
utc["conditions"]["cancellation_policy"]["intervals"][1]["start_at"] = "2030-01-01T10:00:00Z"
check("same absolute cutoff across offsets", compare(base_a, utc)["status"] == "candidate_comparison")
fee_a, fee_b = deepcopy(base_a), deepcopy(base_b)
fee_a["price"]["components"] = [{"role": "room_subtotal", "amount": "190", "currency": "CNY"},
                                {"role": "mandatory_fee", "amount": "10.10", "currency": "CNY"}]
fee_b["price"]["components"] = [{"role": "room_subtotal", "amount": "200", "currency": "CNY"},
                                {"role": "mandatory_fee", "amount": "20.30", "currency": "CNY"}]
check("consistent breakdowns may have different fee amounts", compare(fee_a, fee_b)["status"] == "candidate_comparison")
fee_bad = deepcopy(fee_b)
fee_bad["price"]["components"][1]["amount"] = "20.31"
check("inconsistent fee breakdown rejected", compare(fee_a, fee_bad)["status"] == "not_comparable")
fee_bad["price"]["components"][1]["amount"] = "20.30"
fee_bad["price"]["components"][1]["currency"] = "USD"
check("mixed currency fee breakdown rejected", compare(fee_a, fee_bad)["status"] == "not_comparable")
fee_bad["price"]["components"][1]["currency"] = "CNY"
fee_bad["price"]["components"][1]["role"] = "unknown_supplement"
check("unknown price component role rejected", compare(fee_a, fee_bad)["status"] == "not_comparable")
no_meals_a, no_meals_b = deepcopy(base_a), deepcopy(base_b)
for quote in (no_meals_a, no_meals_b):
    quote["conditions"]["meal_state"] = "verified_no_meals"
    quote["conditions"]["meal_schedule"] = []
check("explicitly verified room-only offers comparable", compare(no_meals_a, no_meals_b)["status"] == "candidate_comparison")
dinner_a, dinner_b = deepcopy(base_a), deepcopy(base_b)
for quote in (dinner_a, dinner_b):
    quote["conditions"]["meal_schedule"].append({"date": "2030-01-02", "room_index": 0, "kind": "dinner", "servings": 3})
check("actual service dates include checkin dinner and checkout breakfast", compare(dinner_a, dinner_b)["status"] == "candidate_comparison")
for label, penalty in (("fixed", {"kind": "fixed", "amount": "100", "currency": "CNY", "basis": "stay_total"}),
                       ("first nights", {"kind": "first_nights", "nights": 1, "basis": "nightly_customer_total_schedule"})):
    same_a, same_b = deepcopy(base_a), deepcopy(base_b)
    for quote in (same_a, same_b):
        quote["conditions"]["cancellation_policy"]["intervals"][1]["penalty"] = deepcopy(penalty)
    check("equal supported "+label+" penalties comparable", compare(same_a, same_b)["status"] == "candidate_comparison")

reject_change("wrong property", ["conditions", "property_key"], "another-property")
reject_change("wrong physical room", ["conditions", "physical_room_key"], "another-room")
reject_change("different checkin", ["conditions", "check_in"], "2030-01-01")
reject_change("different checkout", ["conditions", "check_out"], "2030-01-05")
reject_change("unknown checkout", ["conditions", "check_out"], None)
reject_change("invalid calendar date", ["conditions", "check_out"], "2030-02-30")
reject_change("wrong adult count", ["conditions", "rooms", 0, "adults"], 1)
reject_change("wrong child age", ["conditions", "rooms", 0, "children_ages"], [8])
reject_change("boolean adult count", ["conditions", "rooms", 0, "adults"], True)
reject_change("unknown guests", ["conditions", "rooms"], None)
reject_change("wrong meal servings", ["conditions", "meal_schedule", 0, "servings"], 2)
reject_change("zero servings are not a meal schedule", ["conditions", "meal_schedule", 0, "servings"], 0)
reject_change("wrong meal date", ["conditions", "meal_schedule", 0, "date"], "2030-01-02")
reject_change("unknown meal state", ["conditions", "meal_state"], "unknown")
reject_change("empty schedule is not confirmed no meals", ["conditions", "meal_schedule"], [])
reject_change("no meals state contradicts meal schedule", ["conditions", "meal_state"], "verified_no_meals")
reject_change("wrong payment timing", ["conditions", "payment_timing"], "at_property")
reject_change("different audience layer", ["conditions", "audience_key"], "member-profile")
reject_change("different market", ["conditions", "market"], "US")
reject_change("different device", ["conditions", "device"], "mobile")
reject_change("different additional terms", ["conditions", "other_terms"], ["minimum-stay-three-nights"])
reject_change("conditions not independently normalized", ["conditions", "complete_verified"], False)
reject_change("conditions evidence absent", ["conditions", "evidence_ref"], "")
reject_change("different currency", ["price", "currency"], "USD")
reject_change("supplier cost is not payable", ["price", "role"], "supplier_cost")
reject_change("nightly amount is not full stay", ["price", "basis"], "average_nightly")
reject_change("mandatory charges unverified", ["price", "coverage_verified"], False)
reject_change("floating point total rejected", ["price", "stay_total"], 220.3)
reject_change("zero total rejected", ["price", "stay_total"], "0")
reject_change("unknown price fields rejected", ["price", "informational_fee_amount"], "100")
reject_change("empty fee breakdown rejected", ["price", "components"], [])
reject_change("missing request evidence", ["source", "evidence_ref"], "")
reject_change("unbound response", ["source", "request_binding_verified"], False)
reject_change("unavailable source", ["source", "available"], False)
reject_change("stale quote", ["source", "observed_at"], "2029-12-31T23:00:00Z")
reject_change("future quote", ["source", "observed_at"], "2030-01-01T00:02:00Z")
reject_change("excessive observation skew", ["source", "observed_at"], "2029-12-31T23:59:29Z")
reject_change("unknown observation timezone", ["source", "observed_at"], "2030-01-01T00:00:00-00:00")
reject_change("no absolute cancellation timezone", ["conditions", "cancellation_policy", "intervals", 0, "end_at"], "2030-01-01T18:00:00")
reject_change("policy not complete", ["conditions", "cancellation_policy", "complete_verified"], False)
reject_change("coarse refund enum rejected", ["conditions", "cancellation_policy"], 0)
reject_change("policy gap rejected", ["conditions", "cancellation_policy", "intervals", 1, "start_at"], "2030-01-01T19:00:00+08:00")
reject_change("different penalty percent", ["conditions", "cancellation_policy", "intervals", 1, "penalty", "value"], "50")
reject_change("different penalty basis", ["conditions", "cancellation_policy", "intervals", 1, "penalty", "basis"], "first_night_total")
reject_change("fixed penalty is not percent", ["conditions", "cancellation_policy", "intervals", 1, "penalty"], {"kind":"fixed","amount":"100","currency":"CNY","basis":"stay_total"})
reject_change("first night penalty is not percent", ["conditions", "cancellation_policy", "intervals", 1, "penalty"], {"kind":"first_nights","nights":1,"basis":"nightly_customer_total_schedule"})
reject_change("unsupported first night basis rejected", ["conditions", "cancellation_policy", "intervals", 1, "penalty"], {"kind":"first_nights","nights":1,"basis":"unknown"})
reject_change("unsupported fixed penalty basis rejected", ["conditions", "cancellation_policy", "intervals", 1, "penalty"], {"kind":"fixed","amount":"100","currency":"CNY","basis":"room_only"})
duplicate = deepcopy(base_b)
duplicate["conditions"]["meal_schedule"].append({**duplicate["conditions"]["meal_schedule"][0], "servings": 1})
check("conflicting repeated meal key rejected", compare(base_a, duplicate)["status"] == "not_comparable")
missing = deepcopy(base_b)
del missing["conditions"]["audience_key"]
check("missing required condition rejected", compare(base_a, missing)["status"] == "not_comparable")

print(json.dumps({"scope":"Public fictional normalized comparison fixtures only", "checks":checks,
                  "check_count":len(checks), "real_quote_records":0,
                  "actual_source_adapter_implemented":False, "strict_quote_accepted":False}, indent=2))
