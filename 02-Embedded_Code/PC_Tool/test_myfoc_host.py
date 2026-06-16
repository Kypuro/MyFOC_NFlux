import math
import os
import queue
import re
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
        self.assertEqual(set(host.PLOT_DEFAULT_WINDOWS), {"state", "measure"})
        self.assertLess(host.PLOT_DEFAULT_WINDOWS["state"], 1.0)
        self.assertLess(host.PLOT_DEFAULT_WINDOWS["measure"], 1.0)

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
            "measure",
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

    def test_manual_zoom_stops_that_plot_following_latest(self):
        window = host.MyFocHostWindow()
        window.auto_scroll_check.setChecked(True)

        window._on_plot_range_changed_manually("state")

        self.assertFalse(window.plot_follow_latest["state"])
        self.assertTrue(window.plot_follow_latest["measure"])

    def test_manual_zoom_disables_auto_y_for_that_plot(self):
        window = host.MyFocHostWindow()
        window.auto_scale_check.setChecked(True)

        window._on_plot_range_changed_manually("state")

        self.assertFalse(window.plot_auto_y["state"])
        self.assertTrue(window.plot_auto_y["measure"])

    def test_manual_zoom_updates_only_that_plot_window_width(self):
        window = host.MyFocHostWindow()
        window.auto_scroll_check.setChecked(True)
        old_measure_window = window.plot_window_spins["measure"].value()
        window.plot_items["state"].setXRange(1.0, 1.5, padding=0.0)

        window._on_plot_range_changed_manually("state")

        self.assertAlmostEqual(window.plot_window_spins["state"].value(), 0.5, places=2)
        self.assertAlmostEqual(window.plot_window_spins["measure"].value(), old_measure_window, places=2)

    def test_main_panel_removes_fast_changing_summary_cards(self):
        window = host.MyFocHostWindow()

        self.assertEqual(window.summary_cards, [])

    def test_main_header_has_no_explanatory_subtitle(self):
        window = host.MyFocHostWindow()

        hint_labels = window.main_panel.findChildren(host.QtWidgets.QLabel, "hintText")
        self.assertFalse(any(label.parent().objectName() == "mainHeader" for label in hint_labels))

    def test_main_panel_is_not_wrapped_in_right_side_scroll_area(self):
        window = host.MyFocHostWindow()

        self.assertIsNone(window.main_scroll)

    def test_plot_toolbar_is_in_main_header(self):
        window = host.MyFocHostWindow()

        self.assertIs(window.pause_button.parent(), window.plot_toolbar)
        self.assertIs(window.log_button.parent(), window.plot_toolbar)
        self.assertIs(window.theme_button.parent(), window.plot_toolbar)
        self.assertEqual(window.plot_toolbar.parent().objectName(), "mainHeader")
        self.assertIsNot(window.plot_toolbar.parent(), window.plot_panel)
        self.assertEqual(window.theme_button.text(), "")
        self.assertEqual(window.pause_button.minimumSize().height(), 38)
        self.assertEqual(window.rate_label.minimumHeight(), 36)

    def test_plot_toolbar_uses_drawn_icons_instead_of_text_glyphs(self):
        window = host.MyFocHostWindow()

        for button in (
            window.pause_button,
            window.log_button,
            window.reset_view_button,
            window.clear_data_button,
            window.theme_button,
        ):
            self.assertEqual(button.text(), "")
            self.assertFalse(button.icon().isNull())
            self.assertEqual(button.iconSize(), host.QtCore.QSize(22, 22))

        window._set_paused(True)
        self.assertEqual(window.pause_button.text(), "")
        self.assertFalse(window.pause_button.icon().isNull())

    def test_sidebar_is_compact_without_visible_scrollbar(self):
        window = host.MyFocHostWindow()

        self.assertEqual(
            window.sidebar_scroll.verticalScrollBarPolicy(),
            host.QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.assertLessEqual(window.console.maximumHeight(), 72)
        self.assertLessEqual(window.speed_spin.minimumHeight(), 32)
        self.assertLessEqual(window.port_combo.minimumHeight(), 32)

    def test_combo_boxes_use_flat_modern_style_hook(self):
        window = host.MyFocHostWindow()

        self.assertEqual(window.port_combo.objectName(), "flatCombo")
        self.assertEqual(window.baud_box.objectName(), "flatCombo")

    def test_waveform_uses_two_stacked_plot_panels(self):
        window = host.MyFocHostWindow()

        self.assertEqual(tuple(window.plot_items.keys()), ("state", "measure"))
        self.assertEqual(host.PLOT_PANELS["state"]["channels"], ("theta", "speed", "ref", "tcmp1", "tcmp2", "tcmp3", "foc_state"))
        self.assertEqual(host.PLOT_PANELS["measure"]["channels"], ("ia", "ib", "ic", "id", "iq", "id_ref", "iq_ref", "ud", "uq", "vbus"))
        self.assertFalse(window.legends)

    def test_waveform_uses_one_y_axis_per_plot(self):
        window = host.MyFocHostWindow()

        self.assertEqual(set(window.plot_axis_views["state"]), {"value"})
        self.assertEqual(set(window.plot_axis_views["measure"]), {"value"})
        self.assertEqual(window.plot_axis_items["state"]["value"], window.plot_items["state"].getAxis("left"))
        self.assertEqual(window.plot_axis_items["measure"]["value"], window.plot_items["measure"].getAxis("left"))

    def test_plot_grid_is_visible_but_low_contrast_in_both_themes(self):
        window = host.MyFocHostWindow()

        self.assertGreaterEqual(window._plot_grid_alpha(), 0.28)
        self.assertLessEqual(window._plot_grid_alpha(), 0.40)

        window.theme_button.setChecked(True)

        self.assertGreaterEqual(window._plot_grid_alpha(), 0.18)
        self.assertLessEqual(window._plot_grid_alpha(), 0.30)

    def test_speed_and_vbus_are_bound_to_primary_plot_axes(self):
        window = host.MyFocHostWindow()

        self.assertIn(window.curves["speed"], window.plot_items["state"].listDataItems())
        self.assertIn(window.curves["vbus"], window.plot_items["measure"].listDataItems())

    def test_channel_selectors_are_vertical_pills_left_of_each_plot(self):
        window = host.MyFocHostWindow()

        self.assertEqual(window.channel_pill_layouts["state"].direction(), host.QtWidgets.QBoxLayout.Direction.TopToBottom)
        self.assertEqual(window.channel_pill_layouts["measure"].direction(), host.QtWidgets.QBoxLayout.Direction.TopToBottom)
        self.assertEqual(window.channel_checks["theta"].objectName(), "channelPill")
        self.assertEqual(window.channel_checks["ia"].objectName(), "channelPill")
        self.assertIsInstance(window.channel_checks["theta"], host.QtWidgets.QPushButton)
        self.assertTrue(window.channel_checks["theta"].isCheckable())
        self.assertTrue(window.channel_checks["theta"].text().startswith("\u25cf "))
        self.assertGreaterEqual(window.channel_checks["theta"].minimumWidth(), 96)
        self.assertEqual(
            window.channel_checks["theta"].sizePolicy().horizontalPolicy(),
            host.QtWidgets.QSizePolicy.Policy.Expanding,
        )

    def test_channel_pill_toggles_when_clicking_right_side(self):
        from PySide6 import QtTest

        window = host.MyFocHostWindow()
        window.show()
        self.app.processEvents()
        pill = window.channel_checks["theta"]
        pill.resize(128, 32)
        was_checked = pill.isChecked()

        QtTest.QTest.mouseClick(
            pill,
            host.QtCore.Qt.MouseButton.LeftButton,
            host.QtCore.Qt.KeyboardModifier.NoModifier,
            host.QtCore.QPoint(pill.width() - 4, pill.height() // 2),
        )

        self.assertNotEqual(pill.isChecked(), was_checked)

    def test_channel_selectors_are_vertically_centered(self):
        window = host.MyFocHostWindow()

        for layout in window.channel_pill_layouts.values():
            self.assertIsNotNone(layout.itemAt(0).spacerItem())
            self.assertIsNotNone(layout.itemAt(layout.count() - 1).spacerItem())

    def test_each_plot_is_wrapped_in_a_rounded_plot_card(self):
        window = host.MyFocHostWindow()

        for plot_area in window.plot_areas.values():
            self.assertEqual(plot_area.parent().objectName(), "plotCard")
            self.assertLessEqual(plot_area.minimumHeight(), 240)

    def test_diagnostic_tab_is_not_shown(self):
        window = host.MyFocHostWindow()

        tab_titles = [window.tab_widget.tabText(index) for index in range(window.tab_widget.count())]
        self.assertEqual(tab_titles, ["实时曲线", "控制预留"])
        self.assertEqual(window.diagnostic_chips, {})

    def test_motor_control_button_labels_hide_command_literals(self):
        window = host.MyFocHostWindow()

        self.assertNotIn("RUN=", window.run_button.text())
        self.assertNotIn("RUN=", window.stop_button.text())
        self.assertIn("启动", window.run_button.text())
        self.assertIn("停止", window.stop_button.text())

    def test_spin_boxes_use_modern_no_button_style(self):
        window = host.MyFocHostWindow()

        self.assertEqual(window.speed_spin.buttonSymbols(), host.QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.assertEqual(window.plot_window_spins["state"].buttonSymbols(), host.QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)

    def test_enabling_hidden_channel_populates_existing_history(self):
        window = host.MyFocHostWindow()
        for index in range(10):
            window.time_history.append(index * 0.1)
            for channel in host.CHANNELS:
                value = float(index)
                if channel.key == "tcmp1":
                    value = 4000.0 + index
                window.history[channel.key].append(value)

        window._update_plot()
        x_before, _ = window.curves["tcmp1"].getData()
        self.assertEqual(0 if x_before is None else len(x_before), 0)

        window.channel_checks["tcmp1"].setChecked(True)

        x_after, y_after = window.curves["tcmp1"].getData()
        self.assertIsNotNone(x_after)
        self.assertIsNotNone(y_after)
        self.assertGreater(len(x_after), 0)
        self.assertEqual(len(x_after), len(y_after))

    def test_enabling_hidden_channel_refreshes_its_axis_range(self):
        window = host.MyFocHostWindow()
        for index in range(10):
            window.time_history.append(index * 0.1)
            for channel in host.CHANNELS:
                value = float(index)
                if channel.key == "tcmp1":
                    value = 4000.0 + index
                window.history[channel.key].append(value)

        window._update_plot()
        window.plot_items["state"].getViewBox().setYRange(0.0, 1.0, padding=0.0)
        window.channel_checks["tcmp1"].setChecked(True)

        y_range = window.plot_items["state"].getViewBox().viewRange()[1]
        self.assertLess(y_range[0], 4000.0)
        self.assertGreater(y_range[1], 4009.0)

    def test_primary_views_follow_programmatic_x_ranges(self):
        window = host.MyFocHostWindow()

        window._apply_plot_x_ranges({"state": (1.0, 2.0), "measure": (3.0, 4.0)})
        self.app.processEvents()

        state_range = window.plot_items["state"].getViewBox().viewRange()[0]
        measure_range = window.plot_items["measure"].getViewBox().viewRange()[0]
        self.assertAlmostEqual(state_range[0], 1.0, places=2)
        self.assertAlmostEqual(state_range[1], 2.0, places=2)
        self.assertAlmostEqual(measure_range[0], 3.0, places=2)
        self.assertAlmostEqual(measure_range[1], 4.0, places=2)

    def test_visible_windowed_curves_disable_auto_downsampling(self):
        window = host.MyFocHostWindow()

        for curve in window.curves.values():
            self.assertFalse(curve.opts.get("autoDownsample"))


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

    def test_firmware_diagnostic_order_matches_pc_parser(self):
        project_root = Path(__file__).resolve().parents[1]
        main_source = (project_root / "Core" / "Src" / "main.c").read_text(encoding="utf-8")

        assignments = dict(re.findall(r"load_data\[(\d+)\]\s*=\s*([^;]+);", main_source))
        expected = {
            0: "rtU.ia",
            1: "rtU.ib",
            2: "rtU.ic",
            3: "FluxTheta",
            4: "FluxWm",
            5: "rtU.RefSpeed",
            6: "rtU.v_bus",
            7: "FocDiagId",
            8: "FocDiagIq",
            9: "FocDiagIdRef",
            10: "FocDiagIqRef",
            11: "FocDiagUd",
            12: "FocDiagUq",
            13: "FocDiagTcmp1",
            14: "FocDiagTcmp2",
            15: "FocDiagTcmp3",
            16: "FocDiagState",
        }

        self.assertEqual(tuple(expected), tuple(range(len(host.TELEMETRY_KEYS_DIAGNOSTIC))))
        for index, source_expression in expected.items():
            self.assertEqual(assignments[str(index)].strip(), source_expression)


class TechnicalIssueDocTest(unittest.TestCase):
    def test_technical_issue_log_records_non_ui_issues(self):
        project_root = Path(__file__).resolve().parents[1]
        issue_log = project_root / "Docs" / "technical_issue_log.md"

        text = issue_log.read_text(encoding="utf-8")
        self.assertIn("串口命令偶发无响应", text)
        self.assertIn("低速给定反转和抖动", text)
        self.assertNotIn("缩放体验", text)
        self.assertNotIn("配色", text)


if __name__ == "__main__":
    unittest.main()
