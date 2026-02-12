import argparse
import functools
import os
import typing

from collections import defaultdict

from sophys.cli.core.magics.plan_magics import ModeOfOperation
from sophys.cli.core.magics.plan_magics import PlanCLI, remote_control_available


if remote_control_available:
    from bluesky_queueserver_api.item import BPlan


class _HDFBaseScanCLI:
    def add_hdf_arguments(self, parser):
        parser.add_argument("--hdf_file_name", type=str, nargs='?', default=None, help="Save file name for the data HDF5 file generated (if using an AreaDetector). Defaults to 'ascan_hour_minute_second_scanid.h5'.")
        parser.add_argument("--hdf_file_path", type=str, nargs='?', default=None, help="Save path for the data HDF5 file generated (if using an AreaDetector). Defaults to CWD.")

        return parser

    def parse_hdf_args(self, parsed_namespace, template: str | None = None):
        template = parsed_namespace.hdf_file_name or template

        from datetime import datetime
        hdf_file_name = datetime.now().strftime(template)

        hdf_file_path = parsed_namespace.hdf_file_path
        if hdf_file_path is None:
            hdf_file_path = os.getcwd()

        return hdf_file_name, hdf_file_path


class _AfterBaseScanCLI:
    def add_after_arguments(self, parser):
        parser.add_argument("--max", action="store_true", help="Go to the point of the scan with maximum value at the end.")
        parser.add_argument("--plan_target", type=str, nargs='?', help=argparse.SUPPRESS)

        return parser

    def get_after_plan_behavior_argument(self, parsed_namespace):
        if parsed_namespace.max:
            return "max"
        return "return"

    def get_after_plan_target_argument(self, parsed_namespace):
        if not parsed_namespace.plan_target:
            if len(parsed_namespace.detectors) == 1:
                return parsed_namespace.detectors[0]
        return parsed_namespace.plan_target


class _BeforeBaseScanCLI:
    def add_before_arguments(self, parser):
        parser.add_argument("--max", action="store_true", help="Go to the point of the previous scan with maximum value.")
        parser.add_argument("--min", action="store_true", help="Go to the point of the previous scan with minimum value.")
        parser.add_argument("--plan_target", type=str, nargs='?', help=argparse.SUPPRESS)

        return parser

    def get_before_plan_behavior_argument(self, parsed_namespace):
        if parsed_namespace.max:
            return "max"
        if parsed_namespace.min:
            return "min"
        return None

    def get_before_plan_target_argument(self, parsed_namespace):
        if not parsed_namespace.plan_target:
            if len(parsed_namespace.detectors) == 1:
                return parsed_namespace.detectors[0]
        return parsed_namespace.plan_target


class BaseScanCLI(PlanCLI, _HDFBaseScanCLI, _AfterBaseScanCLI):
    def create_parser(self):
        _a = super().create_parser()

        _a = self.add_hdf_arguments(_a)
        _a = self.add_after_arguments(_a)

        return _a


class PlanNDScan(BaseScanCLI):
    absolute: bool

    def _usage(self):
        return "%(prog)s motor start stop [motor start stop ...] num [exposure_time]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("args", nargs='+', type=str, help="Motor informations, in order (mnemonic start_position end_position)")
        # NOTE: These two are not used in parsing, they're only here for documentation. Their values are taken from args instead.
        _a.add_argument("num", type=int, nargs='?', default=None, help="Number of points between the start and end positions.")
        _a.add_argument("exposure_time", type=float, nargs='?', default=None, help="Per-point exposure time of the detector. Defaults to using the previously defined exposure time on the IOC.")

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        detector = self.get_real_devices_if_needed(parsed_namespace.detectors, local_ns)

        nargs = len(parsed_namespace.args)
        assert (nargs >= 4) or (nargs % 3 == 0), "Not enough arguments have been passed."
        if nargs % 3 == 1:  # motors + num
            _args = parsed_namespace.args
            exp_time = None
        else:  # motors + num + exp time
            _args = parsed_namespace.args[:-1]
            exp_time = float(parsed_namespace.args[-1])

        args, num, motors = self.parse_varargs(_args, local_ns, with_final_num=True)

        md = self.parse_md(*parsed_namespace.detectors, *motors, ns=parsed_namespace)

        base_name = "ascan" if self.absolute else "rscan"
        hdf_file_name, hdf_file_path = self.parse_hdf_args(parsed_namespace, f"{base_name}_%H_%M_%S")

        if "metadata_save_file_location" not in md:
            md["metadata_save_file_location"] = hdf_file_path

        after_plan_behavior = self.get_after_plan_behavior_argument(parsed_namespace)
        after_plan_target = self.get_after_plan_target_argument(parsed_namespace)

        plan_args = (detector, *args)
        plan_kwargs = dict(number_of_points=num, exposure_time=exp_time, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, absolute=self.absolute, after_plan_behavior=after_plan_behavior, after_plan_target=after_plan_target)
        return plan_args, plan_kwargs


