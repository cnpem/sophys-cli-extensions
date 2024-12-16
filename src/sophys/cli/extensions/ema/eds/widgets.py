import functools
import json
import logging
import subprocess

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QGridLayout, QCheckBox, QWidget, QPushButton

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
