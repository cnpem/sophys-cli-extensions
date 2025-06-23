import argparse
import functools
import os
import typing

from collections import defaultdict

from sophys.cli.core.magics.plan_magics import ModeOfOperation
from sophys.cli.core.magics.plan_magics import PlanCLI, remote_control_available


if remote_control_available:
    from bluesky_queueserver_api.item import BPlan


class Plan_map_m1_m2_feasibility(PlanCLI):
    def _usage(self):
        return "%(prog)s -d DETECTOR [--m1_start FLOAT] [--m1_stop FLOAT] [--m1_num INT] [--m2_start FLOAT] [--m2_stop FLOAT] [--m2_num INT] [--step FLOAT]"

    def create_parser(self):
        parser = super().create_parser()
        parser.add_argument("-d", "--detector", nargs='+', required=True, help="Detector(s) to be used.")
        parser.add_argument("--m1_start", type=float, default=0.0, help="M1 pitch start position.")
        parser.add_argument("--m1_stop", type=float, default=0.0, help="M1 pitch stop position.")
        parser.add_argument("--m1_num", type=int, default=11, help="M1 pitch scan points.")
        parser.add_argument("--m2_start", type=float, default=0.0, help="M2 pitch start position.")
        parser.add_argument("--m2_stop", type=float, default=0.0, help="M2 pitch stop position.")
        parser.add_argument("--m2_num", type=int, default=11, help="M2 pitch scan points.")
        parser.add_argument("--step", type=float, default=None, help="Step size to configure the scan points.")
        return parser

    def _create_plan(self, parsed_namespace, local_ns):
        detectors = self.get_real_devices_if_needed(parsed_namespace.detector, local_ns)
        m1_start = parsed_namespace.m1_start
        m1_stop = parsed_namespace.m1_stop
        m1_num = parsed_namespace.m1_num
        m2_start = parsed_namespace.m2_start
        m2_stop = parsed_namespace.m2_stop
        m2_num = parsed_namespace.m2_num
        step = parsed_namespace.step

        if self._mode_of_operation == "Local":
            return functools.partial(
                self._plan,
                detectors,
                m1_start=m1_start,
                m1_stop=m1_stop,
                m1_num=m1_num,
                m2_start=m2_start,
                m2_stop=m2_stop,
                m2_num=m2_num,
                step=step,
            )
        elif self._mode_of_operation == "Remote":
            return BPlan(
                "map_m1_m2_feasibility",
                detectors,
                m1_start=m1_start,
                m1_stop=m1_stop,
                m1_num=m1_num,
                m2_start=m2_start,
                m2_stop=m2_stop,
                m2_num=m2_num,
                step=step,
            )