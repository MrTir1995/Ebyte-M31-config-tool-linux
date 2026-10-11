"""Offline consistency checks for source evidence, never hardware behavior."""

import csv
import json
from pathlib import Path
import re
import unittest

from m31tool.core import M31_REGISTER_CATALOG
from m31tool.device import DEVICE_READ_SPECS, DEVICE_REGISTER_CATALOG


ROOT = Path(__file__).resolve().parents[1] / "docs" / "registers"
TABLES = {
    "coils": "0",
    "discrete_inputs": "1",
    "input_registers": "3",
    "holding_registers": "4",
}


def load_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def load_csv(name):
    with (ROOT / name).open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


class RegisterInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = load_json("non-u-en-v1.1.json")
        cls.comparison = load_json("source-comparison.json")
        cls.hypotheses = load_json("hypotheses.json")
        cls.community = load_json("community-evidence.json")
        cls.definitions = {
            row["id"]: row for row in cls.inventory["definitions"]
        }

    def assert_address(self, row, table=None):
        address = row["wire_decimal_zero_based"]
        self.assertIs(type(address), int)
        self.assertGreaterEqual(address, 0)
        self.assertLessEqual(address, 65535)
        self.assertRegex(row["wire_hex_zero_based"], r"^0x[0-9A-F]{4}$")
        self.assertEqual(int(row["wire_hex_zero_based"], 16), address)
        self.assertEqual(row["vendor_number_one_based"], address + 1)
        if table is not None:
            self.assertEqual(
                row["vendor_reference_normalized"],
                f"{TABLES[table]}-{address + 1:04d}",
            )

    def test_schema_coverage_and_unique_claims(self):
        self.assertEqual(self.inventory["schema_version"], 1)
        self.assertEqual(len(self.definitions), 31)
        self.assertEqual(len(self.inventory["definitions"]), 31)
        self.assertEqual(len(self.inventory["models"]), 12)
        self.assertEqual(
            len({model["model"] for model in self.inventory["models"]}), 12,
        )
        primary = [
            row for row in self.inventory["coverage"]
            if row["section"].startswith("4.8.")
        ]
        self.assertEqual(len(primary), 5)
        self.assertEqual(sum(len(row["tables"]) for row in primary), 13)
        covered = [key for row in primary for key in row["definition_ids"]]
        self.assertEqual(len(covered), 30)
        self.assertEqual(set(covered), set(self.definitions) - {"ao_range_prose"})
        self.assertEqual(
            sum(row["kind"] == "singleton"
                and row["wire_decimal_zero_based"] >= 0x7530
                for row in self.definitions.values()), 18,
        )
        rows = [
            instance for definition in self.definitions.values()
            for instance in definition.get("explicit_instances", [definition])
        ]
        self.assertEqual(len(rows), 71)
        self.assertEqual(len({row["id"] for row in rows}), 71)
        self.assertEqual(
            len({row["wire_hex_zero_based"] for row in rows}), 50,
        )
        self.assertEqual(self.inventory["summary"]["explicit_table_rows"], 70)
        self.assertEqual(self.inventory["summary"]["total_claims"], len(self.definitions))

    def test_address_schema_and_evidence_pages(self):
        for row in walk(self.inventory):
            if not isinstance(row, dict):
                continue
            if "wire_hex_zero_based" in row:
                with self.subTest(address=row["wire_hex_zero_based"]):
                    self.assert_address(row, row.get("modbus_table"))
            if "source_id" in row:
                self.assertEqual(row["source_id"], self.inventory["source"]["id"])
                self.assertIs(type(row["manual_page"]), int)
                self.assertEqual(row["pdf_page_one_based"], row["manual_page"] + 4)
                self.assertTrue(row["quote"].strip())
        for definition in self.definitions.values():
            self.assertIn(definition["modbus_table"], TABLES)
            self.assertTrue(definition["evidence"])
            self.assertIn("access", definition)
            self.assertIn("default", definition)
            self.assertIn("type_encoding", definition)
            self.assertIn("value_range", definition)
            self.assertIn("applicability", definition)
            self.assertIn("non-U", definition["model_scope"])
            self.assertIs(type(definition["word_count_per_value"]), int)
            self.assertGreaterEqual(definition["word_count_per_value"], 0)
            for function in (
                definition["read_function_codes"] + definition["write_function_codes"]
            ):
                self.assertIn(function, {"0x01", "0x02", "0x03", "0x04",
                                         "0x05", "0x06", "0x0F", "0x10"})

    def test_document_conflicts_are_not_promoted(self):
        conflicts = {
            definition["id"] for definition in self.definitions.values()
            if definition["status"] == "conflict"
        }
        self.assertEqual(conflicts, {"ao_process", "ao_range_table", "ao_range_prose"})
        self.assertEqual(self.definitions["ao_range_table"]["wire_decimal_zero_based"], 4500)
        self.assertEqual(self.definitions["ao_range_prose"]["wire_decimal_zero_based"], 3500)
        self.assertEqual(self.definitions["ao_range_prose"]["read_function_codes"], [])
        self.assertNotIn("explicit_instances", self.definitions["ao_range_prose"])
        conflict_ids = {row["id"] for row in self.inventory["conflicts"]}
        self.assertEqual(len(conflict_ids), 12)
        for definition in self.definitions.values():
            self.assertIn(definition["status"], {"documented", "conflict"})
            self.assertFalse(definition["confidence"]["hardware_verified"])
            self.assertEqual(definition["confidence"]["document_extraction"], 1.0)
            for flag in ("runtime_enabled", "automatic_probe_allowed", "automatic_write_allowed"):
                self.assertIs(definition[flag], False)
            if definition["status"] == "conflict":
                self.assertIn("conflict_policy", definition)
            self.assertTrue(set(definition.get("conflict_ids", [])) <= conflict_ids)
        ao = self.definitions["ao_process"]["explicit_instances"][0]
        self.assertEqual(ao["vendor_reference_as_printed"], "3-0501")
        self.assertEqual(ao["vendor_reference_normalized"], "4-0501")

    def test_model_counts_and_non_u_filter_scope(self):
        symbols = self.inventory["model_code_pattern"]["known_count_symbols"]
        self.assertEqual(symbols, {"0": 0, "4": 4, "8": 8, "A": 16})
        for model in self.inventory["models"]:
            code = model["model"].removeprefix("M31-").removesuffix("G")
            self.assertEqual(len(code), 8)
            self.assertEqual(
                model["host_channels"],
                dict(zip(("DI", "AI", "DO", "AO"), (symbols[c] for c in code[4:]))),
            )
            self.assertNotIn("-U", model["model"])
        for name, address in (("di_filter", 0x0DA3), ("ai_filter", 0x0DA2)):
            row = self.definitions[name]
            self.assertEqual(row["kind"], "singleton")
            self.assertEqual(row["wire_decimal_zero_based"], address)
            self.assertIn("not per-channel", row["applicability"])
            self.assertEqual(row["word_count_per_value"], 1)
        u_rows = {row["name"]: row for row in load_csv("u-only-registers.csv")}
        self.assertEqual(u_rows["DI filter"]["address_hex"], "0x1388")
        self.assertEqual(u_rows["AI filter"]["address_hex"], "0x0FA0")
        self.assertNotIn(0x1388, {
            row["wire_decimal_zero_based"] for row in self.definitions.values()
        })
        self.assertNotIn(0x0FA0, {
            row["wire_decimal_zero_based"] for row in self.definitions.values()
        })

    def test_multiword_fields_and_family_strides(self):
        for name in ("ai_float", "ao_float"):
            row = self.definitions[name]
            self.assertEqual(row["word_count_per_value"], 2)
            self.assertEqual(row["address_stride"], 2)
        for definition in self.definitions.values():
            if definition["kind"] == "channel_family":
                stride = definition["address_stride"]
                width = max(1, definition["word_count_per_value"])
                self.assertEqual(stride, width)
                bounds = definition["family_bounds"]
                self.assertIsNone(bounds["channel_max_one_based"])
                self.assertEqual(bounds["documented_max_expansion_modules"], 16)
                self.assertTrue(bounds["guard_is_not_hardware_capacity"])
                self.assertEqual(len(definition["explicit_instances"]), 5)
                for instance in definition["explicit_instances"]:
                    self.assertEqual(
                        instance["wire_decimal_zero_based"],
                        definition["wire_decimal_zero_based"]
                        + (instance["channel_one_based"] - 1) * stride,
                    )
            if "occupied_wire_words" in definition:
                words = definition["occupied_wire_words"]
                self.assertEqual(len(words), definition["word_count_per_value"])
                self.assertEqual(
                    [word["wire_decimal_zero_based"] for word in words],
                    list(range(definition["wire_decimal_zero_based"],
                               definition["wire_decimal_zero_based"] + len(words))),
                )
        for name, width in (("mac", 3), ("local_ip", 2), ("subnet", 2),
                            ("gateway", 2), ("dns", 2), ("destination", 64),
                            ("expansion_fault_bitmap", 2)):
            self.assertEqual(self.definitions[name]["word_count_per_value"], width)

    def test_finite_host_ranges_exact_footprint_and_applicability(self):
        rows = load_csv("known-host-ranges.csv")
        self.assertEqual(len(rows), 38)
        actual_pairs = {(row["model"], row["definition_id"]) for row in rows}
        self.assertEqual(len(actual_pairs), 38)
        models = {model["model"]: model for model in self.inventory["models"]}
        expected_pairs = set()
        for definition in self.definitions.values():
            if definition["kind"] != "channel_family":
                continue
            channel_type = definition["applicability"]["channel_type"]
            applicable = {
                model["model"] for model in models.values()
                if model["host_channels"][channel_type] > 0
            }
            self.assertEqual(set(definition["applicability"]["host_models"]), applicable)
            expected_pairs.update((model, definition["id"]) for model in applicable)
        self.assertEqual(actual_pairs, expected_pairs)
        for row in rows:
            definition = self.definitions[row["definition_id"]]
            count = models[row["model"]]["host_channels"][
                definition["applicability"]["channel_type"]
            ]
            self.assertGreater(count, 0)
            self.assertEqual(int(row["host_channel_count"]), count)
            stride = definition["address_stride"]
            self.assertEqual(int(row["address_stride"]), stride)
            start = json.loads(row["start"])
            last_start = json.loads(row["last_value_start"])
            last_end = json.loads(row["last_value_end"])
            for address in (start, last_start, last_end):
                self.assert_address(address, definition["modbus_table"])
            base = definition["wire_decimal_zero_based"]
            width = max(1, definition["word_count_per_value"])
            self.assertEqual(start["wire_decimal_zero_based"], base)
            self.assertEqual(last_start["wire_decimal_zero_based"], base + (count - 1) * stride)
            self.assertEqual(last_end["wire_decimal_zero_based"], base + (count - 1) * stride + width - 1)
            self.assertEqual(row["status"], definition["status"])
            self.assertTrue(json.loads(row["evidence"]))
            self.assertNotEqual(row["definition_id"], "ao_range_prose")

    def test_runtime_core_and_device_catalog_coverage_without_io(self):
        aliases = self.inventory["runtime_catalog_aliases"]
        for spec in M31_REGISTER_CATALOG:
            key = aliases["core"].get(spec.key, spec.key)
            definition = self.definitions[key]
            self.assertEqual(spec.table, definition["modbus_table"])
            self.assertEqual(spec.address, definition["wire_decimal_zero_based"])
            if spec.words_per_value is not None:
                self.assertEqual(spec.words_per_value, definition["word_count_per_value"])
        for spec in DEVICE_REGISTER_CATALOG:
            key = aliases["device"].get(spec.key, spec.key)
            definition = self.definitions[key]
            self.assertEqual(definition["modbus_table"], "holding_registers")
            self.assertEqual(spec.address, definition["wire_decimal_zero_based"])
            self.assertEqual(spec.count, definition["word_count_per_value"])
            if spec.enumerations:
                self.assertEqual(
                    {code for code, _label in spec.enumerations},
                    {int(code) for code in definition["value_range"]},
                )
        self.assertEqual(len(DEVICE_REGISTER_CATALOG), 17)
        snapshot_words = {
            address for spec in DEVICE_READ_SPECS
            for address in range(spec.address, spec.address + spec.count)
        }
        self.assertEqual(self.definitions["negotiation_start"]["wire_decimal_zero_based"], 0x7585)
        self.assertNotIn(0x7585, snapshot_words)
        defined_module_words = {
            address for row in self.definitions.values()
            if row["kind"] == "singleton" and row["wire_decimal_zero_based"] >= 0x7530
            for address in range(row["wire_decimal_zero_based"],
                                 row["wire_decimal_zero_based"] + row["word_count_per_value"])
        }
        self.assertTrue(snapshot_words <= defined_module_words)
        for gap in (0x753F, 0x7540):
            self.assertNotIn(gap, defined_module_words)
            self.assertNotIn(gap, snapshot_words)

    def test_candidates_and_community_remain_separate_and_inert(self):
        candidates = self.hypotheses["candidates"]
        self.assertEqual({row["id"] for row in candidates}, {f"H{i}" for i in range(1, 7)})
        for row in candidates:
            self.assertTrue(row["status"].startswith(("candidate", "unknown")))
            self.assertTrue(row["alternative"])
            self.assertTrue(row["conflicts"])
            self.assertTrue(row["citations"])
            self.assertTrue(row["validation_needed"])
            self.assertEqual(row["support_counts"]["independent_device_observations"], 0)
            for flag in ("hardware_verified", "runtime_enabled",
                         "automatic_probe_allowed", "automatic_write_allowed"):
                self.assertIs(row[flag], False)
        self.assertTrue(set(self.definitions).isdisjoint(row["id"] for row in candidates))
        self.assertEqual(len(load_csv("u-only-registers.csv")), 64)
        self.assertEqual(len(load_csv("cross-model-comparison.csv")), 25)
        self.assertEqual(len(self.community["sources"]), 4)
        sources = {row["id"] for row in self.community["sources"]}
        self.assertEqual(len(self.community["register_evidence"]), 25)
        for row in self.community["register_evidence"]:
            self.assertIn(row["source"], sources)
            self.assertIn(row["category"], {"communityreported", "hypothesis"})
            self.assertEqual(int(row["address_hex"], 16), row["address_dec"])
            for flag in ("hardware_verified", "runtime_enabled",
                         "automatic_probe_allowed", "automatic_write_allowed"):
                self.assertIs(row[flag], False)
        self.assertTrue(any(
            "current project" in row["reason"]
            for row in self.community["excluded_or_not_independent"]
        ))
        definitions = {row["wire_decimal_zero_based"] for row in self.definitions.values()}
        for address in (0x0C1D, 0x0C1E, 0x0C1F, 0x0C20, 0x0C2C,
                        0x0C60, 0x0C70, 0x0C80, 0x0D80, 0x758A, 0x758B, 0x7590):
            self.assertNotIn(address, definitions)

    def test_u_register_csv_schema_and_array_limits(self):
        rows = load_csv("u-only-registers.csv")
        self.assertEqual(len({row["name"] for row in rows}), 64)
        for row in rows:
            self.assertIn(row["table"], {
                "coil", "discrete_input", "input_register", "holding_register",
            })
            self.assertTrue(row["model_scope"].startswith("U1"))
            self.assertEqual(row["source"], "U1")
            self.assertRegex(row["address_hex"], r"^0x[0-9A-F]{4}$")
            self.assertEqual(int(row["address_hex"], 16), int(row["address_decimal"]))
            self.assertGreater(int(row["stride_words"]), 0)
            width = 1 if row["width_words"] == "bit" else int(row["width_words"])
            self.assertGreater(width, 0)
            self.assertLessEqual(int(row["address_decimal"]) + width - 1, 65535)
            physical_pages = [int(page) for page in row["pdf_pages"].split("-")]
            printed_pages = [int(page) for page in row["printed_pages"].split("-")]
            self.assertEqual(physical_pages, [page + 4 for page in printed_pages])
            self.assertTrue(row["short_evidence"])
        by_name = {row["name"]: row for row in rows}
        self.assertEqual(by_name["Expansion model array"]["width_words"], "256")
        self.assertEqual(by_name["Expansion model array"]["stride_words"], "8")
        self.assertEqual(by_name["Expansion firmware array"]["width_words"], "32")
        self.assertEqual(by_name["Expansion storage capability"]["width_words"], "16")
        self.assertEqual(by_name["Expansion storage enable"]["width_words"], "16")

    def test_source_mirror_hash_and_revision_scope(self):
        sources = {row["id"]: row for row in self.comparison["sources"]}
        primary = self.inventory["source"]
        self.assertEqual(sources["S1"]["sha256"], primary["sha256"])
        self.assertEqual(sources[primary["id"]]["sha256"], primary["sha256"])
        self.assertEqual(primary["revision"], "1.1")
        self.assertEqual(sources["U1"]["revision"], "1.4")
        self.assertNotEqual(sources["N1"]["sha256"], primary["sha256"])
        for source in sources.values():
            self.assertTrue(source["url"].startswith("https://"))
            self.assertTrue(source["title"])
            if "sha256" in source:
                self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(self.comparison["counts"]["independent_hardware_verifications"], 0)
        self.assertTrue(self.comparison["source_relationships"])
        self.assertEqual(self.hypotheses["candidates"][0]["support_counts"]["independent_U_manual_lineages"], 1)

    def test_process_values_preserve_original_conversion_conflicts(self):
        rows = load_csv("analog-process-values.csv")
        self.assertEqual(len(rows), 40)
        self.assertEqual(len({row["table"] for row in rows}), 4)
        self.assertEqual(sum(row["status"] == "conflict" for row in rows), 2)
        for row in rows:
            value = int(row["hex_value_as_printed"], 16)
            signed = value if value < 0x8000 else value - 0x10000
            self.assertEqual(int(row["int16_computed_from_hex"]), signed)
            self.assertEqual(row["is_register_address"], "False")
            self.assertEqual(int(row["pdf_page_one_based"]), int(row["manual_page"]) + 4)

    def test_documentation_frames_offline_crc_and_tcp_length(self):
        examples = self.inventory["protocol_examples"]
        self.assertEqual(len(examples), 5)
        for example in examples:
            rtu = bytes.fromhex(example["rtu_as_printed"])
            tcp = bytes.fromhex(example["tcp_as_printed"])
            crc = 0xFFFF
            for byte in rtu[:-2]:
                crc ^= byte
                for _ in range(8):
                    crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
            self.assertEqual(int.from_bytes(rtu[-2:], "little"), crc)
            self.assertEqual(int.from_bytes(tcp[4:6], "big"), len(tcp) - 6)
            self.assertEqual(tcp[6:], rtu[:-2])
        self.assertTrue(
            self.comparison["frame_and_reference_findings"]["primary_examples"]["rtu_crc_matches"]
        )

    def test_portable_artifacts_and_linked_files(self):
        expected = {
            "README.md", "non-u-en-v1.1.json", "known-host-ranges.csv",
            "analog-process-values.csv", "source-comparison.json",
            "cross-model-comparison.csv", "u-only-registers.csv",
            "hypotheses.json", "community-evidence.json",
        }
        self.assertEqual({path.name for path in ROOT.iterdir()}, expected)
        for path in ROOT.iterdir():
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"/(?:home|tmp|var/tmp|Users)/|file://|[A-Za-z]:\\\\")
            self.assertNotIn("build_inventory.py", text)
            self.assertNotIn("verify_inventory.py", text)
            self.assertTrue(all(line == line.rstrip() for line in text.splitlines()))
        for document in (self.inventory, self.comparison, self.hypotheses, self.community):
            policy = document["evidence_policy"]
            for flag in ("hardware_verified", "runtime_enabled",
                         "automatic_probe_allowed", "automatic_write_allowed"):
                self.assertIs(policy[flag], False)
            for row in walk(document):
                if not isinstance(row, dict):
                    continue
                self.assertTrue({"local_pdf", "local_archive", "file", "text"}.isdisjoint(row))
                for key, value in row.items():
                    if key.endswith("_file"):
                        self.assertTrue((ROOT / value).is_file())
        for value in self.comparison["artifacts"].values():
            self.assertTrue((ROOT / value).is_file())
        for target in re.findall(
            r"\]\(([^)]+)\)", (ROOT / "README.md").read_text(encoding="utf-8"),
        ):
            if not target.startswith("https://"):
                self.assertTrue((ROOT / target).is_file(), target)


if __name__ == "__main__":
    unittest.main()
