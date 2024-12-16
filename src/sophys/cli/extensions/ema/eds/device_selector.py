import functools
import json
import logging
import subprocess
import typing

from dataclasses import dataclass
from enum import IntFlag

from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QMainWindow, QApplication, QFrame, QLabel, QVBoxLayout, QSizePolicy, QTabWidget, QGridLayout, QCheckBox, QComboBox, QSpacerItem, QWidget, QPushButton

from sophys.cli.core.data_source import DataSource
from sophys.cli.core.magics import NamespaceKeys, get_from_namespace


class DeviceType(IntFlag):
    READABLE = 0b001
    SETTABLE = 0b010
    SIMULATED = 0b100


class DeviceROIType(IntFlag):
    WITH_SEPARATE_AD_ROI = 0b01  # Separate ROI and Stats plugins
    WITH_COMBINED_AD_ROI = 0b10  # Unified ROIStats plugin


@dataclass
class DeviceItem:
    user_name: str
    mnemonic: str
    type: DeviceType

    roi_type: typing.Optional[DeviceROIType] = 0
    roi_count: typing.Optional[int] = 4

    extra_mnemonics: typing.Optional[dict[DataSource.DataType, tuple[str]]] = None

    def get_all_mnemonics(self, data_type: DataSource.DataType) -> tuple[str]:
        if self.extra_mnemonics is None:
            return (self.mnemonic,)
        return (self.mnemonic, *self.extra_mnemonics.get(data_type, tuple()))


__VORTEX_EXTRA_MNEMONICS = {
    DataSource.DataType.DETECTORS: (
        "xrf1r1", "xrf1r2", "xrf1r3", "xrf1r4", #"xrf1r5", "xrf1r6",
        "xrf2r1", "xrf2r2", "xrf2r3", "xrf2r4", #"xrf2r5", "xrf2r6",
        "xrf3r1", "xrf3r2", "xrf3r3", "xrf3r4", #"xrf3r5", "xrf3r6",
        "xrf4r1", "xrf4r2", "xrf4r3", "xrf4r4", #"xrf4r5", "xrf4r6",
    ),
    DataSource.DataType.BEFORE: (
        "xrf1r1h", "xrf1r1l", "xrf1r2h", "xrf1r2l", "xrf1r3h", "xrf1r3l",
        "xrf1r4h", "xrf1r4l", #"xrf1r5h", "xrf1r5l", "xrf1r6h", "xrf1r6l",
        "xrf2r1h", "xrf2r1l", "xrf2r2h", "xrf2r2l", "xrf2r3h", "xrf2r3l",
        "xrf2r4h", "xrf2r4l", #"xrf2r5h", "xrf2r5l", "xrf2r6h", "xrf2r6l",
        "xrf3r1h", "xrf3r1l", "xrf3r2h", "xrf3r2l", "xrf3r3h", "xrf3r3l",
        "xrf3r4h", "xrf3r4l", #"xrf3r5h", "xrf3r5l", "xrf3r6h", "xrf3r6l",
        "xrf4r1h", "xrf4r1l", "xrf4r2h", "xrf4r2l", "xrf4r3h", "xrf4r3l",
        "xrf4r4h", "xrf4r4l", #"xrf4r5h", "xrf4r5l", "xrf4r6h", "xrf4r6l",
    ),
    DataSource.DataType.AFTER: (
        "xrf1r1h", "xrf1r1l", "xrf1r2h", "xrf1r2l", "xrf1r3h", "xrf1r3l",
        "xrf1r4h", "xrf1r4l", #"xrf1r5h", "xrf1r5l", "xrf1r6h", "xrf1r6l",
        "xrf2r1h", "xrf2r1l", "xrf2r2h", "xrf2r2l", "xrf2r3h", "xrf2r3l",
        "xrf2r4h", "xrf2r4l", #"xrf2r5h", "xrf2r5l", "xrf2r6h", "xrf2r6l",
        "xrf3r1h", "xrf3r1l", "xrf3r2h", "xrf3r2l", "xrf3r3h", "xrf3r3l",
        "xrf3r4h", "xrf3r4l", #"xrf3r5h", "xrf3r5l", "xrf3r6h", "xrf3r6l",
        "xrf4r1h", "xrf4r1l", "xrf4r2h", "xrf4r2l", "xrf4r3h", "xrf4r3l",
        "xrf4r4h", "xrf4r4l", #"xrf4r5h", "xrf4r5l", "xrf4r6h", "xrf4r6l",
    ),
}


