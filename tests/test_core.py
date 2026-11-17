import json
from pathlib import Path
import tempfile
import unittest

from mcp_catalogue_diff.core import CatalogueError, compare_catalogues, load_catalogue


class CatalogueDiffTests(unittest.TestCase):
    def test_no_drift_when_object_keys_are_reordered(self):
        approved = [{"name": "a", "description": "x", "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}}}]
        live = [{"inputSchema": {"properties": {"q": {"type": "string"}}, "type": "object"}, "description": "x", "name": "a"}]
        report = compare_catalogues(approved, live)
        self.assertFalse(report.has_drift)

    def test_detects_added_removed_and_changed(self):
        approved = [
            {"name": "a", "description": "before", "inputSchema": {}},
            {"name": "removed", "description": "x", "inputSchema": {}},
        ]
        live = [
            {"name": "a", "description": "after", "inputSchema": {"type": "object"}},
            {"name": "added", "description": "x", "inputSchema": {}},
        ]
        report = compare_catalogues(approved, live)
        self.assertEqual(report.added, ["added"])
        self.assertEqual(report.removed, ["removed"])
        self.assertTrue(report.changed[0].description_changed)
        self.assertTrue(report.changed[0].input_schema_changed)

    def test_detects_order_change_separately(self):
        a = {"name": "a", "description": "", "inputSchema": {}}
        b = {"name": "b", "description": "", "inputSchema": {}}
        report = compare_catalogues([a, b], [b, a])
        self.assertTrue(report.order_changed)
        self.assertTrue(report.has_drift)
        self.assertEqual(report.changed, [])

    def test_rejects_duplicate_names(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text(json.dumps({"tools": [{"name": "a"}, {"name": "a"}]}), encoding="utf-8")
            with self.assertRaises(CatalogueError):
                load_catalogue(path)

    def test_array_order_inside_schema_is_preserved(self):
        approved = [{"name": "a", "inputSchema": {"enum": ["one", "two"]}}]
        live = [{"name": "a", "inputSchema": {"enum": ["two", "one"]}}]
        report = compare_catalogues(approved, live)
        self.assertTrue(report.changed[0].input_schema_changed)


if __name__ == "__main__":
    unittest.main()
