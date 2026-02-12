import functools
import logging
import typing

from IPython.core.magic import Magics, magics_class, line_magic, needs_local_scope

from bluesky_queueserver_api.comm_base import RequestFailedError

from sophys.cli.core import ENVVARS

from sophys.cli.core.data_source import LocalInMemoryDataSource, RedisDataSource
from sophys.cli.core.persistent_metadata import PersistentMetadata

from sophys.cli.core.magics import render_custom_magics, setup_remote_session_handler, setup_plan_magics, NamespaceKeys, get_from_namespace, add_to_namespace, get_color

from sophys.cli.core.magics.plan_magics import get_plans, ModeOfOperation, PlanInformation, PlanWhitelist, ExceptionHandlerReturnValue
from sophys.cli.core.magics.tools_magics import KBLMagics, SophysLiveViewMagics, HTTPMagics, MiscMagics

from sophys.cli.core.magics.sample_plan_definitions import PlanReadMany, PlanCount

from .eds.device_selector import spawnDeviceSelector
from .input_processor import input_processor
from .ipython_config import setup_prompt
from .plans import PlanAbsNDScan, PlanRelNDScan, PlanAbsGridScan, PlanRelGridScan, PlanAbsNDListScan, PlanRelNDListScan, PlanGridScanWithJitter, PlanMotorOrigin, PlanCT, PlanMV, PlanEScan, PlanEScanFly, PlanMoveEnergy, PlanAbsGridEnergyScan, PlanRelGridScan


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
    from sophys.ema.utils.mnemonics import mnemonic_to_pv_name

    res = dict()

    def inner(mnemonic, name):
        if name is None:
            if mnemonic.startswith("sim_"):
                res[mnemonic] = mnemonic
                return
            logging.warning("No name found for mnemonic '%s'.", mnemonic)
        else:
            res[mnemonic] = name

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


def do_spec_and_nexus_files(*devices, md):
    if "metadata_save_file_format" not in md:
        md["metadata_save_file_format"] = "SPEC,NEXUS"

    # Assonant metadata
    md["beamline_name"] = "EMA"

    return md


whitelisted_plan_md_preprocessors = [
    populate_mnemonics,
    do_spec_and_nexus_files,
]


def setup_input_transformer(ipython, plan_whitelist, test_mode: bool = False):
    if test_mode:
        remote_data_source = LocalInMemoryDataSource()
    else:
        host = ENVVARS.REDIS_HOST
        port = ENVVARS.REDIS_PORT
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


def render_device_list(device_list: dict[str, typing.Any]) -> list[str]:
    from sophys.ema.utils.mnemonics import get_all_devices_sorted
    return get_all_devices_sorted(device_source=list(device_list.keys()))


def after_plan_submission_callback(ipython):
    return ipython.run_line_magic("wait_for_idle", "")


def after_plan_request_failed_callback(exc: RequestFailedError, local_ns) -> ExceptionHandlerReturnValue:
    if "Plan validation failed" in exc.response["msg"]:
        print("Could not run the provided plan because the sent parameters do not work with the plan:")
        print(exc.response["msg"])
        return ExceptionHandlerReturnValue.EXIT_QUIET
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
    print("The original exception said: ")
    print(exc.response["msg"])
    print()
    print("Use the 'query_state' magic for more information.")
    print()

    return ExceptionHandlerReturnValue.EXIT_QUIET


def sophys_state_query() -> str:
    import subprocess

    render = []

    autosave_host = ENVVARS.AUTOSAVE_HOST
    autosave_port = ENVVARS.AUTOSAVE_PORT
    redis_host = ENVVARS.REDIS_HOST
    redis_port = ENVVARS.REDIS_PORT
    http_host = ENVVARS.HTTPSERVER_HOST
    http_port = ENVVARS.HTTPSERVER_PORT
    kafka_host = ENVVARS.KAFKA_HOST
    kafka_port = ENVVARS.KAFKA_PORT

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


hidden_argument_names = {"detectors", "md"}
_a = hidden_argument_names


whitelisted_plan_list = [
    PlanInformation("mov", "mov", PlanMV, has_detectors=False, hide_args=_a),
    PlanInformation("rmov", "rmov", PlanMV, has_detectors=False, hide_args=_a),
    PlanInformation("read_many", "read", PlanReadMany, has_detectors=False, hide_args=_a),
    PlanInformation("count", "count", PlanCount, hide_args=_a),
    PlanInformation("grid_scan", "grid_scan", PlanAbsGridScan, hide_args=_a),
    PlanInformation("grid_scan", "rel_grid_scan", PlanRelGridScan, hide_args=_a),
    PlanInformation("scanNd", "ascan", PlanAbsNDScan, hide_args=_a),
    PlanInformation("scanNd", "rscan", PlanRelNDScan, hide_args=_a),
    PlanInformation("list_scan_nd", "list_ascan", PlanAbsNDListScan, hide_args=_a),
    PlanInformation("list_scan_nd", "list_rscan", PlanRelNDListScan, hide_args=_a),
    PlanInformation("motor_set_origin", "mset", PlanMotorOrigin, hide_args=_a),
    PlanInformation("ct", "ct", PlanCT, hide_args=_a),
    PlanInformation("grid_scan_with_jitter", "jittermap", PlanGridScanWithJitter, hide_args=_a),
    PlanInformation("escan_step_scan_by_hw", "escan", PlanEScan, hide_args=_a),
    PlanInformation("escan_fly_scan_by_hw", "escan_fly", PlanEScanFly, hide_args=_a),
    PlanInformation("move_energy", "mov_e", PlanMoveEnergy, has_detectors=False, hide_args=_a),
    PlanInformation("grid_energy_scan", "grid_escan", PlanAbsGridScan, hide_args=_a),
    PlanInformation("grid_energy_scan", "rel_grid_escan", PlanRelGridScan, hide_args=_a),
]


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
    ipython.register_magics(SophysLiveViewMagics)
    setup_input_transformer(ipython, plan_whitelist, test_mode)

    KBLMagics.extra_arguments = ["--stats-widget-on-by-default"]
    SophysLiveViewMagics.extra_arguments = ["--show-stats-by-default", "--hour-offset", "1"]

    if not local_mode:
        ipython.register_magics(HTTPMagics)
        ipython.magics_manager.registry["HTTPMagics"].plan_whitelist = plan_whitelist
        ipython.magics_manager.registry["HTTPMagics"].additional_state = [sophys_state_query]
        ipython.magics_manager.registry["HTTPMagics"].device_list_renderer = render_device_list

    if not test_mode:
        add_to_namespace(
            NamespaceKeys.BLACKLISTED_DESCRIPTIONS,
            {"add_md", "remove_md", "disable_auto_increment", "pause", "resume", "stop", "wait_for_idle"}
        )
    print("\n".join(render_custom_magics(ipython)))

    if not local_mode:
        host = ENVVARS.HTTPSERVER_HOST
        port = ENVVARS.HTTPSERVER_PORT
        setup_remote_session_handler(ipython, f"http://{host}:{port}", disable_authentication=True)
    else:
        plans = set(i[0].user_name for i in get_plans("ema", plan_whitelist))
        add_to_namespace(NamespaceKeys.PLANS, plans, ipython=ipython)

    setup_prompt(ipython)

    if local_mode:
        # Configure databroker for 'mov' plan runs
        db = get_from_namespace(NamespaceKeys.DATABROKER, ipython=ipython)
        from sophys.ema.plans import get_globals
        get_globals().update({"db": db})


def unload_ipython_extension(ipython):
    pass

