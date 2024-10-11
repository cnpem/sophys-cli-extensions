import functools

from .. import render_custom_magics, setup_remote_session_handler, setup_plan_magics

from ..plan_magics import get_plans, ModeOfOperation, PlanInformation, PlanWhitelist
from ..tools_magics import KBLMagics, HTTPMagics, MiscMagics

from ..plan_magics import PlanMV, PlanCount, PlanScan, PlanGridScan, PlanAdaptiveScan
from ..plan_magics import PlanCLI, BPlan

from .input_processor import RedisDataSource, input_processor


class Plan1DScan(PlanCLI):
    absolute: bool

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("motor", nargs=1, type=str)
        _a.add_argument("start", type=float)
        _a.add_argument("stop", type=float)
        _a.add_argument("num", type=int)
        _a.add_argument("exposure_time", type=float, nargs='?', default=None)

        return _a

    def _create_plan(self, parsed_namespace, local_ns):
        detector = self.get_real_devices_if_needed(parsed_namespace.detectors, local_ns)
        motor = self.get_real_devices_if_needed(parsed_namespace.motor, local_ns)[0]
        start = parsed_namespace.start
        stop = parsed_namespace.stop
        num = parsed_namespace.num
        exp_time = parsed_namespace.exposure_time
        md = self.parse_md(parsed_namespace)

        if self._mode_of_operation == ModeOfOperation.Local:
            return functools.partial(self._plan, detector, motor, start, stop, num, exp_time, md=md, absolute=self.absolute)
        if self._mode_of_operation == ModeOfOperation.Remote:
            return BPlan(self._plan_name, detector, motor, start, stop, num, exp_time, md=md, absolute=self.absolute)


class PlanAbs1DScan(Plan1DScan):
    absolute = True


class PlanRel1DScan(Plan1DScan):
    absolute = False


PLAN_WHITELIST = PlanWhitelist([
    PlanInformation("mv", "mov", PlanMV, has_detectors=False),
    PlanInformation("count", "count", PlanCount),
    PlanInformation("scan", "scan", PlanScan),
    PlanInformation("grid_scan", "grid_scan", PlanGridScan),
    PlanInformation("adaptive_scan", "adaptive_scan", PlanAdaptiveScan),
    PlanInformation("scan1d", "ascan", PlanAbs1DScan),
    PlanInformation("scan1d", "rscan", PlanRel1DScan),
])


def setup_input_transformer(ipython):
    data_source = RedisDataSource("***REMOVED***", ***REMOVED***)
    proc = functools.partial(input_processor, plan_whitelist=PLAN_WHITELIST, data_source=data_source)
    ipython.input_transformers_cleanup.append(proc)


def load_ipython_extension(ipython):
    local_mode = ipython.user_ns.get("LOCAL_MODE", False)
    mode_of_op = ModeOfOperation.Local if local_mode else ModeOfOperation.Remote

    setup_plan_magics(ipython, "ema", PLAN_WHITELIST, mode_of_op)
    ipython.register_magics(MiscMagics)
    ipython.register_magics(KBLMagics)

    if not local_mode:
        ipython.register_magics(HTTPMagics)
        ipython.magics_manager.registry["HTTPMagics"].plan_whitelist = PLAN_WHITELIST

    print("\n".join(render_custom_magics(ipython)))

    if not local_mode:
        setup_remote_session_handler(ipython, "http://***REMOVED***:***REMOVED***")
    else:
        ipython.push({"P": set(i[0].user_name for i in get_plans("ema", PLAN_WHITELIST))})

    setup_input_transformer(ipython)


def unload_ipython_extension(ipython):
    pass

