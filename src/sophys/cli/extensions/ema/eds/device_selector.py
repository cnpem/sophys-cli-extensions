import typing

from dataclasses import dataclass
from enum import IntFlag, auto
from pathlib import Path

from qtpy.uic import loadUi
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QMainWindow, QApplication, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy, QTabWidget, QGridLayout, QSpacerItem, QWidget

from sophys.cli.core.data_source import DataSource
from sophys.cli.core.magics import NamespaceKeys, get_from_namespace

from .widgets import CombinedROIConfigurationPushButton, SeparateROIConfigurationPushButton, SourcedCheckBox, SourcedComboBox, label


class DeviceType(IntFlag):
    READABLE = auto()
    SETTABLE = auto()
    DVF = auto()
    OPTICAL_ELEMENTS = auto()
    SIMULATED = auto()


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

    DeviceItem("Interferometer - X", "ifmx", DeviceType.SETTABLE),
    DeviceItem("Interferometer - Z", "ifmz", DeviceType.SETTABLE),

    DeviceItem("IVU Gap", "ivu_gap", DeviceType.OPTICAL_ELEMENTS),
    DeviceItem("DCM Energy", "dcm_energy", DeviceType.OPTICAL_ELEMENTS),
    DeviceItem("DCM Bragg Angle", "dcm_bragg", DeviceType.OPTICAL_ELEMENTS),

    DeviceItem("OEA MVS1", "bvs1", DeviceType.DVF),
    DeviceItem("OEA MVS2", "bvs2", DeviceType.DVF),
    DeviceItem("OEA MVS3", "bvs3", DeviceType.DVF),

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

        self._base_ui = loadUi(str(Path(__file__).parent / "base.ui"))
        device_type_tab_widget: QTabWidget = self._base_ui.device_type_tab_widget

        readable_form = self._base_ui.counters_area.layout()
        settable_form = self._base_ui.generic_area.layout()
        dvf_form = self._base_ui.dvf_area.layout()
        optical_elements_form = self._base_ui.optical_elements_area.layout()
        simulated_form = None

        if in_test_mode:
            simulated_page = QWidget()
            device_type_tab_widget.addTab(simulated_page, "Simulated")
            simulated_form = QGridLayout()
            simulated_page.setLayout(simulated_form)

        self.populateDevices(
            readable_form,
            settable_form,
            dvf_form,
            optical_elements_form,
            simulated_form
        )

        self.main_layout.addWidget(device_type_tab_widget)

        main_counter = self._base_ui.main_counter_area
        self.populateMainCounter(main_counter.layout())

        self.main_layout.addWidget(main_counter)

        main_frame = QFrame()
        main_frame.setStyleSheet(".QFrame { margin: 2px; border: 2px solid #000000; border-radius: 4px; }")
        main_frame.setFrameShape(QFrame.Shape.Box)
        main_frame.setLayout(self.main_layout)

        self.setCentralWidget(main_frame)

    def populateMainCounter(self, main_counter_form: QHBoxLayout):
        lbl = QLabel("Main counter")
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        lbl.setToolTip("The main counter to use. This is primarily used as the target of calculations at the end of some plans.")
        main_counter_form.addWidget(lbl)

        combo_box = SourcedComboBox(self._data_source, in_type=DataSource.DataType.DETECTORS, out_type=DataSource.DataType.MAIN_DETECTOR)
        main_counter_form.addWidget(combo_box)

    def populateDevices(
        self,
        readable_form: QGridLayout,
        settable_form: QGridLayout,
        dvf_form: QGridLayout,
        optical_elements_form: QGridLayout,
        simulated_form: typing.Optional[QGridLayout] = None
    ):
        for form in (readable_form, settable_form, dvf_form, optical_elements_form, simulated_form):
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
            if item.type & DeviceType.DVF:
                add_to_layout(item, dvf_form)
            if item.type & DeviceType.OPTICAL_ELEMENTS:
                add_to_layout(item, optical_elements_form)
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
