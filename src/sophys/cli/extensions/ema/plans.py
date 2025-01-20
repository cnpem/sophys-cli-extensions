import argparse
import functools
import os

from sophys.cli.core.magics.plan_magics import ModeOfOperation
from sophys.cli.core.magics.plan_magics import PlanCLI, BPlan


class BaseScanCLI(PlanCLI):
    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("--hdf_file_name", type=str, nargs='?', default=None, help="Save file name for the data HDF5 file generated (if using an AreaDetector). Defaults to 'ascan_hour_minute_second_scanid.h5'.")
        _a.add_argument("--hdf_file_path", type=str, nargs='?', default=None, help="Save path for the data HDF5 file generated (if using an AreaDetector). Defaults to CWD.")

        _a.add_argument("--max", action="store_true", help="Go to the point of the scan with maximum value at the end.")
        _a.add_argument("--after_plan_target", type=str, nargs='?', help=argparse.SUPPRESS)

        return _a

    def parse_hdf_args(self, parsed_namespace, template: str | None = None):
        template = parsed_namespace.hdf_file_name or template

        from datetime import datetime
        hdf_file_name = datetime.now().strftime(template)

        hdf_file_path = parsed_namespace.hdf_file_path
        if hdf_file_path is None:
            hdf_file_path = os.getcwd()

        return hdf_file_name, hdf_file_path

    def get_after_plan_behavior_argument(self, parsed_namespace):
        if parsed_namespace.max:
            return "max"
        return "return"

    def get_after_plan_target_argument(self, parsed_namespace, local_ns):
        if not parsed_namespace.after_plan_target:
            if len(parsed_namespace.detectors) == 1:
                return parsed_namespace.detectors[0]
        return parsed_namespace.after_plan_target


class PlanNDScan(BaseScanCLI):
    absolute: bool

    def _usage(self):
        return "%(prog)s motor start stop [motor start stop ...] num [exposure_time] [--hdf_file_path] [--hdf_file_name] [--md key=value key=value ...]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("args", nargs='+', type=str, help="Motor informations, in order (mnemonic start_position end_position)")
        # NOTE: These two are not used in parsing, they're only here for documentation. Their values are taken from args instead.
        _a.add_argument("num", type=int, nargs='?', default=None, help="Number of points between the start and end positions.")
        _a.add_argument("exposure_time", type=float, nargs='?', default=None, help="Per-point exposure time of the detector. Defaults to using the previously defined exposure time on the IOC.")

        return _a

    def _create_plan(self, parsed_namespace, local_ns):
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

        hdf_file_name, hdf_file_path = self.parse_hdf_args(parsed_namespace, "ascan_%H_%M_%S")

        if "metadata_save_file_location" not in md:
            md["metadata_save_file_location"] = hdf_file_path

        after_plan_behavior = self.get_after_plan_behavior_argument(parsed_namespace)
        after_plan_target = self.get_after_plan_target_argument(parsed_namespace, local_ns)

        if self._mode_of_operation == ModeOfOperation.Local:
            return functools.partial(self._plan, detector, *args, number_of_points=num, exposure_time=exp_time, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, absolute=self.absolute, after_plan_behavior=after_plan_behavior, after_plan_target=after_plan_target)
        if self._mode_of_operation == ModeOfOperation.Remote:
            return BPlan(self._plan_name, detector, *args, number_of_points=num, exposure_time=exp_time, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, absolute=self.absolute, after_plan_behavior=after_plan_behavior, after_plan_target=after_plan_target)


class PlanGridScan(BaseScanCLI):
    absolute: bool

    def _usage(self):
        return "%(prog)s motor start stop num motor start stop num [motor start stop num ...] [exposure_time] [-s/--snake] [--hdf_file_path] [--hdf_file_name] [--md key=value key=value ...]"

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

        hdf_file_name, hdf_file_path = self.parse_hdf_args(parsed_namespace, "gridscan_%H_%M_%S")

        if "metadata_save_file_location" not in md:
            md["metadata_save_file_location"] = hdf_file_path

        after_plan_behavior = self.get_after_plan_behavior_argument(parsed_namespace)
        after_plan_target = self.get_after_plan_target_argument(parsed_namespace, local_ns)

        if self._mode_of_operation == ModeOfOperation.Local:
            return functools.partial(self._plan, detector, *args, exposure_time=exp_time, snake_axes=snake, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, absolute=self.absolute, after_plan_behavior=after_plan_behavior, after_plan_target=after_plan_target)
        if self._mode_of_operation == ModeOfOperation.Remote:
            return BPlan(self._plan_name, detector, *args, exposure_time=exp_time, snake_axes=snake, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, absolute=self.absolute, after_plan_behavior=after_plan_behavior, after_plan_target=after_plan_target)


class PlanGridScanWithJitter(BaseScanCLI):
    def _usage(self):
        return "%(prog)s motor start stop num motor start stop num [motor start stop num ...] [exposure_time] [-s/--snake] [--hdf_file_path] [--hdf_file_name] [--md key=value key=value ...]"

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
        after_plan_target = self.get_after_plan_target_argument(parsed_namespace, local_ns)

        if self._mode_of_operation == ModeOfOperation.Local:
            return functools.partial(self._plan, detector, *args, exposure_time=exp_time, snake_axes=snake, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, after_plan_behavior=after_plan_behavior, after_plan_target=after_plan_target)
        if self._mode_of_operation == ModeOfOperation.Remote:
            return BPlan(self._plan_name, detector, *args, exposure_time=exp_time, snake_axes=snake, md=md, hdf_file_name=hdf_file_name, hdf_file_path=hdf_file_path, after_plan_behavior=after_plan_behavior, after_plan_target=after_plan_target)


class PlanMotorOrigin(PlanCLI):
    def _usage(self):
        return "%(prog)s motor [position] [--md key=value key=value ...]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("motor", nargs=1, type=str, help="Mnemonic of a motor to set the origin of.")
        _a.add_argument("position", type=float, help="Position of the motor to set as origin. Default: current position.", default=None, nargs='?')

        return _a

    def _create_plan(self, parsed_namespace, local_ns):
        motor = self.get_real_devices_if_needed(parsed_namespace.motor, local_ns)[0]
        position = parsed_namespace.position

        md = self.parse_md(parsed_namespace.motor[0], ns=parsed_namespace)

        if self._mode_of_operation == ModeOfOperation.Local:
            return functools.partial(self._plan, motor, position, md=md)
        if self._mode_of_operation == ModeOfOperation.Remote:
            return BPlan(self._plan_name, motor, position, md=md)


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
