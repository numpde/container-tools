"""Inverse CLI projection keeps the probe's all-or-nothing cancellation contract."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import signal
import unittest
from unittest.mock import patch

from linux_idmap import IdMap, IdRange
from linux_idmap import _cli
from linux_idmap.probe import ProbeResult


class InverseCliTests(unittest.TestCase):
    def invoke(self, result, extra):
        output, errors = io.StringIO(), io.StringIO()
        arguments = ["--endpoint", "unix:///test.sock", "--image", "approved:local",
                     "--interpreter", "/usr/bin/python3", "--user-uid", "0",
                     "--user-gid", "0", "--inverse", *extra]
        with patch.object(_cli, "probe_identity", return_value=result), \
                redirect_stdout(output), redirect_stderr(errors):
            status = _cli.main(arguments)
        return status, output.getvalue(), errors.getvalue()

    def test_json_preserves_requested_order_and_independent_group_mapping(self):
        result = ProbeResult(IdMap((IdRange(0, 1000, 1), IdRange(1, 100000, 100))),
                             IdMap((IdRange(0, 200, 1), IdRange(1, 200000, 100))), "c" * 64)
        status, output, errors = self.invoke(result, ["--uid", "100001", "--gid", "200",
                                                    "--uid", "1000", "--uid", "100001"])
        self.assertEqual((0, ""), (status, errors))
        self.assertEqual([2, 0, 2], json.loads(output)["mapped_uids"])
        self.assertEqual([0], json.loads(output)["mapped_gids"])

    def test_inverse_group_failure_never_prints_partial_uid_success(self):
        uids = IdMap((IdRange(0, 1000, 1),))
        for gids in (IdMap((IdRange(0, 3000, 1),)),
                     IdMap((IdRange(0, 2000, 2), IdRange(10, 2000, 2)))):
            with self.subTest(gids=gids):
                result = ProbeResult(uids, gids, "c" * 64)
                status, output, errors = self.invoke(result, ["--uid", "1000", "--gid", "2000", "--values"])
                self.assertEqual((1, ""), (status, output))
                self.assertEqual("unmapped-id", json.loads(errors)["problem"]["category"])
                self.assertEqual("confirmed-retired", json.loads(errors)["state"])

    def test_cancelled_inverse_projection_withholds_values_and_restores_handlers(self):
        result = ProbeResult(IdMap((IdRange(0, 1000, 1),)), IdMap((IdRange(0, 2000, 1),)), "c" * 64)
        inverse = IdMap.translate_inverse
        previous = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}

        def cancel(mapping, value):
            answer = inverse(mapping, value)
            signal.raise_signal(signal.SIGTERM)
            return answer

        with patch.object(IdMap, "translate_inverse", cancel):
            status, output, errors = self.invoke(result, ["--uid", "1000", "--gid", "2000", "--values"])
        self.assertEqual((130, ""), (status, output))
        self.assertEqual("cancelled", json.loads(errors)["problem"]["category"])
        self.assertEqual(previous, {number: signal.getsignal(number) for number in previous})
