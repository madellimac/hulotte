import tempfile
import subprocess
import unittest
from pathlib import Path

from framework.catalog import load_catalog
from framework.generator import generate_cpp
from framework.pipeline import load_pipeline
from framework.project import build_project


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "aff3ct_rs_project"


class Aff3ctCatalogTests(unittest.TestCase):
    def test_generates_shared_rs_resource_and_aff3ct_bindings(self):
        pipeline = load_pipeline(FIXTURE / "pipeline.yaml")
        catalog = load_catalog(FIXTURE / "catalog" / "modules.yaml")
        source = generate_cpp(pipeline, catalog)

        self.assertEqual(source.count("RS_polynomial_generator polynomial"), 1)
        self.assertIn("Encoder_RS<int> encoder(5, 7, polynomial);", source)
        self.assertIn("Decoder_RS_std<int, float> decoder(5, 7, polynomial);", source)
        self.assertIn(
            "encoder[enc::tsk::encode][(int)enc::sck::encode::X_N] = "
            "decoder[dec::tsk::decode_hiho][(int)dec::sck::decode_hiho::Y_N];",
            source,
        )

    def test_rs_pipeline_is_loadable(self):
        pipeline = load_pipeline(FIXTURE / "pipeline.yaml")
        self.assertEqual(pipeline.resources["polynomial"].parameters["t"], 1)

    @unittest.skipUnless(
        (ROOT / "vendor" / "aff3ct" / "include" / "aff3ct.hpp").is_file()
        and bool(list((ROOT / "vendor" / "aff3ct" / "build" / "lib").glob("libaff3ct*.a")))
        and (ROOT / "vendor" / "streampu" / "build" / "lib" / "cpptrace" / "lib" / "libcpptrace.a").is_file(),
        "local AFF3CT and cpptrace builds are not available",
    )
    def test_builds_and_runs_rs_fixture(self):
        executable = build_project(
            FIXTURE,
            streampu_root=ROOT / "vendor" / "streampu",
            aff3ct_root=ROOT / "vendor" / "aff3ct",
        )
        result = subprocess.run([str(executable)], check=False)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
