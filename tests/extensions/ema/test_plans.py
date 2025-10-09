# 'ip' and 'ok_mock_api' fixtures from sophys-cli-core

import pytest

import argparse
import os

from datetime import datetime
from unittest.mock import patch

from sophys.cli.core.magics import setup_plan_magics, get_from_namespace, NamespaceKeys
from sophys.cli.core.magics.plan_magics import ModeOfOperation, PlanWhitelist

from sophys.cli.extensions.ema import plans, whitelisted_plan_list


@pytest.fixture
def mock_datetime():
    mock_now = datetime.now()

    patcher = patch("datetime.datetime")

    patched_datetime = patcher.start()
    patched_datetime.now.return_value = mock_now

    yield mock_now

    patcher.stop()


def test_hdf_base_scan(mock_datetime):
    hdf_base_scan = plans._HDFBaseScanCLI()

    parser = argparse.ArgumentParser()
    hdf_base_scan.add_hdf_arguments(parser)

    args = parser.parse_known_args(["--hdf_file_name", "abacaxi_%S", "--hdf_file_path", "/tmp/"])
    assert args[0].hdf_file_name == "abacaxi_%S"
    assert args[0].hdf_file_path == "/tmp/"

    parsed_name, parsed_path = hdf_base_scan.parse_hdf_args(args[0])
    assert parsed_name == mock_datetime.strftime(args[0].hdf_file_name)
    assert parsed_path == "/tmp/"

    args[0].hdf_file_path = None
    parsed_name, parsed_path = hdf_base_scan.parse_hdf_args(args[0])
    assert parsed_name == mock_datetime.strftime(args[0].hdf_file_name)
    assert parsed_path == os.getcwd()

    parsed_name, parsed_path = hdf_base_scan.parse_hdf_args(args[0], template="%H_cenoura")
    assert parsed_name == mock_datetime.strftime(args[0].hdf_file_name)
    assert parsed_path == os.getcwd()

    args[0].hdf_file_name = None
    parsed_name, parsed_path = hdf_base_scan.parse_hdf_args(args[0], template="%H_cenoura")
    assert parsed_name == mock_datetime.strftime("%H_cenoura")
    assert parsed_path == os.getcwd()


def test_after_base_scan():
    after_base_scan = plans._AfterBaseScanCLI()

    parser = argparse.ArgumentParser()
    after_base_scan.add_after_arguments(parser)

    args = parser.parse_known_args(["--plan_target", "abc"])
    assert not args[0].max
    assert args[0].plan_target == "abc"

    behavior = after_base_scan.get_after_plan_behavior_argument(args[0])
    assert behavior == "return"

    args = parser.parse_known_args(["--max", "--plan_target", "abc"])
    assert args[0].max
    assert args[0].plan_target == "abc"

    behavior = after_base_scan.get_after_plan_behavior_argument(args[0])
    assert behavior == "max"

    args[0].detectors = ["xyz"]
    target = after_base_scan.get_after_plan_target_argument(args[0])
    assert target == "abc"

    args[0].plan_target = None
    target = after_base_scan.get_after_plan_target_argument(args[0])
    assert target == "xyz"


def test_before_base_scan():
    before_base_scan = plans._BeforeBaseScanCLI()

    parser = argparse.ArgumentParser()
    before_base_scan.add_before_arguments(parser)

    args = parser.parse_known_args(["--plan_target", "abc"])
    assert not args[0].max
    assert args[0].plan_target == "abc"

    behavior = before_base_scan.get_before_plan_behavior_argument(args[0])
    assert behavior is None

    args = parser.parse_known_args(["--max", "--plan_target", "abc"])
    assert args[0].max
    assert args[0].plan_target == "abc"

    behavior = before_base_scan.get_before_plan_behavior_argument(args[0])
    assert behavior == "max"

    args[0].detectors = ["xyz"]
    target = before_base_scan.get_before_plan_target_argument(args[0])
    assert target == "abc"

    args[0].plan_target = None
    target = before_base_scan.get_before_plan_target_argument(args[0])
    assert target == "xyz"


