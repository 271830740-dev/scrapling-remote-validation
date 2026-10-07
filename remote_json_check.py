"""Public fictional JSON checks; run only on a GitHub-hosted runner."""
import json
import os
from decimal import Decimal
from quote_json import decode_quote_json

if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
    raise RuntimeError("Remote GitHub-hosted execution required")

checks = []


def check(name, passed):
    assert passed, name
    checks.append({"name": name, "passed": True})


def rejects(name, raw, **options):
    try:
        decode_quote_json(raw, **options)
    except ValueError:
        check(name, True)
    else:
        check(name, False)


value = decode_quote_json('{"amount":0.10,"hotel_id":"00017","missing":null}')
check("decimal type and trailing scale", isinstance(value["amount"], Decimal) and str(value["amount"]) == "0.10")
check("text ID retains leading zeros", value["hotel_id"] == "00017")
check("explicit null remains null", value["missing"] is None)
check("exact integer above binary64 range", decode_quote_json('9007199254740993') == 9007199254740993)
check("decimal exponent does not become infinity", decode_quote_json('1e400') == Decimal('1e400'))
check("Unicode UTF-8 response", decode_quote_json('{"meal":"早餐"}'.encode('utf-8'))["meal"] == "早餐")
check("sibling object keys allowed", decode_quote_json('[{"price":1},{"price":2}]') == [{"price":1},{"price":2}])
check("whitespace and numeric key order allowed", decode_quote_json(' { "a" : 1, "1" : 22 } ') == {"a":1,"1":22})
check("ordinary nested objects", decode_quote_json('{"a":{"b":[]}}') == {"a":{"b":[]}})
rejects("duplicate root price", '{"price":100,"price":200}')
rejects("duplicate nested currency", '{"offer":{"currency":"CNY","currency":"USD"}}')
rejects("escaped duplicate key", '{"price":100,"pr\\u0069ce":200}')
rejects("NaN rejected", '{"price":NaN}')
rejects("Infinity rejected", '{"price":Infinity}')
rejects("negative Infinity rejected", '{"price":-Infinity}')
rejects("UTF-8 BOM rejected", b'\xef\xbb\xbf{}')
rejects("text BOM rejected", '\ufeff{}')
rejects("invalid UTF-8 rejected", b'{"x":"\xff"}')
rejects("trailing document rejected", '{}{}')
rejects("invalid syntax rejected", '{"price":}')
rejects("empty response rejected", '')
rejects("preparsed object rejected", {"price": 100})
rejects("byte limit enforced", '{"price":100}', max_bytes=4)
rejects("Unicode byte limit enforced", '"早"', max_bytes=4)
rejects("numeric token limit enforced", '1' * 129)
rejects("boolean byte limit rejected", '{}', max_bytes=True)

print(json.dumps({"scope":"Public fictional JSON transport fixtures only", "checks":checks,
                  "check_count":len(checks), "real_quote_records":0,
                  "strict_quote_acceptance_implemented":False}, indent=2))