class PlanNDListScan(BaseScanCLI):
    absolute: bool

    class RangeAction(argparse.Action):
        """
        Custom argparse Action to parse list scan position ranges, including
        individual positions and lists / tuples of positions (e.g. inputted via
        a variable substitutions with '$').
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self._current_partial_list = None

        def maybe_fill_partial_list(self, value: str) -> tuple[bool, typing.Iterable | None]:
            """
            If detected, reassemble an input list of positions.

            Parameters
            ----------
            value : str
                The inputted value at the current location.

            Returns
            -------
            tuple of boolean and an iterable or None. The boolean represents whether
            the current value is detected as being a part of a list, and the iterable
            is filled with the full list of parsed positions when the last item is
            retrieved.
            """
            if value.startswith(('[', '(')):
                self._current_partial_list = [value]
                return True, None

            if value.endswith((']', ')')):
                self._current_partial_list.append(value)
                full_positions = [float(x) for x in eval(''.join(self._current_partial_list))]
                self._current_partial_list = None
                return True, full_positions

            if self._current_partial_list is not None:
                self._current_partial_list.append(value)
                return True, None

            return False, None

        def __call__(self, parser, namespace, values, option_string):
            motor_positions = defaultdict(lambda: [])

            current_positioner = None

            for value in values:
                try:
                    # Is it a position value?
                    value = float(value)
                except ValueError:
                    # Not a position value, discover what it is.

                    # A partial list item
                    filling_partial_list, full_position_list = self.maybe_fill_partial_list(value)
                    if filling_partial_list:
                        if full_position_list is not None:
                            motor_positions[current_positioner].extend(full_position_list)
                        continue

                    # A positioner name
                    current_positioner = value
                else:
                    # Is a position value, append it.
                    if current_positioner is None:
                        raise Exception("You need to specify a motor device before the list of positions.")
                    motor_positions[current_positioner].append(value)

            namespace.args = []
            for positioner, positions in motor_positions.items():
                namespace.args.extend([positioner, tuple(positions)])

    def _usage(self):
        return "%(prog)s motor positions [motor positions ...] [-t exposure_time]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("args", nargs='+', action=self.RangeAction, type=str, help="Motor informations, in order (mnemonic positions)")
        _a.add_argument("-t", "--exposure_time", type=float, nargs='?', default=None, help="Per-point exposure time of the detector. Defaults to using the previously defined exposure time on the IOC.")

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        detector = self.get_real_devices_if_needed(parsed_namespace.detectors, local_ns)
        args, _, motors = self.parse_varargs(parsed_namespace.args, local_ns)

        exp_time = parsed_namespace.exposure_time

        md = self.parse_md(*parsed_namespace.detectors, *motors, ns=parsed_namespace)

        base_name = "list_ascan" if self.absolute else "list_rscan"
        hdf_file_name, hdf_file_path = self.parse_hdf_args(parsed_namespace, f"{base_name}_%H_%M_%S")

        if "metadata_save_file_location" not in md:
            md["metadata_save_file_location"] = hdf_file_path

        after_plan_behavior = self.get_after_plan_behavior_argument(parsed_namespace)
        after_plan_target = self.get_after_plan_target_argument(parsed_namespace)

        plan_args = (detector, *args)
        plan_kwargs = dict(exposure_time=exp_time, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, absolute=self.absolute, after_plan_behavior=after_plan_behavior, after_plan_target=after_plan_target)
        return plan_args, plan_kwargs


class PlanGridScan(BaseScanCLI):
    absolute: bool

    def _usage(self):
        return "%(prog)s motor start stop num motor start stop num [exposure_time] [-s/--snake]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("first_motor", nargs=1, type=str, help="Mnemonic of the motor on the slowest axis to move.")
        _a.add_argument("first_start", type=float, help="Start position of the first motor, in the motor's EGU.")
        _a.add_argument("first_stop", type=float, help="End position of the first motor, in the motor's EGU.")
        _a.add_argument("first_num", type=int, help="Number of points between the start and end positions of the first motor.")
        _a.add_argument("second_motor", nargs=1, type=str, help="Mnemonic of the motor on the second slowest axis to move.")
        _a.add_argument("second_start", type=float, help="Start position of the second motor, in the motor's EGU.")
        _a.add_argument("second_stop", type=float, help="End position of the second motor, in the motor's EGU.")
        _a.add_argument("second_num", type=int, help="Number of points between the start and end positions of the second motor.")
        _a.add_argument("exposure_time", type=float, nargs='?', default=None, help="Per-point exposure time of the detector. Defaults to using the previously defined exposure time on the IOC.")
        _a.add_argument("-s", "--snake", action="store_true", help="Whether to snake axes or not. The default behavior is to not snake.")

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        detector = self.get_real_devices_if_needed(parsed_namespace.detectors, local_ns)
        args = [
            parsed_namespace.first_motor[0],
            parsed_namespace.first_start,
            parsed_namespace.first_stop,
            parsed_namespace.first_num,
            parsed_namespace.second_motor[0],
            parsed_namespace.second_start,
            parsed_namespace.second_stop,
            parsed_namespace.second_num,
        ]
        args, _, motor_names = self.parse_varargs(args, local_ns=local_ns)

        exp_time = parsed_namespace.exposure_time
        snake = parsed_namespace.snake

        md = self.parse_md(*parsed_namespace.detectors, *motor_names, ns=parsed_namespace)

        hdf_file_name, hdf_file_path = self.parse_hdf_args(parsed_namespace, "gridscan_%H_%M_%S")

        if "metadata_save_file_location" not in md:
            md["metadata_save_file_location"] = hdf_file_path

        after_plan_behavior = self.get_after_plan_behavior_argument(parsed_namespace)
        after_plan_target = self.get_after_plan_target_argument(parsed_namespace)

        plan_args = (detector, *args)
        plan_kwargs = dict(exposure_time=exp_time, snake_axes=snake, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, absolute=self.absolute, after_plan_behavior=after_plan_behavior, after_plan_target=after_plan_target)
        return plan_args, plan_kwargs


class PlanGridScanWithJitter(BaseScanCLI):
    def _usage(self):
        return "%(prog)s motor start stop num motor start stop num [motor start stop num ...] [exposure_time] [-s/--snake]"

    def _description(self):
        return super()._description() + """