@pytest.fixture
def ip_with_plans(ip, ok_mock_api):
    setup_plan_magics(ip, "ema", PlanWhitelist(*whitelisted_plan_list), ModeOfOperation.Test)

    print("List of registered magics:")
    print(ip.magics_manager.lsmagic()["line"].keys())

    yield ip


def test_ascan(ip_with_plans, mock_datetime, capsys):
    ip_with_plans.run_magic("ascan", "-h")

    captured = capsys.readouterr()
    assert "usage: ascan motor start stop" in captured.out

    ip_with_plans.run_magic("ascan", "sim -1 1 10")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1][1:] == ("sim", -1.0, 1.0)  # *args
    assert plan_data[2]["number_of_steps"] == 10
    assert plan_data[2]["exposure_time"] is None
    assert plan_data[2]["hdf_file_name"] == mock_datetime.strftime("ascan_%H_%M_%S")
    assert plan_data[2]["hdf_file_path"] == os.getcwd()

    ip_with_plans.run_magic("ascan", "sim -1 1 10 0.1")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1][1:] == ("sim", -1.0, 1.0)  # *args
    assert plan_data[2]["number_of_steps"] == 10
    assert plan_data[2]["exposure_time"] == 0.1
    assert plan_data[2]["hdf_file_name"] == mock_datetime.strftime("ascan_%H_%M_%S")
    assert plan_data[2]["hdf_file_path"] == os.getcwd()

    ip_with_plans.run_magic("ascan", "sim -1 1 sim2 -2 1.5 15 0.25")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1][1:] == ("sim", -1.0, 1.0, "sim2", -2, 1.5)  # *args
    assert plan_data[2]["number_of_steps"] == 15
    assert plan_data[2]["exposure_time"] == 0.25
    assert plan_data[2]["hdf_file_name"] == mock_datetime.strftime("ascan_%H_%M_%S")
    assert plan_data[2]["hdf_file_path"] == os.getcwd()


def test_rscan(ip_with_plans, mock_datetime, capsys):
    ip_with_plans.run_magic("rscan", "-h")

    captured = capsys.readouterr()
    assert "usage: rscan motor start stop" in captured.out

    ip_with_plans.run_magic("rscan", "sim -1 1 10")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1][1:] == ("sim", -1.0, 1.0)  # *args
    assert plan_data[2]["number_of_steps"] == 10
    assert plan_data[2]["exposure_time"] is None
    assert plan_data[2]["hdf_file_name"] == mock_datetime.strftime("rscan_%H_%M_%S")
    assert plan_data[2]["hdf_file_path"] == os.getcwd()

    ip_with_plans.run_magic("rscan", "sim -1 1 10 0.1")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1][1:] == ("sim", -1.0, 1.0)  # *args
    assert plan_data[2]["number_of_steps"] == 10
    assert plan_data[2]["exposure_time"] == 0.1
    assert plan_data[2]["hdf_file_name"] == mock_datetime.strftime("rscan_%H_%M_%S")
    assert plan_data[2]["hdf_file_path"] == os.getcwd()

    ip_with_plans.run_magic("rscan", "sim -1 1 sim2 -2 1.5 15 0.25")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1][1:] == ("sim", -1.0, 1.0, "sim2", -2, 1.5)  # *args
    assert plan_data[2]["number_of_steps"] == 15
    assert plan_data[2]["exposure_time"] == 0.25
    assert plan_data[2]["hdf_file_name"] == mock_datetime.strftime("rscan_%H_%M_%S")
    assert plan_data[2]["hdf_file_path"] == os.getcwd()


