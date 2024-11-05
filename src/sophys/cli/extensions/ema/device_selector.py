import functools
import logging
import subprocess

from dataclasses import dataclass
from enum import IntFlag

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QMainWindow, QApplication, QFrame, QLabel, QVBoxLayout, QSizePolicy, QTabWidget, QGridLayout, QCheckBox, QSpacerItem, QWidget, QPushButton

from ...data_source import DataSource


class DeviceType(IntFlag):
    READABLE = 0b0001
    SETTABLE = 0b0010
    WITH_SEPARATE_AD_ROI = 0b0100  # Separate ROI and Stats plugins
    WITH_COMBINED_AD_ROI = 0b1000  # Unified ROIStats plugin


@dataclass
class DeviceItem:
    user_name: str
    mnemonic: str
    type: DeviceType


EMA_DEVICES = [
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

    DeviceItem("Vortex"           , "xrf", DeviceType.READABLE),  # noqa: E203
    DeviceItem("Pimega 540D (S1)" , "ad2", DeviceType.READABLE | DeviceType.WITH_SEPARATE_AD_ROI),  # noqa: E203
    DeviceItem("Mobipix"          , "ad1", DeviceType.READABLE | DeviceType.WITH_SEPARATE_AD_ROI),  # noqa: E203
    DeviceItem("Pilatus 300K"     , "ad4", DeviceType.READABLE | DeviceType.WITH_COMBINED_AD_ROI),  # noqa: E203
]


def label(text, alignment=Qt.AlignHCenter):
    _l = QLabel(text)
    _l.setAlignment(alignment)
    return _l


class SourcedCheckBox(QCheckBox):
    def __init__(self, data_source: DataSource, type: DataSource.DataType, key: str, parent=None):
        super().__init__(parent)

        self._data_source = data_source
        self._data_type = type
        self._key = key

        if self._key in self._data_source.get(type):
            self.setChecked(True)

        self.toggled.connect(self.onToggle)

    def onToggle(self, got_checked: bool):
        if got_checked:
            self._data_source.add(self._data_type, self._key)
        else:
            self._data_source.remove(self._data_type, self._key)


class SeparateROIConfigurationWidget(QWidget):
    def __init__(self, parent_mnemonic: str, parent=None):
        super().__init__(parent)

        self._mnemonic = parent_mnemonic

        self.setVisible(False)

        try:
            from suitscase.widgets.area_detector.plugin_list import getSimplifiedPluginConfigurationFile
        except ImportError:
            logging.error("Failed to import suitscase, which is required for this option.")
            return

        base_command = "pydm --hide-nav-bar --hide-menu-bar --hide-status-bar"
        roi_file_path = getSimplifiedPluginConfigurationFile("NDPluginROI")
        stats_file_path = getSimplifiedPluginConfigurationFile("NDPluginStats")

        def roi_btn_callback(n):
            subprocess.Popen(f"{base_command} -m P={self.parent_prefix},R=ROI{n} {roi_file_path}".split(" "))

        def stats_btn_callback(n):
            subprocess.Popen(f"{base_command} -m P={self.parent_prefix},R=Stats{n} {stats_file_path}".split(" "))

        layout = QGridLayout()
        layout.addWidget(label("ROI plugin"), 0, 1, 1, 2)
        layout.addWidget(label("Stats plugin"), 0, 3, 1, 2)

        for n in range(1, 5):
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
    def __init__(self, text: str, parent_mnemonic: str, parent=None):
        super().__init__(text, parent)

        self.setCheckable(True)

        self._widget = SeparateROIConfigurationWidget(parent_mnemonic)
        self.toggled.connect(self._widget.setVisible)

    @property
    def config_widget(self):
        return self._widget


class CombinedROIConfigurationWidget(QWidget):
    def __init__(self, parent_mnemonic: str, parent=None):
        super().__init__(parent)

        self._mnemonic = parent_mnemonic

        self.setVisible(False)

        try:
            from suitscase.widgets.area_detector.plugin_list import getSimplifiedPluginConfigurationFile
        except ImportError:
            logging.error("Failed to import suitscase, which is required for this option.")
            return

        base_command = "pydm --hide-nav-bar --hide-menu-bar --hide-status-bar"
        roistat_file_path = getSimplifiedPluginConfigurationFile("NDPluginROIStat")

        def roistat_btn_callback(n):
            subprocess.Popen(f"{base_command} -m P={self.parent_prefix},R=ROIStat{n} {roistat_file_path}".split(" "))

        layout = QGridLayout()
        layout.addWidget(label("ROIStat plugin"), 0, 1, 1, 2)

        for n in range(1, 5):
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
    def __init__(self, text: str, parent_mnemonic: str, parent=None):
        super().__init__(text, parent)

        self.setCheckable(True)

        self._widget = CombinedROIConfigurationWidget(parent_mnemonic)
        self.toggled.connect(self._widget.setVisible)

    @property
    def config_widget(self):
        return self._widget


