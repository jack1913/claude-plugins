"""Tests for record_trace.py's stop-file cleanup.

A stop-file left over from an earlier run must not make the next recording
stop at once, silently — and a recording must not leave its own stop-file
behind for the next one to trip over. See UPSTREAM.md Deviations.
"""

from __future__ import annotations

import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "swift"
    / "skills"
    / "swiftui"
    / "scripts"
    / "record_trace.py"
)
SPEC = importlib.util.spec_from_file_location("record_trace", SCRIPT)
assert SPEC and SPEC.loader
record_trace = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(record_trace)


class ClearStopFileUnitTests(unittest.TestCase):
    """Direct tests of the _clear_stop_file helper — no subprocess involved."""

    def test_no_op_when_no_stop_file_was_configured(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            record_trace._clear_stop_file(None, "stale (from an earlier run)")

        self.assertEqual("", stderr.getvalue())

    def test_no_op_when_stop_file_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                record_trace._clear_stop_file(missing, "stale (from an earlier run)")

            self.assertEqual("", stderr.getvalue())

    def test_removes_existing_file_and_notes_it_on_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stop_file = Path(tmp) / "stop-trace"
            stop_file.write_text("")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                record_trace._clear_stop_file(stop_file, "stale (from an earlier run)")

            self.assertFalse(stop_file.exists())
            self.assertIn(
                f"removed stop-file (stale (from an earlier run)): {stop_file}",
                stderr.getvalue(),
            )


class MainStopFileWiringTests(unittest.TestCase):
    """Exercise main() end to end with xctrace mocked out entirely."""

    def test_stale_stop_file_is_cleared_before_recording_starts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stop_file = tmp_path / "stop-trace"
            output = tmp_path / "session.trace"
            stop_file.write_text("leftover from an earlier run\n")

            fake_proc = mock.Mock()
            fake_proc.pid = 4242
            # Three still-running polls, then xctrace exits on its own. If the
            # stale stop-file weren't cleared first, _wait_with_stop would
            # detect it on the very first iteration and stop immediately,
            # so poll() would be called once, not three times.
            fake_proc.poll.side_effect = [None, None, 0]
            fake_proc.wait.return_value = 0

            stderr = io.StringIO()
            with (
                redirect_stderr(stderr),
                mock.patch.object(
                    record_trace.subprocess, "Popen", return_value=fake_proc
                ) as popen,
                mock.patch.object(record_trace.time, "sleep"),
                mock.patch.object(record_trace, "_forward_sigint") as forward_sigint,
            ):
                record_trace.main(
                    [
                        "--attach",
                        "TestApp",
                        "--stop-file",
                        str(stop_file),
                        "--output",
                        str(output),
                    ]
                )

            popen.assert_called_once()
            self.assertEqual(3, fake_proc.poll.call_count)
            forward_sigint.assert_not_called()
            self.assertFalse(stop_file.exists())
            self.assertIn(
                f"removed stop-file (stale (from an earlier run)): {stop_file}",
                stderr.getvalue(),
            )

    def test_stop_file_is_cleared_again_after_the_stop_is_handled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stop_file = tmp_path / "stop-trace"
            output = tmp_path / "session.trace"

            fake_proc = mock.Mock()
            fake_proc.pid = 4242
            fake_proc.wait.return_value = 0

            def fake_poll() -> None:
                # Simulate the stop-file being touched mid-recording, from
                # another shell or tool call, the way agents use it.
                stop_file.touch()
                return None

            fake_proc.poll.side_effect = fake_poll

            stderr = io.StringIO()
            with (
                redirect_stderr(stderr),
                mock.patch.object(
                    record_trace.subprocess, "Popen", return_value=fake_proc
                ),
                mock.patch.object(record_trace.os, "getpgid", return_value=4242),
                mock.patch.object(record_trace.os, "killpg") as killpg,
            ):
                record_trace.main(
                    [
                        "--attach",
                        "TestApp",
                        "--stop-file",
                        str(stop_file),
                        "--output",
                        str(output),
                    ]
                )

            killpg.assert_called_once()
            self.assertFalse(stop_file.exists())
            self.assertIn(
                f"removed stop-file (after stopping): {stop_file}",
                stderr.getvalue(),
            )


if __name__ == "__main__":
    unittest.main()
