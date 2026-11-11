"""The optional resource policy has one exact public meaning."""

from dataclasses import FrozenInstanceError, replace
from functools import partial
import unittest
from unittest.mock import patch

from linux_idmap._probe_spec import ProbeSpec
from linux_idmap.probe import Bounds, ProbeFailure, ProbeRequest, ProbeResources, StepError, probe_identity
from helpers import CID, Engine, Guard


class ProbeResourcesTests(unittest.TestCase):
    def setUp(self):
        self.bounds = Bounds(1, .2, .1, 30)
        self.request = ProbeRequest("unix:///test.sock", "approved:local", "/usr/bin/python3",
                                    1000, 2000, "default", self.bounds)

    def test_existing_positional_request_keeps_its_bounds_and_no_selected_ceilings(self):
        self.assertIs(self.bounds, self.request.bounds)
        self.assertIsNone(self.request.resources)
        arguments = ProbeSpec("b" * 32, "sha256:" + "a" * 64, self.request).create_arguments()
        for option in ("--memory", "--memory-swap", "--pids-limit", "--cpus"):
            self.assertNotIn(option, arguments)

    def test_exact_integer_limits_include_both_endpoints_and_are_immutable(self):
        for values in ((16 * 1024**2, 1, 100_000_000), (1024**3, 256, 4_000_000_000)):
            with self.subTest(values=values):
                resources = ProbeResources(*values)
                self.assertIs(resources, replace(self.request, resources=resources).resources)
                with self.assertRaises(FrozenInstanceError):
                    resources.pids_limit = 2

    def test_wrong_types_and_out_of_range_values_refuse_before_probe_dispatch(self):
        ordinary = [32 * 1024**2, 4, 250_000_000]
        invalid = (
            (True, 32.0, "33554432", None, 16 * 1024**2 - 1, 1024**3 + 1),
            (True, 4.0, "4", None, 0, 257),
            (True, 250_000_000.0, "250000000", None, 99_999_999, 4_000_000_001),
        )
        for index, values in enumerate(invalid):
            for value in values:
                with self.subTest(field=index, value=value):
                    selected = list(ordinary)
                    selected[index] = value
                    with self.assertRaises(StepError) as caught:
                        ProbeResources(*selected)
                    self.assertEqual("invalid-policy", caught.exception.category)
        for value in ({}, True, ordinary):
            with self.subTest(resource_policy=value), self.assertRaises(StepError):
                replace(self.request, resources=value)

    def test_fractional_cpu_values_survive_create_and_inspect_without_rounding(self):
        for nano_cpus, text in ((100_000_000, "0.1"), (100_000_003, "0.100000003"),
                                (250_000_000, "0.25"), (4_000_000_000, "4")):
            with self.subTest(nano_cpus=nano_cpus):
                policy = replace(self.request, resources=ProbeResources(32 * 1024**2, 4, nano_cpus))
                engine = Engine()
                with (
                    patch("linux_idmap._probe_scope.DockerEngine.connect", return_value=engine),
                    patch("linux_idmap._probe_scope.ProbeProcesses", return_value=Guard()),
                ):
                    result = probe_identity(policy)
                self.assertEqual(CID, result.container_id)
                self.assertEqual(text, engine.arguments[engine.arguments.index("--cpus") + 1])
                self.assertIn("start", engine.events)
                self.assertIsNone(engine.container)

    def test_numerically_equal_float_evidence_cannot_authorize_start(self):
        def float_evidence(field, engine):
            isolation = engine.container.isolation
            isolation[field] = float(isolation[field])

        policy = replace(self.request, resources=ProbeResources(16 * 1024**2, 1, 100_000_000))
        for field in ("Memory", "MemorySwap", "PidsLimit", "NanoCpus"):
            with self.subTest(field=field):
                engine = Engine()
                engine.on_create = partial(float_evidence, field)
                with (
                    patch("linux_idmap._probe_scope.DockerEngine.connect", return_value=engine),
                    patch("linux_idmap._probe_scope.ProbeProcesses", return_value=Guard()),
                    self.assertRaises(ProbeFailure) as caught,
                ):
                    probe_identity(policy)
                self.assertEqual("confinement", caught.exception.problem.category)
                self.assertNotIn("start", engine.events)
                self.assertNotIn("uid_map", caught.exception.as_dict())
                self.assertNotIn("gid_map", caught.exception.as_dict())