Example usages:

jittermap ms2l 0.49 0.494 3 ms2r 0.488 0.49 3
    Make a 2D scan over 3 points on the 'ms2l' motor, from point 0.49 to point 0.494, in absolute coordinates,
    and 3 points on the 'ms2r' motor, from point 0.488 to point 0.49, without snaking, with the 'ms2l' axis changing the slowest:

                        |--------------------------------x-----|
              0.490     |------x---->-----x------->------------|
                        |------------------<-------------------|
              0.492     |----------->------x------>-----x------|
                        |----x------------x<-------------------|
              0.494     |------x---->------------->------------|
                        |-------------------------------x------|
                           0.4880       0.4890       0.4900
    ms2l position (abs)           ms2r position (abs)

    The exposure time used is the one set before the scan on the IOC.

jittermap ms2r 0.488 0.49 3 ms2l 0.49 0.494 3 0.1 -s
    Make a 2D scan over 3 points on the 'ms2r' motor, from point 0.488 to point 0.49, in absolute coordinates,
    and 3 points on the 'ms2l' motor, from point 0.49 to point 0.494, with snaking, with the 'ms2r' axis changing
    the slowest, and per-point exposure time equal to 0.1 seconds:

                        |--------------------------------|
              0.490     |-----x-------------->--x--------|
                        |-----|--------x|---------|x-----|
              0.492     |------x--------x----------------|
                        |-----|---------|---------|------|
              0.494     |---------->---x---------x-------|
                        |-----x--------------------------|
                           0.4880    0.4890    0.4900
    ms2l position (abs)        ms2r position (abs)

