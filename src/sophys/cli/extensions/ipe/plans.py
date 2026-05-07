from sophys.cli.core.magics.plan_magics import PlanCLI


class PlanXAS(PlanCLI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hide_args.add("detectors")

    def _usage(self):
        return "%(prog)s start stop step [start stop step ...]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("args", nargs='+', type=float, help="Scan trajectory parameters (start stop step)")

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        assert len(parsed_namespace.args) % 3 == 0, "The number of arguments passed is incorrect."

        return parsed_namespace.args, {}


class PlanMesh(PlanCLI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hide_args.add("detectors")

    def _usage(self):
        return "%(prog)s y (start stop step) x (start stop step) y_motor x_motor exposure [--no-snake]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("y_start", type=float, nargs=1, default=None, help="Starting position of the Y motor.")
        _a.add_argument("y_stop", type=float, nargs=1, default=None, help="Ending position of the Y motor.")
        _a.add_argument("y_step", type=float, nargs=1, default=None, help="Step size between points of the Y motor trajectory.")
        _a.add_argument("x_start", type=float, nargs=1, default=None, help="Starting position of the X motor.")
        _a.add_argument("x_stop", type=float, nargs=1, default=None, help="Ending position of the X motor.")
        _a.add_argument("x_step", type=float, nargs=1, default=None, help="Step size between points of the X motor trajectory.")

        _a.add_argument("y_motor", type=str, default="y", help="One of 'sx', 'x', 'y', 'z' or 'ry'. Defaults to 'y'.")
        _a.add_argument("x_motor", type=str, default="sx", help="One of 'sx', 'x', 'y', 'z' or 'ry'. Defaults to 'sx'.")

        _a.add_argument("exposure", type=float, default=0.1, help="Exposure time for each point in the mesh. Defaults to 0.1 seconds.")

        _a.add_argument("--no-snake", action="store_true", help="Do not traverse the mesh in a snaking manner.")

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        _p = parsed_namespace

        _args = (_p.y_start, _p.y_stop, _p.y_step, _p.x_start, _p.x_stop, _p.x_step, _p.y_motor, _p.x_motor, not _p.no_snake, _p.exposure)

        return _args, {}


class PlanHardwareScan(PlanCLI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hide_args.add("detectors")

    def _usage(self):
        return "%(prog)s motor config start stop step [exposure_time]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("motor", type=str, nargs=1, default=None, help="One of 'x', 'y' or 'z'.")
        _a.add_argument("config", type=str, nargs=1, default=None, help="Configuration to use. One of 'kinetic' or 'real'.")
        _a.add_argument("start", type=float, nargs=1, default=None, help="Starting position of the motor.")
        _a.add_argument("stop", type=float, nargs=1, default=None, help="Ending position of the motor.")
        _a.add_argument("step", type=float, nargs=1, default=None, help="Step size between points of the motor trajectory.")
        _a.add_argument("exposure_time", type=float, default=0.1, help="Exposure time in seconds of the detector. Default to 0.1")

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        _p = parsed_namespace

        _args = (_p.start, _p.stop, _p.step, _p.motor, _p.config, _p.exposure_time)

        return _args, {}


class PlanHardwareGridScan(PlanCLI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hide_args.add("detectors")

    def _usage(self):
        return "%(prog)s motor_1 motor_2 config start_1 stop_1 step_1 start_2 stop_2 step_2 [exposure_time]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("motor_1", type=str, nargs=1, default=None, help="Motor moving the slowest. One of 'x', 'y' or 'z'.")
        _a.add_argument("motor_2", type=str, nargs=1, default=None, help="Motor moving the fastest. One of 'x', 'y' or 'z'.")
        _a.add_argument("config", type=str, nargs=1, default=None, help="Configuration to use. One of 'kinetic' or 'real'.")
        _a.add_argument("start_1", type=float, nargs=1, default=None, help="Starting position of the first motor.")
        _a.add_argument("stop_1", type=float, nargs=1, default=None, help="Ending position of the first motor.")
        _a.add_argument("step_1", type=float, nargs=1, default=None, help="Step size between points of the first motor trajectory.")
        _a.add_argument("start_2", type=float, nargs=1, default=None, help="Starting position of the second motor.")
        _a.add_argument("stop_2", type=float, nargs=1, default=None, help="Ending position of the second motor.")
        _a.add_argument("step_2", type=float, nargs=1, default=None, help="Step size between points of the second motor trajectory.")
        _a.add_argument("exposure_time", type=float, default=0.1, help="Exposure time in seconds of the detector. Default to 0.1")

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        _p = parsed_namespace

        _args = (_p.start, _p.stop, _p.step, _p.motor, _p.config, _p.exposure_time)

        return _args, {}

class PlanSetEnergy(PlanCLI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hide_args.add("detectors")

    def _usage(self):
        return "%(prog)s energy"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("energy", type=float, help="Energy setpoint to configure.")

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        return parsed_namespace.args, {}


class PlanSetScale(PlanCLI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hide_args.add("detectors")

    def _usage(self):
        return "%(prog)s counter scale unit"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("counter", type=str, help="Counter to configure. One of 'tey', 'fy' or 'i0'.")
        _a.add_argument("scale", type=int, help="Nominal scale to configure. One of '1', '2', '5', '10', '20', '50', '100', '200' or '500'.")
        _a.add_argument("unit", type=str, help="Unit of the scale. One of 'pA/V', 'nA/V', 'uA/V' or 'mA/V'.")

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        return parsed_namespace.args, {}


class PlanRIXS(PlanCLI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hide_args.add("detectors")

    def _usage(self):
        return "%(prog)s exposure image_number [energy]"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("exposure", type=float, help="Exposure time in seconds.")
        _a.add_argument("image_number", type=int, help="Number of images to capture.")
        _a.add_argument("energy", type=float, default=None, help="Energy to make the scan in.")

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        return parsed_namespace.args, {}


class PlanRIXSEMap(PlanCLI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hide_args.add("detectors")

    def _usage(self):
        return "%(prog)s start stop step (start stop step...) exposure image_number"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("ranges", nargs='+', type=float, help="Scan trajectory parameters (start stop step)")
        _a.add_argument("exposure", type=float, help="Exposure time in seconds.")
        _a.add_argument("image_number", type=int, help="Number of images to capture.")

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        assert len(parsed_namespace.args) % 3 == 0, "The number of arguments passed is incorrect."

        return parsed_namespace.args, {}


class PlanMoveManipulator(PlanCLI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hide_args.add("detectors")

    def _usage(self):
        return "%(prog)s x y z ry"

    def create_parser(self):
        _a = super().create_parser()

        _a.add_argument("x", type=float, help="X position to send the manipulator to.")
        _a.add_argument("y", type=float, help="Y position to send the manipulator to.")
        _a.add_argument("z", type=float, help="Z position to send the manipulator to.")
        _a.add_argument("ry", type=float, help="Ry rotation to send the manipulator to.")

        return _a

    def _create_plan_arguments(self, parsed_namespace, local_ns):
        return parsed_namespace.args, {}
