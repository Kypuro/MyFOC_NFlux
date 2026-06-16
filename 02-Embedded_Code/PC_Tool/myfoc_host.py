import csv
import math
import os
import queue
import struct
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


BAUD_DEFAULT = 2_000_000
UI_UPDATE_MS = 50
AUTO_Y_RANGE_INTERVAL_S = 0.20
Y_RANGE_PADDING_RATIO = 0.15
CONTROL_COMMAND_REPEAT_COUNT = 3
CONTROL_COMMAND_REPEAT_INTERVAL_MS = 35
FRAME_TAIL = b"\x00\x00\x80\x7f"
FRAME_FLOAT_COUNT_DIAGNOSTIC = 17
FRAME_FLOAT_COUNT_EXTENDED = 8
FRAME_FLOAT_COUNT_NEW = 7
FRAME_FLOAT_COUNT_LEGACY = 6
FRAME_PAYLOAD_SIZE_DIAGNOSTIC = FRAME_FLOAT_COUNT_DIAGNOSTIC * 4
FRAME_PAYLOAD_SIZE_EXTENDED = FRAME_FLOAT_COUNT_EXTENDED * 4
FRAME_PAYLOAD_SIZE_NEW = FRAME_FLOAT_COUNT_NEW * 4
FRAME_PAYLOAD_SIZE_LEGACY = FRAME_FLOAT_COUNT_LEGACY * 4
FRAME_SIZE_MAX = FRAME_PAYLOAD_SIZE_DIAGNOSTIC + len(FRAME_TAIL)
UART_BITS_PER_BYTE = 10
TELEMETRY_KEYS_DIAGNOSTIC = (
    "ia", "ib", "ic", "theta", "speed", "ref", "vbus",
    "id", "iq", "id_ref", "iq_ref", "ud", "uq",
    "tcmp1", "tcmp2", "tcmp3", "foc_state",
)
TELEMETRY_KEYS_NEW = ("ia", "ib", "ic", "theta", "speed", "ref", "vbus")
TELEMETRY_KEYS_LEGACY = ("ia", "theta", "speed", "ref", "vbus")
CSV_HEADERS = (
    "time_s", "ia", "ib", "ic", "FluxTheta", "FluxWm", "RefSpeed", "vbus",
    "Id", "Iq", "Id_ref", "Iq_ref", "Ud", "Uq",
    "Tcmp1", "Tcmp2", "Tcmp3", "FOC_state",
)
HISTORY_LEN = 30000
SPEED_MIN = 120.0
SPEED_MAX = 1800.0
CURRENT_ABS_VALID_MAX = 100.0
THETA_VALID_MIN = -0.25
THETA_VALID_MAX = 2.0 * math.pi + 0.25
SPEED_ABS_VALID_MAX = 20000.0
VBUS_VALID_MIN = -0.5
VBUS_VALID_MAX = 120.0
PLOT_WINDOW_MIN = 0.05
PLOT_WINDOW_MAX = 120.0
PLOT_GRID_ALPHA_LIGHT = 0.36
PLOT_GRID_ALPHA_DARK = 0.24
PLOT_PANELS = {
    "state": {
        "title": "State / Control",
        "channels": ("theta", "speed", "ref", "tcmp1", "tcmp2", "tcmp3", "foc_state"),
        "axes": ("value",),
    },
    "measure": {
        "title": "Current / Voltage",
        "channels": ("ia", "ib", "ic", "id", "iq", "id_ref", "iq_ref", "ud", "uq", "vbus"),
        "axes": ("value",),
    },
}
PLOT_DEFAULT_WINDOWS = {
    "state": 0.65,
    "measure": 0.65,
}
PLOT_MAX_VISIBLE_POINTS = {
    "state": 6000,
    "measure": 6000,
}
PLOT_Y_MIN_SPANS = {
    "state": 0.5,
    "measure": 0.1,
}
THETA_PLOT_Y_MIN = -1.0
THETA_PLOT_Y_MAX = 7.0
CHANNEL_SHORT_LABELS = {
    "ia": "Ia",
    "ib": "Ib",
    "ic": "Ic",
    "theta": "θ",
    "speed": "Speed",
    "ref": "Ref",
    "vbus": "Vbus",
    "id": "Id",
    "iq": "Iq",
    "id_ref": "Id ref",
    "iq_ref": "Iq ref",
    "ud": "Ud",
    "uq": "Uq",
    "tcmp1": "T1",
    "tcmp2": "T2",
    "tcmp3": "T3",
    "foc_state": "FOC",
}
CHANNEL_COLORS = {
    "ia": "#d96a78",
    "ib": "#47b8ac",
    "ic": "#6b98d6",
    "theta": "#9a8fe3",
    "speed": "#5aa7bf",
    "ref": "#d0a24a",
    "vbus": "#a488d4",
    "id": "#8d99aa",
    "iq": "#69aa9b",
    "id_ref": "#adb5c2",
    "iq_ref": "#76ad84",
    "ud": "#cb8756",
    "uq": "#c36b66",
    "tcmp1": "#9a8fe3",
    "tcmp2": "#a68ad0",
    "tcmp3": "#b596cf",
    "foc_state": "#818da0",
}
CHANNEL_AXIS_KEYS = {
    "ia": "A",
    "ib": "A",
    "ic": "A",
    "id": "A",
    "iq": "A",
    "id_ref": "A",
    "iq_ref": "A",
    "ud": "V",
    "uq": "V",
    "vbus": "V",
    "theta": "rad",
    "speed": "rpm",
    "ref": "rpm",
    "tcmp1": "count",
    "tcmp2": "count",
    "tcmp3": "count",
    "foc_state": "state",
}
CHANNEL_PANEL_KEYS = {
    channel_key: panel_key
    for panel_key, panel in PLOT_PANELS.items()
    for channel_key in panel["channels"]
}


def rgba_from_hex(hex_color, alpha):
    color = QtGui.QColor(hex_color)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"


def channel_pill_style(hex_color):
    idle_bg = rgba_from_hex(hex_color, 18)
    idle_border = rgba_from_hex(hex_color, 92)
    active_bg = rgba_from_hex(hex_color, 168)
    active_border = rgba_from_hex(hex_color, 220)
    return f"""
    QPushButton#channelPill {{
        background: {idle_bg};
        border: 1px solid {idle_border};
        border-radius: 15px;
        color: {hex_color};
        font-weight: 700;
        padding: 6px 12px;
        min-height: 18px;
        text-align: left;
    }}
    QPushButton#channelPill:checked {{
        background: {active_bg};
        border-color: {active_border};
        color: #ffffff;
    }}
    QPushButton#channelPill:hover {{
        border-color: {active_border};
    }}
    """


def port_name_from_combo_text(text):
    text = text.strip()
    if not text:
        return ""
    return text.split()[0]


def wrap_angle_0_2pi(theta):
    if not math.isfinite(theta):
        return theta
    return theta % (2.0 * math.pi)


def is_plausible_telemetry(values):
    required_keys = ("ia", "theta", "speed", "ref", "vbus")
    if any(not math.isfinite(float(values.get(key, float("nan")))) for key in required_keys):
        return False

    for key in ("ib", "ic"):
        if key in values and not math.isfinite(float(values[key])):
            return False

    for key in ("id", "iq", "id_ref", "iq_ref", "ud", "uq", "tcmp1", "tcmp2", "tcmp3", "foc_state"):
        if key in values and not math.isfinite(float(values[key])):
            return False

    current_keys = ("ia", "ib", "ic")
    if any(abs(float(values[key])) > CURRENT_ABS_VALID_MAX for key in current_keys if key in values):
        return False

    dq_current_keys = ("id", "iq", "id_ref", "iq_ref")
    if any(abs(float(values[key])) > CURRENT_ABS_VALID_MAX for key in dq_current_keys if key in values):
        return False

    dq_voltage_keys = ("ud", "uq")
    if any(abs(float(values[key])) > 200.0 for key in dq_voltage_keys if key in values):
        return False

    if any(not -1000.0 <= float(values[key]) <= 9000.0 for key in ("tcmp1", "tcmp2", "tcmp3") if key in values):
        return False

    if "foc_state" in values and not -1.0 <= float(values["foc_state"]) <= 10.0:
        return False

    theta = float(values["theta"])
    speed = float(values["speed"])
    ref = float(values["ref"])
    vbus = float(values["vbus"])
    return (
        THETA_VALID_MIN <= theta <= THETA_VALID_MAX
        and abs(speed) <= SPEED_ABS_VALID_MAX
        and abs(ref) <= SPEED_ABS_VALID_MAX
        and VBUS_VALID_MIN <= vbus <= VBUS_VALID_MAX
    )


def time_range_for_latest(latest_time, window, x_values=None, y_values=None):
    window = max(PLOT_WINDOW_MIN, min(PLOT_WINDOW_MAX, float(window)))
    latest_time = float(latest_time)
    left = max(0.0, latest_time - window)
    right = latest_time + max(0.005, window * 0.02)
    if right <= left:
        right = left + 0.5

    if x_values is not None and y_values is not None:
        x = np.asarray(x_values, dtype=float)
        y = np.asarray(y_values, dtype=float)
        if len(x) == len(y) and len(x) > 0:
            mask = (x >= left) & (x <= right) & np.isfinite(y)
            if np.any(mask):
                left = max(left, float(x[mask][0]))
    return left, right


def curve_data_for_plot(plot_key, x_values, y_values):
    x = np.asarray(x_values, dtype=float)
    y = np.asarray(y_values, dtype=float)
    return x, y


def visible_curve_data_for_plot(plot_key, x_values, y_values, left, right, max_points=None):
    x = np.asarray(x_values, dtype=float)
    y = np.asarray(y_values, dtype=float)
    if len(x) != len(y) or len(x) == 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)

    mask = (x >= float(left)) & (x <= float(right))
    x = x[mask]
    y = y[mask]
    if max_points is not None and len(x) > max_points:
        step = max(1, math.ceil(len(x) / int(max_points)))
        x = x[::step]
        y = y[::step]
    return curve_data_for_plot(plot_key, x, y)


def padded_y_range(y_values, min_span):
    y = np.asarray(y_values, dtype=float)
    y = y[np.isfinite(y)]
    if len(y) == 0:
        return None

    y_min = float(np.min(y))
    y_max = float(np.max(y))
    span = max(y_max - y_min, float(min_span))
    center = (y_min + y_max) * 0.5
    half = span * 0.5
    pad = span * Y_RANGE_PADDING_RATIO
    return center - half - pad, center + half + pad


@dataclass(frozen=True)
class Channel:
    key: str
    label: str
    unit: str
    color: str
    plot: str
    default_visible: bool = True