"""

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("first_motor", nargs=1, type=str, help="Mnemonic of the motor on the slowest axis to move.")
        _a.add_argument("first_start", type=float, help="Start position of the first motor, in the motor's EGU.")
        _a.add_argument("first_stop", type=float, help="End position of the first motor, in the motor's EGU.")
        _a.add_argument("first_num", type=int, help="Number of points between the start and end positions of the first motor.")
        _a.add_argument("second_motor", nargs=1, type=str, help="Mnemonic of the motor on the second slowest axis to move.")
        _a.add_argument("second_start", type=float, help="Start position of the second motor, in the motor's EGU.")
        _a.add_argument("second_stop", type=float, help="End position of the second motor, in the motor's EGU.")
        _a.add_argument("second_num", type=int, help="Number of points between the start and end positions of the second motor.")
        _a.add_argument("exposure_time", type=float, nargs='?', default=None, help="Per-point exposure time of the detector. Defaults to using the previously defined exposure time on the IOC.")
        _a.add_argument("-s", "--snake", action="store_true", help="Whether to snake axes or not. The default behavior is to not snake.")

        return _a

    def _create_plan(self, parsed_namespace, local_ns):
        detector = self.get_real_devices_if_needed(parsed_namespace.detectors, local_ns)
        args = [
            parsed_namespace.first_motor[0],
            parsed_namespace.first_start,
            parsed_namespace.first_stop,
            parsed_namespace.first_num,
            parsed_namespace.second_motor[0],
            parsed_namespace.second_start,
            parsed_namespace.second_stop,
            parsed_namespace.second_num,
        ]
        args, _, motor_names = self.parse_varargs(args, local_ns=local_ns)

        exp_time = parsed_namespace.exposure_time
        snake = parsed_namespace.snake

        md = self.parse_md(*parsed_namespace.detectors, *motor_names, ns=parsed_namespace)

        hdf_file_name, hdf_file_path = self.parse_hdf_args(parsed_namespace, "jittermap_%H_%M_%S")

        if "metadata_save_file_location" not in md:
            md["metadata_save_file_location"] = hdf_file_path

        after_plan_behavior = self.get_after_plan_behavior_argument(parsed_namespace)
        after_plan_target = self.get_after_plan_target_argument(parsed_namespace)

        if self._mode_of_operation == ModeOfOperation.Local:
            return functools.partial(self._plan, detector, *args, exposure_time=exp_time, snake_axes=snake, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, after_plan_behavior=after_plan_behavior, after_plan_target=after_plan_target)
        if self._mode_of_operation == ModeOfOperation.Remote:
            return BPlan(self._plan_name, detector, *args, exposure_time=exp_time, snake_axes=snake, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, after_plan_behavior=after_plan_behavior, after_plan_target=after_plan_target)


class PlanMotorOrigin(PlanCLI):
    def _usage(self):
        return "%(prog)s motor [position]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("motor", nargs=1, type=str, help="Mnemonic of a motor to set the origin of.")
        _a.add_argument("position", type=float, help="Position of the motor to set as origin. Default: current position.", default=None, nargs='?')

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        motor = self.get_real_devices_if_needed(parsed_namespace.motor, local_ns)[0]
        position = parsed_namespace.position

        md = self.parse_md(parsed_namespace.motor[0], ns=parsed_namespace)

        return (motor, position), {"md": md}


class PlanCT(PlanCLI, _HDFBaseScanCLI):
    def _usage(self):
        return "%(prog)s number_of_points [exposure_time]"

    def create_parser(self):
        _a = super().create_parser()

        _a = self.add_hdf_arguments(_a)

        _a.add_argument("number_of_points", type=int, nargs='?', default=None, help="Number of acquisitions to take.")
        _a.add_argument("exposure_time", type=float, nargs='?', default=None, help="Per-point exposure time of the detector. Defaults to using the previously defined exposure time on the IOC.")

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        detector = self.get_real_devices_if_needed(parsed_namespace.detectors, local_ns)
        md = self.parse_md(*parsed_namespace.detectors, ns=parsed_namespace)

        number_of_points = parsed_namespace.number_of_points
        exposure_time = parsed_namespace.exposure_time

        hdf_file_name, hdf_file_path = self.parse_hdf_args(parsed_namespace, "ct_%H_%M_%S")

        if "metadata_save_file_location" not in md:
            md["metadata_save_file_location"] = hdf_file_path

        plan_kwargs = dict(number_of_points=number_of_points, exposure_time=exposure_time, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path)
        return (detector,), plan_kwargs


class PlanMV(PlanCLI, _BeforeBaseScanCLI):
    def _usage(self):
        return "%(prog)s motor position [...] OR motors --max"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("args", nargs='+', type=str)
        _a = self.add_before_arguments(_a)

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        args, _, motors = self.parse_varargs(parsed_namespace.args, local_ns)

        md = self.parse_md(*motors, ns=parsed_namespace)

        before_plan_behavior = self.get_before_plan_behavior_argument(parsed_namespace)
        before_plan_target = self.get_before_plan_target_argument(parsed_namespace)

        data_index = 0
        if before_plan_behavior is not None:
            data_index = -1

        plan_kwargs = dict(target=before_plan_target, behavior=before_plan_behavior, use_old_data=data_index, md=md)
        return (*args,), plan_kwargs


class PlanAbsNDScan(PlanNDScan):
    absolute = True

    def _description(self):
        return super()._description() + """

Example usages:

ascan ms2r 0.488 0.49 6
    Make a 1D scan over 6 points on the 'ms2r' motor, from point 0.488 to point 0.49,
    in absolute coordinates:

    | scan point | scan point | scan point | scan point | scan point | scan point |
    |-----x------------x------------x------------x------------x------------x------|
       0.4880       0.4882       0.4884       0.4886       0.4888       0.4900
                                 ms2r position (abs)

    The exposure time used is the one set before the scan on the IOC.

ascan wst 0.0 0.4 5 0.1
    Make a 1D scan over 5 points on the 'wst' motor, from point 0.0 to point 0.4,
    in absolute coordinates, with exposure time per-point equal to 0.1 seconds:

    | scan point | scan point | scan point | scan point | scan point |
    |-----x------------x------------x------------x------------x------|
         0.0          0.1          0.2          0.3          0.4
                           wst position (abs)

ascan ms2r 0.488 0.49 wst 0.0 0.4 5 0.1
    Make a 2D scan over 5 points on the 'ms2r' and 'wst' motors, in absolute coordinates,
    with exposure time per-point equal to 0.1 seconds, and moving at the same time:

    |                     ms2r position (abs)                        |
    |  0.4880       0.4882       0.4884       0.4886       0.4888    |
    |-----x------------x------------x------------x------------x------|
    |    0.0          0.1          0.2          0.3          0.4     |
    |                      wst position (abs)                        |
"""


class PlanRelNDScan(PlanNDScan):
    absolute = False

    def _description(self):
        return super()._description() + """

Example usages:

