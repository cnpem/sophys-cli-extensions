import enum
import functools
import logging

import numpy as np


class DataSource:
    class DataType(enum.StrEnum):
        DETECTORS = "detector"
        BEFORE = "before"
        DURING = "during"
        AFTER = "after"

    def __init__(self):
        self._logger = logging.getLogger("sophys_cli.data_source")

    def get(self, type: DataType) -> np.array:
        raise NotImplementedError


class LocalDataSource(DataSource):
    """Data source backed by a local CSV file."""

    def __init__(self, path: str):
        super().__init__()

        try:
            import pandas as pd
        except ImportError:
            self._logger.critical("Could not import pandas, required by LocalDataSource.", exc_info=True)

        assert path.endswith(".csv"), "LocalDataSource only accepts CSV files."

        self._file_contents = pd.read_csv(path)

    def get(self, type: DataSource.DataType) -> np.array:
        return self._file_contents.loc[self._file_contents.type == type]["name"].to_numpy()


def add_detectors(line: str, source: DataSource):
    """Insert '-d ...' directive into 'line', with detectors taken from 'source'."""
    plan_name, _, args = line.partition(' ')
    detectors_str = " ".join(source.get(DataSource.DataType.DETECTORS))
    return f"{plan_name} -d {detectors_str} {args}"


def input_processor(lines, plan_whitelist: dict, data_source: DataSource):
    """Process 'lines' to create a valid scan call."""
    logger = logging.getLogger("sophys_cli.ema.input_processor")

    if not any(i[0] in line for i in plan_whitelist.values() for line in lines):
        return lines

    logger.debug(f"Processing lines: {'\n'.join(lines)}")
    processors = [
        functools.partial(add_detectors, source=data_source),
    ]

    new_lines = []
    for line in lines:
        for p in processors:
            line = p(line)
        new_lines.append(line)

    logger.debug(f"Processed lines: {'\n'.join(new_lines)}")
    return new_lines
