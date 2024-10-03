import functools

from .. import render_custom_magics

from ..plan_magics import get_plans, register_magic_for_plan, RealMagics, ModeOfOperation
from ..tools_magics import KBLMagics, HTTPMagics, MiscMagics

from ..plan_magics import PlanMV, PlanCount, PlanScan, PlanGridScan, PlanAdaptiveScan

from ...http_utils import RemoteSessionHandler

from .input_processor import LocalDataSource, input_processor


PLAN_WHITELIST = {
    "mv": ("mov", PlanMV),
    "count": ("count", PlanCount),
    "scan": ("scan", PlanScan),
    "grid_scan": ("grid_scan", PlanGridScan),
    "adaptive_scan": ("adaptive_scan", PlanAdaptiveScan),
}


def load_ipython_extension(ipython):
    local_mode = ipython.user_ns.get("LOCAL_MODE", False)
    mode_of_op = ModeOfOperation.Local if local_mode else ModeOfOperation.Remote

    for plan_name, plan in get_plans("ema", PLAN_WHITELIST):
        register_magic_for_plan(plan_name, plan, PLAN_WHITELIST, mode_of_op)
    ipython.register_magics(RealMagics)

    ipython.register_magics(MiscMagics)
    ipython.register_magics(KBLMagics)

    if not local_mode:
        ipython.register_magics(HTTPMagics)
        ipython.magics_manager.registry["HTTPMagics"].plan_whitelist = PLAN_WHITELIST

    print("\n".join(render_custom_magics(ipython)))

    if not local_mode:
        _remote_session_handler = RemoteSessionHandler("http://***REMOVED***:***REMOVED***")
        _remote_session_handler.start()
        _remote_session_handler.ask_for_authentication()

        ipython.push({"_remote_session_handler": _remote_session_handler})

        ipython.run_line_magic("reload_devices", "")
        ipython.run_line_magic("reload_plans", "")
    else:
        ipython.push({"P": set(i[0] for i in get_plans("ema", PLAN_WHITELIST))})

    if local_mode:
        data_path = "ema_sophys_cli_config.csv"

        try:
            data_source = LocalDataSource(data_path)
        except FileNotFoundError:
            print(f"Failed to load file at '{data_path}'. No extra input processing will be done.")
        else:
            proc = functools.partial(input_processor, plan_whitelist=PLAN_WHITELIST, data_source=data_source)
            ipython.input_transformers_cleanup.append(proc)


def unload_ipython_extension(ipython):
    pass