def test_abs_grid_scan(ip_with_plans, mock_datetime, capsys):
    ip_with_plans.run_magic("grid_scan", "-h")

    captured = capsys.readouterr()
    assert "usage: grid_scan motor start stop num motor start stop num" in captured.out

    ip_with_plans.run_magic("grid_scan", "sim1 -1 1 10 sim2 -0.5 0.5 10")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1][1:] == ("sim1", -1.0, 1.0, 10, "sim2", -0.5, 0.5, 10)  # *args
    assert plan_data[2]["exposure_time"] is None
    assert plan_data[2]["snake_axes"] is False
    assert plan_data[2]["hdf_file_name"] == mock_datetime.strftime("gridscan_%H_%M_%S")
    assert plan_data[2]["hdf_file_path"] == os.getcwd()

    ip_with_plans.run_magic("grid_scan", "sim1 -1 1 10 sim2 -0.5 0.5 10 0.25")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1][1:] == ("sim1", -1.0, 1.0, 10, "sim2", -0.5, 0.5, 10)  # *args
    assert plan_data[2]["exposure_time"] == 0.25
    assert plan_data[2]["snake_axes"] is False
    assert plan_data[2]["hdf_file_name"] == mock_datetime.strftime("gridscan_%H_%M_%S")
    assert plan_data[2]["hdf_file_path"] == os.getcwd()

    ip_with_plans.run_magic("grid_scan", "sim1 -1 1 10 sim2 -0.5 0.5 10 0.25 -s")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1][1:] == ("sim1", -1.0, 1.0, 10, "sim2", -0.5, 0.5, 10)  # *args
    assert plan_data[2]["exposure_time"] == 0.25
    assert plan_data[2]["snake_axes"] is True
    assert plan_data[2]["hdf_file_name"] == mock_datetime.strftime("gridscan_%H_%M_%S")
    assert plan_data[2]["hdf_file_path"] == os.getcwd()


def test_rel_grid_scan(ip_with_plans, mock_datetime, capsys):
    ip_with_plans.run_magic("rel_grid_scan", "-h")

    captured = capsys.readouterr()
    assert "usage: rel_grid_scan motor start stop num motor start stop num" in captured.out

    ip_with_plans.run_magic("rel_grid_scan", "sim1 -1 1 10 sim2 -0.5 0.5 10")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1][1:] == ("sim1", -1.0, 1.0, 10, "sim2", -0.5, 0.5, 10)  # *args
    assert plan_data[2]["exposure_time"] is None
    assert plan_data[2]["snake_axes"] is False
    assert plan_data[2]["hdf_file_name"] == mock_datetime.strftime("gridscan_%H_%M_%S")
    assert plan_data[2]["hdf_file_path"] == os.getcwd()

    ip_with_plans.run_magic("rel_grid_scan", "sim1 -1 1 10 sim2 -0.5 0.5 10 0.25")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1][1:] == ("sim1", -1.0, 1.0, 10, "sim2", -0.5, 0.5, 10)  # *args
    assert plan_data[2]["exposure_time"] == 0.25
    assert plan_data[2]["snake_axes"] is False
    assert plan_data[2]["hdf_file_name"] == mock_datetime.strftime("gridscan_%H_%M_%S")
    assert plan_data[2]["hdf_file_path"] == os.getcwd()

    ip_with_plans.run_magic("rel_grid_scan", "sim1 -1 1 10 sim2 -0.5 0.5 10 0.25 -s")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1][1:] == ("sim1", -1.0, 1.0, 10, "sim2", -0.5, 0.5, 10)  # *args
    assert plan_data[2]["exposure_time"] == 0.25
    assert plan_data[2]["snake_axes"] is True
    assert plan_data[2]["hdf_file_name"] == mock_datetime.strftime("gridscan_%H_%M_%S")
    assert plan_data[2]["hdf_file_path"] == os.getcwd()


def test_mov(ip_with_plans, mock_datetime, capsys):
    ip_with_plans.run_magic("mov", "-h")

    captured = capsys.readouterr()
    assert "A simple 'mov' plan" in captured.out

    ip_with_plans.run_magic("mov", "sim 0.1")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1] == ("sim", 0.1)
    assert plan_data[2]["use_old_data"] == 0

    ip_with_plans.run_magic("mov", "sim1 1 sim2 2.3")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1] == ("sim1", 1, "sim2", 2.3)
    assert plan_data[2]["use_old_data"] == 0

    ip_with_plans.run_magic("mov", "sim1 sim2 --max --plan_target sim_det")

    plan_data = get_from_namespace(NamespaceKeys.TEST_DATA, ipython=ip_with_plans)
    assert plan_data[1] == ("sim1", "sim2")
    assert plan_data[2]["target"] == "sim_det"
    assert plan_data[2]["behavior"] == "max"
    assert plan_data[2]["use_old_data"] == -1