CHANNELS = [
    Channel("ia", "A 相电流", "A", "#ef476f", "current", True),
    Channel("ib", "B 相电流", "A", "#06d6a0", "current", True),
    Channel("ic", "C 相电流", "A", "#3b82f6", "current", True),
    Channel("theta", "磁链角", "rad", "#8b5cf6", "theta", True),
    Channel("speed", "观测速度", "rpm", "#118ab2", "speed", True),
    Channel("ref", "参考速度", "rpm", "#f59f00", "speed", True),
    Channel("vbus", "控制母线电压", "V", "#a855f7", "voltage", True),
    Channel("id", "Id", "A", "#64748b", "current", False),
    Channel("iq", "Iq", "A", "#0f766e", "current", False),
    Channel("id_ref", "Id_ref", "A", "#94a3b8", "current", False),
    Channel("iq_ref", "Iq_ref", "A", "#16a34a", "current", False),
    Channel("ud", "Ud", "V", "#f97316", "voltage", False),
    Channel("uq", "Uq", "V", "#dc2626", "voltage", False),
    Channel("tcmp1", "Tcmp1", "count", "#7c3aed", "voltage", False),
    Channel("tcmp2", "Tcmp2", "count", "#9333ea", "voltage", False),
    Channel("tcmp3", "Tcmp3", "count", "#a855f7", "voltage", False),
    Channel("foc_state", "FOC_state", "", "#475569", "speed", False),
]

CHANNELS = [
    Channel(
        channel.key,
        CHANNEL_SHORT_LABELS[channel.key],
        CHANNEL_AXIS_KEYS[channel.key],
        CHANNEL_COLORS[channel.key],
        CHANNEL_PANEL_KEYS[channel.key],
        channel.default_visible,
    )
    for channel in CHANNELS
]
CHANNEL_BY_KEY = {channel.key: channel for channel in CHANNELS}
PRIMARY_CARD_KEYS = ("ia", "ib", "ic", "theta", "speed", "ref", "vbus")
DIAGNOSTIC_VALUE_KEYS = (
    "id",
    "iq",
    "id_ref",
    "iq_ref",
    "ud",
    "uq",
    "tcmp1",
    "tcmp2",
    "tcmp3",
    "foc_state",
)

class WorkerSignals(QtCore.QObject):
    status = QtCore.Signal(str)
    disconnected = QtCore.Signal()


class SerialWorker:
    def __init__(self, frame_queue):
        self.frame_queue = frame_queue
        self.signals = WorkerSignals()
        self.serial = None
        self.thread = None
        self.running = threading.Event()
        self.write_lock = threading.Lock()
        self.frame_interval_s = (FRAME_SIZE_MAX * UART_BITS_PER_BYTE) / BAUD_DEFAULT
        self.last_frame_timestamp = None

    def start(self, port, baud):
        if serial is None:
            raise RuntimeError("缺少 pyserial，请先运行 run.bat 安装依赖。")

        self.stop()
        self.serial = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.02,
            write_timeout=0.2,
        )
        self.frame_interval_s = (FRAME_SIZE_MAX * UART_BITS_PER_BYTE) / float(baud)
        self.last_frame_timestamp = None
        self.running.set()
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
        self.signals.status.emit(f"已连接 {port} @ {baud}")

    def stop(self):
        self.running.clear()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)
        self.thread = None

        if self.serial:
            try:
                self.serial.close()
            except serial.SerialException:
                pass
        self.serial = None

    def is_open(self):
        return self.serial is not None and self.serial.is_open

    def send_line(self, text):
        if not self.is_open():
            raise RuntimeError("串口未连接。")

        data = (text.strip() + "\n").encode("ascii", errors="ignore")
        with self.write_lock:
            self.serial.write(data)
            self.serial.flush()

    def _read_loop(self):
        buffer = bytearray()

        while self.running.is_set():
            try:
                chunk = self.serial.read(4096)
            except serial.SerialException as exc:
                self.signals.status.emit(f"串口读取错误：{exc}")
                break

            if chunk:
                buffer.extend(chunk)
                self._parse_buffer(buffer, time.perf_counter())
            elif len(buffer) > FRAME_SIZE_MAX * 16:
                del buffer[:-FRAME_SIZE_MAX]

        self.running.clear()
        self.signals.disconnected.emit()

    def _queue_frame(self, timestamp, values):
        item = (timestamp, values)
        try:
            self.frame_queue.put_nowait(item)
        except queue.Full:
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                pass
            self.frame_queue.put_nowait(item)

    def _queue_parsed_frames(self, frames, received_at):
        if not frames:
            return

        interval = self.frame_interval_s
        first_timestamp = received_at - (len(frames) - 1) * interval
        if self.last_frame_timestamp is not None:
            first_timestamp = self.last_frame_timestamp + interval

        for index, values in enumerate(frames):
            self._queue_frame(first_timestamp + index * interval, values)

        self.last_frame_timestamp = first_timestamp + (len(frames) - 1) * interval

    def _parse_buffer(self, buffer, received_at=None):
        if received_at is None:
            received_at = time.perf_counter()

        frames = []
        while True:
            tail_index = buffer.find(FRAME_TAIL)
            if tail_index < 0:
                if len(buffer) > 8192:
                    del buffer[:-FRAME_SIZE_MAX]
                self._queue_parsed_frames(frames, received_at)
                return

            values = self._decode_frame_before_tail(buffer, tail_index)
            del buffer[:tail_index + len(FRAME_TAIL)]
            if values is not None:
                frames.append(values)

    def _decode_frame_before_tail(self, buffer, tail_index):
        candidates = (
            (FRAME_PAYLOAD_SIZE_DIAGNOSTIC, FRAME_FLOAT_COUNT_DIAGNOSTIC, TELEMETRY_KEYS_DIAGNOSTIC, False),
            (FRAME_PAYLOAD_SIZE_EXTENDED, FRAME_FLOAT_COUNT_EXTENDED, TELEMETRY_KEYS_NEW, False),
            (FRAME_PAYLOAD_SIZE_NEW, FRAME_FLOAT_COUNT_NEW, TELEMETRY_KEYS_NEW, False),
            (FRAME_PAYLOAD_SIZE_LEGACY, FRAME_FLOAT_COUNT_LEGACY, TELEMETRY_KEYS_LEGACY, True),
        )
        for payload_size, float_count, keys, legacy_missing_phases in candidates:
            if tail_index < payload_size:
                continue

            start = tail_index - payload_size
            payload = bytes(buffer[start:tail_index])
            try:
                raw_values = struct.unpack(f"<{float_count}f", payload)
            except struct.error:
                continue

            values = dict(zip(keys, raw_values))
            if legacy_missing_phases and is_plausible_telemetry(values):
                values["ib"] = float("nan")
                values["ic"] = float("nan")
                return values
            if not legacy_missing_phases and is_plausible_telemetry(values):
                return values

        return None


class TelemetryCard(QtWidgets.QFrame):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        self.setObjectName("telemetryCard")
        self.setMinimumHeight(54)
        self.setMaximumHeight(62)

        stripe = QtWidgets.QFrame()
        stripe.setFixedWidth(5)
        stripe.setStyleSheet(f"background: {channel.color}; border-radius: 2px;")

        self.title = QtWidgets.QLabel(channel.label)
        self.title.setObjectName("cardTitle")
        self.value = QtWidgets.QLabel("--")
        self.value.setObjectName("cardValue")
        self.unit = QtWidgets.QLabel(channel.unit)
        self.unit.setObjectName("cardUnit")

        value_row = QtWidgets.QHBoxLayout()
        value_row.setSpacing(6)
        value_row.addWidget(self.value)
        value_row.addWidget(self.unit)
        value_row.addStretch(1)

        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setContentsMargins(10, 4, 6, 4)
        text_layout.setSpacing(0)
        text_layout.addWidget(self.title)
        text_layout.addLayout(value_row)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(0)
        layout.addWidget(stripe)
        layout.addLayout(text_layout)

    def set_value(self, value):
        if math.isfinite(value):
            self.value.setText(f"{value:.4g}")
        else:
            self.value.setText("--")


