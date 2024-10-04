from .. import render_custom_magics, setup_remote_session_handler, setup_plan_magics

from ..plan_magics import get_plans, ModeOfOperation, PlanInformation
from ..tools_magics import KBLMagics, HTTPMagics, MiscMagics

from ..plan_magics import PlanMV, PlanCount, PlanScan, PlanGridScan, PlanAdaptiveScan


PLAN_WHITELIST = {
    "mv": PlanInformation("mov", PlanMV),
    "count": PlanInformation("count", PlanCount),
    "scan": PlanInformation("scan", PlanScan),
    "grid_scan": PlanInformation("grid_scan", PlanGridScan),
    "adaptive_scan": PlanInformation("adaptive_scan", PlanAdaptiveScan),
}


def load_ipython_extension(ipython):
    local_mode = ipython.user_ns.get("LOCAL_MODE", False)
    mode_of_op = ModeOfOperation.Local if local_mode else ModeOfOperation.Remote

    setup_plan_magics(ipython, "common", PLAN_WHITELIST, mode_of_op)
    ipython.register_magics(MiscMagics)
    ipython.register_magics(KBLMagics)

    if not local_mode:
        ipython.register_magics(HTTPMagics)
        ipython.magics_manager.registry["HTTPMagics"].plan_whitelist = PLAN_WHITELIST

    print("\n".join(render_custom_magics(ipython)))

    if not local_mode:
        setup_remote_session_handler(ipython, "http://***REMOVED***:***REMOVED***")
    else:
        ipython.push({"P": set(i[0] for i in get_plans("common", PLAN_WHITELIST))})


def unload_ipython_extension(ipython):
    pass