__PILATUS_EXTRA_MNEMONICS = {
    DataSource.DataType.DETECTORS: (
        "ad4r1", "ad4r2", "ad4r3", "ad4r4",
        "ad4r5", "ad4r6", "ad4r7", "ad4r8",
    ),
    DataSource.DataType.BEFORE: (
        "ad4r1xi", "ad4r2xi", "ad4r3xi", "ad4r4xi",
        "ad4r5xi", "ad4r6xi", "ad4r7xi", "ad4r8xi",
        "ad4r1xs", "ad4r2xs", "ad4r3xs", "ad4r4xs",
        "ad4r5xs", "ad4r6xs", "ad4r7xs", "ad4r8xs",
    ),
    DataSource.DataType.AFTER: (
        "ad4r1xi", "ad4r2xi", "ad4r3xi", "ad4r4xi",
        "ad4r5xi", "ad4r6xi", "ad4r7xi", "ad4r8xi",
        "ad4r1xs", "ad4r2xs", "ad4r3xs", "ad4r4xs",
        "ad4r5xs", "ad4r6xs", "ad4r7xs", "ad4r8xs",
    ),
}


EMA_DEVICES = [
    DeviceItem("Ring current", "rcurr", DeviceType.READABLE),

    DeviceItem("I0", "i0c", DeviceType.READABLE),
    DeviceItem("I1", "i1c", DeviceType.READABLE),
    DeviceItem("I2", "i2c", DeviceType.READABLE),
    DeviceItem("I3", "i3c", DeviceType.READABLE),
    DeviceItem("I4", "i4c", DeviceType.READABLE),
    DeviceItem("I5", "i5c", DeviceType.READABLE),
    DeviceItem("I6", "i6c", DeviceType.READABLE),
    DeviceItem("I7", "i7c", DeviceType.READABLE),
    DeviceItem("I8", "i8c", DeviceType.READABLE),

    DeviceItem("MVS2", "mvs2", DeviceType.READABLE),
    DeviceItem("MVS3", "mvs3", DeviceType.READABLE),

    DeviceItem("Vortex"           , "xrf", DeviceType.READABLE, extra_mnemonics=__VORTEX_EXTRA_MNEMONICS),  # noqa: E203
    DeviceItem("Pimega 540D (S1)" , "ad2", DeviceType.READABLE, DeviceROIType.WITH_SEPARATE_AD_ROI),  # noqa: E203
    DeviceItem("Mobipix"          , "ad1", DeviceType.READABLE, DeviceROIType.WITH_SEPARATE_AD_ROI),  # noqa: E203
    DeviceItem("Pilatus 300K"     , "ad4", DeviceType.READABLE, DeviceROIType.WITH_COMBINED_AD_ROI, roi_count=1, extra_mnemonics=__PILATUS_EXTRA_MNEMONICS),  # noqa: E203

    DeviceItem("Random value", "sim_rand", DeviceType.SIMULATED),

    DeviceItem("Motor", "sim_motor", DeviceType.SIMULATED),
    DeviceItem("Detector (Motor)", "sim_det", DeviceType.SIMULATED),
    DeviceItem("Noisy Detector (Motor)", "sim_noisy_det", DeviceType.SIMULATED),

    DeviceItem("Motor 1", "sim_motor1", DeviceType.SIMULATED),
    DeviceItem("Motor 2", "sim_motor2", DeviceType.SIMULATED),
    DeviceItem("Detector (Motor 1 + Motor 2)", "sim_det4", DeviceType.SIMULATED),

    DeviceItem("Jittery Motor 1", "sim_jittery_motor1", DeviceType.SIMULATED),
    DeviceItem("Jittery Motor 2", "sim_jittery_motor2", DeviceType.SIMULATED),
    DeviceItem("Detector (Jittery Motor 1 + Jittery Motor 2)", "sim_det5", DeviceType.SIMULATED),
]