rscan ms2r 0.488 0.49 6
    Make a 1D scan over 6 points on the 'ms2r' motor, from point 0.488 to point 0.49,
    relative to the current position:

    | scan point | scan point | scan point | scan point | scan point | scan point |
    |-----x------------x------------x------------x------------x------------x------|
       0.4880       0.4882       0.4884       0.4886       0.4888       0.4900
                                 ms2r position (rel)

    The exposure time used is the one set before the scan on the IOC.

rscan wst 0.0 0.4 5 0.1
    Make a 1D scan over 5 points on the 'wst' motor, from point 0.0 to point 0.4,
    relative to the current position, with exposure time per-point equal to 0.1 seconds:

    | scan point | scan point | scan point | scan point | scan point |
    |-----x------------x------------x------------x------------x------|
         0.0          0.1          0.2          0.3          0.4
                            wst position (rel)

rscan ms2r 0.488 0.49 wst 0.0 0.4 5 0.1
    Make a 2D scan over 5 points on the 'ms2r' and 'wst' motors, relative to the current position,
    with exposure time per-point equal to 0.1 seconds, and moving at the same time:

    |                     ms2r position (rel)                        |
    |  0.4880       0.4882       0.4884       0.4886       0.4888    |
    |-----x------------x------------x------------x------------x------|
    |    0.0          0.1          0.2          0.3          0.4     |
    |                      wst position (rel)                        |
"""


class PlanAbsNDListScan(PlanNDListScan):
    absolute = True

    def _description(self):
        return super()._description() + """

Example usages:

list_ascan ms2r 1 2 4
    Make a 1D scan over 3 points on the 'ms2r' motor, in absolute coordinates:

    | scan point | scan point |            | scan point |
    |-----x------------x-------------------------x------|
          1            2                         4
                     ms2r position (abs)

    The exposure time used is the one set before the scan on the IOC.

list_ascan wst 0.0 0.4 0.5 0.6 -t 0.1
    Make a 1D scan over 4 points on the 'wst' motor, in absolute coordinates,
    with exposure time per-point equal to 0.1 seconds:

    | scan point |            | scan point | scan point | scan point |
    |-----x------------//-----------x------------x------------x------|
         0.0                       0.4          0.5          0.6
                           wst position (abs)

list_ascan ms2r [1, 2, 3] wst 0.0 0.2 0.4 -t 0.1
    Make a 2D scan over 3 points on the 'ms2r' and 'wst' motors, in absolute coordinates,
    with exposure time per-point equal to 0.1 seconds, and moving at the same time:

    |         ms2r position (abs)         |
    |    1.0          2.0          3.0    |
    |-----x------------x------------x-----|
    |    0.0          0.2          0.4    |
    |          wst position (abs)         |
"""


class PlanRelNDListScan(PlanNDListScan):
    absolute = False

    def _description(self):
        return super()._description() + """

Example usages:

list_rscan ms2r -1 1 5
    Make a 1D scan over 3 points on the 'ms2r' motor, in relative coordinates:

    | scan point | scan point |            | scan point |
    |-----x------------x-------------------------x------|
         -1            1                         5
                     ms2r position (rel)

    The exposure time used is the one set before the scan on the IOC.

list_rscan wst 0.0 0.4 0.5 0.6 -t 0.1
    Make a 1D scan over 4 points on the 'wst' motor, in relative coordinates,
    with exposure time per-point equal to 0.1 seconds:

    | scan point |            | scan point | scan point | scan point |
    |-----x------------//-----------x------------x------------x------|
         0.0                       0.4          0.5          0.6
                           wst position (rel)

list_rscan ms2r [1, 2, 3] wst 0.0 0.2 0.4 -t 0.1
    Make a 2D scan over 3 points on the 'ms2r' and 'wst' motors, in relative coordinates,
    with exposure time per-point equal to 0.1 seconds, and moving at the same time:

    |         ms2r position (rel)         |
    |    1.0          2.0          3.0    |
    |-----x------------x------------x-----|
    |    0.0          0.2          0.4    |
    |          wst position (rel)         |
"""


class PlanAbsGridScan(PlanGridScan):
    absolute = True

    def _description(self):
        return super()._description() + """

Example usages:

grid_scan ms2l 0.49 0.494 3 ms2r 0.488 0.49 3
    Make a 2D scan over 3 points on the 'ms2l' motor, from point 0.49 to point 0.494, in absolute coordinates,
    and 3 points on the 'ms2r' motor, from point 0.488 to point 0.49, without snaking, with the 'ms2l' axis changing the slowest:

                        |--------------------------------------|
              0.490     |-----x----->------x------>-----x------|
                        |------------------<-------------------|
              0.492     |-----x----->------x------>-----x------|
                        |------------------<-------------------|
              0.494     |-----x----->------x------>-----x------|
                        |--------------------------------------|
                           0.4880       0.4890       0.4900
    ms2l position (abs)           ms2r position (abs)

    The exposure time used is the one set before the scan on the IOC.