class SummaryCard(QtWidgets.QFrame):
    def __init__(self, title, rows):
        super().__init__()
        self.rows = rows
        self.value_labels = {}
        self.setObjectName("summaryCard")
        self.setMinimumHeight(56)
        self.setMaximumHeight(68)

        self.title = QtWidgets.QLabel(title)
        self.title.setObjectName("summaryTitle")

        values_layout = QtWidgets.QHBoxLayout()
        values_layout.setSpacing(8)
        for key, label, unit in rows:
            value = QtWidgets.QLabel("--")
            value.setObjectName("summaryValue")
            self.value_labels[key] = (value, label, unit)
            values_layout.addWidget(value)
        values_layout.addStretch(1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(2)
        layout.addWidget(self.title)
        layout.addLayout(values_layout)

    def set_values(self, values):
        for key, (label_widget, label, unit) in self.value_labels.items():
            value = values.get(key, float("nan"))
            if math.isfinite(value):
                suffix = f" {unit}" if unit else ""
                label_widget.setText(f"{label} {value:.4g}{suffix}")
            else:
                label_widget.setText(f"{label} --")


class MyFocHostWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MyFOC_NFlux Host")
        self.resize(1420, 860)
        self.setMinimumSize(1120, 720)

        self.frame_queue = queue.Queue(maxsize=10000)
        self.worker = SerialWorker(self.frame_queue)
        self.worker.signals.status.connect(self.set_status)
        self.worker.signals.disconnected.connect(self._on_worker_disconnected)

        self.time_history = deque(maxlen=HISTORY_LEN)
        self.history = {channel.key: deque(maxlen=HISTORY_LEN) for channel in CHANNELS}
        self.curves = {}
        self.plot_items = {}
        self.plot_areas = {}
        self.plot_axis_views = {}
        self.plot_axis_items = {}
        self.plot_axis_for_channel = {}
        self.legends = {}
        self.channel_checks = {}
        self.channel_pill_layouts = {}
        self.plot_window_spins = {}
        self.plot_follow_latest = {}
        self.plot_auto_y = {}
        self.cards = {}
        self.summary_cards = []
        self.diagnostic_value_labels = {}
        self.diagnostic_chips = {}
        self.main_scroll = None
        self.sidebar_scroll = None
        self.t0 = None
        self.connected = False
        self.paused = False
        self.dark_theme = False
        self.demo_enabled = False
        self.demo_phase = 0.0
        self.last_values = {channel.key: float("nan") for channel in CHANNELS}
        self.programmatic_range_change = False

        self.logging = False
        self.log_file = None
        self.log_writer = None

        self.frames_total = 0
        self.frames_this_second = 0
        self.last_rate_time = time.perf_counter()
        self.last_auto_y_time = 0.0
        self.last_port_devices = []
        self.last_port_scan_status = ""

        self._configure_plot_theme()
        self._build_ui()
        self._connect_ui()
        self.refresh_ports(force_status=True)

        self.ui_timer = QtCore.QTimer(self)
        self.ui_timer.setInterval(UI_UPDATE_MS)
        self.ui_timer.timeout.connect(self._update_ui)
        self.ui_timer.start()

        self.port_timer = QtCore.QTimer(self)
        self.port_timer.setInterval(1000)
        self.port_timer.timeout.connect(self.refresh_ports)
        self.port_timer.start()

        self.demo_timer = QtCore.QTimer(self)
        self.demo_timer.setInterval(5)
        self.demo_timer.timeout.connect(self._push_demo_frame)

    def _configure_plot_theme(self):
        pg.setConfigOptions(antialias=False, foreground="#334155", background="#ffffff")

    def _build_ui(self):
        self.setStyleSheet(self._style_sheet())
        self.statusBar().showMessage("未连接")

        root = QtWidgets.QWidget()
        root_layout = QtWidgets.QHBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)
        self.setCentralWidget(root)

        sidebar = self._build_sidebar()
        main_panel = self._build_main_panel()
        root_layout.addWidget(sidebar)
        self.main_scroll = None
        root_layout.addWidget(main_panel, 1)
        self._apply_theme()

    def _build_sidebar(self):
        container = QtWidgets.QFrame()
        container.setObjectName("sidebar")
        container.setFixedWidth(370)

        scroll = QtWidgets.QScrollArea()
        self.sidebar_scroll = scroll
        scroll.setObjectName("sidebarScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(container)

        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)

        title = QtWidgets.QLabel("MyFOC_NFlux")
        title.setObjectName("appTitle")
        subtitle = QtWidgets.QLabel("FOC 调试上位机")
        subtitle.setObjectName("appSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addWidget(self._connection_group())
        layout.addWidget(self._control_group())
        layout.addWidget(self._plot_group())
        layout.addWidget(self._command_group())
        layout.addStretch(1)
        return scroll

    def _connection_group(self):
        group = QtWidgets.QGroupBox("串口连接")
        form = QtWidgets.QGridLayout(group)
        form.setContentsMargins(8, 8, 8, 8)
        form.setHorizontalSpacing(6)
        form.setVerticalSpacing(6)

        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setObjectName("flatCombo")
        self.port_combo.setFixedHeight(30)
        self.port_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.port_combo.setMinimumContentsLength(24)
        self.port_combo.setEditable(True)
        self.port_combo.lineEdit().setPlaceholderText("COM12")
        self.refresh_button = QtWidgets.QPushButton("刷新")
        self.connect_button = QtWidgets.QPushButton("连接")
        self.connect_button.setObjectName("primaryButton")
        self.baud_box = QtWidgets.QComboBox()
        self.baud_box.setObjectName("flatCombo")
        self.baud_box.setFixedHeight(30)
        for baud in ["2000000", "115200", "921600", "460800"]:
            self.baud_box.addItem(baud)
        self.baud_box.setEditable(True)

        form.addWidget(QtWidgets.QLabel("端口"), 0, 0)
        form.addWidget(self.port_combo, 0, 1, 1, 2)
        form.addWidget(QtWidgets.QLabel("波特率"), 1, 0)
        form.addWidget(self.baud_box, 1, 1, 1, 2)
        form.addWidget(self.refresh_button, 2, 1)
        form.addWidget(self.connect_button, 2, 2)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(2, 1)
        return group

    def _control_group(self):
        group = QtWidgets.QGroupBox("电机控制")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        buttons = QtWidgets.QHBoxLayout()
        buttons.setSpacing(8)
        self.run_button = QtWidgets.QPushButton("启动")
        self.run_button.setObjectName("runButton")
        self.stop_button = QtWidgets.QPushButton("停止")
        self.stop_button.setObjectName("stopButton")
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.stop_button)
        layout.addLayout(buttons)

        speed_row = QtWidgets.QHBoxLayout()
        speed_row.addWidget(QtWidgets.QLabel("目标速度"))
        self.speed_spin = QtWidgets.QDoubleSpinBox()
        self.speed_spin.setFixedHeight(30)
        self.speed_spin.setRange(SPEED_MIN, SPEED_MAX)
        self.speed_spin.setDecimals(1)
        self.speed_spin.setSingleStep(10.0)
        self.speed_spin.setValue(600.0)
        self.speed_spin.setSuffix(" rpm")
        self.speed_spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        speed_row.addWidget(self.speed_spin)
        layout.addLayout(speed_row)

        self.speed_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.speed_slider.setRange(int(SPEED_MIN), int(SPEED_MAX))
        self.speed_slider.setValue(600)
        layout.addWidget(self.speed_slider)

        send_row = QtWidgets.QHBoxLayout()
        send_row.setSpacing(8)
        self.speed_send_button = QtWidgets.QPushButton("下发速度")
        self.speed_send_button.setObjectName("primaryButton")
        self.demo_button = QtWidgets.QPushButton("演示数据")
        self.demo_button.setCheckable(True)
        send_row.addWidget(self.speed_send_button)
        send_row.addWidget(self.demo_button)
        layout.addLayout(send_row)
        return group

    def _plot_group(self):
        group = QtWidgets.QGroupBox("曲线与通道")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        controls = QtWidgets.QGridLayout()
        controls.setHorizontalSpacing(8)
        controls.setVerticalSpacing(4)
        self.auto_scroll_check = QtWidgets.QCheckBox("跟随最新数据")
        self.auto_scroll_check.setChecked(True)
        self.auto_scale_check = QtWidgets.QCheckBox("Y 轴自动缩放")
        self.auto_scale_check.setChecked(True)
        self.grid_check = QtWidgets.QCheckBox("网格")
        self.grid_check.setChecked(True)

        controls.addWidget(self.auto_scroll_check, 0, 0, 1, 2)
        controls.addWidget(self.auto_scale_check, 1, 0, 1, 2)
        controls.addWidget(self.grid_check, 2, 0, 1, 2)
        window_labels = {
            "state": "状态窗",
            "measure": "测量窗",
        }
        for row, plot_key in enumerate(PLOT_PANELS, start=3):
            spin = QtWidgets.QDoubleSpinBox()
            spin.setFixedHeight(30)
            spin.setRange(PLOT_WINDOW_MIN, PLOT_WINDOW_MAX)
            spin.setDecimals(2)
            spin.setSingleStep(0.05 if PLOT_DEFAULT_WINDOWS[plot_key] < 1.0 else 1.0)
            spin.setValue(PLOT_DEFAULT_WINDOWS[plot_key])
            spin.setSuffix(" s")
            spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
            self.plot_window_spins[plot_key] = spin
            controls.addWidget(QtWidgets.QLabel(window_labels[plot_key]), row, 0)
            controls.addWidget(spin, row, 1)
        layout.addLayout(controls)

        return group

    def _logging_group(self):
        group = QtWidgets.QGroupBox("数据记录")
        layout = QtWidgets.QVBoxLayout(group)
        self.log_button = QtWidgets.QPushButton("开始记录 CSV")
        self.log_label = QtWidgets.QLabel("未记录")
        self.log_label.setObjectName("hintText")
        self.log_label.setWordWrap(True)
        layout.addWidget(self.log_button)
        layout.addWidget(self.log_label)
        return group

    def _command_group(self):
        group = QtWidgets.QGroupBox("命令窗口")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.command_edit = QtWidgets.QLineEdit()
        self.command_edit.setFixedHeight(30)
        self.command_edit.setPlaceholderText("例如 SPD=600 或 RUN=1")
        self.command_send_button = QtWidgets.QPushButton("发送命令")
        self.console = QtWidgets.QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(72)
        self.console.setMaximumBlockCount(300)
        self.console.setPlaceholderText("串口状态和发送记录会显示在这里")
        layout.addWidget(self.command_edit)
        layout.addWidget(self.command_send_button)
        layout.addWidget(self.console, 1)
        return group

    def _build_main_panel(self):
        panel = QtWidgets.QWidget()
        self.main_panel = panel
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QtWidgets.QHBoxLayout()
        title_box = QtWidgets.QVBoxLayout()
        main_title = QtWidgets.QLabel("实时遥测")
        main_title.setObjectName("sectionTitle")
        main_subtitle = QtWidgets.QLabel("四块曲线共用时间轴；鼠标滚轮缩放，拖拽平移，取消“跟随最新数据”后可以自由检查历史波形。")
        main_subtitle.setObjectName("hintText")
        title_box.addWidget(main_title)
        title_box.addWidget(main_subtitle)
        header.addLayout(title_box, 1)

        self.theme_button = QtWidgets.QPushButton("深色主题")
        self.theme_button.setObjectName("themeButton")
        self.theme_button.setCheckable(True)
        self.theme_button.setFixedSize(112, 48)

        self.rate_label = QtWidgets.QLabel("0 frame/s")
        self.rate_label.setObjectName("rateBadge")
        self.rate_label.setMinimumHeight(36)
        self.rate_label.setMinimumWidth(180)
        self.rate_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        header_actions = QtWidgets.QHBoxLayout()
        header_actions.setSpacing(12)
        header_actions.addWidget(self.theme_button)
        header_actions.addWidget(self.rate_label)
        header.addLayout(header_actions, 0)
        header.setAlignment(header_actions, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        cards = QtWidgets.QGridLayout()
        cards.setSpacing(8)
        for index, key in enumerate(PRIMARY_CARD_KEYS):
            channel = CHANNEL_BY_KEY[key]
            card = TelemetryCard(channel)
            self.cards[channel.key] = card
            cards.addWidget(card, index // 4, index % 4)
        layout.addLayout(cards)

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setObjectName("mainTabs")
        self.plot_tab = QtWidgets.QWidget()
        plot_tab_layout = QtWidgets.QVBoxLayout(self.plot_tab)
        plot_tab_layout.setContentsMargins(0, 0, 0, 0)

        self.plot_panel = QtWidgets.QFrame()
        self.plot_panel.setObjectName("plotPanel")
        plot_panel_layout = QtWidgets.QVBoxLayout(self.plot_panel)
        plot_panel_layout.setContentsMargins(12, 12, 12, 12)
        plot_panel_layout.setSpacing(10)
        plot_panel_layout.addWidget(self._build_plot_toolbar())

        self.plot_area = pg.GraphicsLayoutWidget()
        self.plot_area.setMinimumHeight(680)

        current_plot = self.plot_area.addPlot(row=0, col=0, title="三相电流")
        theta_plot = self.plot_area.addPlot(row=0, col=1, title="磁链角")
        speed_plot = self.plot_area.addPlot(row=1, col=0, title="速度")
        voltage_plot = self.plot_area.addPlot(row=1, col=1, title="母线电压")
        self.plot_items = {
            "current": current_plot,
            "theta": theta_plot,
            "speed": speed_plot,
            "voltage": voltage_plot,
        }
        self.plot_follow_latest = {key: True for key in self.plot_items}
        self.plot_auto_y = {key: True for key in self.plot_items}
        plot_units = {
            "current": ("电流", "A"),
            "theta": ("角度", "rad"),
            "speed": ("速度", "rpm"),
            "voltage": ("电压", "V"),
        }

        for key, plot_item in self.plot_items.items():
            plot_item.showGrid(x=True, y=True, alpha=0.25)
            self.legends[key] = plot_item.addLegend(offset=(10, 8), labelTextColor="#0f172a")
            plot_item.setMenuEnabled(True)
            plot_item.getViewBox().setMouseEnabled(x=True, y=True)
            axis_label, axis_unit = plot_units[key]
            plot_item.setLabel("left", axis_label, units=axis_unit)
            left_axis = plot_item.getAxis("left")
            if hasattr(left_axis, "enableAutoSIPrefix"):
                left_axis.enableAutoSIPrefix(False)
            view_box = plot_item.getViewBox()
            if hasattr(view_box, "sigRangeChangedManually"):
                view_box.sigRangeChangedManually.connect(
                    lambda *args, plot_key=key: self._on_plot_range_changed_manually(plot_key)
                )

        speed_plot.setLabel("bottom", "时间", units="s")
        voltage_plot.setLabel("bottom", "时间", units="s")

        for channel in CHANNELS:
            plot_item = self.plot_items[channel.plot]
            curve = plot_item.plot(
                [],
                [],
                pen=pg.mkPen(channel.color, width=2.1),
                name=channel.label,
            )
            curve.setVisible(channel.default_visible)
            curve.setDownsampling(auto=False)
            curve.setClipToView(True)
            self.curves[channel.key] = curve
            self._install_legend_click_handler(channel)

        plot_panel_layout.addWidget(self.plot_area, 1)
        plot_tab_layout.addWidget(self.plot_panel, 1)
        self.tab_widget.addTab(self.plot_tab, "实时曲线")
        self.tab_widget.addTab(self._build_reserved_control_tab(), "控制预留")
        layout.addWidget(self.tab_widget, 1)
        return panel

    def _build_plot_toolbar(self):
        self.channel_toolbar = QtWidgets.QFrame()
        self.channel_toolbar.setObjectName("channelToolbar")
        toolbar_layout = QtWidgets.QHBoxLayout(self.channel_toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(10)

        self.channel_pill_scroll = QtWidgets.QScrollArea()
        self.channel_pill_scroll.setObjectName("channelPillScroll")
        self.channel_pill_scroll.setWidgetResizable(True)
        self.channel_pill_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.channel_pill_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.channel_pill_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        pill_host = QtWidgets.QWidget()
        pill_host.setObjectName("channelPillHost")
        self.channel_pill_layout = QtWidgets.QHBoxLayout(pill_host)
        self.channel_pill_layout.setContentsMargins(0, 0, 0, 0)
        self.channel_pill_layout.setSpacing(8)
        for channel in CHANNELS:
            check = QtWidgets.QCheckBox(channel.label)
            check.setObjectName("channelPill")
            check.setChecked(channel.default_visible)
            check.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            check.setStyleSheet(channel_pill_style(channel.color))
            self.channel_checks[channel.key] = check
            self.channel_pill_layout.addWidget(check)
        self.channel_pill_layout.addStretch(1)
        self.channel_pill_scroll.setWidget(pill_host)
        toolbar_layout.addWidget(self.channel_pill_scroll, 1)

        self.select_all_button = QtWidgets.QPushButton("全选")
        self.select_none_button = QtWidgets.QPushButton("全不选")
        self.reset_view_button = QtWidgets.QPushButton("重置视图")
        self.clear_data_button = QtWidgets.QPushButton("清空曲线")
        for button in (
            self.select_all_button,
            self.select_none_button,
            self.reset_view_button,
            self.clear_data_button,
        ):
            button.setObjectName("toolbarButton")
            toolbar_layout.addWidget(button)
        return self.channel_toolbar

    def _build_diagnostic_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)

        for index, key in enumerate(DIAGNOSTIC_VALUE_KEYS):
            channel = CHANNEL_BY_KEY[key]
            row = index // 2
            col = (index % 2) * 3

            name = QtWidgets.QLabel(channel.label)
            name.setObjectName("diagName")
            value = QtWidgets.QLabel("--")
            value.setObjectName("diagValue")
            unit = QtWidgets.QLabel(channel.unit)
            unit.setObjectName("diagUnit")
            self.diagnostic_value_labels[key] = value

            layout.addWidget(name, row, col)
            layout.addWidget(value, row, col + 1)
            layout.addWidget(unit, row, col + 2)

        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(4, 1)
        return tab

    def _build_reserved_control_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout(tab)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(14)

        position_group = QtWidgets.QGroupBox("位置控制")
        position_layout = QtWidgets.QGridLayout(position_group)
        self.position_enable_check = QtWidgets.QCheckBox("位置模式")
        self.position_enable_check.setEnabled(False)
        self.position_target_spin = QtWidgets.QDoubleSpinBox()
        self.position_target_spin.setRange(-36000.0, 36000.0)
        self.position_target_spin.setSuffix(" deg")
        self.position_target_spin.setEnabled(False)
        self.position_kp_spin = QtWidgets.QDoubleSpinBox()
        self.position_kp_spin.setRange(0.0, 1000.0)
        self.position_kp_spin.setDecimals(3)
        self.position_kp_spin.setEnabled(False)
        self.position_send_button = QtWidgets.QPushButton("下发位置参数")
        self.position_send_button.setEnabled(False)
        position_layout.addWidget(self.position_enable_check, 0, 0, 1, 2)
        position_layout.addWidget(QtWidgets.QLabel("目标位置"), 1, 0)
        position_layout.addWidget(self.position_target_spin, 1, 1)
        position_layout.addWidget(QtWidgets.QLabel("位置 Kp"), 2, 0)
        position_layout.addWidget(self.position_kp_spin, 2, 1)
        position_layout.addWidget(self.position_send_button, 3, 0, 1, 2)

        profile_group = QtWidgets.QGroupBox("轨迹规划")
        profile_layout = QtWidgets.QGridLayout(profile_group)
        self.profile_mode_combo = QtWidgets.QComboBox()
        self.profile_mode_combo.addItems(["梯形速度", "S 曲线", "点动"])
        self.profile_mode_combo.setEnabled(False)
        self.profile_speed_spin = QtWidgets.QDoubleSpinBox()
        self.profile_speed_spin.setRange(0.0, 5000.0)
        self.profile_speed_spin.setSuffix(" rpm")
        self.profile_speed_spin.setEnabled(False)
        self.profile_acc_spin = QtWidgets.QDoubleSpinBox()
        self.profile_acc_spin.setRange(0.0, 100000.0)
        self.profile_acc_spin.setSuffix(" rpm/s")
        self.profile_acc_spin.setEnabled(False)
        profile_layout.addWidget(QtWidgets.QLabel("轨迹模式"), 0, 0)
        profile_layout.addWidget(self.profile_mode_combo, 0, 1)
        profile_layout.addWidget(QtWidgets.QLabel("速度限制"), 1, 0)
        profile_layout.addWidget(self.profile_speed_spin, 1, 1)
        profile_layout.addWidget(QtWidgets.QLabel("加速度限制"), 2, 0)
        profile_layout.addWidget(self.profile_acc_spin, 2, 1)

        identify_group = QtWidgets.QGroupBox("参数辨识")
        identify_layout = QtWidgets.QVBoxLayout(identify_group)
        self.identify_rs_button = QtWidgets.QPushButton("辨识 Rs")
        self.identify_ldq_button = QtWidgets.QPushButton("辨识 Ld/Lq")
        self.identify_flux_button = QtWidgets.QPushButton("辨识磁链")
        for button in [self.identify_rs_button, self.identify_ldq_button, self.identify_flux_button]:
            button.setEnabled(False)
            identify_layout.addWidget(button)
        identify_layout.addStretch(1)

        layout.addWidget(position_group, 0, 0)
        layout.addWidget(profile_group, 0, 1)
        layout.addWidget(identify_group, 1, 0, 1, 2)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(2, 1)
        return tab

    def _build_main_panel(self):
        panel = QtWidgets.QWidget()
        self.main_panel = panel
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QtWidgets.QFrame()
        header.setObjectName("mainHeader")
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)
        title_box = QtWidgets.QVBoxLayout()
        title_box.setSpacing(2)
        main_title = QtWidgets.QLabel("实时遥测")
        main_title.setObjectName("sectionTitle")
        main_subtitle = QtWidgets.QLabel("两幅主图共用时间轴；左侧胶囊选择曲线，右上角控制暂停、记录和主题。")
        main_subtitle.setObjectName("removedHintText")
        main_subtitle.setVisible(False)
        title_box.addWidget(main_title)
        header_layout.addLayout(title_box, 1)
        header_layout.addWidget(self._build_plot_toolbar(), 0, QtCore.Qt.AlignmentFlag.AlignTop)
        layout.addWidget(header)

        summary_layout = QtWidgets.QHBoxLayout()
        summary_layout.setSpacing(10)
        summary_specs = [
            ("Iabc", (("ia", "Ia", "A"), ("ib", "Ib", "A"), ("ic", "Ic", "A"))),
            ("Speed", (("speed", "Obs", "rpm"), ("ref", "Ref", "rpm"))),
            ("Flux / Bus", (("theta", "θ", "rad"), ("vbus", "Vbus", "V"))),
            ("DQ / State", (("id", "Id", "A"), ("iq", "Iq", "A"), ("foc_state", "FOC", ""))),
        ]
        for title, rows in summary_specs:
            card = SummaryCard(title, rows)
            card.setVisible(False)
            self.summary_cards.append(card)
            summary_layout.addWidget(card, 1)
        layout.addLayout(summary_layout)
        self.summary_cards.clear()

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setObjectName("mainTabs")
        self.plot_tab = QtWidgets.QWidget()
        plot_tab_layout = QtWidgets.QVBoxLayout(self.plot_tab)
        plot_tab_layout.setContentsMargins(0, 0, 0, 0)

        self.plot_panel = QtWidgets.QFrame()
        self.plot_panel.setObjectName("plotPanel")
        plot_panel_layout = QtWidgets.QVBoxLayout(self.plot_panel)
        plot_panel_layout.setContentsMargins(14, 14, 14, 14)
        plot_panel_layout.setSpacing(10)
        for panel_key in PLOT_PANELS:
            plot_panel_layout.addWidget(self._build_plot_row(panel_key), 1)

        plot_tab_layout.addWidget(self.plot_panel, 1)
        self.tab_widget.addTab(self.plot_tab, "实时曲线")
        self.tab_widget.addTab(self._build_reserved_control_tab(), "控制预留")
        layout.addWidget(self.tab_widget, 1)
        return panel

    def _build_plot_toolbar(self):
        self.plot_toolbar = QtWidgets.QFrame()
        self.plot_toolbar.setObjectName("plotToolbar")
        toolbar_layout = QtWidgets.QHBoxLayout(self.plot_toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)
        toolbar_layout.addStretch(1)

        self.pause_button = QtWidgets.QPushButton()
        self.pause_button.setObjectName("iconButton")
        self.pause_button.setCheckable(True)
        self.pause_button.setToolTip("暂停绘图")

        self.log_button = QtWidgets.QPushButton()
        self.log_button.setObjectName("recordButton")
        self.log_button.setToolTip("记录 CSV")
        self.log_label = QtWidgets.QLabel("未记录")
        self.log_label.setVisible(False)

        self.reset_view_button = QtWidgets.QPushButton()
        self.reset_view_button.setObjectName("iconButton")
        self.reset_view_button.setToolTip("重置视图")
        self.clear_data_button = QtWidgets.QPushButton()
        self.clear_data_button.setObjectName("iconButton")
        self.clear_data_button.setToolTip("清空曲线")

        self.theme_button = QtWidgets.QPushButton()
        self.theme_button.setObjectName("iconButton")
        self.theme_button.setCheckable(True)
        self.theme_button.setToolTip("深色主题")

        self.rate_label = QtWidgets.QLabel("0 frame/s")
        self.rate_label.setObjectName("rateBadge")
        self.rate_label.setMinimumHeight(36)
        self.rate_label.setMinimumWidth(180)
        self.rate_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        for button in (
            self.pause_button,
            self.log_button,
            self.reset_view_button,
            self.clear_data_button,
            self.theme_button,
        ):
            button.setFixedSize(38, 38)
            button.setIconSize(QtCore.QSize(22, 22))
            button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            toolbar_layout.addWidget(button)
        self._refresh_toolbar_icons()
        toolbar_layout.addWidget(self.rate_label)
        return self.plot_toolbar

    def _toolbar_icon_color(self):
        return "#d4deef" if self.dark_theme else "#475569"

    def _make_toolbar_icon(self, kind, color):
        pixmap = QtGui.QPixmap(24, 24)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)

        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        icon_color = QtGui.QColor(color)
        pen = QtGui.QPen(icon_color, 2.2)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)

        if kind == "pause":
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QBrush(icon_color))
            painter.drawRoundedRect(QtCore.QRectF(7.2, 6.0, 3.4, 12.0), 1.2, 1.2)
            painter.drawRoundedRect(QtCore.QRectF(13.4, 6.0, 3.4, 12.0), 1.2, 1.2)
        elif kind == "play":
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QBrush(icon_color))
            painter.drawPolygon(
                QtGui.QPolygonF(
                    [
                        QtCore.QPointF(8.0, 5.8),
                        QtCore.QPointF(18.0, 12.0),
                        QtCore.QPointF(8.0, 18.2),
                    ]
                )
            )
        elif kind == "record":
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#e05264")))
            painter.drawEllipse(QtCore.QPointF(12.0, 12.0), 5.0, 5.0)
        elif kind == "reset":
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawArc(QtCore.QRectF(6.0, 6.0, 12.0, 12.0), 25 * 16, 290 * 16)
            painter.drawPolyline(
                QtGui.QPolygonF(
                    [
                        QtCore.QPointF(7.0, 6.8),
                        QtCore.QPointF(6.2, 10.6),
                        QtCore.QPointF(10.1, 9.7),
                    ]
                )
            )
        elif kind == "clear":
            painter.setPen(pen)
            painter.drawLine(QtCore.QPointF(7.4, 7.4), QtCore.QPointF(16.6, 16.6))
            painter.drawLine(QtCore.QPointF(16.6, 7.4), QtCore.QPointF(7.4, 16.6))
        elif kind == "sun":
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QtCore.QPointF(12.0, 12.0), 3.6, 3.6)
            for angle in range(0, 360, 45):
                radians = math.radians(angle)
                inner = QtCore.QPointF(12.0 + math.cos(radians) * 6.2, 12.0 + math.sin(radians) * 6.2)
                outer = QtCore.QPointF(12.0 + math.cos(radians) * 8.8, 12.0 + math.sin(radians) * 8.8)
                painter.drawLine(inner, outer)
        else:
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QBrush(icon_color))
            painter.drawEllipse(QtCore.QRectF(6.0, 4.0, 12.5, 16.0))
            painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Clear)
            painter.drawEllipse(QtCore.QRectF(10.2, 2.9, 12.5, 16.0))

        painter.end()
        return QtGui.QIcon(pixmap)

    def _set_toolbar_button_icon(self, button, kind):
        button.setText("")
        button.setIcon(self._make_toolbar_icon(kind, self._toolbar_icon_color()))
        button.setIconSize(QtCore.QSize(22, 22))

    def _refresh_toolbar_icons(self):
        if not hasattr(self, "pause_button"):
            return
        self._set_toolbar_button_icon(self.pause_button, "play" if self.paused else "pause")
        self._set_toolbar_button_icon(self.log_button, "record")
        self._set_toolbar_button_icon(self.reset_view_button, "reset")
        self._set_toolbar_button_icon(self.clear_data_button, "clear")
        self._set_toolbar_button_icon(self.theme_button, "sun" if self.dark_theme else "moon")

    def _build_plot_row(self, panel_key):
        panel = PLOT_PANELS[panel_key]
        row = QtWidgets.QFrame()
        row.setObjectName("plotCard")
        row_layout = QtWidgets.QHBoxLayout(row)
        row_layout.setContentsMargins(12, 10, 12, 10)
        row_layout.setSpacing(10)

        pill_column = QtWidgets.QFrame()
        pill_column.setObjectName("channelPillColumn")
        pill_layout = QtWidgets.QVBoxLayout(pill_column)
        pill_layout.setContentsMargins(0, 8, 0, 8)
        pill_layout.setSpacing(8)
        self.channel_pill_layouts[panel_key] = pill_layout
        pill_layout.addStretch(1)
        for channel_key in panel["channels"]:
            channel = CHANNEL_BY_KEY[channel_key]
            check = QtWidgets.QPushButton(f"\u25cf {CHANNEL_SHORT_LABELS[channel_key]}")
            check.setObjectName("channelPill")
            check.setCheckable(True)
            check.setMinimumWidth(96)
            check.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            check.setChecked(channel.default_visible)
            check.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            check.setStyleSheet(channel_pill_style(channel.color))
            self.channel_checks[channel.key] = check
            pill_layout.addWidget(check)
        pill_layout.addStretch(1)
        row_layout.addWidget(pill_column, 0)

        plot_area = pg.GraphicsLayoutWidget()
        plot_area.setObjectName("plotCanvas")
        plot_area.setMinimumHeight(230)
        plot_item = plot_area.addPlot(row=0, col=0, title=panel["title"])
        self.plot_areas[panel_key] = plot_area
        self._setup_panel_plot(panel_key, plot_item)
        row_layout.addWidget(plot_area, 1)
        return row

    def _setup_panel_plot(self, panel_key, plot_item):
        panel = PLOT_PANELS[panel_key]
        primary_axis = "value"
        self.plot_items[panel_key] = plot_item
        self.plot_axis_views[panel_key] = {primary_axis: plot_item.getViewBox()}
        self.plot_axis_items[panel_key] = {primary_axis: plot_item.getAxis("left")}

        plot_item.showGrid(x=True, y=True, alpha=self._plot_grid_alpha())
        plot_item.setMenuEnabled(True)
        plot_item.getViewBox().setMouseEnabled(x=True, y=True)
        plot_item.setLabel("left", "Value")
        plot_item.setLabel("bottom", "Time", units="s")
        left_axis = plot_item.getAxis("left")
        if hasattr(left_axis, "enableAutoSIPrefix"):
            left_axis.enableAutoSIPrefix(False)

        view_box = plot_item.getViewBox()
        if hasattr(view_box, "sigRangeChangedManually"):
            view_box.sigRangeChangedManually.connect(
                lambda *args, plot_key=panel_key: self._on_plot_range_changed_manually(plot_key)
            )

        for channel_key in panel["channels"]:
            channel = CHANNEL_BY_KEY[channel_key]
            curve = pg.PlotDataItem([], [], pen=pg.mkPen(channel.color, width=2.0), name=channel.label)
            curve.setVisible(channel.default_visible)
            curve.setDownsampling(auto=False)
            curve.setClipToView(True)
            plot_item.addItem(curve)
            self.plot_axis_for_channel[channel.key] = primary_axis
            self.curves[channel.key] = curve

        self.plot_follow_latest[panel_key] = True
        self.plot_auto_y[panel_key] = True

    def _sync_axis_views(self, panel_key):
        plot_item = self.plot_items.get(panel_key)
        if plot_item is None:
            return
        source_view = plot_item.getViewBox()
        for axis_key, view in self.plot_axis_views.get(panel_key, {}).items():
            if view is source_view:
                continue
            view.setGeometry(source_view.sceneBoundingRect())
            view.linkedViewChanged(source_view, view.XAxis)

    def _build_diagnostic_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        for index, key in enumerate(DIAGNOSTIC_VALUE_KEYS):
            channel = CHANNEL_BY_KEY[key]
            chip = QtWidgets.QFrame()
            chip.setObjectName("diagnosticChip")
            chip.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
            chip.setMinimumSize(150, 34)
            chip.setMaximumHeight(34)
            chip_layout = QtWidgets.QHBoxLayout(chip)
            chip_layout.setContentsMargins(10, 5, 10, 5)
            chip_layout.setSpacing(6)
            name = QtWidgets.QLabel(CHANNEL_SHORT_LABELS[key])
            name.setObjectName("diagName")
            value = QtWidgets.QLabel("--")
            value.setObjectName("diagValue")
            unit = QtWidgets.QLabel(channel.unit)
            unit.setObjectName("diagUnit")
            chip_layout.addWidget(name)
            chip_layout.addWidget(value)
            if channel.unit:
                chip_layout.addWidget(unit)
            self.diagnostic_chips[key] = chip
            self.diagnostic_value_labels[key] = value
            layout.addWidget(chip, index // 4, index % 4)
        layout.setColumnStretch(4, 1)
        layout.setRowStretch((len(DIAGNOSTIC_VALUE_KEYS) + 3) // 4, 1)
        return tab

    def _connect_ui(self):
        self.refresh_button.clicked.connect(self.refresh_ports)
        self.connect_button.clicked.connect(self.toggle_connection)
        self.run_button.clicked.connect(lambda: self.send_control_command("RUN=1"))
        self.stop_button.clicked.connect(lambda: self.send_control_command("RUN=0"))
        self.speed_send_button.clicked.connect(self.send_speed)
        self.demo_button.toggled.connect(self.toggle_demo)
        self.command_send_button.clicked.connect(self.send_custom_command)
        self.command_edit.returnPressed.connect(self.send_custom_command)
        self.log_button.clicked.connect(self.toggle_logging)
        self.theme_button.toggled.connect(self._set_dark_theme)
        self.auto_scroll_check.toggled.connect(self._set_follow_latest)
        self.pause_button.toggled.connect(self._set_paused)
        self.grid_check.toggled.connect(self._set_grid_visible)
        self.auto_scale_check.toggled.connect(self._apply_auto_scale)
        self.reset_view_button.clicked.connect(self.reset_view)
        if hasattr(self, "select_all_button"):
            self.select_all_button.clicked.connect(lambda: self._set_all_channels(True))
        if hasattr(self, "select_none_button"):
            self.select_none_button.clicked.connect(lambda: self._set_all_channels(False))
        self.clear_data_button.clicked.connect(self.clear_data)

        self.speed_slider.valueChanged.connect(lambda value: self.speed_spin.setValue(float(value)))
        self.speed_spin.valueChanged.connect(lambda value: self.speed_slider.setValue(int(value)))

        for plot_key, spin in self.plot_window_spins.items():
            spin.valueChanged.connect(
                lambda value, plot_key=plot_key: self._on_plot_window_changed(plot_key, value)
            )

        for check in self.channel_checks.values():
            check.toggled.connect(self._update_channel_visibility)

    def _install_legend_click_handler(self, channel):
        legend = self.legends.get(channel.plot)
        if legend is None or not legend.items:
            return

        sample, label = legend.items[-1]

        def toggle_from_legend(event=None, key=channel.key):
            self._toggle_channel_from_legend(key)
            if event is not None and hasattr(event, "accept"):
                event.accept()

        for item in (sample, label):
            try:
                item.setAcceptedMouseButtons(QtCore.Qt.MouseButton.LeftButton)
            except AttributeError:
                pass
            item.mouseClickEvent = toggle_from_legend

    def _toggle_channel_from_legend(self, key):
        check = self.channel_checks.get(key)
        if check is None:
            return
        check.setChecked(not check.isChecked())

    def _set_dark_theme(self, checked):
        self.dark_theme = checked
        self.theme_button.setToolTip("浅色主题" if checked else "深色主题")
        self._apply_theme()

    def _plot_grid_alpha(self):
        return PLOT_GRID_ALPHA_DARK if self.dark_theme else PLOT_GRID_ALPHA_LIGHT

    def _apply_theme(self):
        self.setStyleSheet(self._style_sheet())
        self._refresh_toolbar_icons()
        plot_bg = "#151c2b" if self.dark_theme else "#ffffff"
        axis_pen = "#273348" if self.dark_theme else "#e2e8f0"
        tick_pen = "#7c889b" if self.dark_theme else "#94a3b8"
        title_pen = "#e5e7eb" if self.dark_theme else "#475569"
        grid_alpha = self._plot_grid_alpha()

        for plot_area in self.plot_areas.values():
            plot_area.setBackground(plot_bg)

        for key, plot_item in self.plot_items.items():
            plot_item.getViewBox().setBackgroundColor(plot_bg)
            plot_item.showGrid(x=self.grid_check.isChecked(), y=self.grid_check.isChecked(), alpha=grid_alpha)
            for axis_name in ("left", "bottom"):
                axis = plot_item.getAxis(axis_name)
                axis.setPen(pg.mkPen(axis_pen))
                axis.setTextPen(pg.mkPen(tick_pen))
                axis.setStyle(tickTextOffset=6)
            for axis in self.plot_axis_items.get(key, {}).values():
                axis.setPen(pg.mkPen(axis_pen))
                axis.setTextPen(pg.mkPen(tick_pen))
                axis.setStyle(tickTextOffset=6)
            title = plot_item.titleLabel
            if title is not None:
                title.setText(title.text, color=title_pen)

        for legend in self.legends.values():
            for _, label in legend.items:
                label.setText(label.text, color=tick_pen)

    def refresh_ports(self, force_status=False):
        if self.connected:
            return

        current_device = self._selected_port()
        current_text = self.port_combo.currentText().strip()

        if list_ports is None:
            self.set_status("未安装 pyserial，运行 run.bat 会自动安装。")
            return

        ports = list(list_ports.comports())
        devices = [port.device for port in ports]
        if (not force_status) and (devices == self.last_port_devices):
            return

        self.last_port_devices = devices
        self.port_combo.clear()
        for port in ports:
            label = f"{port.device}  {port.description}"
            self.port_combo.addItem(label, port.device)

        if ports:
            index = 0
            for i, port in enumerate(ports):
                if current_device == port.device:
                    index = i
                    break
            self.port_combo.setCurrentIndex(index)
        elif current_text:
            self.port_combo.addItem(current_text, port_name_from_combo_text(current_text))
            self.port_combo.setCurrentIndex(0)

        status = f"发现 {len(ports)} 个串口"
        if not ports:
            status += "，可手动输入 COMx 后连接"
        if force_status or status != self.last_port_scan_status:
            self.last_port_scan_status = status
            self.set_status(status)

    def _selected_port(self):
        port = self.port_combo.currentData()
        if port:
            return port
        return port_name_from_combo_text(self.port_combo.currentText())

    def toggle_connection(self):
        if self.connected:
            self.worker.stop()
            self._set_connected(False)
            self.set_status("已断开")
            self.refresh_ports(force_status=True)
            return

        port = self._selected_port()
        if not port:
            QtWidgets.QMessageBox.warning(self, "串口", "先选择一个串口。")
            return

        try:
            baud = int(self.baud_box.currentText())
            self.worker.start(port, baud)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "连接失败", str(exc))
            return

        self._set_connected(True)

    def _set_connected(self, connected):
        self.connected = connected
        self.connect_button.setText("断开" if connected else "连接")
        self.connect_button.setObjectName("stopButton" if connected else "primaryButton")
        self.connect_button.style().unpolish(self.connect_button)
        self.connect_button.style().polish(self.connect_button)

    def _on_worker_disconnected(self):
        if self.connected:
            self._set_connected(False)
            self.set_status("串口已断开")

    def send_command(self, command, announce=True):
        try:
            self.worker.send_line(command)
            if announce:
                self.append_console(f"> {command}")
                self.set_status(f"已发送 {command}")
        except Exception as exc:
            if announce:
                QtWidgets.QMessageBox.warning(self, "发送失败", str(exc))
            else:
                self.append_console(f"发送失败: {command} ({exc})")

    def send_control_command(self, command):
        self.send_command(command)
        for repeat_index in range(1, CONTROL_COMMAND_REPEAT_COUNT):
            QtCore.QTimer.singleShot(
                CONTROL_COMMAND_REPEAT_INTERVAL_MS * repeat_index,
                lambda command=command: self.send_command(command, announce=False),
            )

    def send_speed(self):
        speed = max(SPEED_MIN, min(SPEED_MAX, self.speed_spin.value()))
        self.speed_spin.setValue(speed)
        self.send_control_command(f"SPD={speed:.1f}")

    def send_custom_command(self):
        text = self.command_edit.text().strip()
        if not text:
            return
        self.send_command(text)
        self.command_edit.clear()

    def toggle_demo(self, checked):
        self.demo_enabled = checked
        if checked:
            self.t0 = None
            self.demo_timer.start()
            self.set_status("演示数据已开启")
        else:
            self.demo_timer.stop()
            self.set_status("演示数据已关闭")

    def toggle_logging(self):
        if self.logging:
            self._stop_logging()
        else:
            self._start_logging()

    def _start_logging(self):
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir, datetime.now().strftime("myfoc_%Y%m%d_%H%M%S.csv"))
        self.log_file = open(path, "w", newline="", encoding="utf-8")
        self.log_writer = csv.writer(self.log_file)
        self.log_writer.writerow(CSV_HEADERS)
        self.logging = True
        self.log_button.setText("\u25cf")
        self.log_button.setToolTip("停止记录 CSV")
        self.log_label.setText(path)
        self.append_console(f"CSV 记录开始：{path}")

    def _stop_logging(self):
        was_logging = self.logging
        self.logging = False
        if self.log_file:
            self.log_file.close()
        self.log_file = None
        self.log_writer = None
        self.log_button.setText("\u25cf")
        self.log_button.setToolTip("记录 CSV")
        if was_logging:
            self.append_console("CSV 记录停止")

    def set_status(self, text):
        self.statusBar().showMessage(text)
        self.append_console(text)

    def append_console(self, text):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console.appendPlainText(f"[{timestamp}] {text}")

    def _set_paused(self, checked):
        self.paused = checked
        if hasattr(self, "pause_button"):
            self._set_toolbar_button_icon(self.pause_button, "play" if checked else "pause")
            self.pause_button.setToolTip("继续绘图" if checked else "暂停绘图")

    def _set_follow_latest(self, checked):
        if checked:
            self.plot_follow_latest = {key: True for key in self.plot_items}
            self._scroll_to_latest()
        elif self.time_history:
            self.programmatic_range_change = True
            try:
                self.plot_follow_latest = {key: False for key in self.plot_items}
            finally:
                self.programmatic_range_change = False

    def _on_plot_range_changed_manually(self, plot_key):
        if self.programmatic_range_change:
            return
        self.plot_follow_latest[plot_key] = False
        self._sync_plot_window_from_view(plot_key)
        self.plot_auto_y[plot_key] = False
        self.plot_items[plot_key].enableAutoRange(axis="y", enable=False)

    def _sync_plot_window_from_view(self, plot_key):
        spin = self.plot_window_spins.get(plot_key)
        plot_item = self.plot_items.get(plot_key)
        if spin is None or plot_item is None:
            return

        view_range = plot_item.getViewBox().viewRange()[0]
        window = max(PLOT_WINDOW_MIN, min(PLOT_WINDOW_MAX, float(view_range[1] - view_range[0])))
        spin.blockSignals(True)
        try:
            spin.setValue(window)
        finally:
            spin.blockSignals(False)

    def _set_grid_visible(self, checked):
        grid_alpha = self._plot_grid_alpha()
        for plot_item in self.plot_items.values():
            plot_item.showGrid(x=checked, y=checked, alpha=grid_alpha)

    def _on_plot_window_changed(self, plot_key, _value):
        self.plot_follow_latest[plot_key] = True
        if self.auto_scroll_check.isChecked():
            self._scroll_to_latest()

    def _apply_auto_scale(self):
        enabled = self.auto_scale_check.isChecked()
        self.plot_auto_y = {key: enabled for key in self.plot_items}
        for plot_item in self.plot_items.values():
            plot_item.enableAutoRange(axis="y", enable=False)
        if enabled:
            self._refresh_visible_y_ranges(force=True)

    def reset_view(self):
        self.auto_scroll_check.setChecked(True)
        self.auto_scale_check.setChecked(True)
        self.plot_follow_latest = {key: True for key in self.plot_items}
        self.plot_auto_y = {key: True for key in self.plot_items}
        self.programmatic_range_change = True
        try:
            for plot_item in self.plot_items.values():
                plot_item.enableAutoRange(axis="y", enable=False)
            self._scroll_to_latest()
            self._refresh_visible_y_ranges(force=True)
        finally:
            self.programmatic_range_change = False

    def clear_data(self):
        self.t0 = None
        self.time_history.clear()
        for data in self.history.values():
            data.clear()
        for curve in self.curves.values():
            curve.setData([], [])
        self.frames_total = 0
        self.frames_this_second = 0
        self.last_auto_y_time = 0.0
        self.rate_label.setText("0 frame/s | 0 frames")
        self.append_console("已清空曲线缓存")

    def _set_all_channels(self, checked):
        for check in self.channel_checks.values():
            check.setChecked(checked)

    def _update_channel_visibility(self):
        for key, curve in self.curves.items():
            curve.setVisible(self.channel_checks[key].isChecked())
        if self.time_history:
            self._update_plot()
            if self.auto_scale_check.isChecked():
                self._refresh_visible_y_ranges(force=True)
        elif self.auto_scale_check.isChecked():
            self._refresh_visible_y_ranges(force=True)

    def _push_demo_frame(self):
        now = time.perf_counter()
        self.demo_phase += 0.025
        phase = self.demo_phase
        values = {
            "ia": 0.42 + 0.08 * math.sin(phase * 6.0) + 0.015 * math.sin(phase * 31.0),
            "ib": 0.38 + 0.08 * math.sin(phase * 6.0 - 2.094) + 0.012 * math.sin(phase * 27.0),
            "ic": 0.40 + 0.08 * math.sin(phase * 6.0 + 2.094) + 0.010 * math.sin(phase * 23.0),
            "theta": (phase * 1.8) % (2.0 * math.pi),
            "speed": 600.0 + 18.0 * math.sin(phase * 0.9) + 2.0 * math.sin(phase * 8.0),
            "ref": self.speed_spin.value(),
            "vbus": 24.0 + 0.05 * math.sin(phase * 0.6),
            "id": 0.02 * math.sin(phase * 3.0),
            "iq": 0.45 + 0.06 * math.sin(phase * 1.7),
            "id_ref": 0.0,
            "iq_ref": 0.5,
            "ud": 0.2 * math.sin(phase * 2.0),
            "uq": 7.5 + 0.3 * math.sin(phase * 0.9),
            "tcmp1": 4000.0 + 120.0 * math.sin(phase * 6.0),
            "tcmp2": 4000.0 + 120.0 * math.sin(phase * 6.0 - 2.094),
            "tcmp3": 4000.0 + 120.0 * math.sin(phase * 6.0 + 2.094),
            "foc_state": 5.0,
        }
        try:
            self.frame_queue.put_nowait((now, values))
        except queue.Full:
            pass

    def _update_ui(self):
        drained = self._drain_frames()
        if drained > 0 and not self.paused:
            self._update_plot()
            self._update_cards()
        self._update_rate()

    def _drain_frames(self):
        drained = 0
        max_frames_per_tick = 2500

        while drained < max_frames_per_tick:
            try:
                timestamp, values = self.frame_queue.get_nowait()
            except queue.Empty:
                break

            if self.t0 is None:
                self.t0 = timestamp
            t_rel = timestamp - self.t0
            self.time_history.append(t_rel)

            for channel in CHANNELS:
                value = float(values.get(channel.key, float("nan")))
                if channel.key == "theta":
                    value = wrap_angle_0_2pi(value)
                self.last_values[channel.key] = value
                if channel.key == "theta":
                    self.history[channel.key].append(value)
                else:
                    self.history[channel.key].append(value)

            if self.logging and self.log_writer:
                self.log_writer.writerow([
                    f"{t_rel:.6f}",
                    *[f"{float(values.get(key, float('nan'))):.8g}" for key in TELEMETRY_KEYS_DIAGNOSTIC],
                ])

            drained += 1
            self.frames_total += 1
            self.frames_this_second += 1

        if self.logging and self.log_file and drained:
            self.log_file.flush()
        return drained

    def _update_plot(self):
        if not self.time_history:
            return

        x = np.fromiter(self.time_history, dtype=float)
        latest_time = float(x[-1])
        y_arrays = {}
        for channel in CHANNELS:
            if not self.channel_checks[channel.key].isChecked():
                continue
            y = np.fromiter(self.history[channel.key], dtype=float)
            y_arrays[channel.key] = y

        ranges = self._active_plot_x_ranges(latest_time, x, y_arrays)

        for channel in CHANNELS:
            if not self.channel_checks[channel.key].isChecked():
                continue
            y = y_arrays.get(channel.key)
            if len(y) == len(x):
                left, right = ranges[channel.plot]
                plot_x, plot_y = visible_curve_data_for_plot(
                    channel.plot,
                    x,
                    y,
                    left,
                    right,
                    PLOT_MAX_VISIBLE_POINTS[channel.plot],
                )
                self.curves[channel.key].setData(plot_x, plot_y)

        if self.auto_scroll_check.isChecked():
            self._apply_plot_x_ranges(ranges, only_following=True)

        if self.auto_scale_check.isChecked():
            now = time.perf_counter()
            if now - self.last_auto_y_time >= AUTO_Y_RANGE_INTERVAL_S:
                self._apply_visible_y_ranges(x, y_arrays, ranges)
                self.last_auto_y_time = now

    def _active_plot_x_ranges(self, latest_time, x=None, y_arrays=None):
        latest_ranges = self._plot_time_ranges(latest_time, x, y_arrays)
        current_ranges = self._current_plot_x_ranges()
        if not self.auto_scroll_check.isChecked():
            return current_ranges
        return {
            plot_key: latest_ranges[plot_key] if self.plot_follow_latest.get(plot_key, True) else current_ranges[plot_key]
            for plot_key in self.plot_items
        }

    def _plot_time_ranges(self, latest_time, x=None, y_arrays=None):
        ranges = {}
        for plot_key in self.plot_items:
            spin = self.plot_window_spins.get(plot_key)
            window = spin.value() if spin is not None else PLOT_DEFAULT_WINDOWS[plot_key]
            y_for_plot = None
            if x is not None and y_arrays is not None:
                finite_mask = np.zeros(len(x), dtype=bool)
                for channel in CHANNELS:
                    if channel.plot != plot_key:
                        continue
                    y = y_arrays.get(channel.key)
                    if y is not None and len(y) == len(x):
                        finite_mask |= np.isfinite(y)
                if np.any(finite_mask):
                    y_for_plot = finite_mask.astype(float)
                    y_for_plot[~finite_mask] = float("nan")
            ranges[plot_key] = time_range_for_latest(latest_time, window, x, y_for_plot)
        return ranges

    def _current_plot_x_ranges(self):
        ranges = {}
        for plot_key, plot_item in self.plot_items.items():
            view_range = plot_item.getViewBox().viewRange()[0]
            ranges[plot_key] = (float(view_range[0]), float(view_range[1]))
        return ranges

    def _apply_plot_x_ranges(self, ranges, only_following=False):
        self.programmatic_range_change = True
        try:
            for plot_key, plot_item in self.plot_items.items():
                if only_following and not self.plot_follow_latest.get(plot_key, True):
                    continue
                left, right = ranges[plot_key]
                plot_item.setXRange(left, right, padding=0.0)
                self._sync_axis_views(plot_key)
        finally:
            self.programmatic_range_change = False

    def _refresh_visible_y_ranges(self, force=False):
        if not self.time_history:
            return
        now = time.perf_counter()
        if not force and now - self.last_auto_y_time < AUTO_Y_RANGE_INTERVAL_S:
            return

        x = np.fromiter(self.time_history, dtype=float)
        y_arrays = {
            channel.key: np.fromiter(self.history[channel.key], dtype=float)
            for channel in CHANNELS
            if self.channel_checks[channel.key].isChecked()
        }
        ranges = self._active_plot_x_ranges(float(x[-1]), x, y_arrays)
        self._apply_visible_y_ranges(x, y_arrays, ranges)
        self.last_auto_y_time = now

    def _apply_visible_y_ranges(self, x, y_arrays, ranges):
        self.programmatic_range_change = True
        try:
            for plot_key in self.plot_items:
                if not self.auto_scale_check.isChecked() or not self.plot_auto_y.get(plot_key, True):
                    continue

                left, right = ranges[plot_key]
                mask = (x >= left) & (x <= right)
                visible_parts = []
                for channel_key in PLOT_PANELS[plot_key]["channels"]:
                    y = y_arrays.get(channel_key)
                    if y is not None and len(y) == len(x):
                        visible_parts.append(y[mask])
                if not visible_parts:
                    continue

                y_range = padded_y_range(np.concatenate(visible_parts), PLOT_Y_MIN_SPANS[plot_key])
                if y_range is not None:
                    self.plot_items[plot_key].getViewBox().setYRange(y_range[0], y_range[1], padding=0.0)
        finally:
            self.programmatic_range_change = False

    def _scroll_to_latest(self):
        if not self.time_history:
            return

        x = np.fromiter(self.time_history, dtype=float)
        y_arrays = {
            channel.key: np.fromiter(self.history[channel.key], dtype=float)
            for channel in CHANNELS
            if self.channel_checks[channel.key].isChecked()
        }
        ranges = self._active_plot_x_ranges(float(x[-1]), x, y_arrays)
        self._apply_plot_x_ranges(ranges, only_following=True)

    def _update_cards(self):
        for card in self.summary_cards:
            card.set_values(self.last_values)
        for key, card in self.cards.items():
            card.set_value(self.last_values[key])
        for key, label in self.diagnostic_value_labels.items():
            value = self.last_values.get(key, float("nan"))
            label.setText(f"{value:.4g}" if math.isfinite(value) else "--")

    def _update_rate(self):
        now = time.perf_counter()
        elapsed = now - self.last_rate_time
        if elapsed >= 1.0:
            fps = self.frames_this_second / elapsed
            self.rate_label.setText(f"{fps:.0f} frame/s | {self.frames_total} frames")
            self.frames_this_second = 0
            self.last_rate_time = now

    def closeEvent(self, event):
        self._stop_logging()
        self.demo_timer.stop()
        self.worker.stop()
        event.accept()

    def _style_sheet(self):
        if self.dark_theme:
            return """
            QMainWindow, QWidget {
                background: #0b1120;
                color: #e5e7eb;
                font-family: "Microsoft YaHei UI", "Segoe UI";
                font-size: 10pt;
            }
            #sidebar {
                background: #111827;
                border: 1px solid #334155;
                border-radius: 18px;
            }
            #sidebarScroll {
                background: transparent;
                border: none;
            }
            #mainScroll {
                background: transparent;
                border: none;
            }
            #appTitle {
                font-size: 20px;
                font-weight: 800;
                color: #f8fafc;
            }
            #appSubtitle, #hintText {
                color: #94a3b8;
            }
            #sectionTitle {
                font-size: 20px;
                font-weight: 800;
                color: #f8fafc;
            }
            #rateBadge {
                background: #1b2637;
                color: #d4deef;
                border: 1px solid #2f3d52;
                border-radius: 14px;
                padding: 6px 10px;
                font-weight: 700;
            }
            QGroupBox {
                border: 1px solid #334155;
                border-radius: 14px;
                margin-top: 8px;
                padding: 8px;
                background: #111827;
                color: #e5e7eb;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #cbd5e1;
            }
            QTabWidget::pane {
                border: none;
                border-top: 1px solid #263244;
                background: transparent;
            }
            QTabBar::tab {
                background: transparent;
                color: #8b97aa;
                border: none;
                border-bottom: 3px solid transparent;
                padding: 12px 22px 10px 22px;
                margin-right: 8px;
                font-size: 11pt;
            }
            QTabBar::tab:selected {
                color: #8b7cf6;
                border-bottom-color: #8b7cf6;
            }
            QTabBar::tab:hover {
                color: #dbeafe;
            }
            QLineEdit, QComboBox, QDoubleSpinBox, QPlainTextEdit {
                background: #0f172a;
                color: #e5e7eb;
                border: 1px solid #3a4658;
                border-radius: 12px;
                padding: 2px 8px;
                min-height: 20px;
            }
            QComboBox#flatCombo {
                background: #121b2b;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 2px 24px 2px 10px;
            }
            QComboBox#flatCombo::drop-down {
                border: none;
                background: transparent;
                width: 24px;
            }
            QComboBox#flatCombo::down-arrow {
                image: none;
                width: 0;
                height: 0;
            }
            QComboBox#flatCombo QAbstractItemView {
                background: #111827;
                color: #e5e7eb;
                border: 1px solid #334155;
                selection-background-color: #263244;
            }
            QPlainTextEdit {
                background: #020617;
                color: #bbf7d0;
                font-family: Consolas, "Cascadia Mono";
                font-size: 9pt;
            }
            QPushButton {
                background: #1e293b;
                color: #e5e7eb;
                border: 1px solid #3a4658;
                border-radius: 12px;
                padding: 3px 10px;
                min-height: 20px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #334155;
            }
            #themeButton {
                background: #0f172a;
                color: #e0f2fe;
                border-color: #38bdf8;
            }
            #primaryButton {
                background: #667aa4;
                color: #ffffff;
                border-color: #5b6f95;
            }
            #runButton {
                background: #6f9878;
                color: #ffffff;
                border-color: #63886c;
            }
            #stopButton {
                background: #b27575;
                color: #ffffff;
                border-color: #a16969;
            }
            #plotPanel {
                background: #0a101c;
                border: 1px solid #1e293b;
                border-radius: 20px;
            }
            #plotToolbar, #channelToolbar {
                background: transparent;
                border: none;
            }
            #plotCard {
                background: #151c2b;
                border: 1px solid #293548;
                border-radius: 18px;
            }
            #plotCanvas {
                background: transparent;
                border: none;
            }
            #channelPillColumn {
                background: transparent;
                min-width: 96px;
                max-width: 112px;
            }
            #channelPillScroll {
                background: transparent;
                border: none;
                min-height: 36px;
                max-height: 42px;
            }
            #channelPillHost {
                background: transparent;
            }
            #toolbarButton {
                background: #1b2637;
                color: #b9c4d6;
                border: 1px solid #2f3d52;
                border-radius: 15px;
                padding: 5px 10px;
                min-height: 28px;
            }
            #toolbarButton:hover {
                background: #243249;
                color: #f8fafc;
            }
            #iconButton, #recordButton {
                background: #1b2637;
                color: #d4deef;
                border: 1px solid #2f3d52;
                border-radius: 19px;
                padding: 0;
                min-height: 36px;
                font-size: 18px;
            }
            #iconButton:checked, #recordButton:checked {
                background: #1b2637;
                color: #d4deef;
                border-color: #2f3d52;
            }
            #recordButton {
                color: #e05264;
            }
            #iconButton:hover, #recordButton:hover {
                background: #243249;
            }
            #telemetryCard {
                background: #111827;
                border: 1px solid #334155;
                border-radius: 16px;
            }
            #summaryCard {
                background: #111827;
                border: 1px solid #334155;
                border-radius: 16px;
            }
            #summaryTitle {
                color: #94a3b8;
                font-weight: 700;
            }
            #summaryValue {
                color: #f8fafc;
                font-size: 13px;
                font-weight: 800;
            }
            #cardTitle {
                color: #94a3b8;
                font-weight: 600;
            }
            #cardValue {
                color: #f8fafc;
                font-size: 16px;
                font-weight: 800;
            }
            #cardUnit {
                color: #64748b;
                font-size: 9pt;
            }
            #diagName {
                color: #94a3b8;
                font-weight: 700;
            }
            #diagValue {
                background: #020617;
                border: 1px solid #1e293b;
                border-radius: 14px;
                color: #f8fafc;
                font-weight: 800;
                padding: 8px 10px;
            }
            #diagUnit {
                color: #64748b;
            }
            #diagnosticChip {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 14px;
            }
            QCheckBox {
                color: #e5e7eb;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                border-radius: 5px;
                min-height: 44px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QStatusBar {
                background: #020617;
                color: #cbd5e1;
            }
            """

        return """
        QMainWindow, QWidget {
            background: #ffffff;
            color: #111827;
            font-family: "Microsoft YaHei UI", "Segoe UI";
            font-size: 10pt;
        }
        #sidebar {
            background: #ffffff;
            border: 1px solid #d9dee7;
            border-radius: 18px;
        }
        #sidebarScroll {
            background: transparent;
            border: none;
        }
        #mainScroll {
            background: transparent;
            border: none;
        }
        #appTitle {
            font-size: 20px;
            font-weight: 800;
            color: #111827;
        }
        #appSubtitle, #hintText {
            color: #64748b;
        }
        #sectionTitle {
            font-size: 20px;
            font-weight: 800;
        }
        #rateBadge {
            background: #ffffff;
            color: #111827;
            border: 1px solid #cfd6e1;
            border-radius: 14px;
            padding: 6px 10px;
            font-weight: 700;
        }
        QGroupBox {
            border: 1px solid #d9dee7;
            border-radius: 14px;
            margin-top: 8px;
            padding: 8px;
            background: #ffffff;
            font-weight: 700;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
            color: #374151;
        }
        QTabWidget::pane {
            border: none;
            border-top: 1px solid #e5e7eb;
            background: transparent;
        }
        QTabBar::tab {
            background: transparent;
            color: #64748b;
            border: none;
            border-bottom: 3px solid transparent;
            padding: 12px 22px 10px 22px;
            margin-right: 8px;
            font-size: 11pt;
        }
        QTabBar::tab:selected {
            color: #6d5df2;
            border-bottom-color: #6d5df2;
        }
        QTabBar::tab:hover {
            color: #111827;
        }
        QLineEdit, QComboBox, QDoubleSpinBox, QPlainTextEdit {
            background: #ffffff;
            border: 1px solid #cfd6e1;
            border-radius: 12px;
            padding: 2px 8px;
            min-height: 20px;
        }
        QComboBox#flatCombo {
            background: #f8fafc;
            border: 1px solid #d7dee8;
            border-radius: 12px;
            padding: 2px 24px 2px 10px;
        }
        QComboBox#flatCombo::drop-down {
            border: none;
            background: transparent;
            width: 24px;
        }
        QComboBox#flatCombo::down-arrow {
            image: none;
            width: 0;
            height: 0;
        }
        QComboBox#flatCombo QAbstractItemView {
            background: #ffffff;
            color: #111827;
            border: 1px solid #d7dee8;
            selection-background-color: #eef2f7;
        }
        QPlainTextEdit {
            background: #0f172a;
            color: #d1fae5;
            font-family: Consolas, "Cascadia Mono";
            font-size: 9pt;
        }
        QPushButton {
            background: #eef2f7;
            border: 1px solid #cfd6e1;
            border-radius: 12px;
            padding: 3px 10px;
            min-height: 20px;
            font-weight: 600;
        }
        QPushButton:hover {
            background: #e2e8f0;
        }
        #themeButton {
            background: #ffffff;
            color: #111827;
            border-color: #cfd6e1;
        }
        #primaryButton {
            background: #7588b2;
            color: #ffffff;
            border-color: #697ba0;
        }
        #runButton {
            background: #78a381;
            color: #ffffff;
            border-color: #6b9274;
        }
        #stopButton {
            background: #bc7c7c;
            color: #ffffff;
            border-color: #aa7070;
        }
        #plotPanel {
            background: #f8fafc;
            border: 1px solid #e5e7eb;
            border-radius: 20px;
        }
        #plotToolbar, #channelToolbar {
            background: transparent;
            border: none;
        }
        #plotCard {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 18px;
        }
        #plotCanvas {
            background: transparent;
            border: none;
        }
        #channelPillColumn {
            background: transparent;
            min-width: 96px;
            max-width: 112px;
        }
        #channelPillScroll {
            background: transparent;
            border: none;
            min-height: 36px;
            max-height: 42px;
        }
        #channelPillHost {
            background: transparent;
        }
        #toolbarButton {
            background: #ffffff;
            color: #475569;
            border: 1px solid #e2e8f0;
            border-radius: 15px;
            padding: 5px 10px;
            min-height: 28px;
        }
        #toolbarButton:hover {
            background: #f1f5f9;
            color: #0f172a;
        }
        #iconButton, #recordButton {
            background: #ffffff;
            color: #475569;
            border: 1px solid #e2e8f0;
            border-radius: 19px;
            padding: 0;
            min-height: 36px;
            font-size: 18px;
        }
        #iconButton:checked, #recordButton:checked {
            background: #ffffff;
            color: #475569;
            border-color: #e2e8f0;
        }
        #recordButton {
            color: #d9465f;
        }
        #iconButton:hover, #recordButton:hover {
            background: #f1f5f9;
            color: #0f172a;
        }
        #telemetryCard {
            background: #ffffff;
            border: 1px solid #d9dee7;
            border-radius: 16px;
        }
        #summaryCard {
            background: #ffffff;
            border: 1px solid #d9dee7;
            border-radius: 16px;
        }
        #summaryTitle {
            color: #64748b;
            font-weight: 700;
        }
        #summaryValue {
            color: #0f172a;
            font-size: 13px;
            font-weight: 800;
        }
        #cardTitle {
            color: #64748b;
            font-weight: 600;
        }
        #cardValue {
            color: #0f172a;
            font-size: 16px;
            font-weight: 800;
        }
        #cardUnit {
            color: #94a3b8;
            font-size: 9pt;
        }
        #diagName {
            color: #64748b;
            font-weight: 700;
        }
        #diagValue {
            background: #f8fafc;
            border: 1px solid #d9dee7;
            border-radius: 14px;
            color: #0f172a;
            font-weight: 800;
            padding: 8px 10px;
        }
        #diagUnit {
            color: #94a3b8;
        }
        #diagnosticChip {
            background: #ffffff;
            border: 1px solid #d9dee7;
            border-radius: 14px;
        }
        QScrollBar:vertical {
            background: transparent;
            width: 10px;
            margin: 0;
        }
        QScrollBar::handle:vertical {
            background: #cbd5e1;
            border-radius: 5px;
            min-height: 44px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: transparent;
        }
        QStatusBar {
            background: #ffffff;
            color: #334155;
        }
        """


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("MyFOC_NFlux Host")
    window = MyFocHostWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
