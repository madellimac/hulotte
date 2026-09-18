import tempfile
import unittest
from pathlib import Path

from framework import PipelineCycleError, PipelineValidationError, load_pipeline, validate_pipeline


VALID_PIPELINE = """
modules:
  source:
    type: streampu
    class: spu::module::Source_random
    sockets:
      generate:
        outputs:
          out_data: {type: int32, frame_size: 16}
  filter:
    type: custom
    class: Filter
    sockets:
      process:
        inputs:
          in: {type: int32, frame_size: 16}
        outputs:
          out: {type: int32, frame_size: 16}
connections:
  - from: source.generate.out_data
    to: filter.process.in
"""


class PipelineCoreTests(unittest.TestCase):
    def test_loads_and_validates_pipeline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pipeline.yaml"
            path.write_text(VALID_PIPELINE, encoding="utf-8")
            pipeline = load_pipeline(path)

        validate_pipeline(
            pipeline,
            capabilities={"streampu": True, "custom": True},
            require_source=True,
        )
        self.assertEqual(set(pipeline.modules), {"source", "filter"})

    def test_rejects_duplicate_input(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pipeline.yaml"
            path.write_text(
                VALID_PIPELINE + "  - from: source.generate.out_data\n    to: filter.process.in\n",
                encoding="utf-8",
            )
            pipeline = load_pipeline(path)

        with self.assertRaises(PipelineValidationError) as context:
            validate_pipeline(pipeline)
        self.assertIn("connected more than once", str(context.exception))

    def test_rejects_incompatible_socket_type(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pipeline.yaml"
            path.write_text(VALID_PIPELINE.replace("type: int32, frame_size: 16", "type: uint8, frame_size: 16", 1), encoding="utf-8")
            pipeline = load_pipeline(path)

        with self.assertRaises(PipelineValidationError) as context:
            validate_pipeline(pipeline)
        self.assertIn("incompatible socket types", str(context.exception))

    def test_rejects_disabled_capability(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pipeline.yaml"
            path.write_text(VALID_PIPELINE, encoding="utf-8")
            pipeline = load_pipeline(path)

        with self.assertRaises(PipelineValidationError) as context:
            validate_pipeline(pipeline, capabilities={"streampu": True, "custom": False})
        self.assertIn("disabled capability 'custom'", str(context.exception))

    def test_orders_modules_from_connections(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pipeline.yaml"
            path.write_text(VALID_PIPELINE, encoding="utf-8")
            pipeline = load_pipeline(path)

        self.assertEqual(pipeline.topological_order(), ("source", "filter"))
        self.assertEqual(pipeline.source_modules(), ("source",))

    def test_rejects_cycles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pipeline.yaml"
            path.write_text(
                VALID_PIPELINE.replace(
                    "  - from: source.generate.out_data\n    to: filter.process.in\n",
                    "  - from: source.generate.out_data\n    to: filter.process.in\n"
                    "  - from: filter.process.out\n    to: source.generate.out_data\n",
                ),
                encoding="utf-8",
            )
            pipeline = load_pipeline(path)

        with self.assertRaises(PipelineCycleError):
            pipeline.topological_order()


if __name__ == "__main__":
    unittest.main()
