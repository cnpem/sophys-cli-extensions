import os

from sophys.cli.core import HTTPSERVER_HOST_ENVVAR, HTTPSERVER_PORT_ENVVAR, get_cli_envvar

from sophys.cli.core.magics import render_custom_magics, setup_remote_session_handler, setup_plan_magics, NamespaceKeys, add_to_namespace, get_from_namespace

from sophys.cli.core.magics.plan_magics import get_plans, ModeOfOperation, PlanInformation, PlanWhitelist
from sophys.cli.core.magics.tools_magics import KBLMagics, HTTPMagics, MiscMagics, SophysLiveViewMagics

from sophys.cli.core.magics.sample_plan_definitions import PlanMV, PlanCount, PlanScan, PlanGridScan, PlanAdaptiveScan


PLAN_WHITELIST = PlanWhitelist(*[
    PlanInformation("mv", "mov", PlanMV),
    PlanInformation("count", "count", PlanCount),
    PlanInformation("scan", "scan", PlanScan),
    PlanInformation("grid_scan", "grid_scan", PlanGridScan),
    PlanInformation("adaptive_scan", "adaptive_scan", PlanAdaptiveScan),
])


def load_ipython_extension(ipython):
    local_mode = get_from_namespace(NamespaceKeys.LOCAL_MODE, False, ipython)
    mode_of_op = ModeOfOperation.Local if local_mode else ModeOfOperation.Remote

    setup_plan_magics(ipython, "ipe", PLAN_WHITELIST, mode_of_op)
    ipython.register_magics(MiscMagics)
    ipython.register_magics(KBLMagics)
    ipython.register_magics(SophysLiveViewMagics)

    if not local_mode:
        ipython.register_magics(HTTPMagics)
        ipython.magics_manager.registry["HTTPMagics"].plan_whitelist = PLAN_WHITELIST

    print("\n".join(render_custom_magics(ipython)))

    if not local_mode:
        host = get_cli_envvar(HTTPSERVER_HOST_ENVVAR)
        port = get_cli_envvar(HTTPSERVER_PORT_ENVVAR)
        setup_remote_session_handler(ipython, f"http://{host}:{port}")
    else:
        plans = set(i[0].user_name for i in get_plans("ipe", PLAN_WHITELIST))
        add_to_namespace(NamespaceKeys.PLANS, plans, ipython=ipython)


def unload_ipython_extension(ipython):
    pass
