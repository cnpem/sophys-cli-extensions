import functools
import logging
import os

from IPython.core.magic import Magics, magics_class, line_magic, needs_local_scope

from sophys.cli.core.data_source import LocalInMemoryDataSource, RedisDataSource
from sophys.cli.core.persistent_metadata import PersistentMetadata

from sophys.cli.core.magics import render_custom_magics, setup_remote_session_handler, setup_plan_magics, NamespaceKeys, get_from_namespace, add_to_namespace, get_color

from sophys.cli.core.magics.plan_magics import get_plans, ModeOfOperation, PlanInformation, PlanWhitelist
from sophys.cli.core.magics.tools_magics import KBLMagics, HTTPMagics, MiscMagics

from sophys.cli.core.magics.plan_magics import PlanMV, PlanReadMany, PlanCount, PlanScan, PlanAdaptiveScan
from sophys.cli.core.magics.plan_magics import PlanCLI, BPlan

from .device_selector import spawnDeviceSelector
from .input_processor import input_processor
from .ipython_config import setup_prompt


@magics_class
class DeviceSelectorMagics(Magics):
    @line_magic
    @needs_local_scope
    def eds(self, line, local_ns):
        data_source = get_from_namespace(NamespaceKeys.REMOTE_DATA_SOURCE, ns=local_ns)
        if data_source is None:
            logging.error("Could not run device selector. No data source variable in the namespace.")

        spawnDeviceSelector(data_source)

    @staticmethod
    def description():
        tools = []
        tools.append(("eds", "Open the EMA Device Selector", get_color("\x1b[38;5;82m")))
        return tools


@magics_class
class UtilityMagics(Magics):
    @line_magic
    @needs_local_scope
    def newfile(self, line, local_ns):
        persistent_metadata = get_from_namespace(NamespaceKeys.PERSISTENT_METADATA, ns=local_ns)
        persistent_metadata.add_entry("metadata_save_file_identifier", line)
        print(f"Metadata file configured to '{line}'.")

    @line_magic
    @needs_local_scope
    def disable_auto_increment(self, line, local_ns):
        persistent_metadata = get_from_namespace(NamespaceKeys.PERSISTENT_METADATA, ns=local_ns)

        key = "metadata_save_increment_disable"
        if persistent_metadata.get_entry(key) is None:
            persistent_metadata.add_entry(key, "Disabled")
            print("Disabled auto-increment of metadata file name.")
        else:
            persistent_metadata.remove_entry(key)
            print("Enabled auto-increment of metadata file name.")

    @staticmethod
    def description():
        tools = []
        tools.append(("newfile", "Configure the local metadata so metadata files are created with the specified name.", get_color("\x1b[38;5;218m")))
        tools.append(("disable_auto_increment", "Toggle usage of auto-increment in the metadata file name.", get_color("\x1b[38;5;218m")))
        return tools


def populate_mnemonics(*devices, md):
    from sophys.ema.utils import mnemonic_to_pv_name

    res = dict()

    def inner(mnemonic, pv_name):
        if pv_name is None:
            logging.warning("No PV name found for mnemonic '%s'.", mnemonic)
        else:
            res[mnemonic] = pv_name

    for d in devices:
        inner(d, mnemonic_to_pv_name(d))

    for d in md.get("READ_BEFORE", "").split(','):
        if len(d) > 0:
            inner(d, mnemonic_to_pv_name(d))
    for d in md.get("READ_AFTER", "").split(','):
        if len(d) > 0:
            inner(d, mnemonic_to_pv_name(d))

    md["MNEMONICS"] = ",".join(f"{mnemonic}={pv_name}" for mnemonic, pv_name in res.items())
    return md


def do_spec_files(*devices, md):
    md["metadata_save_file_format"] = "SPEC"
    return md


