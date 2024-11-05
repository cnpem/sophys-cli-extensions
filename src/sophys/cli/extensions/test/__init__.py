from .. import render_custom_magics, setup_remote_session_handler, setup_plan_magics, NamespaceKeys, add_to_namespace

from ..plan_magics import get_plans, ModeOfOperation, PlanInformation, PlanWhitelist
from ..tools_magics import KBLMagics, HTTPMagics, MiscMagics

from ..plan_magics import PlanMV, PlanCount, PlanScan, PlanGridScan, PlanAdaptiveScan


PLAN_WHITELIST = PlanWhitelist([
    PlanInformation("mv", "mov", PlanMV),
    PlanInformation("count", "count", PlanCount),
    PlanInformation("scan", "scan", PlanScan),
    PlanInformation("grid_scan", "grid_scan", PlanGridScan),
    PlanInformation("adaptive_scan", "adaptive_scan", PlanAdaptiveScan),
])


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
        plans = set(i[0].user_name for i in get_plans("common", PLAN_WHITELIST))
        add_to_namespace(NamespaceKeys.PLANS, plans, ipython=ipython)


def unload_ipython_extension(ipython):
    pass
