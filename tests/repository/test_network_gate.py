"""Acquisition must reject routing ambiguity before invoking the engine."""

from tools.container_guard import require_container

require_container()

import os
import shlex
import subprocess
import unittest
from pathlib import Path


class NetworkGateTests(unittest.TestCase):
    def invoke(self, interface=None, proxy_user=None):
        environment = dict(os.environ)
        environment["CONTAINER_TOOLS_SELECTED_DOCKER_ENDPOINT"] = "unix:///var/run/docker.sock"
        environment["DOCKER_CONTEXT_INPUT_ORIGIN"] = "command line"
        environment["DOCKER_CONTEXT_INPUT"] = "default"
        # silent-defaults: allow-pop-default -- Remove an inherited forwarded interface so omission cannot authorize routing; proof=tests/repository/test_network_gate.py::NetworkGateTests.test_networked_lanes_require_an_explicit_interface
        environment.pop("NETWORK_INTERFACE_INPUT", None)
        # silent-defaults: allow-pop-default -- Remove the ambient interface before checking that routing requires an explicit selector; proof=tests/repository/test_network_gate.py::NetworkGateTests.test_networked_lanes_require_an_explicit_interface
        environment.pop("NETWORK_INTERFACE", None)

        if interface is not None:
            environment["NETWORK_INTERFACE_INPUT"] = interface
        return subprocess.run(
            ["bash", "tools/docker.sh", "--print", "run", "--proxy-user", proxy_user if proxy_user is not None else f"{os.getuid()}:{os.getgid()}", "--pull", "never", "--read-only", "--user", f"{os.getuid()}:{os.getgid()}", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--cpus", "2", "--memory", "512m", "--memory-swap", "512m", "--pids-limit", "64", "--env", "CONTAINER_TOOLS_IN_CONTAINER=1", "inert-image"],
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_networked_lanes_require_an_explicit_interface(self):
        for script, lane in (("docker", "run"),):
            with self.subTest(script=script, lane=lane):
                result = self.invoke()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("NETWORK_INTERFACE", result.stderr)
                self.assertEqual("", result.stdout)

    def test_networked_lanes_reject_an_unavailable_interface(self):
        for script, lane in (("docker", "run"),):
            with self.subTest(script=script, lane=lane):
                result = self.invoke("fixture_missing0")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("fixture_missing0", result.stderr)
                self.assertEqual("", result.stdout)

    def test_mapped_proxy_identity_is_explicit_and_validated(self):
        missing = subprocess.run(
            ["bash", "tools/docker.sh", "--print", "run", "--pull", "never", "inert-image"],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(0, missing.returncode)
        self.assertEqual("", missing.stdout)
        self.assertIn("--proxy-user", missing.stderr)
        result = self.invoke("lo", proxy_user="0:0")
        self.assertEqual(0, result.returncode, msg=result.stderr)
        proxy = shlex.split(result.stdout.splitlines()[0])
        self.assertEqual("0:0", proxy[proxy.index("--user") + 1])
        for identity in ("", "-1:0", "1:2:3", "4294967295:0", "0:4294967295"):
            with self.subTest(identity=identity):
                rejected = self.invoke("lo", proxy_user=identity)
                self.assertNotEqual(0, rejected.returncode)
                self.assertEqual("", rejected.stdout)
                self.assertIn("proxy", rejected.stderr)

    def test_proxy_and_worker_are_contained_and_override_proxy_environment(self):
        result = self.invoke("lo")
        self.assertEqual(0, result.returncode, msg=result.stderr)
        proxy, start_proxy, worker, start_worker = [shlex.split(line) for line in result.stdout.splitlines()]
        self.assertEqual(["start", "PROXY_ID"], start_proxy[-2:])
        self.assertEqual(["start", "--attach", "WORKER_ID"], start_worker[-3:])
        for command in (proxy, worker):
            self.assertIn("create", command)
            self.assertNotIn("--rm", command)
            self.assertIn("--read-only", command)
            self.assertIn("no-new-privileges:true", command)
            self.assertEqual(f"{os.getuid()}:{os.getgid()}", command[command.index("--user") + 1])
            self.assertEqual("ALL", command[command.index("--cap-drop") + 1])
            self.assertEqual("never", command[command.index("--pull") + 1])
            self.assertIn("CONTAINER_TOOLS_IN_CONTAINER=1", command)
            for limit in ("--cpus", "--memory", "--memory-swap", "--pids-limit"):
                self.assertIn(limit, command)
            mounts = [command[i + 1] for i, arg in enumerate(command) if arg == "--mount"]
            self.assertFalse(any("docker.sock" in mount or "dst=/home" in mount for mount in mounts))
        self.assertIn("python3", proxy)
        self.assertEqual("tools.bound_http_proxy", proxy[proxy.index("-m") + 1])
        self.assertEqual("/workspace", proxy[proxy.index("--workdir") + 1])
        proxy_mounts = [proxy[i + 1] for i, arg in enumerate(proxy) if arg == "--mount"]
        expected_mounts = {
            f"type=bind,src={Path.cwd()}/tools/bound_http_proxy.py,dst=/workspace/tools/bound_http_proxy.py,readonly",
            f"type=bind,src={Path.cwd()}/tools/container_guard.py,dst=/workspace/tools/container_guard.py,readonly",
            "type=bind,src=/tmp/container-tools-proxy.PRINT/ready,dst=/ready",
        }
        resolver = Path("/run/systemd/resolve/resolv.conf")
        if resolver.exists():
            expected_mounts.add(f"type=bind,src={resolver},dst={resolver},readonly")
        self.assertEqual(expected_mounts, set(proxy_mounts))
        self.assertIn("type=bind,src=/tmp/container-tools-proxy.PRINT/ready,dst=/ready", proxy)
        self.assertNotIn("type=bind,src=/tmp/container-tools-proxy.PRINT,dst=/ready", proxy)
        self.assertEqual("lo", proxy[proxy.index("--interface") + 1])
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            self.assertIn(f"{name}=http://127.0.0.1:PORT", worker)
        for name in ("NO_PROXY", "no_proxy", "ALL_PROXY", "all_proxy"):
            self.assertIn(f"{name}=", worker)