class Plan1DScan(PlanCLI):
    absolute: bool

    def _usage(self):
        return "%(prog)s motor start stop num [exposure_time] [--hdf_file_path] [--hdf_file_name] [--md key=value key=value ...]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("motor", nargs=1, type=str, help="Mnemonic of a motor to move.")
        _a.add_argument("start", type=float, help="Start position, in the motor's EGU.")
        _a.add_argument("stop", type=float, help="End position, in the motor's EGU.")
        _a.add_argument("num", type=int, help="Number of points between the start and end positions.")
        _a.add_argument("exposure_time", type=float, nargs='?', default=None, help="Per-point exposure time of the detector. Defaults to using the previously defined exposure time on the IOC.")
        _a.add_argument("--hdf_file_name", type=str, nargs='?', default=None, help="Save file name for the data HDF5 file generated (if using an AreaDetector). Defaults to 'ascan_hour_minute_second_scanid.h5'.")
        _a.add_argument("--hdf_file_path", type=str, nargs='?', default=None, help="Save path for the data HDF5 file generated (if using an AreaDetector). Defaults to CWD.")

        return _a

    def _create_plan(self, parsed_namespace, local_ns):
        detector = self.get_real_devices_if_needed(parsed_namespace.detectors, local_ns)
        motor = self.get_real_devices_if_needed(parsed_namespace.motor, local_ns)[0]
        start = parsed_namespace.start
        stop = parsed_namespace.stop
        num = parsed_namespace.num
        exp_time = parsed_namespace.exposure_time

        md = self.parse_md(*parsed_namespace.detectors, parsed_namespace.motor[0], ns=parsed_namespace)

        template = parsed_namespace.hdf_file_name or "ascan_%H_%M_%S"
        from datetime import datetime
        hdf_file_name = datetime.now().strftime(template)

        hdf_file_path = parsed_namespace.hdf_file_path
        if hdf_file_path is None:
            hdf_file_path = os.getcwd()

        if "metadata_save_file_location" not in md:
            md["metadata_save_file_location"] = hdf_file_path

        if self._mode_of_operation == ModeOfOperation.Local:
            return functools.partial(self._plan, detector, motor, start, stop, num, exp_time, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, absolute=self.absolute)
        if self._mode_of_operation == ModeOfOperation.Remote:
            return BPlan(self._plan_name, detector, motor, start, stop, num, exp_time, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, absolute=self.absolute)


class PlanGridScan(PlanCLI):
    def _usage(self):
        return "%(prog)s motor start stop num motor start stop num [motor start stop num ...] [exposure_time] [-s/--snake] [--hdf_file_path] [--hdf_file_name] [--md key=value key=value ...]"

    def _description(self):
        return super()._description() + """

Example usages:

grid_scan ms2l 0.49 0.494 3 ms2r 0.488 0.49 3
    Make a 2D scan over 3 points on the 'ms2l' motor, from point 0.49 to point 0.494, in absolute coordinates,
    and 3 points on the 'ms2r' motor, from point 0.488 to point 0.49, without snaking, with the 'ms2l' axis changing the slowest:

                        |--------------------------------------|
              0.490     |-----x----->------x------>-----x------|
                        |------------------<-------------------|
              0.492     |-----x----->------x------>-----x------|
                        |------------------<-------------------|
              0.494     |-----x----->------x------>-----x------|
                        |--------------------------------------|
                           0.4880       0.4890       0.4900
    ms2l position (abs)           ms2r position (abs)

    The exposure time used is the one set before the scan on the IOC.

grid_scan ms2r 0.488 0.49 3 ms2l 0.49 0.494 3 0.1 -s
    Make a 2D scan over 3 points on the 'ms2r' motor, from point 0.488 to point 0.49, in absolute coordinates,
    and 3 points on the 'ms2l' motor, from point 0.49 to point 0.494, with snaking, with the 'ms2r' axis changing
    the slowest, and per-point exposure time equal to 0.1 seconds:

                        |--------------------------------|
              0.490     |-----x---------x---->----x------|
                        |-----|---------|---------|------|
              0.492     |-----x---------x---------x------|
                        |-----|---------|---------|------|
              0.494     |-----x---->----x---------x------|
                        |--------------------------------|
                           0.4880    0.4890    0.4900
    ms2l position (abs)        ms2r position (abs)

"""

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("first_motor", nargs=1, type=str, help="Mnemonic of the motor on the slowest axis to move.")
        _a.add_argument("first_start", type=float, help="Start position of the first motor, in the motor's EGU.")
        _a.add_argument("first_stop", type=float, help="End position of the first motor, in the motor's EGU.")
        _a.add_argument("first_num", type=int, help="Number of points between the start and end positions of the first motor.")
        _a.add_argument("second_motor", nargs=1, type=str, help="Mnemonic of the motor on the second slowest axis to move.")
        _a.add_argument("second_start", type=float, help="Start position of the second motor, in the motor's EGU.")
        _a.add_argument("second_stop", type=float, help="End position of the second motor, in the motor's EGU.")
        _a.add_argument("second_num", type=int, help="Number of points between the start and end positions of the second motor.")
        _a.add_argument("exposure_time", type=float, nargs='?', default=None, help="Per-point exposure time of the detector. Defaults to using the previously defined exposure time on the IOC.")
        _a.add_argument("-s", "--snake", action="store_true", help="Whether to snake axes or not. The default behavior is to not snake.")
        _a.add_argument("--hdf_file_name", type=str, nargs='?', default=None, help="Save file name for the data HDF5 file generated (if using an AreaDetector). Defaults to 'ascan_hour_minute_second_scanid.h5'.")
        _a.add_argument("--hdf_file_path", type=str, nargs='?', default=None, help="Save path for the data HDF5 file generated (if using an AreaDetector). Defaults to CWD.")

        return _a

    def _create_plan(self, parsed_namespace, local_ns):
        detector = self.get_real_devices_if_needed(parsed_namespace.detectors, local_ns)
        args = [
            parsed_namespace.first_motor,
            parsed_namespace.first_start,
            parsed_namespace.first_stop,
            parsed_namespace.first_num,
            parsed_namespace.second_motor,
            parsed_namespace.second_start,
            parsed_namespace.second_stop,
            parsed_namespace.second_num,
        ]
        args, _, motor_names = self.parse_varargs(args, local_ns=local_ns)

        exp_time = parsed_namespace.exposure_time

        md = self.parse_md(*parsed_namespace.detectors, *motor_names, ns=parsed_namespace)

        template = parsed_namespace.hdf_file_name or "gridscan_%H_%M_%S"
        from datetime import datetime
        hdf_file_name = datetime.now().strftime(template)

        hdf_file_path = parsed_namespace.hdf_file_path
        if hdf_file_path is None:
            hdf_file_path = os.getcwd()

        if "metadata_save_file_location" not in md:
            md["metadata_save_file_location"] = hdf_file_path

        if self._mode_of_operation == ModeOfOperation.Local:
            return functools.partial(self._plan, detector, args, exp_time, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path)
        if self._mode_of_operation == ModeOfOperation.Remote:
            return BPlan(self._plan_name, detector, args, exp_time, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path)


