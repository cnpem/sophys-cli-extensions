import functools
import logging
import os

from IPython.core.magic import Magics, magics_class, line_magic, needs_local_scope

from .. import render_custom_magics, setup_remote_session_handler, setup_plan_magics

from ..plan_magics import get_plans, ModeOfOperation, PlanInformation, PlanWhitelist
from ..tools_magics import KBLMagics, HTTPMagics, MiscMagics

from ..plan_magics import PlanMV, PlanReadMany, PlanCount, PlanScan, PlanGridScan, PlanAdaptiveScan
from ..plan_magics import PlanCLI, BPlan

from .data_source import RedisDataSource
from .device_selector import spawnDeviceSelector
from .input_processor import input_processor
from .ipython_config import setup_prompt


@magics_class
class DeviceSelectorMagics(Magics):
    @line_magic
    @needs_local_scope
    def eds(self, line, local_ns):
        if "__data_source" not in local_ns:
            logging.error("Could not run device selector. No '__data_source' variable in the namespace.")

        spawnDeviceSelector(local_ns["__data_source"])

    @staticmethod
    def description():
        tools = []
        tools.append(("eds", "Open the EMA Device Selector", "\x1b[38;5;82m"))
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
        inner(d, mnemonic_to_pv_name(d))
    for d in md.get("READ_AFTER", "").split(','):
        inner(d, mnemonic_to_pv_name(d))

    md["MNEMONICS"] = ",".join(f"{mnemonic}={pv_name}" for mnemonic, pv_name in res.items())
    return md


def do_spec_files(*devices, md):
    md["metadata_save_file_format"] = "SPEC"
    return md


class Plan1DScan(PlanCLI):
    absolute: bool

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


class PlanAbs1DScan(Plan1DScan):
    absolute = True


class PlanRel1DScan(Plan1DScan):
    absolute = False


PLAN_WHITELIST = PlanWhitelist(
    PlanInformation("mov", "mov", PlanMV, has_detectors=False),
    PlanInformation("read_many", "read", PlanReadMany, has_detectors=False),
    PlanInformation("count", "count", PlanCount),
    PlanInformation("scan", "scan", PlanScan),
    PlanInformation("grid_scan", "grid_scan", PlanGridScan),
    PlanInformation("adaptive_scan", "adaptive_scan", PlanAdaptiveScan),
    PlanInformation("scan1d", "ascan", PlanAbs1DScan),
    PlanInformation("scan1d", "rscan", PlanRel1DScan),
    pre_processing_md=[populate_mnemonics, do_spec_files])


def setup_input_transformer(ipython):
    data_source = RedisDataSource("***REMOVED***", ***REMOVED***)
    ipython.push({"__data_source": data_source})

    proc = functools.partial(input_processor, plan_whitelist=PLAN_WHITELIST, data_source=data_source)
    ipython.input_transformers_cleanup.append(proc)

    ipython.register_magics(DeviceSelectorMagics)


def after_plan_submission_callback(ipython):
    ipython.run_line_magic("wait_for_idle", "")


def load_ipython_extension(ipython):
    local_mode = ipython.user_ns.get("LOCAL_MODE", False)
    mode_of_op = ModeOfOperation.Local if local_mode else ModeOfOperation.Remote

    post_submission_callbacks = []
    if mode_of_op == ModeOfOperation.Remote:
        post_submission_callbacks.append(functools.partial(after_plan_submission_callback, ipython))

    setup_plan_magics(ipython, "ema", PLAN_WHITELIST, mode_of_op, post_submission_callbacks)
    ipython.register_magics(MiscMagics)
    ipython.register_magics(KBLMagics)
    setup_input_transformer(ipython)

    if not local_mode:
        ipython.register_magics(HTTPMagics)
        ipython.magics_manager.registry["HTTPMagics"].plan_whitelist = PLAN_WHITELIST

    print("\n".join(render_custom_magics(ipython)))

    if not local_mode:
        setup_remote_session_handler(ipython, "http://***REMOVED***:***REMOVED***")
    else:
        ipython.push({"P": set(i[0].user_name for i in get_plans("ema", PLAN_WHITELIST))})

    setup_prompt(ipython)


def unload_ipython_extension(ipython):
    pass