def label(text, alignment=Qt.AlignHCenter):
    _l = QLabel(text)
    _l.setAlignment(alignment)
    return _l


class SourcedCheckBox(QCheckBox):
    def __init__(self, data_source: DataSource, type: DataSource.DataType, keys: tuple[str], parent=None):
        super().__init__(parent)

        self._data_source = data_source
        self._data_type = type
        self._keys = keys

        if any(key in self._data_source.get(type) for key in self._keys):
            self.setChecked(True)

        self.toggled.connect(self.onToggle)

    def onToggle(self, got_checked: bool):
        if got_checked:
            self._data_source.add(self._data_type, *self._keys)
        else:
            self._data_source.remove(self._data_type, *self._keys)


class SeparateROIConfigurationWidget(QWidget):
    def __init__(self, parent_mnemonic: str, number_of_rois: int, parent=None):
        super().__init__(parent)

        self._mnemonic = parent_mnemonic

        self.setVisible(False)

        try:
            from suitscase.widgets.area_detector.plugin_list import (
                getSimplifiedPluginConfigurationFile,
                getSimplifiedExtraPluginConfigurationMacros,
            )
        except ImportError:
            logging.error("Failed to import suitscase, which is required for this option.")
            return

        from pathlib import Path
        base_command = [str(Path(__file__).parent / "open_plugin_page.sh")]

        roi_file_path = getSimplifiedPluginConfigurationFile("NDPluginROI")
        roi_macros = getSimplifiedExtraPluginConfigurationMacros("NDPluginROI")
        stats_file_path = getSimplifiedPluginConfigurationFile("NDPluginStats")
        stats_macros = getSimplifiedExtraPluginConfigurationMacros("NDPluginStats")

        def roi_btn_callback(n):
            macros = {"P": self.parent_prefix, "R": f"ROI{n}", **roi_macros}
            subprocess.Popen([*base_command, "-m", json.dumps(macros), roi_file_path])

        def stats_btn_callback(n):
            macros = {"P": self.parent_prefix, "R": f"Stats{n}", **stats_macros}
            subprocess.Popen([*base_command, "-m", json.dumps(macros), stats_file_path])

        layout = QGridLayout()
        layout.addWidget(label("ROI plugin"), 0, 1, 1, 2)
        layout.addWidget(label("Stats plugin"), 0, 3, 1, 2)

        for n in range(1, number_of_rois + 1):
            row = n

            layout.addWidget(QLabel("ROI " + str(n)), row, 0, 1, 1)

            roi_btn = QPushButton("Configuration")
            roi_btn.clicked.connect(functools.partial(roi_btn_callback, n))
            layout.addWidget(roi_btn, row, 1, 1, 2)

            stats_btn = QPushButton("Configuration")
            stats_btn.clicked.connect(functools.partial(stats_btn_callback, n))
            layout.addWidget(stats_btn, row, 3, 1, 2)

        self.setLayout(layout)

    @functools.cached_property
    def parent_prefix(self):
        from sophys.ema.utils import mnemonic_to_pv_name
        return mnemonic_to_pv_name(self._mnemonic)


class SeparateROIConfigurationPushButton(QPushButton):
    def __init__(self, text: str, parent_mnemonic: str, number_of_rois: int, parent=None):
        super().__init__(text, parent)

        self.setCheckable(True)

        self._widget = SeparateROIConfigurationWidget(parent_mnemonic, number_of_rois)
        self.toggled.connect(self._widget.setVisible)

    @property
    def config_widget(self):
        return self._widget


