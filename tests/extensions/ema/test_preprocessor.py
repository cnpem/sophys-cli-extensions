import pytest

import itertools

from bluesky import RunEngine, plans as bp
from bluesky.tests.utils import MsgCollector

from ophyd.sim import hw as _hw

from sophys.cli.extensions.ema.run_engine import create_metadata_inserter_preprocessor


@pytest.fixture
def run_engine():
    RE = RunEngine({})
    RE.preprocessors.append(create_metadata_inserter_preprocessor())
    return RE


@pytest.fixture(scope="session")
def hw():
    from sophys.common.utils.registry import register_devices

    with register_devices("SIM"):
        simulated_hardware = _hw()
        simulated_hardware.rand.start_simulation()
        simulated_hardware.rand.kind = "hinted"

    return simulated_hardware


def run_with_clean(plan, run_engine: RunEngine) -> tuple[MsgCollector, MsgCollector]:
    clean_collector = MsgCollector()
    clean_run_engine = RunEngine({})
    clean_run_engine.msg_hook = clean_collector

    collector = MsgCollector()
    run_engine.msg_hook = collector

    plans = itertools.tee(plan)
    run_engine(plans[0])
    clean_run_engine(plans[1])

    return collector, clean_collector


def assert_len_msg_collectors(got: MsgCollector, clean: MsgCollector, add_to_clean: int = 0):
    la = len(got.msgs)
    lb = len(clean.msgs)

    debug_list = [f"{got.msgs[i].command} - {clean.msgs[i].command}" for i in range(min(la, lb))]
    print("Got - Clean")
    print('\n'.join(debug_list))
    assert la == lb + add_to_clean


def test_simple(run_engine, hw):
    # Assert a simple plan run doesn't explode.
    run_engine(bp.scan([hw.rand], hw.motor1, -1, 1, num=3))


def test_msg_no_metadata(run_engine, hw):
    plan = bp.scan([hw.rand], hw.motor1, -1, 1, num=3)
    collector, clean_collector = run_with_clean(plan, run_engine)

    assert_len_msg_collectors(collector, clean_collector)
    num_msgs = len(collector.msgs)
    assert all(collector.msgs[i].command == clean_collector.msgs[i].command for i in range(num_msgs))
    assert all(collector.msgs[i].obj == clean_collector.msgs[i].obj for i in range(num_msgs))


@pytest.mark.parametrize(
    "md,extra_messages", [
        # 1 (create) + 1 (read) + 1 (save)
        ({"READ_BEFORE": "det4"}, 3),
        # 1 (create) + 1 (drop)
        ({"READ_BEFORE": "non_existing_det"}, 2),
        # 1 (create) + 4 (read) + 1 (save)
        ({"READ_BEFORE": "det4,rand,motor1,noisy_det"}, 6),
        # 1 (create) + 3 (read) + 1 (save)
        ({"READ_BEFORE": "det4,rand,non_existing_motor1,noisy_det"}, 5),
        # 1 (create) + 1 (read) + 1 (save)
        ({"READ_AFTER": "det4"}, 3),
        # 1 (create) + 1 (drop)
        ({"READ_AFTER": "non_existing_det"}, 2),
        # 1 (create) + 4 (read) + 1 (save)
        ({"READ_AFTER": "det4,rand,motor1,noisy_det"}, 6),
        # 1 (create) + 3 (read) + 1 (save)
        ({"READ_AFTER": "det4,rand,non_existing_motor1,noisy_det"}, 5),
        # 2 (create) + 2 (read) + 2 (save)
        ({"READ_BEFORE": "det4", "READ_AFTER": "det4"}, 6),
        # 2 (create) + 4 (read) + 2 (save)
        ({"READ_BEFORE": "det4,rand", "READ_AFTER": "det4,rand"}, 8),
        # 2 (create) + 3 (read) + 2 (save)  (asymmetric)
        ({"READ_BEFORE": "det4,rand", "READ_AFTER": "det4"}, 7),
        # 2 (create) + 3 (read) + 2 (save)  (asymmetric)
        ({"READ_BEFORE": "det4", "READ_AFTER": "det4,rand"}, 7),
    ]
)
def test_msg_with_metadata(run_engine, hw, md, extra_messages):
    plan = bp.scan([hw.rand], hw.motor1, -1, 1, num=3, md=md)
    collector, clean_collector = run_with_clean(plan, run_engine)

    assert_len_msg_collectors(collector, clean_collector, extra_messages)

