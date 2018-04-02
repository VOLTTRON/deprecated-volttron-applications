"""
-*- coding: utf-8 -*- {{{
vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

Copyright (c) 2017, Battelle Memorial Institute
All rights reserved.

1.  Battelle Memorial Institute (hereinafter Battelle) hereby grants
    permission to any person or entity lawfully obtaining a copy of this
    software and associated documentation files (hereinafter "the Software")
    to redistribute and use the Software in source and binary forms, with or
    without modification.  Such person or entity may use, copy, modify, merge,
    publish, distribute, sublicense, and/or sell copies of the Software, and
    may permit others to do so, subject to the following conditions:

    -   Redistributions of source code must retain the above copyright notice,
        this list of conditions and the following disclaimers.

    -	Redistributions in binary form must reproduce the above copyright
        notice, this list of conditions and the following disclaimer in the
        documentation and/or other materials provided with the distribution.

    -	Other than as used herein, neither the name Battelle Memorial Institute
        or Battelle may be used in any form whatsoever without the express
        written consent of Battelle.

2.	THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
    AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
    IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
    ARE DISCLAIMED. IN NO EVENT SHALL BATTELLE OR CONTRIBUTORS BE LIABLE FOR
    ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
    DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
    SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
    CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
    LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
    OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
    DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the FreeBSD Project.

This material was prepared as an account of work sponsored by an agency of the
United States Government. Neither the United States Government nor the United
States Department of Energy, nor Battelle, nor any of their employees, nor any
jurisdiction or organization that has cooperated in the development of these
materials, makes any warranty, express or implied, or assumes any legal
liability or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed, or
represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or service by
trade name, trademark, manufacturer, or otherwise does not necessarily
constitute or imply its endorsement, recommendation, or favoring by the
United States Government or any agency thereof, or Battelle Memorial Institute.
The views and opinions of authors expressed herein do not necessarily state or
reflect those of the United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by
BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
}}}
"""
import re
from sympy import symbols
import logging
from collections import defaultdict
from sympy.parsing.sympy_parser import parse_expr
from volttron.platform.agent.utils import setup_logging


setup_logging()
_log = logging.getLogger(__name__)


def parse_sympy(data, condition=False):
    """
    :param condition:
    :param data:
    :return:
    """

    def clean_text(text, rep={" ": ""}):
        rep = dict((re.escape(k), v) for k, v in rep.iteritems())
        pattern = re.compile("|".join(rep.keys()))
        new_key = pattern.sub(lambda m: rep[re.escape(m.group(0))], text)
        return new_key

    if isinstance(data, dict):
        return_data = {}
        for key, value in data.items():
            new_key = clean_text(key)
            return_data[new_key] = value

    elif isinstance(data, list):
        if condition:
            return_data = ""
            for item in data:
                parsed_string = clean_text(item)
                parsed_string = "(" + clean_text(item) + ")" if parsed_string not in ("&", "|") else parsed_string
                return_data += parsed_string
        else:
            return_data = []
            for item in data:
                return_data.append(clean_text(item))
    else:
        return_data = clean_text(data)
    return return_data


class CurtailmentCluster(object):
    def __init__(self, cluster_config, actuator):
        self.devices = {}
        for device_name, device_config in cluster_config.items():
            self.devices[device_name, actuator] = CurtailmentManager(device_config)

    def get_all_on_devices(self):
        results = []
        for device_info, device in self.devices.items():
            for device_id in device.get_on_commands():
                results.append((device_info[0], device_id, device_info[1]))
        return results


class CurtailmentContainer(object):
    def __init__(self):
        self.clusters = []
        self.devices = {}

    def add_curtailment_cluster(self, cluster):
        self.clusters.append(cluster)
        self.devices.update(cluster.devices)

    def get_device_name_list(self):
        return self.devices.keys()

    def get_device(self, device_name):
        return self.devices[device_name]

    def reset_curtail_count(self):
        for device in self.devices.itervalues():
            device.reset_curtail_count()

    def reset_currently_curtailed(self):
        for device in self.devices.itervalues():
            for device_id in self.command_status:
                device.reset_currently_curtailed(device_id)

    def get_on_devices(self):
        all_on_devices = []
        for cluster in self.clusters:
            on_device = cluster.get_all_on_devices()
            all_on_devices.extend(on_device)
        return all_on_devices


