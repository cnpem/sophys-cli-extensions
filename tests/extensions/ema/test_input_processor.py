import pytest

from sophys.cli.extensions.ema.input_processor import LocalDataSource, add_detectors, add_metadata


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
        ("scan -m -1 1 --num 10", "scan -d abc1 abc2 abc3 -m -1 1 --num 10"),
        ("scan -mvs1 -1 1 10 0.1", "scan -d abc1 abc2 abc3 -mvs1 -1 1 10 0.1"),
        ("super_scan whatever whatever", "super_scan -d abc1 abc2 abc3 whatever whatever"),
    ])
def test_add_detectors(sample_line, expected, local_data_source):
    assert (ret := add_detectors(sample_line, local_data_source)) == expected, ret


@pytest.mark.parametrize(
    "sample_line,expected", [
        ("scan -m -1 1 --num 10", "scan -m -1 1 --num 10 --md READ_BEFORE=xyz1 READ_DURING=mno1,mno2 READ_AFTER=rst1,rst2"),
        ("scan -mvs1 -1 1 10 0.1", "scan -mvs1 -1 1 10 0.1 --md READ_BEFORE=xyz1 READ_DURING=mno1,mno2 READ_AFTER=rst1,rst2"),
        ("super_scan whatever whatever", "super_scan whatever whatever --md READ_BEFORE=xyz1 READ_DURING=mno1,mno2 READ_AFTER=rst1,rst2"),
    ])
def test_add_metadata(sample_line, expected, local_data_source):
    assert (ret := add_metadata(sample_line, local_data_source)) == expected, ret
