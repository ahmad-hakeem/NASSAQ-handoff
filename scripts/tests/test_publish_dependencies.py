"""Exercise the build's install command without installing packages or using a DB."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PublishDependencyTests(unittest.TestCase):
    def test_install_uses_runtime_python_without_workspace_redirects(self):
        build = (ROOT / "build.sh").read_text()
        section = build.split('echo "Installing backend dependencies..."', 1)[1]
        section = section.split("# Replit Publish", 1)[0]
        section = "\n".join(line for line in section.splitlines()
                            if not line.startswith("cd "))
        with tempfile.TemporaryDirectory() as directory:
            for name in ("python", "pip"):
                stub = Path(directory) / name
                stub.write_text(
                    f"#!{sys.executable}\n"
                    "import json, os, sys\n"
                    "print(json.dumps({'exe':os.path.basename(sys.argv[0]),"
                    "'args':sys.argv[1:], 'redirects':[k for k in "
                    "('PIP_TARGET','PIP_PREFIX','PIP_USER','PYTHONPATH','PYTHONHOME') "
                    "if k in os.environ]}))\n")
                stub.chmod(0o755)
            env = {"PATH": directory + ":/usr/bin:/bin"}
            env.update({key: "workspace-redirect" for key in
                        ("PIP_TARGET", "PIP_PREFIX", "PIP_USER", "PYTHONPATH", "PYTHONHOME")})
            # Stub shebang uses the workspace interpreter, so do not poison
            # PYTHONHOME itself; the build must still explicitly unset it.
            env.pop("PYTHONHOME")
            result = subprocess.run(["bash", "-e", "-c", section], env=env,
                                    text=True, capture_output=True, check=True)
            invocation = json.loads(result.stdout.strip())
        self.assertEqual(invocation["exe"], "python")
        self.assertEqual(invocation["args"][:4], ["-I", "-m", "pip", "install"])
        self.assertEqual(invocation["redirects"], [])
        self.assertIn("--ignore-installed", invocation["args"])

    def test_publish_requirements_include_workspace_only_runtime_packages(self):
        requirements = (ROOT / "backend/requirements.txt").read_text().lower()
        for package in ("openpyxl", "pyotp", "resend", "webauthn"):
            with self.subTest(package=package):
                self.assertRegex(requirements, rf"(?m)^{package}>=")