class PlanMotorOrigin(PlanCLI):
    def _usage(self):
        return "%(prog)s motor [position] [--md key=value key=value ...]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("motor", nargs=1, type=str, help="Mnemonic of a motor to set the origin of.")
        _a.add_argument("position", type=float, help="Position of the motor to set as origin. Default: current position.", default=None, nargs='?')

        return _a

    def _create_plan(self, parsed_namespace, local_ns):
        motor = self.get_real_devices_if_needed(parsed_namespace.motor, local_ns)[0]
        position = parsed_namespace.position

        md = self.parse_md(parsed_namespace.motor[0], ns=parsed_namespace)

        if self._mode_of_operation == ModeOfOperation.Local:
            return functools.partial(self._plan, motor, position, md=md)
        if self._mode_of_operation == ModeOfOperation.Remote:
            return BPlan(self._plan_name, motor, position, md=md)


class PlanAbs1DScan(Plan1DScan):
    absolute = True

    def _description(self):
        return super()._description() + """

Example usages:

ascan ms2r 0.488 0.49 6
    Make a 1D scan over 6 points on the 'ms2r' motor, from point 0.488 to point 0.49,
    in absolute coordinates:

    | scan point | scan point | scan point | scan point | scan point | scan point |
    |-----x------------x------------x------------x------------x------------x------|
       0.4880       0.4882       0.4884       0.4886       0.4888       0.4900
                                 ms2r position (abs)

    The exposure time used is the one set before the scan on the IOC.

ascan wst 0.0 0.4 5 0.1
    Make a 1D scan over 5 points on the 'wst' motor, from point 0.0 to point 0.4,
    in absolute coordinates, with exposure time per-point equal to 0.1 seconds:

    | scan point | scan point | scan point | scan point | scan point |
    |-----x------------x------------x------------x------------x------|
         0.0          0.1          0.2          0.3          0.4
                           wst position (abs)
"""


