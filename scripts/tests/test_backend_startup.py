"""DB-free tests: run with python -m unittest discover -s scripts/tests."""
import importlib.util
import asyncio
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "benchmark_backend_startup.py"


class StartupBenchmarkTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("startup_benchmark", SCRIPT)
        self.benchmark = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.benchmark)

    def test_child_environment_does_not_inherit_credentials(self):
        with patch.dict("os.environ", {"DATABASE_URL": "must-not-be-used",
                                      "SENTRY_DSN": "must-not-be-used"}):
            env = self.benchmark.child_environment()
        self.assertNotIn("SENTRY_DSN", env)
        self.assertNotIn("must-not-be-used", env.values())
        self.assertEqual(env["PYTHON_DOTENV_DISABLED"], "1")

    def test_slow_and_eager_imports_fail(self):
        failures = self.benchmark.failures_for(
            {"import_seconds": 20, "forbidden_modules": ["pandas"]}, 10
        )
        self.assertEqual(len(failures), 2)

    def test_fast_import_passes(self):
        self.assertEqual(self.benchmark.failures_for(
            {"import_seconds": 1, "forbidden_modules": []}, 10), [])

    def test_gate_is_separate_read_only_and_not_ready_fails(self):
        original = object()
        engine = SimpleNamespace(dispose=AsyncMock())
        db = SimpleNamespace(engine=original, _get_async_url=lambda: "unused",
                             init_pg_tables=AsyncMock(return_value={"schema_ready": False}))
        with patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=engine) as create:
            result = asyncio.run(self.benchmark.measure_schema_gate(db))
        self.assertIs(db.engine, original)
        engine.dispose.assert_awaited_once()
        db.init_pg_tables.assert_awaited_once()
        self.assertEqual(create.call_args.kwargs["connect_args"]["server_settings"]
                         ["default_transaction_read_only"], "on")
        self.assertGreater(result["schema_gate_seconds"], 0)
        result.update(import_seconds=1, forbidden_modules=[])
        self.assertIn("not ready", self.benchmark.failures_for(result, 10)[0])

    def test_gate_failure_propagates_and_disposes(self):
        original = object()
        engine = SimpleNamespace(dispose=AsyncMock())
        db = SimpleNamespace(engine=original, _get_async_url=lambda: "unused",
                             init_pg_tables=AsyncMock(side_effect=RuntimeError("gate failed")))
        with patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=engine):
            with self.assertRaisesRegex(RuntimeError, "gate failed"):
                asyncio.run(self.benchmark.measure_schema_gate(db))
        self.assertIs(db.engine, original)
        engine.dispose.assert_awaited_once()

    def test_timeout_fails_closed(self):
        with patch.object(self.benchmark.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired([], 1)):
            with self.assertRaisesRegex(RuntimeError, "exceeded"):
                self.benchmark.run_probe("server", 1)

    def test_direct_internal_schema_probe_is_rejected(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--probe", "server", "--schema-gate"],
            env={"PATH": os.environ.get("PATH", ""), "DATABASE_URL": "must-not-be-used"},
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--probe is internal", result.stderr)
        self.assertNotIn("must-not-be-used", result.stderr)

    def test_schema_target_rejects_deployments_and_app_database_alias(self):
        url = "postgresql://dummy:dummy@db:5432/benchmark"
        for env in (
            {},
            {"BENCHMARK_DATABASE_URL": url, "REPLIT_DEPLOYMENT": "1"},
            {"BENCHMARK_DATABASE_URL": url,
             "DATABASE_URL": "postgresql+asyncpg://other:other@db/benchmark?sslmode=require"},
        ):
            with self.subTest(env=env), self.assertRaises(ValueError):
                self.benchmark.validate_schema_target(env)
        self.assertEqual(self.benchmark.validate_schema_target(
            {"BENCHMARK_DATABASE_URL": url}), url)

    def test_subprocess_failure_is_reported_without_output_leak(self):
        with patch.object(self.benchmark.subprocess, "run",
                          return_value=subprocess.CompletedProcess([], 1, "secret", "secret")):
            with self.assertRaisesRegex(RuntimeError, "exited with status 1") as caught:
                self.benchmark.run_probe("server", 30)
        self.assertNotIn("secret", str(caught.exception))

    def test_probe_failure_includes_safe_exception_location_not_message(self):
        try:
            raise RuntimeError("postgresql://private:secret@example.invalid/db")
        except RuntimeError as exc:
            detail = self.benchmark.safe_probe_error(exc)
        self.assertEqual(detail["exception"], "RuntimeError")
        self.assertIn("test_backend_startup.py:", detail["location"])
        self.assertNotIn("secret", str(detail))
        self.assertNotIn("postgresql", str(detail))

    def test_missing_module_is_identified(self):
        detail = self.benchmark.safe_probe_error(
            ModuleNotFoundError("sensitive arbitrary message", name="resend"))
        self.assertEqual(detail["missing_module"], "resend")
        self.assertNotIn("sensitive", str(detail))

    def test_structured_failure_reaches_build_report(self):
        output = 'STARTUP_BENCHMARK_ERROR={"exception":"ImportError","location":"db.py:12"}\n'
        with patch.object(self.benchmark.subprocess, "run",
                          return_value=subprocess.CompletedProcess([], 1, output, "secret")):
            with self.assertRaisesRegex(RuntimeError, "ImportError.*db.py:12") as caught:
                self.benchmark.run_probe("dependencies", 30)
        self.assertNotIn("secret", str(caught.exception))

    def test_full_app_and_dependencies_in_fresh_processes(self):
        for module in ("dependencies", "server"):
            with self.subTest(module=module):
                result = self.benchmark.run_probe(module, 60)
                self.assertEqual(self.benchmark.failures_for(result, 30), [])
                self.assertGreater(result["process_seconds"], result["import_seconds"])
                self.assertIsNone(result["schema_gate_seconds"])
                if module == "server":
                    self.assertGreater(result["route_count"], 100)