class DeviceSelectorMainWindow(QMainWindow):
    def __init__(self, data_source: DataSource, parent=None):
        super().__init__(parent)

        self._data_source = data_source

        self.main_layout = QVBoxLayout()
        main_title = QLabel("<h1>EMA Device Selector</h1>")
        main_title.setAlignment(Qt.AlignHCenter)
        self.main_layout.addWidget(main_title)

        readable_page = QWidget()
        settable_page = QWidget()

        readable_form = QGridLayout()
        settable_form = QGridLayout()

        self.populateDevices(readable_form, settable_form)

        readable_page.setLayout(readable_form)
        settable_page.setLayout(settable_form)

        device_type_tab_widget = QTabWidget()
        device_type_tab_widget.addTab(readable_page, "Detectors")
        device_type_tab_widget.addTab(settable_page, "Motors")
        self.main_layout.addWidget(device_type_tab_widget)

        main_frame = QFrame()
        main_frame.setStyleSheet(".QFrame { margin: 2px; border: 2px solid #000000; border-radius: 4px; }")
        main_frame.setFrameShape(QFrame.Shape.Box)
        main_frame.setLayout(self.main_layout)

        self.setCentralWidget(main_frame)

    def populateDevices(self, readable_form: QGridLayout, settable_form: QGridLayout):
        readable_form.addWidget(label("Device name"), 0, 0, 1, 1)
        readable_form.addWidget(label("Mnemonic"), 0, 1, 1, 1)
        readable_form.addWidget(label("Read configuration"), 0, 2, 1, 10)
        readable_form.addWidget(label("Before the scan"), 1, 2, 1, 3)
        readable_form.addWidget(label("During the scan"), 1, 5, 1, 3)
        readable_form.addWidget(label("After the scan"), 1, 8, 1, 3)

        def add_to_layout(item, layout):
            row = layout.rowCount()

            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Fixed, QSizePolicy.Expanding), row, 0, 1, 1)
            row += 1

            layout.addWidget(label(item.user_name), row, 0, 1, 1)
            layout.addWidget(label(item.mnemonic), row, 1, 1, 1)

            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), row, 2, 1, 1)
            before_checkbox = SourcedCheckBox(self._data_source, DataSource.DataType.BEFORE, item.mnemonic)
            layout.addWidget(before_checkbox, row, 3, 1, 1)
            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), row, 4, 1, 1)

            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), row, 5, 1, 1)
            during_checkbox = SourcedCheckBox(self._data_source, DataSource.DataType.DETECTORS, item.mnemonic)
            layout.addWidget(during_checkbox, row, 6, 1, 1)
            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), row, 7, 1, 1)

            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), row, 8, 1, 1)
            after_checkbox = SourcedCheckBox(self._data_source, DataSource.DataType.AFTER, item.mnemonic)
            layout.addWidget(after_checkbox, row, 9, 1, 1)
            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), row, 10, 1, 1)

            if item.type & DeviceType.WITH_SEPARATE_AD_ROI:
                roi_push_button = SeparateROIConfigurationPushButton("ROIs", item.mnemonic)
                roi_push_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                layout.addWidget(roi_push_button, row, 11, 1, 1)
                layout.addWidget(roi_push_button.config_widget, row+1, 2, 1, 10)

            if item.type & DeviceType.WITH_COMBINED_AD_ROI:
                roi_push_button = CombinedROIConfigurationPushButton("ROIs", item.mnemonic)
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
    def __main(data_source: DataSource):
        if QApplication.instance():
            app = QApplication.instance()
        else:
            app = QApplication(["EMA Device Selector"])

        main_window = DeviceSelectorMainWindow(data_source)
        main_window.setStyleSheet(WINDOW_STYLESHEET)
        main_window.show()

        app.exec()

    __main(data_source)