class CombinedROIConfigurationWidget(QWidget):
    def __init__(self, parent_mnemonic: str, number_of_rois: int, parent=None):
        super().__init__(parent)

        self._mnemonic = parent_mnemonic

        self.setVisible(False)

        try:
            from suitscase.widgets.area_detector.plugin_list import (
                getSimplifiedPluginConfigurationFile,
                getSimplifiedExtraPluginConfigurationMacros,
            )
        except ImportError:
            logging.error("Failed to import suitscase, which is required for this option.")
            return

        base_command = "pydm --hide-nav-bar --hide-menu-bar --hide-status-bar".split(' ')
        roistat_file_path = getSimplifiedPluginConfigurationFile("NDPluginROIStat")
        roistat_macros = getSimplifiedExtraPluginConfigurationMacros("NDPluginROIStat")

        def roistat_btn_callback(n):
            macros = {"P": self.parent_prefix, "R": f"ROIStat{n}", **roistat_macros}
            subprocess.Popen([*base_command, "-m", json.dumps(macros), roistat_file_path])

        layout = QGridLayout()
        layout.addWidget(label("ROIStat plugin"), 0, 1, 1, 2)

        for n in range(1, number_of_rois + 1):
            row = n

            layout.addWidget(QLabel("ROI " + str(n)), row, 0, 1, 1)

            roistat_btn = QPushButton("Configuration")
            roistat_btn.clicked.connect(functools.partial(roistat_btn_callback, n))
            layout.addWidget(roistat_btn, row, 1, 1, 2)

        self.setLayout(layout)

    @functools.cached_property
    def parent_prefix(self):
        from sophys.ema.utils import mnemonic_to_pv_name
        return mnemonic_to_pv_name(self._mnemonic)


class CombinedROIConfigurationPushButton(QPushButton):
    def __init__(self, text: str, parent_mnemonic: str, number_of_rois: int, parent=None):
        super().__init__(text, parent)

        self.setCheckable(True)

        self._widget = CombinedROIConfigurationWidget(parent_mnemonic, number_of_rois)
        self.toggled.connect(self._widget.setVisible)

    @property
    def config_widget(self):
        return self._widget


