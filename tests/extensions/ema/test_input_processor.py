import pytest

from sophys.cli.extensions.plan_magics import PlanInformation
from sophys.cli.extensions.ema import PLAN_WHITELIST
from sophys.cli.extensions.ema.data_source import LocalDataSource
from sophys.cli.extensions.ema.input_processor import add_detectors, add_metadata, input_processor


@pytest.fixture
def local_data_source(test_data_location):
    return LocalDataSource(test_data_location + "ema_input_processor_data_source.csv")


def test_local_data_source_creation(local_data_source):
    assert local_data_source._file_contents.shape[0] == 8, local_data_source._file_contents
    assert local_data_source._file_contents.shape[1] == 2, local_data_source._file_contents


def test_local_data_source_get(local_data_source):
    assert len(dets := local_data_source.get(LocalDataSource.DataType.DETECTORS)) == 3, dets
    assert len(before := local_data_source.get(LocalDataSource.DataType.BEFORE)) == 1, before
    assert len(during := local_data_source.get(LocalDataSource.DataType.DURING)) == 2, during
    assert len(after := local_data_source.get(LocalDataSource.DataType.AFTER)) == 2, after


@pytest.mark.parametrize(
    "sample_line,expected", [
        ("scan -m -1 1 --num 10", "scan -m -1 1 --num 10 -d abc1 abc2 abc3"),
        ("scan -mvs1 -1 1 10 0.1", "scan -mvs1 -1 1 10 0.1 -d abc1 abc2 abc3"),
        ("super_scan whatever whatever", "super_scan whatever whatever -d abc1 abc2 abc3"),
    ])
def test_add_detectors(sample_line, expected, local_data_source):
    assert (ret := add_detectors(sample_line, local_data_source)) == expected, ret


@pytest.mark.parametrize(
    "sample_line,plan_information,expected", [
        ("scan -m -1 1 --num 10", PlanInformation("scan", "scan", None), "scan -m -1 1 --num 10 -d abc1 abc2 abc3"),
        ("scan -m -1 1 --num 10", PlanInformation("scan", "scan", None, has_detectors=True), "scan -m -1 1 --num 10 -d abc1 abc2 abc3"),
        ("scan -m -1 1 --num 10", PlanInformation("scan", "scan", None, has_detectors=False), "scan -m -1 1 --num 10"),
        ("super_scan -m -1 1 --num 10", PlanInformation("super_scan", "scan", None), "super_scan -m -1 1 --num 10 -d abc1 abc2 abc3"),
        ("super_scan -m -1 1 --num 10", PlanInformation("super_scan", "scan", None, has_detectors=True), "super_scan -m -1 1 --num 10 -d abc1 abc2 abc3"),
        ("super_scan -m -1 1 --num 10", PlanInformation("super_scan", "scan", None, has_detectors=False), "super_scan -m -1 1 --num 10"),
    ])
def test_add_detectors_with_plan_information(sample_line, plan_information, expected, local_data_source):
    assert (ret := add_detectors(sample_line, local_data_source, plan_information=plan_information)) == expected, ret


@pytest.mark.parametrize(
    "sample_line,expected", [
        ("scan -m -1 1 --num 10", "scan -m -1 1 --num 10 --md READ_BEFORE=xyz1 READ_DURING=mno1,mno2 READ_AFTER=rst1,rst2"),
        ("scan -mvs1 -1 1 10 0.1", "scan -mvs1 -1 1 10 0.1 --md READ_BEFORE=xyz1 READ_DURING=mno1,mno2 READ_AFTER=rst1,rst2"),
        ("super_scan whatever whatever", "super_scan whatever whatever --md READ_BEFORE=xyz1 READ_DURING=mno1,mno2 READ_AFTER=rst1,rst2"),
    ])
def test_add_metadata(sample_line, expected, local_data_source):
    assert (ret := add_metadata(sample_line, local_data_source)) == expected, ret


@pytest.mark.parametrize(
    "sample_lines,expected", [
        (["scan -m -1 1 --num 10"], ["scan -m -1 1 --num 10 -d abc1 abc2 abc3 --md READ_BEFORE=xyz1 READ_DURING=mno1,mno2 READ_AFTER=rst1,rst2"]),
        (["scan -mvs1 -1 1 10 0.1"], ["scan -mvs1 -1 1 10 0.1 -d abc1 abc2 abc3 --md READ_BEFORE=xyz1 READ_DURING=mno1,mno2 READ_AFTER=rst1,rst2"]),
        (["super_scan whatever whatever"], ["super_scan whatever whatever"]),
        (["mov xyz1 -1 xyz2 1"], ["mov xyz1 -1 xyz2 1 --md READ_BEFORE=xyz1 READ_DURING=mno1,mno2 READ_AFTER=rst1,rst2"])
    ])
def test_input_processor(sample_lines, expected, local_data_source):
    assert (ret := input_processor(sample_lines, PLAN_WHITELIST, local_data_source)) == expected, ret