grid_scan ms2r 0.488 0.49 3 ms2l 0.49 0.494 3 0.1 -s
    Make a 2D scan over 3 points on the 'ms2r' motor, from point 0.488 to point 0.49, in absolute coordinates,
    and 3 points on the 'ms2l' motor, from point 0.49 to point 0.494, with snaking, with the 'ms2r' axis changing
    the slowest, and per-point exposure time equal to 0.1 seconds:

                        |--------------------------------|
              0.490     |-----x---------x---->----x------|
                        |-----|---------|---------|------|
              0.492     |-----x---------x---------x------|
                        |-----|---------|---------|------|
              0.494     |-----x---->----x---------x------|
                        |--------------------------------|
                           0.4880    0.4890    0.4900
    ms2l position (abs)        ms2r position (abs)

"""


class PlanRelGridScan(PlanGridScan):
    absolute = False

    def _description(self):
        return super()._description() + """

Example usages:

rel_grid_scan ms2l 0.49 0.494 3 ms2r 0.488 0.49 3
    Make a 2D scan over 3 points on the 'ms2l' motor, from point 0.49 to point 0.494, relative to its current position,
    and 3 points on the 'ms2r' motor, from point 0.488 to point 0.49, without snaking, with the 'ms2l' axis changing the slowest:

                        |--------------------------------------|
              0.490     |-----x----->------x------>-----x------|
                        |------------------<-------------------|
              0.492     |-----x----->------x------>-----x------|
                        |------------------<-------------------|
              0.494     |-----x----->------x------>-----x------|
                        |--------------------------------------|
                           0.4880       0.4890       0.4900
    ms2l position (rel)           ms2r position (rel)

    The exposure time used is the one set before the scan on the IOC.

rel_grid_scan ms2r 0.488 0.49 3 ms2l 0.49 0.494 3 0.1 -s
    Make a 2D scan over 3 points on the 'ms2r' motor, from point 0.488 to point 0.49, relative to its current position,
    and 3 points on the 'ms2l' motor, from point 0.49 to point 0.494, with snaking, with the 'ms2r' axis changing
    the slowest, and per-point exposure time equal to 0.1 seconds:

                        |--------------------------------|
              0.490     |-----x---------x---->----x------|
                        |-----|---------|---------|------|
              0.492     |-----x---------x---------x------|
                        |-----|---------|---------|------|
              0.494     |-----x---->----x---------x------|
                        |--------------------------------|
                           0.4880    0.4890    0.4900
    ms2l position (rel)        ms2r position (rel)

