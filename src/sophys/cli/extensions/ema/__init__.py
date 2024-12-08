import functools
import logging
import os

from IPython.core.magic import Magics, magics_class, line_magic, needs_local_scope

from bluesky_queueserver_api.comm_base import RequestFailedError

from sophys.cli.core import ENVVARS, get_cli_envvar

from sophys.cli.core.data_source import LocalInMemoryDataSource, RedisDataSource
from sophys.cli.core.persistent_metadata import PersistentMetadata

from sophys.cli.core.magics import render_custom_magics, setup_remote_session_handler, setup_plan_magics, NamespaceKeys, get_from_namespace, add_to_namespace, get_color

from sophys.cli.core.magics.plan_magics import get_plans, ModeOfOperation, PlanInformation, PlanWhitelist, ExceptionHandlerReturnValue
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
        if mnemonic.startswith("sim_"):
            res[mnemonic] = mnemonic
        elif pv_name is None:
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


class PlanNDScan(PlanCLI):
    absolute: bool

    def _usage(self):
        return "%(prog)s motor start stop [motor start stop ...] num [exposure_time] [--hdf_file_path] [--hdf_file_name] [--md key=value key=value ...]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("args", nargs='+', type=str, help="Motor informations, in order (mnemonic start_position end_position)")
        # NOTE: These two are not used in parsing, they're only here for documentation. Their values are taken from args instead.
        _a.add_argument("num", type=int, nargs='?', default=None, help="Number of points between the start and end positions.")
        _a.add_argument("exposure_time", type=float, nargs='?', default=None, help="Per-point exposure time of the detector. Defaults to using the previously defined exposure time on the IOC.")

        _a.add_argument("--hdf_file_name", type=str, nargs='?', default=None, help="Save file name for the data HDF5 file generated (if using an AreaDetector). Defaults to 'ascan_hour_minute_second_scanid.h5'.")
        _a.add_argument("--hdf_file_path", type=str, nargs='?', default=None, help="Save path for the data HDF5 file generated (if using an AreaDetector). Defaults to CWD.")

        return _a

    def _create_plan(self, parsed_namespace, local_ns):
        detector = self.get_real_devices_if_needed(parsed_namespace.detectors, local_ns)

        nargs = len(parsed_namespace.args)
        assert (nargs >= 4) or (nargs % 3 == 0), "Not enough arguments have been passed."
        if nargs % 3 == 1:  # motors + num
            _args = parsed_namespace.args
            exp_time = None
        else:  # motors + num + exp time
            _args = parsed_namespace.args[:-1]
            exp_time = float(parsed_namespace.args[-1])

        args, num, motors = self.parse_varargs(_args, local_ns, with_final_num=True)

        md = self.parse_md(*parsed_namespace.detectors, *motors, ns=parsed_namespace)

        template = parsed_namespace.hdf_file_name or "ascan_%H_%M_%S"
        from datetime import datetime
        hdf_file_name = datetime.now().strftime(template)

        hdf_file_path = parsed_namespace.hdf_file_path
        if hdf_file_path is None:
            hdf_file_path = os.getcwd()

        if "metadata_save_file_location" not in md:
            md["metadata_save_file_location"] = hdf_file_path

        if self._mode_of_operation == ModeOfOperation.Local:
            return functools.partial(self._plan, detector, *args, number_of_points=num, exposure_time=exp_time, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, absolute=self.absolute)
        if self._mode_of_operation == ModeOfOperation.Remote:
            return BPlan(self._plan_name, detector, *args, number_of_points=num, exposure_time=exp_time, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, absolute=self.absolute)


class PlanGridScan(PlanCLI):
    absolute: bool

    def _usage(self):
        return "%(prog)s motor start stop num motor start stop num [motor start stop num ...] [exposure_time] [-s/--snake] [--hdf_file_path] [--hdf_file_name] [--md key=value key=value ...]"

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
            parsed_namespace.first_motor[0],
            parsed_namespace.first_start,
            parsed_namespace.first_stop,
            parsed_namespace.first_num,
            parsed_namespace.second_motor[0],
            parsed_namespace.second_start,
            parsed_namespace.second_stop,
            parsed_namespace.second_num,
        ]
        args, _, motor_names = self.parse_varargs(args, local_ns=local_ns)

        exp_time = parsed_namespace.exposure_time
        snake = parsed_namespace.snake

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
            return functools.partial(self._plan, detector, *args, exposure_time=exp_time, snake_axes=snake, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, absolute=self.absolute)
        if self._mode_of_operation == ModeOfOperation.Remote:
            return BPlan(self._plan_name, detector, *args, exposure_time=exp_time, snake_axes=snake, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, absolute=self.absolute)


