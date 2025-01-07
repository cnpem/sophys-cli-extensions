import functools
import json
import logging
import subprocess

from natsort import natsorted

from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QLabel, QGridLayout, QCheckBox, QComboBox, QWidget, QPushButton

from sophys.cli.core.data_source import DataSource


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


class SourcedComboBox(QComboBox):
    def __init__(self, data_source: DataSource, in_type: DataSource.DataType, out_type: DataSource.DataType, parent=None):
        super().__init__(parent)

        self._data_source = data_source
        self._in_data_type = in_type
        self._out_data_type = out_type

        self._current_key = data_source.get(out_type)
        if len(self._current_key) == 0:
            self._current_key = None
        else:
            self._current_key = self._current_key[0]

        self.currentTextChanged.connect(self.onSelectedKeyChanged)

        self._timer = QTimer(self)
        self._timer.setInterval(2_000)
        self._timer.setSingleShot(False)
        self._timer.timeout.connect(self.updateOptions)
        self._timer.start()

        self.updateOptions()

    def updateOptions(self):
        new_opts = natsorted(list(self._data_source.get(self._in_data_type)))
        new_opts.insert(0, "No selected device.")

        self.blockSignals(True)
        self.clear()
        self.addItems(new_opts)
        if self._current_key is not None:
            self.setCurrentText(self._current_key)
        self.blockSignals(False)

        if self.currentText() != self._current_key:
            if self._current_key is not None:
                self._data_source.remove(self._out_data_type, self._current_key)
            self._current_key = None

    def onSelectedKeyChanged(self, new_key: str):
        if self._current_key is not None:
            self._data_source.remove(self._out_data_type, self._current_key)

        if new_key == "No selected device.":
            self._current_key = None
            return

        self._data_source.add(self._out_data_type, new_key)
        self._current_key = new_key


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

