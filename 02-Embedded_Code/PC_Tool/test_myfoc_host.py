import math
import os
import queue
import re
import struct
import sys
import tempfile
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

    def test_visible_curve_data_keeps_all_points_to_avoid_aliasing(self):
        x, y = host.visible_curve_data_for_plot(
            "measure",
            [0, 1, 2, 3, 4, 5, 6],
            [10, 11, 12, 13, 14, 15, 16],
            2,
            6,
            max_points=3,
        )

        self.assertEqual(list(x), [2.0, 3.0, 4.0, 5.0, 6.0])
        self.assertEqual(list(y), [12.0, 13.0, 14.0, 15.0, 16.0])

    def test_padded_y_range_ignores_nan(self):
        y_min, y_max = host.padded_y_range([1.0, float("nan"), 2.0], min_span=0.5)

        self.assertLess(y_min, 1.0)
        self.assertGreater(y_max, 2.0)

    def test_padded_y_range_centers_constant_large_signal_with_readable_padding(self):
        y_min, y_max = host.padded_y_range([600.0] * 16, min_span=0.5)

        self.assertAlmostEqual((y_min + y_max) * 0.5, 600.0, places=6)
        self.assertGreaterEqual(y_max - y_min, 50.0)


class PlotInteractionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6 import QtWidgets

        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_manual_zoom_keeps_that_plot_following_latest(self):
        window = host.MyFocHostWindow()

        window._on_plot_range_changed_manually("state")

        self.assertTrue(window.plot_follow_latest["state"])
        self.assertTrue(window.plot_follow_latest["measure"])

    def test_manual_zoom_disables_auto_y_for_that_plot(self):
        window = host.MyFocHostWindow()

        window._on_plot_range_changed_manually("state")

        self.assertFalse(window.plot_auto_y["state"])
        self.assertTrue(window.plot_auto_y["measure"])

    def test_auto_y_keeps_tracking_new_data_without_manual_zoom(self):
        window = host.MyFocHostWindow()

        for index in range(10):
            window.time_history.append(index * 0.1)
            for channel in host.CHANNELS:
                value = float(index)
                if channel.key == "speed":
                    value = 600.0 + index
                window.history[channel.key].append(value)

        window._refresh_visible_y_ranges(force=True)
        first_range = window.plot_items["state"].getViewBox().viewRange()[1]

        window.time_history.append(1.0)
        for channel in host.CHANNELS:
            value = 20.0
            if channel.key == "speed":
                value = 900.0
            window.history[channel.key].append(value)

        window._refresh_visible_y_ranges(force=True)
        second_range = window.plot_items["state"].getViewBox().viewRange()[1]

        self.assertTrue(window.plot_auto_y["state"])
        self.assertGreater(second_range[1], first_range[1])

    def test_drain_frames_updates_all_diagnostic_last_values(self):
        window = host.MyFocHostWindow()
        values = {
            "ia": 0.1,
            "ib": 0.2,
            "ic": 0.3,
            "theta": 1.2,
            "speed": 600.0,
            "ref": 650.0,
            "vbus": 24.0,
            "id": 0.01,
            "iq": 0.42,
            "id_ref": 0.0,
            "iq_ref": 0.5,
            "ud": -0.2,
            "uq": 8.3,
            "tcmp1": 3900.0,
            "tcmp2": 4100.0,
            "tcmp3": 4050.0,
            "foc_state": 5.0,
        }

        window.frame_queue.put_nowait((100.0, values))
        window._drain_frames()

        self.assertAlmostEqual(window.last_values["foc_state"], 5.0)
        self.assertAlmostEqual(window.last_values["iq_ref"], 0.5)

    def test_manual_zoom_updates_only_that_plot_window_width(self):
        window = host.MyFocHostWindow()
        old_measure_window = window.plot_window_spins["measure"].value()
        window.plot_items["state"].setXRange(1.0, 1.5, padding=0.0)

        window._on_plot_range_changed_manually("state")

        self.assertAlmostEqual(window.plot_window_spins["state"].value(), 0.5, places=2)
        self.assertAlmostEqual(window.plot_window_spins["measure"].value(), old_measure_window, places=2)

    def test_manual_zoom_keeps_curve_scrolling_with_new_data(self):
        window = host.MyFocHostWindow()

        for index in range(16):
            window.time_history.append(index * 0.1)
            for channel in host.CHANNELS:
                window.history[channel.key].append(float(index))

        window.plot_items["state"].setXRange(0.8, 1.2, padding=0.0)
        window._on_plot_range_changed_manually("state")

        for index in range(16, 31):
            window.time_history.append(index * 0.1)
            for channel in host.CHANNELS:
                window.history[channel.key].append(float(index))

        window._update_plot()

        view_range = window.plot_items["state"].getViewBox().viewRange()[0]
        self.assertAlmostEqual(view_range[1], 3.0, delta=0.02)
        self.assertAlmostEqual(view_range[1] - view_range[0], 0.4, delta=0.02)

    def test_paused_manual_pan_loads_historical_curve_window(self):
        window = host.MyFocHostWindow()
        for key, check in window.channel_checks.items():
            check.setChecked(key in {"speed", "ref"})

        for index in range(101):
            t = index * 0.1
            window.time_history.append(t)
            for channel in host.CHANNELS:
                value = 0.0
                if channel.key == "speed":
                    value = 500.0 + t
                elif channel.key == "ref":
                    value = 600.0
                window.history[channel.key].append(value)

        window._update_plot()
        latest_x, _ = window.curves["speed"].getData()
        self.assertGreater(float(latest_x[-1]), 9.0)

        window._set_paused(True)
        window.plot_items["state"].setXRange(2.0, 2.5, padding=0.0)
        window._on_plot_range_changed_manually("state")

        history_x, history_y = window.curves["speed"].getData()
        self.assertFalse(window.plot_follow_latest["state"])
        self.assertGreater(len(history_x), 0)
        self.assertLessEqual(float(history_x[0]), 2.05)
        self.assertGreaterEqual(float(history_x[-1]), 2.45)
        self.assertTrue(all(501.9 <= float(value) <= 502.6 for value in history_y))

    def test_manual_y_zoom_out_keeps_span_but_recenters_visible_data(self):
        window = host.MyFocHostWindow()
        view_box = window.plot_items["state"].getViewBox()

        self.assertTrue(view_box.state["mouseEnabled"][0])
        self.assertTrue(view_box.state["mouseEnabled"][1])

        for index in range(30):
            t = index * 0.1
            window.time_history.append(t)
            for channel in host.CHANNELS:
                value = 0.0
                if channel.key == "theta":
                    value = float(index)
                elif channel.key == "speed":
                    value = 500.0 + index * 5.0
                elif channel.key == "ref":
                    value = 600.0
                window.history[channel.key].append(value)

        window.plot_items["state"].setYRange(-100.0, 1000.0, padding=0.0)
        window.plot_items["state"].setXRange(2.3, 2.9, padding=0.0)
        window._on_plot_range_changed_manually("state")
        window._update_plot()

        y_range = window.plot_items["state"].getViewBox().viewRange()[1]
        self.assertAlmostEqual(y_range[1] - y_range[0], 1100.0, delta=2.0)
        self.assertLess(y_range[0], 600.0)
        self.assertGreater(y_range[1], 640.0)

    def test_manual_y_zoom_in_is_expanded_to_visible_data_with_padding(self):
        window = host.MyFocHostWindow()

        for index in range(30):
            t = index * 0.1
            window.time_history.append(t)
            for channel in host.CHANNELS:
                value = 0.0
                if channel.key == "speed":
                    value = 500.0 + index * 5.0
                elif channel.key == "ref":
                    value = 600.0
                window.history[channel.key].append(value)

        window.plot_items["state"].setXRange(2.3, 2.9, padding=0.0)
        window.plot_items["state"].setYRange(590.0, 610.0, padding=0.0)
        window._on_plot_range_changed_manually("state")

        y_range = window.plot_items["state"].getViewBox().viewRange()[1]
        self.assertLess(y_range[0], 600.0)
        self.assertGreater(y_range[1], 640.0)

    def test_channel_toggle_immediately_recomputes_y_range_for_new_scale(self):
        window = host.MyFocHostWindow()
        for key, check in window.channel_checks.items():
            check.setChecked(key == "ia")

        for index in range(20):
            window.time_history.append(index * 0.1)
            for channel in host.CHANNELS:
                value = 0.2
                if channel.key == "vbus":
                    value = 24.0
                window.history[channel.key].append(value)

        window._refresh_visible_y_ranges(force=True)
        ia_range = window.plot_items["measure"].getViewBox().viewRange()[1]
        window.plot_items["measure"].setYRange(-1.0, 1.0, padding=0.0)
        window._on_plot_range_changed_manually("measure")
        self.assertFalse(window.plot_auto_y["measure"])

        window.channel_checks["ia"].setChecked(False)
        window.channel_checks["vbus"].setChecked(True)
        vbus_range = window.plot_items["measure"].getViewBox().viewRange()[1]

        self.assertTrue(window.plot_auto_y["measure"])
        self.assertLess(ia_range[1], 2.0)
        self.assertLess(vbus_range[0], 24.0)
        self.assertGreater(vbus_range[1], 24.0)
        self.assertGreater(vbus_range[0], 20.0)

    def test_send_speed_autoscales_state_plot_to_requested_reference(self):
        window = host.MyFocHostWindow()
        for key, check in window.channel_checks.items():
            check.setChecked(key in {"speed", "ref"})

        for index in range(20):
            window.time_history.append(index * 0.1)
            for channel in host.CHANNELS:
                value = 0.0
                if channel.key in {"speed", "ref"}:
                    value = 600.0
                window.history[channel.key].append(value)

        window._refresh_visible_y_ranges(force=True)
        window.plot_items["state"].setYRange(580.0, 620.0, padding=0.0)
        window._on_plot_range_changed_manually("state")
        self.assertFalse(window.plot_auto_y["state"])

        window.speed_spin.setValue(1200.0)
        with mock.patch.object(window, "send_control_command"):
            window.send_speed()

        y_range = window.plot_items["state"].getViewBox().viewRange()[1]
        self.assertTrue(window.plot_auto_y["state"])
        self.assertLess(y_range[0], 600.0)
        self.assertGreater(y_range[1], 1200.0)

    def test_target_speed_edit_previews_state_y_range_before_send(self):
        window = host.MyFocHostWindow()
        for key, check in window.channel_checks.items():
            check.setChecked(key in {"speed", "ref"})

        for index in range(20):
            window.time_history.append(index * 0.1)
            for channel in host.CHANNELS:
                value = 0.0
                if channel.key in {"speed", "ref"}:
                    value = 600.0
                window.history[channel.key].append(value)

        window._refresh_visible_y_ranges(force=True)
        initial_y_range = window.plot_items["state"].getViewBox().viewRange()[1]
        self.assertLess(initial_y_range[1], 700.0)

        window.speed_spin.setValue(1200.0)

        preview_y_range = window.plot_items["state"].getViewBox().viewRange()[1]
        self.assertLess(preview_y_range[0], 600.0)
        self.assertGreater(preview_y_range[1], 1200.0)

    def test_target_speed_edit_schedules_delayed_y_autoscale(self):
        window = host.MyFocHostWindow()
        for key, check in window.channel_checks.items():
            check.setChecked(key in {"speed", "ref"})

        for index in range(20):
            window.time_history.append(index * 0.1)
            for channel in host.CHANNELS:
                value = 0.0
                if channel.key in {"speed", "ref"}:
                    value = 600.0
                window.history[channel.key].append(value)

        with mock.patch.object(host.QtCore.QTimer, "singleShot") as single_shot:
            window.speed_spin.setValue(1200.0)

        self.assertTrue(
            any(call.args[0] == 800 for call in single_shot.call_args_list)
        )

    def test_target_speed_edit_expands_small_window_to_tracking_window(self):
        window = host.MyFocHostWindow()
        for key, check in window.channel_checks.items():
            check.setChecked(key in {"speed", "ref"})

        for index in range(101):
            t = index * 0.1
            window.time_history.append(t)
            for channel in host.CHANNELS:
                value = 0.0
                if channel.key in {"speed", "ref"}:
                    value = 600.0
                window.history[channel.key].append(value)

        window.plot_window_spins["state"].setValue(1.5)
        window._update_plot()
        window.plot_items["state"].setXRange(9.7, 10.0, padding=0.0)
        window._on_plot_range_changed_manually("state")
        self.assertAlmostEqual(window.plot_window_spins["state"].value(), 0.3, places=2)
        self.assertFalse(window.plot_auto_y["state"])

        window.speed_spin.setValue(1200.0)

        view_range = window.plot_items["state"].getViewBox().viewRange()[0]
        self.assertAlmostEqual(window.plot_window_spins["state"].value(), host.TARGET_TRACKING_WINDOW_MIN_S, places=2)
        self.assertAlmostEqual(view_range[1] - view_range[0], 5.1, delta=0.04)
        self.assertGreater(view_range[1], 10.0)
        self.assertTrue(window.plot_auto_y["state"])

    def test_target_speed_edit_uses_at_least_tracking_window_after_wheel_zoom(self):
        window = host.MyFocHostWindow()
        for key, check in window.channel_checks.items():
            check.setChecked(key in {"speed", "ref"})

        for index in range(101):
            t = index * 0.1
            window.time_history.append(t)
            for channel in host.CHANNELS:
                value = 0.0
                if channel.key in {"speed", "ref"}:
                    value = 600.0
                window.history[channel.key].append(value)

        window._apply_plot_x_ranges({"state": (7.0, 10.0), "measure": (7.0, 10.0)})
        window.plot_items["state"].setXRange(9.7, 10.0, padding=0.0)
        window._on_plot_range_changed_manually("state")

        window.speed_spin.setValue(1200.0)

        view_range = window.plot_items["state"].getViewBox().viewRange()[0]
        self.assertAlmostEqual(window.plot_window_spins["state"].value(), host.TARGET_TRACKING_WINDOW_MIN_S, places=2)
        self.assertAlmostEqual(view_range[1] - view_range[0], 5.1, delta=0.04)
        self.assertGreater(view_range[1], 10.0)

    def test_main_panel_removes_fast_changing_summary_cards(self):
        window = host.MyFocHostWindow()

        self.assertEqual(window.summary_cards, [])

    def test_main_header_has_no_explanatory_subtitle(self):
        window = host.MyFocHostWindow()

        hint_labels = window.main_panel.findChildren(host.QtWidgets.QLabel, "hintText")
        self.assertFalse(any(label.parent().objectName() == "mainHeader" for label in hint_labels))

    def test_sidebar_has_no_app_subtitle(self):
        window = host.MyFocHostWindow()

        self.assertFalse(window.sidebar_scroll.findChildren(host.QtWidgets.QLabel, "appSubtitle"))

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
        self.assertEqual(window.theme_button.text(), "🌙")
        self.assertEqual(window.pause_button.minimumSize().height(), 38)
        self.assertEqual(window.rate_label.minimumHeight(), 36)

    def test_plot_toolbar_uses_drawn_icons_instead_of_text_glyphs(self):
        window = host.MyFocHostWindow()

        for button in (
            window.pause_button,
            window.log_button,
            window.reset_view_button,
            window.clear_data_button,
        ):
            self.assertEqual(button.text(), "")
            self.assertFalse(button.icon().isNull())
            self.assertEqual(button.iconSize(), host.QtCore.QSize(22, 22))

        self.assertEqual(window.theme_button.text(), "🌙")
        self.assertTrue(window.theme_button.icon().isNull())

        window._set_paused(True)
        self.assertEqual(window.pause_button.text(), "")
        self.assertFalse(window.pause_button.icon().isNull())

    def test_reset_icon_uses_top_right_filled_arrow_head(self):
        window = host.MyFocHostWindow()

        image = window._make_toolbar_icon("reset", "#475569").pixmap(24, 24).toImage()

        self.assertGreater(image.pixelColor(20, 6).alpha(), 120)
        self.assertGreater(image.pixelColor(13, 3).alpha(), 120)

    def test_theme_button_uses_moon_and_sun_emoji(self):
        window = host.MyFocHostWindow()

        self.assertEqual(window.theme_button.text(), "🌙")
        window.theme_button.setChecked(True)
        self.assertEqual(window.theme_button.text(), "☀")

    def test_follow_and_auto_y_sidebar_buttons_are_removed(self):
        window = host.MyFocHostWindow()

        self.assertFalse(hasattr(window, "follow_latest_button"))
        self.assertFalse(hasattr(window, "auto_y_button"))
        self.assertFalse(window.sidebar_scroll.findChildren(host.QtWidgets.QPushButton, "plotToggleButton"))

    def test_csv_logging_keeps_record_button_icon_only(self):
        import tempfile

        window = host.MyFocHostWindow()
        self.assertEqual(window.log_button.property("iconKind"), "record")

        with tempfile.TemporaryDirectory() as data_root:
            with mock.patch("myfoc_host.os.path.dirname", return_value=data_root):
                window._start_logging()
                try:
                    self.assertTrue(window.logging)
                    self.assertEqual(window.log_button.text(), "")
                    self.assertFalse(window.log_button.icon().isNull())
                    self.assertEqual(window.log_button.property("iconKind"), "record_pause")
                finally:
                    window._stop_logging()
                self.assertFalse(window.logging)
                self.assertEqual(window.log_button.text(), "")
                self.assertFalse(window.log_button.icon().isNull())
                self.assertEqual(window.log_button.property("iconKind"), "record")

    def test_record_icon_is_white_center_dot_only(self):
        window = host.MyFocHostWindow()

        image = window._make_toolbar_icon("record", "#475569").pixmap(24, 24).toImage()
        center = image.pixelColor(12, 12)
        larger_dot_edge = image.pixelColor(15, 12)
        outer = image.pixelColor(12, 5)

        self.assertGreater(center.red(), 240)
        self.assertGreater(center.green(), 240)
        self.assertGreater(center.blue(), 240)
        self.assertGreater(larger_dot_edge.alpha(), 180)
        self.assertLess(outer.alpha(), 20)

    def test_record_button_style_is_red_circle(self):
        window = host.MyFocHostWindow()

        style = window._style_sheet()

        self.assertIn("#recordButton", style)
        self.assertIn("background: #e05264;", style)
        self.assertIn("border-color: #e05264;", style)

    def test_sidebar_is_compact_without_visible_scrollbar(self):
        window = host.MyFocHostWindow()

        self.assertEqual(
            window.sidebar_scroll.verticalScrollBarPolicy(),
            host.QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.assertLessEqual(window.console.maximumHeight(), 72)
        self.assertLessEqual(window.speed_spin.minimumHeight(), 32)
        self.assertLessEqual(window.port_combo.minimumHeight(), 32)

    def test_sidebar_viewport_is_not_narrower_than_content(self):
        window = host.MyFocHostWindow()
        window.resize(1539, 1000)
        window.show()
        self.app.processEvents()

        self.assertGreaterEqual(
            window.sidebar_scroll.viewport().width(),
            window.sidebar_scroll.widget().width(),
        )

    def test_combo_boxes_use_flat_modern_style_hook(self):
        window = host.MyFocHostWindow()

        self.assertEqual(window.port_combo.objectName(), "flatCombo")
        self.assertEqual(window.baud_box.objectName(), "flatCombo")

    def test_port_combo_shows_short_device_name_with_full_tooltip(self):
        class FakePort:
            device = "COM11"
            description = "USB-SERIAL CH340 (COM11)"

        class FakeListPorts:
            @staticmethod
            def comports():
                return [FakePort()]

        with mock.patch.object(host, "list_ports", FakeListPorts):
            window = host.MyFocHostWindow()

        self.assertEqual(window.port_combo.currentText(), "COM11")
        self.assertEqual(window.port_combo.currentData(), "COM11")
        self.assertIn("USB-SERIAL CH340", window.port_combo.toolTip())

    def test_waveform_uses_two_stacked_plot_panels(self):
        window = host.MyFocHostWindow()

        self.assertEqual(tuple(window.plot_items.keys()), ("state", "measure"))
        self.assertEqual(host.PLOT_PANELS["state"]["channels"], ("theta", "speed", "ref", "tcmp1", "tcmp2", "tcmp3"))
        self.assertEqual(host.PLOT_PANELS["measure"]["channels"], ("ia", "ib", "ic", "id", "iq", "id_ref", "iq_ref", "ud", "uq", "vbus"))
        self.assertNotIn("foc_state", window.channel_checks)
        self.assertFalse(window.legends)

    def test_two_plot_cards_share_available_height_equally(self):
        window = host.MyFocHostWindow()
        layout = window.plot_panel.layout()

        self.assertEqual(layout.count(), 2)
        self.assertEqual(layout.stretch(0), 1)
        self.assertEqual(layout.stretch(1), 1)
        for index in range(layout.count()):
            row = layout.itemAt(index).widget()
            self.assertEqual(row.sizePolicy().verticalPolicy(), host.QtWidgets.QSizePolicy.Policy.Expanding)

    def test_waveform_uses_one_y_axis_per_plot(self):
        window = host.MyFocHostWindow()

        self.assertEqual(set(window.plot_axis_views["state"]), {"value"})
        self.assertEqual(set(window.plot_axis_views["measure"]), {"value"})
        self.assertEqual(window.plot_axis_items["state"]["value"], window.plot_items["state"].getAxis("left"))
        self.assertEqual(window.plot_axis_items["measure"]["value"], window.plot_items["measure"].getAxis("left"))

    def test_plot_panels_do_not_show_internal_titles_or_value_axis_label(self):
        window = host.MyFocHostWindow()

        for plot_item in window.plot_items.values():
            self.assertEqual(plot_item.titleLabel.text, "")
            self.assertEqual(plot_item.getAxis("left").labelText, "")

    def test_plot_cards_use_compact_margins_for_larger_canvas(self):
        window = host.MyFocHostWindow()
        plot_panel_layout = window.plot_panel.layout()

        self.assertLessEqual(plot_panel_layout.contentsMargins().top(), 10)
        for index in range(plot_panel_layout.count()):
            row = plot_panel_layout.itemAt(index).widget()
            self.assertLessEqual(row.layout().contentsMargins().top(), 8)

    def test_default_visible_channels_are_speed_ref_and_iabc(self):
        window = host.MyFocHostWindow()

        checked_channels = {
            key
            for key, check in window.channel_checks.items()
            if check.isChecked()
        }

        self.assertEqual(checked_channels, {"speed", "ref", "ia", "ib", "ic"})

    def test_dq_reference_channels_use_distinct_colors(self):
        def rgb_distance(left, right):
            left = host.QtGui.QColor(left)
            right = host.QtGui.QColor(right)
            return math.sqrt(
                (left.red() - right.red()) ** 2
                + (left.green() - right.green()) ** 2
                + (left.blue() - right.blue()) ** 2
            )

        self.assertGreater(rgb_distance(host.CHANNEL_COLORS["id"], host.CHANNEL_COLORS["id_ref"]), 80.0)
        self.assertGreater(rgb_distance(host.CHANNEL_COLORS["iq"], host.CHANNEL_COLORS["iq_ref"]), 80.0)

    def test_manual_y_range_expands_when_live_speed_drops(self):
        window = host.MyFocHostWindow()
        for key, check in window.channel_checks.items():
            check.setChecked(key in {"speed", "ref"})

        for index in range(10):
            window.time_history.append(index * 0.1)
            for channel in host.CHANNELS:
                value = 600.0 if channel.key in {"speed", "ref"} else 0.0
                window.history[channel.key].append(value)

        window.plot_items["state"].setYRange(580.0, 620.0, padding=0.0)
        window._on_plot_range_changed_manually("state")
        self.assertFalse(window.plot_auto_y["state"])

        window.time_history.append(1.0)
        for channel in host.CHANNELS:
            if channel.key == "speed":
                value = 420.0
            elif channel.key == "ref":
                value = 600.0
            else:
                value = 0.0
            window.history[channel.key].append(value)

        window._update_plot()

        y_range = window.plot_items["state"].getViewBox().viewRange()[1]
        self.assertLess(y_range[0], 420.0)
        self.assertGreater(y_range[1], 600.0)

    def test_plot_grid_is_visible_but_low_contrast_in_both_themes(self):
        window = host.MyFocHostWindow()

        self.assertGreaterEqual(window._plot_grid_alpha(), 0.28)
        self.assertLessEqual(window._plot_grid_alpha(), 0.50)

        window.theme_button.setChecked(True)

        self.assertGreaterEqual(window._plot_grid_alpha(), 0.18)
        self.assertLessEqual(window._plot_grid_alpha(), 0.38)

    def test_grid_checkbox_removed_and_grid_is_always_enabled(self):
        window = host.MyFocHostWindow()

        self.assertFalse(hasattr(window, "grid_check"))

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
        repeat_intervals = {
            host.CONTROL_COMMAND_REPEAT_INTERVAL_MS * repeat_index
            for repeat_index in range(1, host.CONTROL_COMMAND_REPEAT_COUNT)
        }
        repeat_calls = [
            call
            for call in single_shot.call_args_list
            if call.args[0] in repeat_intervals
        ]
        self.assertEqual(len(repeat_calls), host.CONTROL_COMMAND_REPEAT_COUNT - 1)

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


class ParameterIdentificationGuiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6 import QtWidgets

        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_rs_identification_loads_csv_and_reports_result(self):
        window = host.MyFocHostWindow()
        self.addCleanup(window.close)
        self.addCleanup(window.deleteLater)

        self.assertTrue(window.identify_rs_button.isEnabled())
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "rs_capture.csv"
            rows = []
            for level_index, current in enumerate([-0.6, -0.4, 0.4, 0.6]):
                for sample_index in range(6):
                    measured_current = current + sample_index * 0.0002
                    rows.append(
                        f"{level_index},{measured_current},{6.97 * measured_current + 0.32},0.1"
                    )
            csv_path.write_text(
                "id_level,id_current_meas,id_voltage_eff,speed\n" + "\n".join(rows),
                encoding="utf-8",
            )

            with mock.patch.object(
                host.QtWidgets.QFileDialog,
                "getOpenFileName",
                return_value=(str(csv_path), "CSV"),
            ):
                result = window.identify_rs_from_csv()

        self.assertAlmostEqual(result.rs_ohm, 6.97, places=3)
        self.assertIn("Rs ID", window.console.toPlainText())
        self.assertIn("6.9700", window.console.toPlainText())
        self.assertIn("Rs ID OK", window.statusBar().currentMessage())


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