class PlanGridScanWithJitter(PlanCLI):
    def _usage(self):
        return "%(prog)s motor start stop num motor start stop num [motor start stop num ...] [exposure_time] [-s/--snake] [--hdf_file_path] [--hdf_file_name] [--md key=value key=value ...]"

    def _description(self):
        return super()._description() + """

Example usages:

jittermap ms2l 0.49 0.494 3 ms2r 0.488 0.49 3
    Make a 2D scan over 3 points on the 'ms2l' motor, from point 0.49 to point 0.494, in absolute coordinates,
    and 3 points on the 'ms2r' motor, from point 0.488 to point 0.49, without snaking, with the 'ms2l' axis changing the slowest:

                        |--------------------------------x-----|
              0.490     |------x---->-----x------->------------|
                        |------------------<-------------------|
              0.492     |----------->------x------>-----x------|
                        |----x------------x<-------------------|
              0.494     |------x---->------------->------------|
                        |-------------------------------x------|
                           0.4880       0.4890       0.4900
    ms2l position (abs)           ms2r position (abs)

    The exposure time used is the one set before the scan on the IOC.

jittermap ms2r 0.488 0.49 3 ms2l 0.49 0.494 3 0.1 -s
    Make a 2D scan over 3 points on the 'ms2r' motor, from point 0.488 to point 0.49, in absolute coordinates,
    and 3 points on the 'ms2l' motor, from point 0.49 to point 0.494, with snaking, with the 'ms2r' axis changing
    the slowest, and per-point exposure time equal to 0.1 seconds:

                        |--------------------------------|
              0.490     |-----x-------------->--x--------|
                        |-----|--------x|---------|x-----|
              0.492     |------x--------x----------------|
                        |-----|---------|---------|------|
              0.494     |---------->---x---------x-------|
                        |-----x--------------------------|
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
            parsed_namespace.first_motor[0],
            parsed_namespace.first_start,
            parsed_namespace.first_stop,
            parsed_namespace.first_num,
            parsed_namespace.second_motor[0],
            parsed_namespace.second_start,
            parsed_namespace.second_stop,
            parsed_namespace.second_num,
        ]
        args, _, motor_names = self.parse_varargs(args, local_ns=local_ns)

        exp_time = parsed_namespace.exposure_time
        snake = parsed_namespace.snake

        md = self.parse_md(*parsed_namespace.detectors, *motor_names, ns=parsed_namespace)

        template = parsed_namespace.hdf_file_name or "jittermap_%H_%M_%S"
        from datetime import datetime
        hdf_file_name = datetime.now().strftime(template)

        hdf_file_path = parsed_namespace.hdf_file_path
        if hdf_file_path is None:
            hdf_file_path = os.getcwd()

        if "metadata_save_file_location" not in md:
            md["metadata_save_file_location"] = hdf_file_path

        if self._mode_of_operation == ModeOfOperation.Local:
            return functools.partial(self._plan, detector, *args, exposure_time=exp_time, snake_axes=snake, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path)
        if self._mode_of_operation == ModeOfOperation.Remote:
            return BPlan(self._plan_name, detector, *args, exposure_time=exp_time, snake_axes=snake, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path)


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


class PlanAbsNDScan(PlanNDScan):
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

ascan ms2r 0.488 0.49 wst 0.0 0.4 5 0.1
    Make a 2D scan over 5 points on the 'ms2r' and 'wst' motors, in absolute coordinates,
    with exposure time per-point equal to 0.1 seconds, and moving at the same time:

    |                     ms2r position (abs)                        |
    |  0.4880       0.4882       0.4884       0.4886       0.4888    |
    |-----x------------x------------x------------x------------x------|
    |    0.0          0.1          0.2          0.3          0.4     |
    |                      wst position (abs)                        |
"""


class PlanRelNDScan(PlanNDScan):
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

rscan ms2r 0.488 0.49 wst 0.0 0.4 5 0.1
    Make a 2D scan over 5 points on the 'ms2r' and 'wst' motors, relative to the current position,
    with exposure time per-point equal to 0.1 seconds, and moving at the same time:

    |                     ms2r position (rel)                        |
    |  0.4880       0.4882       0.4884       0.4886       0.4888    |
    |-----x------------x------------x------------x------------x------|
    |    0.0          0.1          0.2          0.3          0.4     |
    |                      wst position (rel)                        |