"""


class EScanRangeAction(argparse.Action):
    """
    Custom argparse Action to parse energy and k-space ranges.

    This action deals with 2 and 3-element k-space range specifications,
    and maintains the range ordering in the populated tuples. This means
    that it provides support for later stages to calculate missing start
    positions (None as the start position), based on the last sequential
    range provided by the user.

    It populates the namespace with two keys, 'e' and 'k', each being a
    list of tuples of the form:
        (range index, start position (can be None), end position, step)
    """

    def __call__(self, parser, namespace, values, option_string):
        if not hasattr(namespace, "_current_range_index"):
            namespace._current_range_index = 0

        match option_string:
            case "-e":
                if namespace.e is None:
                    namespace.e = []

                n_values = len(values)
                if n_values == 3:
                    namespace.e.append(tuple([namespace._current_range_index, *values]))
                else:
                    raise Exception(f"Can only specify an energy range with 3 values, not {n_values}.")

            case "-k":
                if namespace.k is None:
                    namespace.k = []

                n_values = len(values)
                if n_values == 2:
                    if namespace._current_range_index == 0:
                        raise Exception("You need to specify a range with a start position before specifying one without.")
                    namespace.k.append(tuple([namespace._current_range_index, None, *values]))
                elif n_values == 3:
                    namespace.k.append(tuple([namespace._current_range_index, *values]))
                else:
                    raise Exception(f"Can only specify a k-space range with 2 ou 3 values, not {n_values}.")

        namespace._current_range_index += 1


class PlanEScan(BaseScanCLI):
    def _usage(self):
        return "%(prog)s [-e start stop step] [-r energy] [-k [start] stop step] [-e0 initial_energy] [-t acquisition_time] [-st settling_time]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("-e", nargs="+", type=float, action=EScanRangeAction, help="Specify an energy range (in eV), with a step size (in eV).")
        _a.add_argument("-r", "--relative_to", type=float, default=0, help="Calculate all energies relative to this one, in eV.")
        _a.add_argument("-k", nargs="+", type=float, action=EScanRangeAction, help="Specify a K-space range (start stop step_size).")

        _a.add_argument("-e0", "--initial_energy", type=float, help="Initial energy value, in eV.")

        _a.add_argument("-st", "--settling_time", type=int, default=250, help="Time (ms) to wait after DCM movement for settling. Default: 250ms")
        _a.add_argument("-t", "--acquisition_time", type=int, default=1000, help="Time (ms) for each acquisition pulse. Default: 1000ms")

        _a.add_argument("--no-use-undulator", action="store_true", help="Don't change undulator parameters in this plan.")
        _a.add_argument("--no-use-crio01", action="store_true", help="Don't change or trigger CRIO01 parameters in this plan.")
        _a.add_argument("--no-use-crio02", action="store_true", help="Don't change or trigger CRIO02 parameters in this plan.")

        return _a

    def _create_plan(self, parsed_namespace, local_ns):
        if len(parsed_namespace.detectors) == 0:
            parsed_namespace.detectors = ["i0c", "i1c"]
        parsed_namespace.detectors.extend(["dcm_energy"])
        use_vortex = any("xrf" in det for det in parsed_namespace.detectors)

        detectors = self.get_real_devices_if_needed(parsed_namespace.detectors, local_ns)

        energy_ranges = parsed_namespace.e
        if energy_ranges is None:
            energy_ranges = []
        k_ranges = parsed_namespace.k
        if k_ranges is None:
            k_ranges = []

        r = parsed_namespace.relative_to
        energy_ranges = [(idx, x + r, y + r, s) for idx, x, y, s in energy_ranges]

        initial_energy = parsed_namespace.initial_energy

        settle_time = parsed_namespace.settling_time
        acq_time = parsed_namespace.acquisition_time

        use_undulator = not parsed_namespace.no_use_undulator
        use_crio01 = not parsed_namespace.no_use_crio01
        use_crio02 = not parsed_namespace.no_use_crio02

        md = self.parse_md(*parsed_namespace.detectors, ns=parsed_namespace)

        if "metadata_save_file_location" not in md:
            md["metadata_save_file_location"] = os.getcwd()

        # Assonant metadata
        md["experimental_technique"] = "XAS"
        md["experiment_stage"] = "sample_acquisition"

        plan_args = (detectors, energy_ranges, k_ranges)
        plan_kwargs = dict(initial_energy=initial_energy, md=md, settling_time=settle_time, acquisition_time=acq_time, use_undulator=use_undulator, use_crio01=use_crio01, use_crio02=use_crio02, use_vortex=use_vortex)
        return plan_args, plan_kwargs


class PlanEScanFly(BaseScanCLI):
    def _usage(self):
        return "%(prog)s [-e start stop velocity] [-r energy] [-t acquisition_time] [-st settling_time]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("-e", nargs="+", type=float, action=EScanRangeAction, help="Specify an energy range (in eV), with a velocity (in eV/s).")
        _a.add_argument("-r", "--relative_to", type=float, default=0, help="Calculate all energies relative to this one, in eV.")

        _a.add_argument("-st", "--settling_time", type=int, default=250, help="Time (ms) to wait after DCM movement for settling. Default: 250ms")
        _a.add_argument("-t", "--acquisition_time", type=int, default=1000, help="Time (ms) for each acquisition pulse. Default: 1000ms")

        _a.add_argument("--no-use-undulator", action="store_true", help="Don't change undulator parameters in this plan.")
        _a.add_argument("--no-use-crio01", action="store_true", help="Don't change or trigger CRIO01 parameters in this plan.")
        _a.add_argument("--no-use-crio02", action="store_true", help="Don't change or trigger CRIO02 parameters in this plan.")

        return _a

    def _create_plan(self, parsed_namespace, local_ns):
        if len(parsed_namespace.detectors) == 0:
            parsed_namespace.detectors = ["i0c", "i1c"]
        parsed_namespace.detectors.extend(["dcm_energy"])
        use_vortex = any("xrf" in det for det in parsed_namespace.detectors)

        detectors = self.get_real_devices_if_needed(parsed_namespace.detectors, local_ns)

        energy_ranges = parsed_namespace.e
        if energy_ranges is None:
            energy_ranges = []

        r = parsed_namespace.relative_to
        energy_ranges = [(idx, x + r, y + r, v) for idx, x, y, v in energy_ranges]

        settle_time = parsed_namespace.settling_time
        acq_time = parsed_namespace.acquisition_time

        use_undulator = not parsed_namespace.no_use_undulator
        use_crio01 = not parsed_namespace.no_use_crio01
        use_crio02 = not parsed_namespace.no_use_crio02

        md = self.parse_md(*parsed_namespace.detectors, ns=parsed_namespace)

        if "metadata_save_file_location" not in md:
            md["metadata_save_file_location"] = os.getcwd()

        # Assonant metadata
        md["experimental_technique"] = "XAS"
        md["experiment_stage"] = "sample_acquisition"

        plan_args = (detectors, energy_ranges)
        plan_kwargs = dict(md=md, settling_time=settle_time, acquisition_time=acq_time, use_undulator=use_undulator, use_crio01=use_crio01, use_crio02=use_crio02, use_vortex=use_vortex)
        return plan_args, plan_kwargs


class PlanMoveEnergy(PlanCLI):
    def _usage(self):
        return "%(prog)s energy"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("energy", type=float, help="Energy to move to, in eV.")

        return _a

    def _create_plan(self, parsed_namespace, local_ns):
        energy = parsed_namespace.energy

        md = self.parse_md(ns=parsed_namespace)

        return (energy,), {"md": md}


class PlanGridEnergyScan(BaseScanCLI):
    absolute: bool

    def _usage(self):
        return "%(prog)s motor start stop num motor start stop num [-s/--snake] [-e start stop step] [-r energy] [-k [start] stop step] [-e0 initial_energy] [-t acquisition_time] [-st settling_time]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("first_motor", nargs=1, type=str, help="Mnemonic of the motor on the slowest axis to move.")
        _a.add_argument("first_start", type=float, help="Start position of the first motor, in the motor's EGU.")
        _a.add_argument("first_stop", type=float, help="End position of the first motor, in the motor's EGU.")
        _a.add_argument("first_num", type=int, help="Number of steps between the start and end positions of the first motor.")
        _a.add_argument("second_motor", nargs=1, type=str, help="Mnemonic of the motor on the second slowest axis to move.")
        _a.add_argument("second_start", type=float, help="Start position of the second motor, in the motor's EGU.")
        _a.add_argument("second_stop", type=float, help="End position of the second motor, in the motor's EGU.")
        _a.add_argument("second_num", type=int, help="Number of steps between the start and end positions of the second motor.")
        _a.add_argument("-s", "--snake", action="store_true", help="Whether to snake axes or not. The default behavior is to not snake.")

        _a.add_argument("-e", nargs="+", type=float, action=EScanRangeAction, help="Specify an energy range (in eV), with a step size (in eV).")
        _a.add_argument("-r", "--relative_to", type=float, default=0, help="Calculate all energies relative to this one, in eV.")
        _a.add_argument("-k", nargs="+", type=float, action=EScanRangeAction, help="Specify a K-space range (start stop step_size).")

        _a.add_argument("-e0", "--initial_energy", type=float, help="Initial energy value, in eV.")

        _a.add_argument("-st", "--settling_time", type=int, default=250, help="Time (ms) to wait after DCM movement for settling. Default: 250ms")
        _a.add_argument("-t", "--acquisition_time", type=int, default=1000, help="Time (ms) for each acquisition pulse. Default: 1000ms")

        _a.add_argument("--no-use-undulator", action="store_true", help="Don't change undulator parameters in this plan.")
        _a.add_argument("--no-use-crio01", action="store_true", help="Don't change or trigger CRIO01 parameters in this plan.")
        _a.add_argument("--no-use-crio02", action="store_true", help="Don't change or trigger CRIO02 parameters in this plan.")

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        parsed_namespace.detectors.extend(["dcm_energy"])
        use_vortex = any("xrf" in det for det in parsed_namespace.detectors)

        detectors = self.get_real_devices_if_needed(parsed_namespace.detectors, local_ns)

        args = [
            parsed_namespace.first_motor[0],
            parsed_namespace.first_start,
            parsed_namespace.first_stop,
            parsed_namespace.first_num,
            parsed_namespace.second_motor[0],
            parsed_namespace.second_start,
            parsed_namespace.second_stop,
            parsed_namespace.second_num,
        ]
        args, _, motor_names = self.parse_varargs(args, local_ns=local_ns)

        snake = parsed_namespace.snake

        energy_ranges = parsed_namespace.e
        if energy_ranges is None:
            energy_ranges = []
        k_ranges = parsed_namespace.k
        if k_ranges is None:
            k_ranges = []

        r = parsed_namespace.relative_to
        energy_ranges = [(idx, x + r, y + r, s) for idx, x, y, s in energy_ranges]

        initial_energy = parsed_namespace.initial_energy

        settle_time = parsed_namespace.settling_time
        acq_time = parsed_namespace.acquisition_time

        use_undulator = not parsed_namespace.no_use_undulator
        use_crio01 = not parsed_namespace.no_use_crio01
        use_crio02 = not parsed_namespace.no_use_crio02

        md = self.parse_md(*parsed_namespace.detectors, *motor_names, ns=parsed_namespace)

        if "metadata_save_file_location" not in md:
            md["metadata_save_file_location"] = os.getcwd()

        hdf_file_name, hdf_file_path = self.parse_hdf_args(parsed_namespace, "energy_gridscan_%H_%M_%S")

        after_plan_behavior = self.get_after_plan_behavior_argument(parsed_namespace)
        after_plan_target = self.get_after_plan_target_argument(parsed_namespace)

        plan_args = (detectors, *args)
        plan_kwargs = dict(
            snake_axes=snake,
            hdf_file_name=hdf_file_name,
            hdf_file_path=hdf_file_path,
            absolute=self.absolute,
            after_plan_behavior=after_plan_behavior,
            after_plan_target=after_plan_target,
            using_steps_instead_of_points=False,
            energy_ranges=energy_ranges,
            k_ranges=k_ranges,
            initial_energy=initial_energy,
            md=md,
            settling_time=settle_time,
            acquisition_time=acq_time,
            use_undulator=use_undulator,
            use_crio01=use_crio01,
            use_crio02=use_crio02,
            use_vortex=use_vortex
        )

        return plan_args, plan_kwargs


class PlanAbsGridEnergyScan(PlanGridEnergyScan):
    absolute = True


class PlanRelGridEnergyScan(PlanGridEnergyScan):
    absolute = False
