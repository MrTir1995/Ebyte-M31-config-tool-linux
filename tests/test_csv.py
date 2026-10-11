from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
import uuid

from m31tool.app import load_csv, save_csv


class CSVTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(__file__).parent / (".csv-test-" + uuid.uuid4().hex)
        self.directory.mkdir()
        self.addCleanup(shutil.rmtree, self.directory)
        self.path = self.directory / "values.csv"

    def write(self, content):
        self.path.write_text(content, encoding="utf-8")

    def test_all_types_round_trip(self):
        rows = [
            ("Coils", 0, 1),
            ("Discrete inputs", 65535, 0),
            ("Holding registers", 500, 65535),
            ("Input registers", 1000, 1234),
        ]
        save_csv(self.path, rows)
        self.assertEqual(load_csv(self.path), rows)
        self.assertEqual(
            self.path.read_text(encoding="utf-8").splitlines()[0],
            "object_type,address,value",
        )

    def test_empty_export_is_valid_empty_import(self):
        save_csv(self.path, [])
        self.assertEqual(load_csv(self.path), [])

    def test_bom_and_hexadecimal_values(self):
        self.write(
            "\ufeffobject_type,address,value\nInput registers,0x03E8,0xFFFF\n"
        )
        self.assertEqual(load_csv(self.path), [("Input registers", 1000, 65535)])

    def test_invalid_headers(self):
        for content in (
            "",
            "address,object_type,value\n",
            "object_type,address\n",
            "object_type,address,value,extra\n",
        ):
            with self.subTest(content=content):
                self.write(content)
                with self.assertRaises(ValueError):
                    load_csv(self.path)

    def test_missing_extra_and_invalid_columns(self):
        for row in (
            "Input registers,0",
            "Input registers,0,1,extra",
            "Unknown,0,1",
            "Coils,-1,1",
            "Coils,65536,1",
            "Coils,0,2",
            "Discrete inputs,0,-1",
            "Holding registers,0,65536",
            "Input registers,0,-1",
            "Input registers,0,1.5",
            "Input registers,not-an-address,1",
            "Input registers,,1",
            "Input registers,0,",
        ):
            with self.subTest(row=row):
                self.write("object_type,address,value\n" + row + "\n")
                with self.assertRaises(ValueError):
                    load_csv(self.path)

    def test_partial_valid_file_is_rejected_as_a_whole(self):
        self.write(
            "object_type,address,value\nCoils,0,1\nInput registers,0,invalid\n"
        )
        with self.assertRaises(ValueError):
            load_csv(self.path)

    def test_row_limit(self):
        self.write("object_type,address,value\n" + "Coils,0,1\n" * 100_001)
        with self.assertRaisesRegex(ValueError, "100"):
            load_csv(self.path)

    @patch("m31tool.app.ModbusSession")
    def test_import_and_export_do_not_create_a_device_session(self, session):
        rows = [("Holding registers", 0, 42)]
        save_csv(self.path, rows)
        self.assertEqual(load_csv(self.path), rows)
        session.assert_not_called()

    def test_missing_file_reports_io_error(self):
        with self.assertRaises(FileNotFoundError):
            load_csv(self.path)


if __name__ == "__main__":
    unittest.main()
