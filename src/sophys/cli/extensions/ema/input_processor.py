import functools
import logging
import typing

from sophys.cli.core.data_source import DataSource
from sophys.cli.core.magics.plan_magics import PlanInformation


def add_detectors(line: str, source: DataSource, plan_information: typing.Optional[PlanInformation] = None):
    """Insert '-d ...' directive into 'line', with detectors taken from 'source'."""
    if plan_information is not None:
        if not plan_information.extra_props.get("has_detectors", True):
            return line

    plan_name, _, args = line.partition(' ')
    detectors_str = " ".join(source.get(DataSource.DataType.DETECTORS))
    return f"{line.strip()} -d {detectors_str}"


def add_metadata(line: str, source: DataSource):
    """
    Insert '--md ...' directive into 'line', with metadata entries taken from 'source'.

    This function only inserts metadata related to detector collection code (i.e. baselines and monitors).
    """
    before_str = ",".join(source.get(DataSource.DataType.BEFORE))
    during_str = ",".join(source.get(DataSource.DataType.DURING))
    after_str = ",".join(source.get(DataSource.DataType.AFTER))

    md = ""
    if len(before_str) != 0:
        md += f"READ_BEFORE={before_str} "
    if len(during_str) != 0:
        md += f"READ_DURING={during_str} "
    if len(after_str) != 0:
        md += f"READ_AFTER={after_str} "

    if len(md) == 0:
        return line

    return f"{line.strip()} --md {md.strip()}"


def add_plan_target(line: str, source: DataSource):
    """
    Insert '--after_plan_target' directive into 'line', with the target taken from 'source'.
    """

    targets = source.get(DataSource.DataType.MAIN_DETECTOR)
    if len(targets) == 0:
        if len(detectors := source.get(DataSource.DataType.DETECTORS)) != 1:
            return line

        # When with a single detector selected, use it as the target by default.
        targets = detectors
    target = targets[0].strip()
    return f"{line.strip()} --plan_target {target} --md MAIN_COUNTER={target}"


def input_processor(lines: list[str], plan_whitelist: list[PlanInformation], data_source: DataSource):
    """Process 'lines' to create a valid scan call."""
    logger = logging.getLogger("sophys_cli.ema.input_processor")

    def test_should_process():
        for info in plan_whitelist:
            needle = info.user_name + " "
            for line in lines:
                line = line.strip()
                if line.startswith(needle) or line.startswith("%" + needle):
                    return True, info
        return False, None

    should_process, plan_information = test_should_process()
    if not should_process:
        return lines

    logger.debug(f"Processing lines: {'\n'.join(lines)}")
    processors = [
        functools.partial(add_detectors, source=data_source, plan_information=plan_information),
        functools.partial(add_metadata, source=data_source),
        functools.partial(add_plan_target, source=data_source),
    ]

    new_lines = []
    for line in lines:
        for p in processors:
            line = p(line)
        new_lines.append(line)

    logger.debug(f"Processed lines: {'\n'.join(new_lines)}")
    return new_lines