"""


class PlanAbsGridScan(PlanGridScan):
    absolute = True

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


class PlanRelGridScan(PlanGridScan):
    absolute = False

    def _description(self):
        return super()._description() + """

Example usages:

rel_grid_scan ms2l 0.49 0.494 3 ms2r 0.488 0.49 3
    Make a 2D scan over 3 points on the 'ms2l' motor, from point 0.49 to point 0.494, relative to its current position,
    and 3 points on the 'ms2r' motor, from point 0.488 to point 0.49, without snaking, with the 'ms2l' axis changing the slowest:

                        |--------------------------------------|
              0.490     |-----x----->------x------>-----x------|
                        |------------------<-------------------|
              0.492     |-----x----->------x------>-----x------|
                        |------------------<-------------------|
              0.494     |-----x----->------x------>-----x------|
                        |--------------------------------------|
                           0.4880       0.4890       0.4900
    ms2l position (rel)           ms2r position (rel)

    The exposure time used is the one set before the scan on the IOC.

rel_grid_scan ms2r 0.488 0.49 3 ms2l 0.49 0.494 3 0.1 -s
    Make a 2D scan over 3 points on the 'ms2r' motor, from point 0.488 to point 0.49, relative to its current position,
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
    ms2l position (rel)        ms2r position (rel)

