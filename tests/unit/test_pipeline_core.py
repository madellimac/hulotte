import tempfile
import unittest
from pathlib import Path

from framework import (
    BlockCanvas,
    BlockCanvasValidationError,
    CanvasBlock,
    CanvasConnection,
    CanvasPort,
    PipelineCycleError,
    PipelineValidationError,
    load_pipeline,
    validate_pipeline,
)
from framework.gui.backend.services import GraphEditorService


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

    def test_exposes_ui_graph_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pipeline.yaml"
            path.write_text(
                VALID_PIPELINE.replace(
                    "  filter:\n    type: custom\n    class: Filter\n    sockets:\n      process:\n        inputs:\n          in: {type: int32, frame_size: 16}\n        outputs:\n          out: {type: int32, frame_size: 16}\n",
                    "  filter:\n    type: custom\n    class: Filter\n    ports:\n      inputs:\n        - name: in\n          type: int32\n          frame_size: 16\n      outputs:\n        - name: out\n          type: int32\n          frame_size: 16\n    sockets:\n      process:\n        inputs:\n          in: {type: int32, frame_size: 16}\n        outputs:\n          out: {type: int32, frame_size: 16}\n",
                    1,
                ),
                encoding="utf-8",
            )
            pipeline = load_pipeline(path)

        graph = pipeline.ui_graph()
        self.assertEqual(graph["blocks"][1]["ports"]["inputs"][0]["name"], "in")
        self.assertEqual(graph["connections"][0]["from"], "source.generate.out_data")

    def test_block_canvas_validates_compatible_ports(self):
        source_block = CanvasBlock(
            block_id="source",
            kind="streampu",
            x=0,
            y=0,
            inputs=(),
            outputs=(CanvasPort("out_data", "output", "int32", 16),),
        )
        filter_block = CanvasBlock(
            block_id="filter",
            kind="custom",
            x=240,
            y=0,
            inputs=(CanvasPort("in", "input", "int32", 16),),
            outputs=(CanvasPort("out", "output", "int32", 16),),
        )
        canvas = BlockCanvas(blocks={"source": source_block, "filter": filter_block}, connections=())

        canvas.validate_connection(CanvasConnection("source", "out_data", "filter", "in"))

        incompatible_block = CanvasBlock(
            block_id="bad_filter",
            kind="custom",
            x=240,
            y=120,
            inputs=(CanvasPort("in", "input", "uint8", 16),),
            outputs=(CanvasPort("out", "output", "uint8", 16),),
        )
        canvas.blocks["bad_filter"] = incompatible_block
        with self.assertRaises(BlockCanvasValidationError):
            canvas.validate_connection(CanvasConnection("source", "out_data", "bad_filter", "in"))

    def test_block_canvas_can_add_and_connect_blocks(self):
        source_block = CanvasBlock(
            block_id="source",
            kind="streampu",
            outputs=(CanvasPort("out_data", "output", "int32", 16),),
        )
        filter_block = CanvasBlock(
            block_id="filter",
            kind="custom",
            inputs=(CanvasPort("in", "input", "int32", 16),),
            outputs=(CanvasPort("out", "output", "int32", 16),),
        )
        canvas = BlockCanvas(blocks={}, connections=())
        canvas.add_block(source_block)
        canvas.add_block(filter_block)
        canvas.connect(
            CanvasConnection("source", "out_data", "filter", "in", source_task="generate", target_task="process")
        )

        self.assertEqual(len(canvas.connections), 1)
        payload = canvas.serialize()
        self.assertEqual(payload["connections"][0]["from"], "source.generate.out_data")
        self.assertEqual(payload["connections"][0]["to"], "filter.process.in")

    def test_graph_editor_service_builds_canvas_from_catalog(self):
        service = GraphEditorService()
        palette = service.palette()
        self.assertIn("source_random_int", {item["catalog_id"] for item in palette})

        canvas = service.new_canvas()
        service.add_block(canvas, "source_random_int", "source")
        service.add_block(canvas, "custom_passthrough", "filter")
        service.connect(canvas, "source", "generate", "out_data", "filter", "process", "in")

        payload = service.serialize(canvas)
        self.assertEqual(payload["connections"][0]["from"], "source.generate.out_data")
        self.assertEqual(payload["connections"][0]["to"], "filter.process.in")

    def test_block_canvas_serializes_to_pipeline(self):
        source_block = CanvasBlock(
            block_id="source",
            kind="streampu",
            task="generate",
            outputs=(CanvasPort("out_data", "output", "int32", 16),),
        )
        filter_block = CanvasBlock(
            block_id="filter",
            kind="custom",
            task="process",
            inputs=(CanvasPort("in", "input", "int32", 16),),
            outputs=(CanvasPort("out", "output", "int32", 16),),
        )
        canvas = BlockCanvas(
            blocks={"source": source_block, "filter": filter_block},
            connections=(
                CanvasConnection("source", "out_data", "filter", "in", source_task="generate", target_task="process")
            ),
        )

        pipeline = canvas.to_pipeline()
        self.assertEqual(pipeline["connections"][0]["from"], "source.generate.out_data")
        self.assertEqual(pipeline["connections"][0]["to"], "filter.process.in")
        self.assertIn("out_data", pipeline["modules"]["source"]["sockets"]["generate"]["outputs"])

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
