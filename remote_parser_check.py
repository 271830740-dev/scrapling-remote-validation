"""Prepared remote-only offline checks. Synthetic HTML never counts as Ctrip quotes."""
import importlib.metadata
import json
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import platform
from tempfile import TemporaryDirectory

from scrapling.parser import Selector
from scrapling.core.storage import SQLiteStorageSystem


def main():
    version = importlib.metadata.version("scrapling")
    if version != "0.4.15":
        raise RuntimeError(f"Expected 0.4.15, got {version}")
    checks = []
    observations = {}

    def require(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    old = '<main><article id="target" class="room"><h3>Fixture room A</h3><span class="price">321.00</span></article><article id="other" class="room"><h3>Fixture room B</h3><span class="price">123.00</span></article></main>'
    changed = '<main><div><article data-id="target" class="room changed"><h3>Fixture room A</h3><span class="price">321.00</span></article></div><article id="other" class="room"><h3>Fixture room B</h3><span class="price">123.00</span></article></main>'
    def matches_identity(candidates, expected_name):
        return len(candidates) == 1 and candidates.css("h3::text").get() == expected_name

    def guarded_price(candidates, expected_name):
        if not matches_identity(candidates, expected_name):
            return None
        return candidates.css("span.price::text").get()

    with TemporaryDirectory() as directory:
        # Logical URLs only: no request is made. Use recognized suffixes so the
        # library does not collapse both domains into its default storage key.
        logical_url = "https://example.com/rooms"
        storage_args = {"storage_file": str(Path(directory) / "elements.sqlite"), "url": logical_url}
        with closing(SQLiteStorageSystem(**storage_args)):
            before = Selector(old, url=logical_url, adaptive=True, storage_args=storage_args)
            require("css_two_rooms", len(before.css("article.room")) == 2)
            require("xpath_price", before.xpath('//*[@id="target"]//span/text()').get() == "321.00")
            text_match = before.find_by_text("Fixture room A")
            require("text_search", text_match is not None and text_match.get_all_text(strip=True) == "Fixture room A")
            require("save_target", len(before.css("#target", auto_save=True)) == 1)
            require("saved_identity_retrievable", before.retrieve("#target") is not None)
            after = Selector(changed, url=logical_url, adaptive=True, storage_args=storage_args)
            require("old_selector_absent", len(after.css("#target")) == 0)
            relocated = after.css("#target", adaptive=True)
            observations["unassisted_adaptive"] = {
                "candidate_count": len(relocated),
                "names": relocated.css("h3::text").getall(),
                "prices": relocated.css("span.price::text").getall(),
                "exact_identity_passed": matches_identity(relocated, "Fixture room A"),
            }
            # Retain the failed unassisted result as evidence. Never accept it
            # merely because the adaptive selector returned some elements.
            adaptive_price = guarded_price(relocated, "Fixture room A")
            observations["unassisted_adaptive"]["guarded_price"] = adaptive_price
            if observations["unassisted_adaptive"]["exact_identity_passed"]:
                require("adaptive_identity_price_correct", adaptive_price == "321.00")
            else:
                require("unsafe_adaptive_result_rejected", adaptive_price is None)
            recovered = after.xpath('//article[h3="Fixture room A"]')
            require("identity_recovery_unique", matches_identity(recovered, "Fixture room A"))
            require("identity_recovery_price", recovered.css("span.price::text").get() == "321.00")
            wrong_candidate = after.css("#other")
            require("identity_conflict_rejected", not matches_identity(wrong_candidate, "Fixture room A"))
            require("wrong_identity_cannot_emit_price", guarded_price(wrong_candidate, "Fixture room A") is None)
            require("list_completeness_independent", len(after.css("article.room")) == 2)
            foreign_args = {**storage_args, "url": "https://example.net/rooms"}
            with closing(SQLiteStorageSystem(**foreign_args)):
                foreign = Selector(old, url=foreign_args["url"], adaptive=True, storage_args=foreign_args)
                require("domain_isolation", foreign.retrieve("#target") is None)
    print(json.dumps({"status":"passed", "scope":"guarded_synthetic_offline_parser_only", "scrapling_version":version, "python_version":platform.python_version(), "operating_system":platform.system(), "finished_at_utc":datetime.now(timezone.utc).isoformat(), "script_sha256":sha256(Path(__file__).read_bytes()).hexdigest(), "checks":checks, "observations":observations, "unassisted_adaptive_universal_success":False, "real_ctrip_quotes":0, "remote_execution_requires_independent_receipt":True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