class DeviceSelectorMainWindow(QMainWindow):
    def __init__(self, data_source: DataSource, in_test_mode: bool = False, parent=None):
        super().__init__(parent)

        self._data_source = data_source

        self.main_layout = QVBoxLayout()

        main_title_text = "<h1>EMA Device Selector</h1>"
        if in_test_mode:
            main_title_text += f"<br/><h4>Testing mode ({data_source.__class__.__name__})</h4>"

        main_title = QLabel(main_title_text)
        main_title.setAlignment(Qt.AlignHCenter)
        self.main_layout.addWidget(main_title)

        readable_page = QWidget()
        settable_page = QWidget()
        simulated_page = None

        readable_form = QGridLayout()
        settable_form = QGridLayout()
        simulated_form = None

        if in_test_mode:
            simulated_page = QWidget()
            simulated_form = QGridLayout()

        self.populateDevices(readable_form, settable_form, simulated_form)

        readable_page.setLayout(readable_form)
        settable_page.setLayout(settable_form)
        if simulated_page is not None:
            simulated_page.setLayout(simulated_form)

        device_type_tab_widget = QTabWidget()
        device_type_tab_widget.addTab(readable_page, "Detectors")
        device_type_tab_widget.addTab(settable_page, "Motors")
        if simulated_page is not None:
            device_type_tab_widget.addTab(simulated_page, "Simulated")
        self.main_layout.addWidget(device_type_tab_widget)

        main_frame = QFrame()
        main_frame.setStyleSheet(".QFrame { margin: 2px; border: 2px solid #000000; border-radius: 4px; }")
        main_frame.setFrameShape(QFrame.Shape.Box)
        main_frame.setLayout(self.main_layout)

        self.setCentralWidget(main_frame)

    def populateDevices(self, readable_form: QGridLayout, settable_form: QGridLayout, simulated_form: typing.Optional[QGridLayout] = None):
        for form in (readable_form, settable_form, simulated_form):
            if form is None:
                continue

            form.addWidget(label("Device name"), 0, 0, 1, 1)
            form.addWidget(label("Mnemonic"), 0, 1, 1, 1)
            form.addWidget(label("Read configuration"), 0, 2, 1, 10)
            form.addWidget(label("Before the scan"), 1, 2, 1, 3)
            form.addWidget(label("During the scan"), 1, 5, 1, 3)
            form.addWidget(label("After the scan"), 1, 8, 1, 3)

        def add_to_layout(item, layout):
            row = layout.rowCount()

            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Fixed, QSizePolicy.Expanding), row, 0, 1, 1)
            row += 1

            layout.addWidget(label(item.user_name), row, 0, 1, 1)
            layout.addWidget(label(item.mnemonic), row, 1, 1, 1)

            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), row, 2, 1, 1)
            before_mnemonics = item.get_all_mnemonics(DataSource.DataType.BEFORE)
            before_checkbox = SourcedCheckBox(self._data_source, DataSource.DataType.BEFORE, before_mnemonics)
            layout.addWidget(before_checkbox, row, 3, 1, 1)
            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), row, 4, 1, 1)

            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), row, 5, 1, 1)
            during_mnemonics = item.get_all_mnemonics(DataSource.DataType.DETECTORS)
            during_checkbox = SourcedCheckBox(self._data_source, DataSource.DataType.DETECTORS, during_mnemonics)
            layout.addWidget(during_checkbox, row, 6, 1, 1)
            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), row, 7, 1, 1)

            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), row, 8, 1, 1)
            after_mnemonics = item.get_all_mnemonics(DataSource.DataType.AFTER)
            after_checkbox = SourcedCheckBox(self._data_source, DataSource.DataType.AFTER, after_mnemonics)
            layout.addWidget(after_checkbox, row, 9, 1, 1)
            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), row, 10, 1, 1)

            if item.roi_type & DeviceROIType.WITH_SEPARATE_AD_ROI:
                roi_push_button = SeparateROIConfigurationPushButton("ROIs", item.mnemonic, item.roi_count)
                roi_push_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                layout.addWidget(roi_push_button, row, 11, 1, 1)
                layout.addWidget(roi_push_button.config_widget, row+1, 2, 1, 10)

            if item.roi_type & DeviceROIType.WITH_COMBINED_AD_ROI:
                roi_push_button = CombinedROIConfigurationPushButton("ROIs", item.mnemonic, item.roi_count)
                roi_push_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                layout.addWidget(roi_push_button, row, 11, 1, 1)
                layout.addWidget(roi_push_button.config_widget, row+1, 2, 1, 10)

            row += 1
            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Fixed, QSizePolicy.Expanding), row, 0, 1, 1)

        for item in EMA_DEVICES:
            if item.type & DeviceType.READABLE:
                add_to_layout(item, readable_form)
            if item.type & DeviceType.SETTABLE:
                add_to_layout(item, settable_form)
            if item.type & DeviceType.SIMULATED and (simulated_form is not None):
                add_to_layout(item, simulated_form)


WINDOW_STYLESHEET = """
QTabWidget {
    background-color: #e0e0e6;
}
QTabBar::tab {
    border: 1px solid #a0a0b0;
    border-bottom: 0px;
    border-top-left-radius: 2px;
    border-top-right-radius: 2px;
    padding: 4px 12px 4px 12px;
    margin-bottom: 1px;
}
QTabBar::tab:selected {
    background-color: #ededf0;
    border-color: #9B9B9B;
    border-bottom-color: #ededf0; /* same as pane color */
}
"""


def spawnDeviceSelector(data_source: DataSource):
    def __main(data_source: DataSource, in_test_mode: bool):
        if QApplication.instance():
            app = QApplication.instance()
        else:
            app = QApplication(["EMA Device Selector"])

        main_window = DeviceSelectorMainWindow(data_source, in_test_mode)
        main_window.setStyleSheet(WINDOW_STYLESHEET)
        main_window.show()

        app.exec()

    in_test_mode = get_from_namespace(NamespaceKeys.TEST_MODE, False)
    __main(data_source, in_test_mode)