"""


whitelisted_plan_list = [
    PlanInformation("mov", "mov", PlanMV, has_detectors=False),
    PlanInformation("rmov", "rmov", PlanMV, has_detectors=False),
    PlanInformation("read_many", "read", PlanReadMany, has_detectors=False),
    PlanInformation("count", "count", PlanCount),
    PlanInformation("grid_scan", "grid_scan", PlanAbsGridScan),
    PlanInformation("grid_scan", "rel_grid_scan", PlanRelGridScan),
    PlanInformation("scanNd", "ascan", PlanAbsNDScan),
    PlanInformation("scanNd", "rscan", PlanRelNDScan),
    PlanInformation("motor_set_origin", "mset", PlanMotorOrigin),
    PlanInformation("grid_scan_with_jitter", "jittermap", PlanGridScanWithJitter),
]

whitelisted_plan_md_preprocessors = [
    populate_mnemonics,
    do_spec_files,
]


def setup_input_transformer(ipython, plan_whitelist, test_mode: bool = False):
    if test_mode:
        remote_data_source = LocalInMemoryDataSource()
    else:
        host = get_cli_envvar(ENVVARS.REDIS_HOST_ENVVAR)
        port = get_cli_envvar(ENVVARS.REDIS_PORT_ENVVAR)
        remote_data_source = RedisDataSource(host, port)

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
    return ipython.run_line_magic("wait_for_idle", "")


def after_plan_request_failed_callback(exc: RequestFailedError, local_ns) -> ExceptionHandlerReturnValue:
    print()
    print("Could not run the provided plan because the server is already running something else.")
    print("This could be due to either:")
    print("  - Another user is executing a plan right now;")
    print("  - The server is stuck in an infinite loop due to some bogus circunstance.")
    print()
    print("Restarting the server would solve the latter situation.")
    print("Checking if a pause is pending...")
    print()

    handler = get_from_namespace(NamespaceKeys.REMOTE_SESSION_HANDLER, ns=local_ns)
    manager = handler.get_authorized_manager()

    # TODO: Add error handling to here.
    res = manager.status()
    if res["pause_pending"]:
        print("A pause is pending, so it's likely the second circunstance.")
        print("We'll destroy the environment and create another one.")
        print()

        HTTPMagics._reload_environment(manager, True, logging.getLogger("sophys_cli.tools"))

        print()
        print("Environment recreated. Will retry to run the provided plan.")
        print()

        return ExceptionHandlerReturnValue.RETRY

    print("A pause is not pending, so it's likely someone else is using the server right now.")
    print("Use the 'query_state' magic for more information.")
    print()

    return ExceptionHandlerReturnValue.EXIT_QUIET


def sophys_state_query() -> str:
    import subprocess

    render = []

    autosave_host = get_cli_envvar(ENVVARS.AUTOSAVE_HOST_ENVVAR)
    autosave_port = get_cli_envvar(ENVVARS.AUTOSAVE_PORT_ENVVAR)
    redis_host = get_cli_envvar(ENVVARS.REDIS_HOST_ENVVAR)
    redis_port = get_cli_envvar(ENVVARS.REDIS_PORT_ENVVAR)
    http_host = get_cli_envvar(ENVVARS.HTTPSERVER_HOST_ENVVAR)
    http_port = get_cli_envvar(ENVVARS.HTTPSERVER_PORT_ENVVAR)
    kafka_host = get_cli_envvar(ENVVARS.KAFKA_HOST_ENVVAR)
    kafka_port = get_cli_envvar(ENVVARS.KAFKA_PORT_ENVVAR)

    # Hosts
    def ping(addr):
        command = ["ping", "-c", "1", "-w5", addr]
        ret_code = subprocess.run(args=command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
        return "OK" if ret_code == 0 else "TIMEOUT"

    render.append("Hosts:")
    render.append(f"  Autosave: {ping(autosave_host)} ({autosave_host})")
    render.append(f"  Redis: {ping(redis_host)} ({redis_host})")
    render.append(f"  Httpserver: {ping(http_host)} ({http_host})")
    render.append(f"  Kafka: {ping(kafka_host)} ({kafka_host})")

    render.append("")

    # Ports
    def port_open(addr, port):
        command = [f'nmap -p {port} {addr} | grep "{port}" | grep "open"']
        has_nmap = subprocess.run(args=["nmap -V"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if not has_nmap:
            return "'nmap' is not installed on this system."
        ret_code = subprocess.run(args=command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
        return "OK" if ret_code == 0 else "TIMEOUT"

    render.append("Ports:")
    render.append(f"  Autosave: {port_open(autosave_host, autosave_port)} ({autosave_port})")
    render.append(f"  Redis: {port_open(redis_host, redis_port)} ({redis_port})")
    render.append(f"  Httpserver: {port_open(http_host, http_port)} ({http_port})")
    render.append(f"  Kafka: {port_open(kafka_host, kafka_port)} ({kafka_port})")

    return "\n".join(render)


def load_ipython_extension(ipython):
    local_mode = get_from_namespace(NamespaceKeys.LOCAL_MODE, False, ipython)
    test_mode = get_from_namespace(NamespaceKeys.TEST_MODE, False, ipython)

    mode_of_op = ModeOfOperation.Local if local_mode else ModeOfOperation.Remote

    post_submission_callbacks = []
    if mode_of_op == ModeOfOperation.Remote:
        post_submission_callbacks.append(functools.partial(after_plan_submission_callback, ipython))

    exception_handlers = {RequestFailedError: after_plan_request_failed_callback}

    permanent_md_preprocessor = setup_persistent_metadata(ipython)
    whitelisted_plan_md_preprocessors.append(permanent_md_preprocessor)

    plan_whitelist = PlanWhitelist(*whitelisted_plan_list, pre_processing_md=whitelisted_plan_md_preprocessors)

    setup_plan_magics(ipython, "ema", plan_whitelist, mode_of_op, post_submission_callbacks, exception_handlers)
    ipython.register_magics(MiscMagics)
    ipython.register_magics(UtilityMagics)
    ipython.register_magics(KBLMagics)
    setup_input_transformer(ipython, plan_whitelist, test_mode)

    if not local_mode:
        ipython.register_magics(HTTPMagics)
        ipython.magics_manager.registry["HTTPMagics"].plan_whitelist = plan_whitelist
        ipython.magics_manager.registry["HTTPMagics"].additional_state = [sophys_state_query]

    if not test_mode:
        add_to_namespace(NamespaceKeys.BLACKLISTED_DESCRIPTIONS, {"add_md", "remove_md", "disable_auto_increment"})
    print("\n".join(render_custom_magics(ipython)))

    if not local_mode:
        host = get_cli_envvar(ENVVARS.HTTPSERVER_HOST_ENVVAR)
        port = get_cli_envvar(ENVVARS.HTTPSERVER_PORT_ENVVAR)
        setup_remote_session_handler(ipython, f"http://{host}:{port}")
    else:
        plans = set(i[0].user_name for i in get_plans("ema", plan_whitelist))
        add_to_namespace(NamespaceKeys.PLANS, plans, ipython=ipython)

    setup_prompt(ipython)


def unload_ipython_extension(ipython):
    pass