class PlanRel1DScan(Plan1DScan):
    absolute = False

    def _description(self):
        return super()._description() + """

Example usages:

rscan ms2r 0.488 0.49 6
    Make a 1D scan over 6 points on the 'ms2r' motor, from point 0.488 to point 0.49,
    relative to the current position:

    | scan point | scan point | scan point | scan point | scan point | scan point |
    |-----x------------x------------x------------x------------x------------x------|
       0.4880       0.4882       0.4884       0.4886       0.4888       0.4900
                                 ms2r position (rel)

    The exposure time used is the one set before the scan on the IOC.

rscan wst 0.0 0.4 5 0.1
    Make a 1D scan over 5 points on the 'wst' motor, from point 0.0 to point 0.4,
    relative to the current position, with exposure time per-point equal to 0.1 seconds:

    | scan point | scan point | scan point | scan point | scan point |
    |-----x------------x------------x------------x------------x------|
         0.0          0.1          0.2          0.3          0.4
                            wst position (rel)
"""


whitelisted_plan_list = [
    PlanInformation("mov", "mov", PlanMV, has_detectors=False),
    PlanInformation("rmov", "rmov", PlanMV, has_detectors=False),
    PlanInformation("read_many", "read", PlanReadMany, has_detectors=False),
    PlanInformation("count", "count", PlanCount),
    PlanInformation("scan", "scan", PlanScan),
    PlanInformation("grid_scan", "grid_scan", PlanGridScan),
    PlanInformation("adaptive_scan", "adaptive_scan", PlanAdaptiveScan),
    PlanInformation("scan1d", "ascan", PlanAbs1DScan),
    PlanInformation("scan1d", "rscan", PlanRel1DScan),
    PlanInformation("motor_set_origin", "mset", PlanMotorOrigin),
]

whitelisted_plan_md_preprocessors = [
    populate_mnemonics,
    do_spec_files,
]


def setup_input_transformer(ipython, plan_whitelist):
    remote_data_source = RedisDataSource("***REMOVED***", ***REMOVED***)
    add_to_namespace(NamespaceKeys.REMOTE_DATA_SOURCE, remote_data_source, ipython=ipython)

    proc = functools.partial(input_processor, plan_whitelist=plan_whitelist, data_source=remote_data_source)
    ipython.input_transformers_cleanup.append(proc)

    ipython.register_magics(DeviceSelectorMagics)


def setup_persistent_metadata(ipython):
    local_data_source = LocalInMemoryDataSource()
    add_to_namespace(NamespaceKeys.LOCAL_DATA_SOURCE, local_data_source, ipython=ipython)

    persistent_metadata = PersistentMetadata(local_data_source)
    add_to_namespace(NamespaceKeys.PERSISTENT_METADATA, persistent_metadata, ipython=ipython)

    return persistent_metadata.populate_permanent_md


def after_plan_submission_callback(ipython):
    ipython.run_line_magic("wait_for_idle", "")


def load_ipython_extension(ipython):
    local_mode = ipython.user_ns.get("LOCAL_MODE", False)
    mode_of_op = ModeOfOperation.Local if local_mode else ModeOfOperation.Remote

    post_submission_callbacks = []
    if mode_of_op == ModeOfOperation.Remote:
        post_submission_callbacks.append(functools.partial(after_plan_submission_callback, ipython))

    permanent_md_preprocessor = setup_persistent_metadata(ipython)
    whitelisted_plan_md_preprocessors.append(permanent_md_preprocessor)

    plan_whitelist = PlanWhitelist(*whitelisted_plan_list, pre_processing_md=whitelisted_plan_md_preprocessors)

    setup_plan_magics(ipython, "ema", plan_whitelist, mode_of_op, post_submission_callbacks)
    ipython.register_magics(MiscMagics)
    ipython.register_magics(UtilityMagics)
    ipython.register_magics(KBLMagics)
    setup_input_transformer(ipython, plan_whitelist)

    if not local_mode:
        ipython.register_magics(HTTPMagics)
        ipython.magics_manager.registry["HTTPMagics"].plan_whitelist = plan_whitelist

    add_to_namespace(NamespaceKeys.BLACKLISTED_DESCRIPTIONS, {"add_md", "remove_md", "disable_auto_increment"})
    print("\n".join(render_custom_magics(ipython)))

    if not local_mode:
        setup_remote_session_handler(ipython, "http://***REMOVED***:***REMOVED***")
    else:
        plans = set(i[0].user_name for i in get_plans("ema", plan_whitelist))
        add_to_namespace(NamespaceKeys.PLANS, plans, ipython=ipython)

    setup_prompt(ipython)


def unload_ipython_extension(ipython):
    pass

