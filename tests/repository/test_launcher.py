"""Exercise actual checker launch admission without an engine or host effects."""

from tools.container_guard import require_container

require_container()

import os
import pty
import select
import signal
import time
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.repository.quality.sources import ROOT


class LauncherTests(unittest.TestCase):
    def test_linux_idmap_preview_reuses_checker_isolation_and_selects_package(self):
        result = subprocess.run(
            ["bash", "tools/repository.sh", "--print", "tests/unit/linux-idmap"],
            cwd=ROOT,
            env=os.environ | {"CONTAINER_TOOLS_SELECTED_DOCKER_ENDPOINT": "unix:///fixture.sock"},
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)
        arguments = shlex.split(result.stdout.splitlines()[-1])
        self.assertIn("PYTHONPATH=/workspace:/workspace/packages/linux-idmap/src", arguments)
        self.assertEqual(
            ["discover", "-s", "packages/linux-idmap/tests", "-t", "packages/linux-idmap/tests",
             "-p", "test*.py", "-v"],
            arguments[-8:],
        )
        for grant in ("--init", "--network=none", "--read-only", "--cap-drop=ALL", "--pull=never"):
            self.assertIn(grant, arguments)
        self.assertNotIn("--privileged", arguments)
        self.assertFalse(any("docker.sock" in item for item in arguments if item.startswith("type=bind,")))

    def test_preview_ignores_ambient_engine_and_make_overrides(self):
        environment = os.environ | {
            "DOCKER_HOST": "tcp://unreviewed.invalid:2375",
            "DOCKER_CONTEXT": "default",
            "DOCKER_CONFIG": "/unreviewed",
            "COMPOSE_FILE": "unreviewed.yml",
            "MAKEFLAGS": "SHELL=malicious .DEFAULT_GOAL=unreviewed",
            "PATH": f"{ROOT / 'tests/repository/fixtures/docker-context'}:{os.environ['PATH']}",
        }
        result = subprocess.run(
            ["make", "--no-print-directory", "tests/repository/command", "DOCKER_CONTEXT=default"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)
        arguments = shlex.split(result.stdout.splitlines()[-1])
        self.assertNotIn("unreviewed", " ".join(arguments))
        self.assertEqual("env", arguments[0])
        self.assertIn("DOCKER_HOST", arguments)
        self.assertIn("unix:///tmp/selected-default.sock", arguments)
        self.assertIn("--pull=never", arguments)
        self.assertIn("--network=none", arguments)
        self.assertNotIn("--privileged", arguments)

    def test_missing_context_without_terminal_refuses_before_engine_use(self):
        environment = os.environ | {"DOCKER_CONTEXT": "unreviewed", "CONTAINER_TOOLS_SELECTED_DOCKER_ENDPOINT": "unix:///tmp/poison.sock", "DOCKER_CONTEXT_INPUT_ORIGIN": "command line", "DOCKER_CONTEXT_INPUT": "local-test", "MAKELEVEL": "1"}
        result = subprocess.run(
            ["make", "--no-print-directory", "tests/repository/command"],
            cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, start_new_session=True,
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("DOCKER_CONTEXT", result.stderr)
        self.assertNotIn("docker --config", result.stdout)

    def test_selected_context_is_resolved_to_local_socket_and_remote_is_refused(self):
        directory = ROOT / "tests/repository/fixtures/docker-context"
        env = os.environ | {"PATH": f"{directory}:{os.environ['PATH']}", "DOCKER_CONTEXT": "local-test", "CONTAINER_TOOLS_SELECTED_DOCKER_ENDPOINT": "unix:///tmp/poison.sock", "MAKELEVEL": "1"}
        command = ["make", "--no-print-directory", "tests/repository/command", "DOCKER_CONTEXT=local-test"]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, msg=result.stderr)
        self.assertIn("unix:///run/user/1000/docker.sock", result.stdout)
        self.assertNotIn("unix:///tmp/poison.sock", result.stdout)
        command[-1] = "DOCKER_CONTEXT=remote-test"
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("ssh://example.invalid", result.stdout)

    def test_interactive_menu_offers_only_local_contexts(self):
        fixture = ROOT / "tests/repository/fixtures/docker-context"
        environment = {key: value for key, value in os.environ.items()
                       if key not in {"DOCKER_CONTEXT_INPUT_ORIGIN", "DOCKER_CONTEXT_INPUT", "CONTAINER_TOOLS_SELECTED_DOCKER_CONTEXT", "CONTAINER_TOOLS_SELECTED_DOCKER_ENDPOINT"}}
        environment["PATH"] = f"{fixture}:{os.environ['PATH']}"
        pid, terminal = pty.fork()
        if pid == 0:
            os.chdir(ROOT)
            os.execvpe("make", ["make", "--no-print-directory", "tests/repository/command"], environment)
        output = b""
        sent = False
        deadline = time.monotonic() + 10
        try:
            while time.monotonic() < deadline:
                readable, _, _ = select.select([terminal], [], [], 0.2)
                if readable:
                    try:
                        part = os.read(terminal, 4096)
                    except OSError:
                        break
                    output += part
                    if not sent and b"Choice [" in output:
                        os.write(terminal, b"1\n")
                        sent = True
            if not sent:
                os.kill(pid, signal.SIGKILL)
            _, status = os.waitpid(pid, 0)
        finally:
            os.close(terminal)
        self.assertTrue(sent, msg=output.decode(errors="replace"))
        self.assertTrue(os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0, msg=output.decode(errors="replace"))
        self.assertIn(b"local-test", output)
        self.assertNotIn(b"remote-test", output)
        self.assertIn(b"--host unix:///run/user/1000/docker.sock", output)

    def test_make_introspection_has_no_docker_side_effects(self):
        fixture = ROOT / "tests/repository/fixtures/docker-context"
        for arguments in (
            ("-qp", "checks/base-image/download"),
            ("-qp", "tests/repository/command"),
            ("--question", "tests"),
            ("--dry-run", "checks/base-image/download"),
            ("--dry-run", "checks/prepare"),
            ("--dry-run", "package/build"),
            ("--dry-run", "tests"),
            ("--dry-run", "publish/prepare"),
        ):
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as directory:
                log = Path(directory) / "inspections"
                environment = os.environ | {"PATH": f"{fixture}:{os.environ['PATH']}",
                    "FAKE_CONTEXT_LOG": str(log)}
                for name in ("CONTAINER_TOOLS_SELECTED_DOCKER_ENDPOINT",
                             "DOCKER_CONTEXT_INPUT_ORIGIN", "DOCKER_CONTEXT_INPUT"):
                    environment.pop(name, None)
                result = subprocess.run(
                    ["make", "--no-print-directory", *arguments],
                    cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
                    start_new_session=True, capture_output=True, text=True,
                    check=False, timeout=8,
                )
                self.assertIn(result.returncode, (0, 1), result.stderr)
                self.assertNotIn("Select a local Docker context (no default)", result.stderr)
                self.assertFalse(log.exists(), f"Make discovery inspected Docker: {arguments}")

    def test_interactive_database_query_does_not_open_docker_menu(self):
        # Completion interrogates Make's target database with a live terminal.
        fixture = ROOT / "tests/repository/fixtures/docker-context"
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "inspections"
            environment = os.environ | {"PATH": f"{fixture}:{os.environ['PATH']}",
                "FAKE_CONTEXT_LOG": str(log)}
            for name in ("CONTAINER_TOOLS_SELECTED_DOCKER_ENDPOINT",
                         "DOCKER_CONTEXT_INPUT_ORIGIN", "DOCKER_CONTEXT_INPUT"):
                environment.pop(name, None)
            pid, terminal = pty.fork()
            if pid == 0:
                os.chdir(ROOT)
                os.execvpe("make", ["make", "--no-print-directory", "-qp",
                                    "checks/base-image/download"], environment)
            received = bytearray()
            status = None
            deadline = time.monotonic() + 6
            try:
                while time.monotonic() < deadline:
                    if select.select([terminal], [], [], 0.1)[0]:
                        try:
                            received.extend(os.read(terminal, 65536))
                        except OSError:
                            pass
                    finished, candidate = os.waitpid(pid, os.WNOHANG)
                    if finished:
                        status = candidate
                        break
                if status is None:
                    os.killpg(pid, signal.SIGKILL)
                    os.waitpid(pid, 0)
            finally:
                os.close(terminal)
            self.assertIsNotNone(status, "Make target discovery blocked on interactive input")
            self.assertTrue(os.WIFEXITED(status), received[-2000:].decode(errors="replace"))
            self.assertNotIn(b"Select a local Docker context (no default)", received)
            self.assertNotIn(b"Choice [", received)
            self.assertFalse(log.exists(), "Make database inspection called Docker")

    def test_tests_aggregate_resolves_context_once_at_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tools").mkdir()
            shutil.copyfile(ROOT / "Makefile", root / "Makefile")
            shutil.copyfile(ROOT / "tools/docker_context.sh", root / "tools/docker_context.sh")
            (root / "tools/repository.sh").write_text(
                'source tools/docker_context.sh; select_docker_context\n'
                'printf "%s %s\n" "$1" "$CONTAINER_TOOLS_SELECTED_DOCKER_ENDPOINT" >> "$FAKE_TEST_LOG"\n'
            )
            inspected = root / "inspections"
            logged = root / "suites"
            fixture = ROOT / "tests/repository/fixtures/docker-context"
            environment = os.environ | {"PATH": f"{fixture}:{os.environ['PATH']}",
                "FAKE_CONTEXT_LOG": str(inspected), "FAKE_TEST_LOG": str(logged)}
            result = subprocess.run(
                ["make", "--no-print-directory", "tests", "DOCKER_CONTEXT=local-test"],
                cwd=root, env=environment, capture_output=True, text=True,
                check=False, timeout=8,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(["inspect"], inspected.read_text().splitlines())
            self.assertEqual([
                "tests/repository unix:///run/user/1000/docker.sock",
                "tests/unit/linux-idmap unix:///run/user/1000/docker.sock",
            ], logged.read_text().splitlines())

    def test_make_passes_selected_endpoint_to_checker_prepare(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "tools", root / "tools")
            shutil.copyfile(ROOT / "Makefile", root / "Makefile")
            (root / "tools/checker.sh").write_text(
                'source tools/docker_context.sh; select_docker_context\n'
                'printf "selected=%s\n" "$CONTAINER_TOOLS_SELECTED_DOCKER_ENDPOINT"\n'
            )
            log = root / "context-inspections"
            fixture = ROOT / "tests/repository/fixtures/docker-context"
            env = os.environ | {"PATH": f"{fixture}:{os.environ['PATH']}", "FAKE_CONTEXT_LOG": str(log)}
            result = subprocess.run(
                ["make", "--no-print-directory", "checks/prepare", "DOCKER_CONTEXT=local-test"],
                cwd=root, env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(0, result.returncode, msg=result.stderr)
            self.assertIn("selected=unix:///run/user/1000/docker.sock", result.stdout)
            self.assertEqual(["inspect"], log.read_text().splitlines())

    def test_preview_discovers_new_public_roots_and_rejects_hidden_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("tools", "requirements", "containers"):
                shutil.copytree(ROOT / name, root / name)
            (root / "future-source").mkdir()
            (root / ".work").mkdir()
            (root / ".aws").mkdir()
            launcher = root / "tools/repository.sh"
            launcher.write_bytes((ROOT / "tools/repository.sh").read_bytes())
            environment = os.environ | {"CONTAINER_TOOLS_SELECTED_DOCKER_ENDPOINT": "unix:///var/run/docker.sock"}
            command = ["bash", str(launcher), "--print", "tests/repository"]
            result = subprocess.run(command, env=environment, capture_output=True, text=True, check=False)
            self.assertEqual(0, result.returncode, msg=result.stderr)
            arguments = shlex.split(result.stdout)
            self.assertIn(f"type=bind,src={root}/future-source,dst=/workspace/future-source,readonly", arguments)
            self.assertNotIn(f"type=bind,src={root}/.aws,dst=/workspace/.aws,readonly", arguments)
            self.assertIn(f"type=bind,src={root}/.work,dst=/workspace/.work,readonly", arguments)
            (root / "linked").symlink_to(root / "future-source", target_is_directory=True)
            result = subprocess.run(command, env=environment, capture_output=True, text=True, check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("", result.stdout)
            self.assertIn("Cannot grant repository source", result.stderr)

    def test_missing_inputs_and_unknown_target_fail_before_engine_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tools").mkdir()
            launcher = root / "tools/repository.sh"
            launcher.write_bytes((ROOT / "tools/repository.sh").read_bytes())
            for target, message in (
                ("tests/repository", "checker_inputs.sh"),
                ("unreviewed", "unknown target"),
            ):
                result = subprocess.run(
                    ["bash", str(launcher), "--print", target],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(0, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertIn(message, result.stderr)

    def test_empty_unittest_discovery_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", "discover", "-s", directory, "-v"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("NO TESTS RAN", result.stderr)
