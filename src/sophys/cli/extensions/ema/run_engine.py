import functools
import logging

from bluesky import Msg, plan_stubs as bps
from bluesky.preprocessors import plan_mutator


def get_device_by_name(name: str):
    """Context-independent way of finding a device object from its name."""
    from sophys.common.utils.registry import find_all
    return find_all(name=name)[0]


def create_metadata_inserter_preprocessor(metadata_before_stream_name="baseline_before", metadata_after_stream_name="baseline_after"):
    """
    Create a RunEngine preprocessor for adding various baseline readings to a plan.

    Parameters
    ----------
    metadata_before_stream_name : str, optional
        The stream name given to the readings before the start of the scan.
    metadata_after_stream_name : str, optional
        The stream name given to the readings before the end of the scan.

    Notes
    -----
    If two metadata stream names are equal, having asymmetric before and after
    reads **WILL** throw an exception.

    This means that, if you intend on having different devices on the before
    and after, you **MUST NOT** have the same name for both.

    The reason for this is that the descriptor document is only emitted once,
    so it can not handle a changing device list.
    """

    # NOTE: This is a list so we can somewhat support multiple
    # concurrent runs, since we do not have access to UUIDs in
    # the Msg layer.
    #
    # How it works then is that the last list element consists
    # of the most recently opened run.
    #
    # This will only work if the assumption that multiple runs
    # are strictly contained in their generating run is held.
    _kwargs_for_runs = []

    _logger = logging.getLogger("sophys_cli.ema.preprocessor")

    def metadata_inserter_preprocessor(msg: Msg):
        nonlocal _kwargs_for_runs

        def __read_plan(device_name_list, metadata_stream_name):
            """Read a list of devices into a data stream."""
            yield from bps.create(metadata_stream_name)

            read_any = False
            for device_name in device_name_list:
                try:
                    device = get_device_by_name(device_name)
                except Exception:
                    _logger.error("Failed to find device named '%s'. Ignoring it.", device_name)
                    continue

                read_any = True
                yield from bps.read(device)

            if read_any:
                yield from bps.save()
            else:
                yield from bps.drop()

        def __before_plan(kwargs):
            """Plan to read devices right before starting the scan."""
            device_names_to_read = kwargs.get("READ_BEFORE", "")
            if len(device_names_to_read) != 0:
                yield from __read_plan(device_names_to_read.split(','), metadata_before_stream_name)

        def __after_plan(kwargs):
            """Plan to read devices right before finishing the scan."""
            device_names_to_read = kwargs.get("READ_AFTER", "")
            if len(device_names_to_read) != 0:
                yield from __read_plan(device_names_to_read.split(','), metadata_after_stream_name)

            # Do not mutate message.
            yield msg

        if msg.command == "open_run":
            _logger.debug("Msg 'open_run' received with kwargs:")
            _logger.debug(msg.kwargs)

            _kwargs_for_runs.append(msg.kwargs)

            return (None, __before_plan(msg.kwargs))

        if msg.command == "close_run":
            kwargs = _kwargs_for_runs.pop()

            _logger.debug("Msg 'close_run' received. Using kwargs:")
            _logger.debug(kwargs)

            return (__after_plan(kwargs), None)

        return (None, None)

    return functools.partial(plan_mutator, msg_proc=metadata_inserter_preprocessor)

