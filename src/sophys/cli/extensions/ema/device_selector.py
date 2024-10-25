import multiprocessing
import sys

from dataclasses import dataclass
from enum import IntFlag

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QMainWindow, QApplication, QFrame, QLabel, QVBoxLayout, QSizePolicy, QTabWidget, QGridLayout, QHBoxLayout, QCheckBox, QSpacerItem, QWidget

from .data_source import DataSource


class DeviceType(IntFlag):
    READABLE = 0b01
    SETTABLE = 0b10


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

    DeviceItem("Vortex"           , "xrf", DeviceType.READABLE),  # noqa: E203
    DeviceItem("Pimega 540D (S1)" , "ad2", DeviceType.READABLE),  # noqa: E203
    DeviceItem("Mobipix"          , "ad1", DeviceType.READABLE),  # noqa: E203
    DeviceItem("Pilatus 300K"     , "ad4", DeviceType.READABLE),  # noqa: E203
]


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
        def label(text, alignment=Qt.AlignHCenter):
            _l = QLabel(text)
            _l.setAlignment(alignment)
            return _l

        readable_form.addWidget(label("Device name"), 0, 0, 1, 1)
        readable_form.addWidget(label("Mnemonic"), 0, 1, 1, 1)
        readable_form.addWidget(label("Read configuration"), 0, 2, 1, 9)
        readable_form.addWidget(label("Before the scan"), 1, 2, 1, 3)
        readable_form.addWidget(label("During the scan"), 1, 5, 1, 3)
        readable_form.addWidget(label("After the scan"), 1, 8, 1, 3)

        def add_to_layout(item, layout):
            row = layout.rowCount()

            layout.addWidget(label(item.user_name), row, 0, 1, 1)
            layout.addWidget(label(item.mnemonic), row, 1, 1, 1)

            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), 2, 1, 1)
            before_checkbox = SourcedCheckBox(self._data_source, DataSource.DataType.BEFORE, item.mnemonic)
            layout.addWidget(before_checkbox, row, 3, 1, 1)
            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), 4, 1, 1)

            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), 5, 1, 1)
            during_checkbox = SourcedCheckBox(self._data_source, DataSource.DataType.DETECTORS, item.mnemonic)
            layout.addWidget(during_checkbox, row, 6, 1, 1)
            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), 7, 1, 1)

            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), 8, 1, 1)
            after_checkbox = SourcedCheckBox(self._data_source, DataSource.DataType.AFTER, item.mnemonic)
            layout.addWidget(after_checkbox, row, 9, 1, 1)
            layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed), 10, 1, 1)

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
        app = QApplication(["EMA Device Selector"])

        main_window = DeviceSelectorMainWindow(data_source)
        main_window.setStyleSheet(WINDOW_STYLESHEET)
        main_window.show()

        sys.exit(app.exec())

    p = multiprocessing.Process(target=__main, args=(data_source,))
    p.start()
