import math
import os
import queue
import struct
import sys
import unittest
from unittest import mock
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import myfoc_host as host


class SerialWorkerParserTest(unittest.TestCase):
    def make_frame(self, *values):
        return bytearray(struct.pack("<7f", *values) + host.FRAME_TAIL)

    def make_float_frame(self, *values):
        return bytearray(struct.pack(f"<{len(values)}f", *values) + host.FRAME_TAIL)

    def test_timestamps_follow_sample_sequence_not_pc_receive_gap(self):
        frame_queue = queue.Queue()
        worker = host.SerialWorker(frame_queue)
        worker.frame_interval_s = 0.01

        worker._parse_buffer(self.make_frame(1, 2, 3, 4, 5, 6, 7), received_at=100.0)
        worker._parse_buffer(self.make_frame(2, 3, 4, 5, 6, 7, 8), received_at=200.0)

        t0, _ = frame_queue.get_nowait()
        t1, _ = frame_queue.get_nowait()
        self.assertAlmostEqual(t1 - t0, 0.01)

    def test_parser_rejects_nonfinite_or_implausible_frame(self):
        frame_queue = queue.Queue()
        worker = host.SerialWorker(frame_queue)

        worker._parse_buffer(
            self.make_frame(math.nan, math.nan, 0.1, 2.0, 600.0, 600.0, 24.0),
            received_at=100.0,
        )
        worker._parse_buffer(
            self.make_frame(0.1, 0.2, 0.3, 2.0, 600.0, 600.0, 600.0),
            received_at=100.0,
        )

        self.assertTrue(frame_queue.empty())

    def test_parser_accepts_legacy_eight_float_frame(self):
        frame_queue = queue.Queue()
        worker = host.SerialWorker(frame_queue)
        payload = struct.pack("<8f", -0.1, 0.1, 0.0, 1.2, 600.0, 600.0, 24.0, 24.1)

        worker._parse_buffer(bytearray(payload + host.FRAME_TAIL), received_at=100.0)

        _timestamp, values = frame_queue.get_nowait()
        self.assertAlmostEqual(values["ia"], -0.1, places=5)
        self.assertAlmostEqual(values["theta"], 1.2, places=5)
        self.assertAlmostEqual(values["vbus"], 24.0, places=5)

    def test_parser_accepts_diagnostic_seventeen_float_frame(self):
        frame_queue = queue.Queue()
        worker = host.SerialWorker(frame_queue)

        worker._parse_buffer(
            self.make_float_frame(
                -0.1, 0.2, -0.1, 1.2, 600.0, 650.0, 24.0,
                0.01, 0.42, 0.0, 0.5, -0.2, 8.3, 3900.0, 4100.0, 4050.0, 5.0,
            ),
            received_at=100.0,
        )

        _timestamp, values = frame_queue.get_nowait()
        self.assertAlmostEqual(values["iq"], 0.42, places=5)
        self.assertAlmostEqual(values["iq_ref"], 0.5, places=5)
        self.assertAlmostEqual(values["uq"], 8.3, places=5)
        self.assertAlmostEqual(values["tcmp3"], 4050.0, places=5)
        self.assertAlmostEqual(values["foc_state"], 5.0, places=5)


class PlotWindowTest(unittest.TestCase):
    def test_default_plot_windows_match_signal_types(self):
        self.assertLess(host.PLOT_DEFAULT_WINDOWS["current"], 1.0)
        self.assertLess(host.PLOT_DEFAULT_WINDOWS["theta"], 1.0)
        self.assertGreater(host.PLOT_DEFAULT_WINDOWS["speed"], host.PLOT_DEFAULT_WINDOWS["theta"])
        self.assertGreater(host.PLOT_DEFAULT_WINDOWS["voltage"], host.PLOT_DEFAULT_WINDOWS["theta"])

    def test_time_range_uses_requested_window(self):
        left, right = host.time_range_for_latest(10.0, 0.65)

        self.assertAlmostEqual(left, 9.35)
        self.assertGreater(right, 10.0)
        self.assertLess(right, 10.1)

    def test_wrapped_angle_plot_connects_reset_like_vofa(self):
        x, y = host.curve_data_for_plot(
            "theta",
            [0.0, 0.1, 0.2, 0.3],
            [6.0, 6.2, 0.1, 0.3],
        )

        self.assertEqual(list(x), [0.0, 0.1, 0.2, 0.3])
        self.assertEqual(list(y), [6.0, 6.2, 0.1, 0.3])

    def test_time_range_clamps_to_first_visible_finite_sample(self):
        left, right = host.time_range_for_latest(
            10.0,
            5.0,
            [0, 1, 6, 7, 8, 9, 10],
            [float("nan"), float("nan"), 1, 1, 1, 1, 1],
        )

        self.assertEqual(left, 6.0)
        self.assertGreater(right, 10.0)

    def test_visible_curve_data_limits_points_to_active_window(self):
        x, y = host.visible_curve_data_for_plot(
            "current",
            [0, 1, 2, 3, 4, 5, 6],
            [10, 11, 12, 13, 14, 15, 16],
            2,
            6,
            max_points=3,
        )

        self.assertEqual(list(x), [2.0, 4.0, 6.0])
        self.assertEqual(list(y), [12.0, 14.0, 16.0])

    def test_padded_y_range_ignores_nan(self):
        y_min, y_max = host.padded_y_range([1.0, float("nan"), 2.0], min_span=0.5)

        self.assertLess(y_min, 1.0)
        self.assertGreater(y_max, 2.0)


class PlotInteractionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6 import QtWidgets

        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_manual_zoom_keeps_that_plot_following_latest(self):
        window = host.MyFocHostWindow()
        window.auto_scroll_check.setChecked(True)

        window._on_plot_range_changed_manually("speed")

        self.assertTrue(window.plot_follow_latest["speed"])
        self.assertTrue(window.plot_follow_latest["current"])

    def test_manual_zoom_updates_only_that_plot_window_width(self):
        window = host.MyFocHostWindow()
        window.auto_scroll_check.setChecked(True)
        old_current_window = window.plot_window_spins["current"].value()
        window.plot_items["speed"].setXRange(1.0, 1.5, padding=0.0)

        window._on_plot_range_changed_manually("speed")

        self.assertAlmostEqual(window.plot_window_spins["speed"].value(), 0.5, places=2)
        self.assertAlmostEqual(window.plot_window_spins["current"].value(), old_current_window, places=2)


class CommandSendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6 import QtWidgets

        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_speed_command_uses_same_repeated_send_as_run_stop(self):
        window = host.MyFocHostWindow()
        sent = []

        with mock.patch.object(
            window,
            "send_command",
            side_effect=lambda command, announce=True: sent.append((command, announce)),
        ), mock.patch.object(host.QtCore.QTimer, "singleShot") as single_shot:
            window.speed_spin.setValue(900.0)
            window.send_speed()

        self.assertEqual(sent, [("SPD=900.0", True)])
        self.assertEqual(single_shot.call_count, host.CONTROL_COMMAND_REPEAT_COUNT - 1)
        self.assertEqual(single_shot.call_args_list[0].args[0], host.CONTROL_COMMAND_REPEAT_INTERVAL_MS)

    def test_speed_command_clamps_below_configured_min_speed(self):
        window = host.MyFocHostWindow()
        sent = []

        with mock.patch.object(
            window,
            "send_command",
            side_effect=lambda command, announce=True: sent.append((command, announce)),
        ), mock.patch.object(host.QtCore.QTimer, "singleShot"):
            window.speed_spin.setValue(100.0)
            window.send_speed()

        self.assertEqual(sent, [("SPD=120.0", True)])
        self.assertEqual(window.speed_spin.value(), 120.0)

    def test_speed_command_clamps_above_configured_max_speed(self):
        window = host.MyFocHostWindow()
        sent = []

        with mock.patch.object(
            window,
            "send_command",
            side_effect=lambda command, announce=True: sent.append((command, announce)),
        ), mock.patch.object(host.QtCore.QTimer, "singleShot"):
            window.speed_spin.setValue(2500.0)
            window.send_speed()

        self.assertEqual(sent, [("SPD=1800.0", True)])
        self.assertEqual(window.speed_spin.value(), 1800.0)


class LoggingSchemaTest(unittest.TestCase):
    def test_csv_header_includes_diagnostic_channels(self):
        self.assertIn("Iq_ref", host.CSV_HEADERS)
        self.assertIn("Ud", host.CSV_HEADERS)
        self.assertIn("Uq", host.CSV_HEADERS)
        self.assertIn("Tcmp3", host.CSV_HEADERS)
        self.assertIn("FOC_state", host.CSV_HEADERS)


class FirmwareCommandRxTest(unittest.TestCase):
    def test_firmware_uses_dma_ring_for_host_command_rx(self):
        project_root = Path(__file__).resolve().parents[1]
        main_source = (project_root / "Core" / "Src" / "main.c").read_text(encoding="utf-8")
        usart_source = (project_root / "Core" / "Src" / "usart.c").read_text(encoding="utf-8")

        self.assertIn("HAL_UART_Receive_DMA(&huart3, host_rx_dma_buffer", main_source)
        self.assertIn("HostCommand_PollDmaRx();", main_source)
        self.assertIn("hdma_usart3_rx.Init.Mode = DMA_CIRCULAR;", usart_source)
        self.assertNotIn("HAL_UART_Receive_IT(&huart3, &uart_rx_byte, 1U);", main_source)

    def test_firmware_clamps_speed_below_configured_min_speed(self):
        project_root = Path(__file__).resolve().parents[1]
        main_source = (project_root / "Core" / "Src" / "main.c").read_text(encoding="utf-8")

        self.assertIn("#define SPEED_SENSORLESS_MIN_RPM 120.0f", main_source)
        self.assertIn("#define SPEED_MIN_RPM SPEED_SENSORLESS_MIN_RPM", main_source)

    def test_firmware_clamps_speed_above_configured_max_speed(self):
        project_root = Path(__file__).resolve().parents[1]
        main_source = (project_root / "Core" / "Src" / "main.c").read_text(encoding="utf-8")

        self.assertIn("#define SPEED_MAX_RPM 1800.0f", main_source)

    def test_firmware_sends_diagnostic_telemetry_frame(self):
        project_root = Path(__file__).resolve().parents[1]
        main_source = (project_root / "Core" / "Src" / "main.c").read_text(encoding="utf-8")
        foc_header = (project_root / "Matlab" / "FOC.h").read_text(encoding="utf-8")

        self.assertIn("float load_data[17];", main_source)
        self.assertIn("FocDiagId", foc_header)
        self.assertIn("FocDiagIqRef", foc_header)
        self.assertIn("FocDiagUq", foc_header)
        self.assertIn("FocDiagState", foc_header)
        self.assertIn("load_data[16] = FocDiagState;", main_source)


class TechnicalIssueDocTest(unittest.TestCase):
    def test_technical_issue_log_records_non_ui_issues(self):
        project_root = Path(__file__).resolve().parents[1]
        issue_log = project_root / "Docs" / "technical_issue_log.md"

        text = issue_log.read_text(encoding="utf-8")
        self.assertIn("串口命令偶发无响应", text)
        self.assertIn("低速给定反转和抖动", text)
        self.assertNotIn("界面", text)


if __name__ == "__main__":
    unittest.main()
