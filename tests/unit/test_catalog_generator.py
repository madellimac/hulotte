import tempfile
import unittest
from pathlib import Path

from framework import load_pipeline
from framework.catalog import CatalogError, load_catalog
from framework.generator import GenerationError, generate_cpp


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "framework" / "catalog" / "modules.yaml"


PIPELINE = """
modules:
  source:
    type: streampu
    catalog: source_random_int
    parameters: {frame_size: 16}
    sockets:
      generate:
        outputs:
          out_data: {type: int32}
  filter:
    type: custom
    catalog: custom_passthrough
    parameters: {frame_size: 16}
    sockets:
      process:
        inputs:
          in: {type: int32}
        outputs:
          out: {type: int32}
connections:
  - from: source.generate.out_data
    to: filter.process.in
"""


class CatalogGeneratorTests(unittest.TestCase):
    def test_catalog_resolves_known_module(self):
        catalog = load_catalog(CATALOG_PATH)
        self.assertEqual(catalog.resolve("source_random_int").class_name, "spu::module::Source_random<int>")

    def test_catalog_rejects_unknown_module(self):
        catalog = load_catalog(CATALOG_PATH)
        with self.assertRaises(CatalogError):
            catalog.resolve("missing")

    def test_generates_deterministic_cpp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pipeline.yaml"
            path.write_text(PIPELINE, encoding="utf-8")
            pipeline = load_pipeline(path)

        catalog = load_catalog(CATALOG_PATH)
        first = generate_cpp(pipeline, catalog)
        second = generate_cpp(pipeline, catalog)
        self.assertEqual(first, second)
        self.assertIn("Source_random<int> source(16);", first)
        self.assertLess(first.index("Source_random<int> source"), first.index("CustomModule filter"))
        self.assertIn('first_tasks.push_back(&source("generate"));', first)
        self.assertNotIn('first_tasks.push_back(&filter("process"));', first)
        self.assertIn('source["generate::out_data"] = filter["process::in"];', first)

    def test_missing_constructor_parameter_fails_before_write(self):
        invalid = PIPELINE.replace("parameters: {frame_size: 16}", "parameters: {}", 1)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pipeline.yaml"
            path.write_text(invalid, encoding="utf-8")
            pipeline = load_pipeline(path)

        with self.assertRaises(GenerationError):
            generate_cpp(pipeline, load_catalog(CATALOG_PATH))


if __name__ == "__main__":
    unittest.main()