class CurtailmentManager(object):
    def __init__(self, device_config):
        self.conditional_curtailments = defaultdict(list)
        self.command_status = {}
        self.device_status_args = {}
        self.condition = {}
        self.points = {}
        self.expr = {}
        self.currently_curtailed = {}
        self.curtail_count = {}
        self.default_curtailment = {}

        for device_id, curtail_config in device_config.items():
            default_curtailment = curtail_config.pop('curtail')
            conditional_curtailment = curtail_config.pop('conditional_curtail', [])

            for settings in conditional_curtailment:
                conditional_curtailment = ConditionalCurtailment(**settings)
                self.conditional_curtailments[device_id].append(conditional_curtailment)
            self.default_curtailment[device_id] = CurtailmentSetting(**default_curtailment)

            device_status_dict = curtail_config.pop('device_status')
            device_status_args = parse_sympy(device_status_dict['device_status_args'])
            condition = device_status_dict['condition']

            self.device_status_args[device_id] = device_status_args
            self.condition[device_id] = parse_sympy(condition, condition=True)
            self.points[device_id] = symbols(device_status_args)
            self.expr[device_id] = parse_expr(self.condition[device_id])

            self.command_status[device_id] = False
            self.curtail_count[device_id] = 0.0
            self.currently_curtailed[device_id] = False

    def ingest_data(self, data):
        for device_id, conditional_curtailment in self.conditional_curtailments.items():
            for conditional_curtail_instance in conditional_curtailment:
                conditional_curtail_instance.ingest_data(data)

        for device_id in self.command_status:
            conditional_points = []
            for item in self.device_status_args[device_id]:
                conditional_points.append((item, data[item]))
            conditional_value = False
            if conditional_points:
                conditional_value = self.expr[device_id].subs(conditional_points)
            _log.debug('{} (device status) evaluated to {}'.format(self.condition[device_id], conditional_value))
            try:
                self.command_status[device_id] = bool(conditional_value)
            except TypeError:
                self.command_status[device_id] = False

    def get_curtailment(self, device_id):
        curtailment = self.default_curtailment[device_id].get_curtailment_dict()

        for conditional_curtailment in self.conditional_curtailments[device_id]:
            if conditional_curtailment.check_condition():
                curtailment = conditional_curtailment.get_curtailment()
                break

        return curtailment

    def reset_curtail_count(self):
        for device_id in self.curtail_count:
            self.curtail_count[device_id] = 0.0

    def increment_curtail(self, device_id):
        self.currently_curtailed[device_id] = True
        self.curtail_count[device_id] += 1.0

    def reset_curtail_status(self, device_id):
        self.currently_curtailed[device_id] = False

    def get_on_commands(self):
        return [command for command, state in self.command_status.iteritems() if state]


class CurtailmentSetting(object):
    def __init__(self, point=None, value=None, load=None, offset=None, maximum=None, minimum=None,
                 revert_priority=None, equation=None, curtailment_method=None):
        if curtailment_method is None:
            raise ValueError("Missing 'curtailment_method' configuration parameter!")
        if point is None:
            raise ValueError("Missing device curtailment 'point' configuration parameter!")
        if load is None:
            raise ValueError("Missing device 'load' estimation configuration parameter!")

        self.point = point
        self.curtailment_method = curtailment_method
        self.value = value

        self.offset = offset
        self.revert_priority = revert_priority
        self.maximum = maximum
        self.minimum = minimum

        if self.curtailment_method.lower() == 'equation':
            self.equation_args = parse_sympy(equation['equation_args'])
            self.points = symbols(self.equation_args)
            self.curtail_value_formula = parse_expr(parse_sympy(equation['operation']))
            self.maximum = equation['maximum']
            self.minimum = equation['minimum']

        if isinstance(load, dict):
            load_args = parse_sympy(load['equation_args'])
            actuator_args = load['equation_args']
            self.load_points = symbols(load_args)
            load_expr = parse_expr(parse_sympy(load['operation']))
            self.load = {
                'load_equation': load_expr,
                'load_equation_args': load_args,
                'actuator_args': actuator_args
            }
        else:
            self.load = load

    def get_curtailment_dict(self):
        if self.curtailment_method.lower() == 'equation':
            return {
                'point': self.point,
                'load': self.load,
                'revert_priority': self.revert_priority,
                'curtail_equation': self.curtail_value_formula,
                'curtail_equation_args': self.equation_args,
                'curtailment_method': self.curtailment_method,
                'maximum': self.maximum,
                'minimum': self.minimum
            }
        elif self.curtailment_method.lower() == 'offset':
            return {
                'point': self.point,
                'load': self.load,
                'offset': self.offset,
                'revert_priority': self.revert_priority,
                'curtailment_method': self.curtailment_method,
                'maximum': self.maximum,
                'minimum': self.minimum
            }
        elif self.curtailment_method.lower() == 'value':
            return {
                'point': self.point,
                'load': self.load,
                'value': self.value,
                'revert_priority': self.revert_priority,
                'curtailment_method': self.curtailment_method,
                'maximum': self.maximum,
                'minimum': self.minimum
            }


class ConditionalCurtailment(object):
    def __init__(self, condition=None, conditional_args=None, **kwargs):
        if None in (condition, conditional_args):
            raise ValueError('Missing parameter')
        self.conditional_args = parse_sympy(conditional_args)
        self.points = symbols(self.conditional_args)
        self.conditional_expr = parse_sympy(condition, condition=True)
        self.conditional_curtail = parse_expr(self.conditional_expr)
        self.curtailment = CurtailmentSetting(**kwargs)
        self.conditional_points = []

    def check_condition(self):
        if self.conditional_points:
            value = self.conditional_curtail.subs(self.conditional_points)
            _log.debug('{} (conditional_curtail) evaluated to {}'.format(self.conditional_expr, value))
        else:
            value = False
        return value

    def ingest_data(self, data):
        point_list = []
        for point in self.conditional_args:
            point_list.append((point, data[point]))
        self.conditional_points = point_list

    def get_curtailment(self):
        return self.curtailment.get_curtailment_dict()
