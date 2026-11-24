from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]

PYTHON_IMAGE = (
    "python:3.13-slim@sha256:"
    "f82c96458eedc847b233e582eb31336f4954b39cae020b6dcf5b3ed0e5cbcd74"
)
DOCKER_IMAGE = (
    "docker:28.5.1-cli@sha256:"
    "9190b0613792e658a7783cf14b2d5ace5941bb68ede7276922ea36ee457d76ad"
)


class CISourcePortabilityTests(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_e7_ci_uses_official_pinned_images(self):
        workflow = self.read(".github/workflows/e7-b4-gate.yml")
        self.assertIn(
            f"--build-arg BASE_IMAGE={PYTHON_IMAGE}",
            workflow,
        )
        self.assertIn(
            f"--build-arg DOCKER_CLI_IMAGE={DOCKER_IMAGE}",
            workflow,
        )

    def test_e8_ci_uses_official_sources(self):
        workflow = self.read(".github/workflows/e8e10.yml")
        self.assertIn(
            f"--build-arg BASE_IMAGE={PYTHON_IMAGE}",
            workflow,
        )
        self.assertIn(
            "--build-arg USE_TUNA_MIRROR=0",
            workflow,
        )
        self.assertIn(
            "--build-arg PIP_INDEX_URL=https://pypi.org/simple",
            workflow,
        )

    def test_e8_local_defaults_remain_explicit(self):
        dockerfile = self.read(
            "labs/e8e10/environment/services/buildchecker/Dockerfile"
        )
        self.assertIn("ARG USE_TUNA_MIRROR=1", dockerfile)
        self.assertIn(
            "ARG PIP_INDEX_URL="
            "https://pypi.tuna.tsinghua.edu.cn/simple",
            dockerfile,
        )
        self.assertIn(
            'if [ "$USE_TUNA_MIRROR" = "1" ]',
            dockerfile,
        )
        self.assertIn(
            'elif [ "$USE_TUNA_MIRROR" != "0" ]',
            dockerfile,
        )
        self.assertIn(
            '--index-url "${PIP_INDEX_URL}"',
            dockerfile,
        )


if __name__ == "__main__":
    unittest.main()
