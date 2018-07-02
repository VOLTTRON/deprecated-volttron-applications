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
import abc
from sympy import symbols
from sympy.core import numbers
from sympy.parsing.sympy_parser import parse_expr
from collections import deque
import logging
from datetime import timedelta as td
from volttron.platform.agent.utils import setup_logging
from ilc.ilc_matrices import (extract_criteria, calc_column_sums, normalize_matrix,
                              validate_input, build_score, input_matrix)
setup_logging()
_log = logging.getLogger(__name__)

criterion_registry = {}


def register_criterion(name):
    def decorator(klass):
        criterion_registry[name] = klass
        return klass
    return decorator


def parse_sympy(data, condition=False):
    """
    Parser for sympy.
    :param data:
    :param condition:
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
    #_log.debug("Parsing: {} to {}".format(data, return_data))
    return return_data


class CriteriaCluster(object):
    def __init__(self, priority, criteria_labels, row_average, cluster_config):
        self.criteria = {}
        self.priority = priority
        self.criteria_labels = criteria_labels
        self.row_average = row_average
        global mappers
        try:
            mappers = cluster_config.pop("mappers")
        except KeyError:
            mappers = {}

        for device_name, device_criteria in cluster_config.items():
            self.criteria[device_name] = DeviceCriteria(device_criteria)

    def get_all_evaluations(self):
        results = {}
        for name, device in self.criteria.items():
            for device_id in device.criteria.keys():
                evaluations = device.evaluate(device_id)
                results[name, device_id] = evaluations
        return results


class CriteriaContainer(object):
    def __init__(self):
        self.clusters = []
        self.devices = {}

    def add_criteria_cluster(self, cluster):
        self.clusters.append(cluster)
        self.devices.update(cluster.criteria)

    def get_score_order(self):
        all_scored = []
        for cluster in self.clusters:
            evaluations = cluster.get_all_evaluations()

            _log.debug('Device Evaluations: ' + str(evaluations))

            if not evaluations:
                continue

            input_arr = input_matrix(evaluations, cluster.criteria_labels)
            scores = build_score(input_arr, cluster.row_average, cluster.priority)
            all_scored.extend(scores)

            _log.debug('Input Array: ' + str(input_arr))
            _log.debug('Scored devices: ' + str(scores))

        all_scored.sort(reverse=True)
        results = [x[1] for x in all_scored]

        return results

    def get_device(self, device_name):
        return self.devices[device_name]


class DeviceCriteria(object):
    def __init__(self, criteria_config):
        self.criteria = {}
        self.points = {}
        self.expressions = {}
        self.condition = {}

        for device_id, device_criteria in criteria_config.items():
            criteria = Criteria(device_criteria)
            self.criteria[device_id] = criteria

    def ingest_data(self, time_stamp, data):
        for criteria in self.criteria.values():
            criteria.ingest_data(time_stamp, data)

    def criteria_status(self, token, status):
        self.criteria[token].criteria_status(status)

    def evaluate(self, token):
        return self.criteria[token].evaluate()


class Criteria(object):
    def __init__(self, criteria):
        self.criteria = {}
        for name, criterion in criteria.items():
            self.add(name, criterion)

    def add(self, name, criterion):
        _log.debug("Criteria: {}".format(criterion))
        operation_type = criterion.pop('operation_type')
        klass = criterion_registry[operation_type]
        self.criteria[name] = klass(**criterion)

    def evaluate(self):
        results = {}
        for name, criterion in self.criteria.items():
            result = criterion.evaluate_criterion()
            results[name] = result
        return results

    def ingest_data(self, time_stamp, data):
        for criterion in self.criteria.values():
            criterion.ingest_data(time_stamp, data)

    def criteria_status(self, status):
        for criterion in self.criteria.values():
            criterion.criteria_status(status)


class BaseCriterion(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, minimum=None, maximum=None):
        self.min_func = (lambda x: x) if minimum is None else (lambda x: max(x, minimum))
        self.max_func = (lambda x: x) if maximum is None else (lambda x: min(x, maximum))
        self.minimum = minimum
        self.maximum = maximum

    def numeric_check(self, value):
        """
        Ensure the value returned by a criteria is a numeric type.  If the value of a criteria is non-numeric the value
        will be converted if possible.  If it is not the fall-back will be to return zero.
        :param value:
        :return:
        """
        if not isinstance(value, (int, float, long, numbers.Float, numbers.Integer)):
            if isinstance(value, str):
                try:
                    value = float(value)
                except ValueError:
                    value = 0.0
            elif isinstance(value, complex):
                value = value.real
            else:
                value = 0.0
        return value

    def evaluate_bounds(self, value):
        """
        If the value of the evaluated criteria is less than the minimum or greater than the maximum configured value for
        the criteria return the minimum or maximum value respectively.
        :param value:
        :return:
        """
        value = self.min_func(value)
        value = self.max_func(value)
        return value

    def evaluate_criterion(self):
        value = self.evaluate()
        value = self.numeric_check(value)
        value = self.evaluate_bounds(value)
        return value

    @abc.abstractmethod
    def evaluate(self):
        pass

    def ingest_data(self, time_stamp, data):
        pass

    def criteria_status(self, status):
        pass


@register_criterion('status')
class StatusCriterion(BaseCriterion):
    def __init__(self, on_value=None, off_value=0.0, point_name=None, **kwargs):
        super(StatusCriterion, self).__init__(**kwargs)
        if on_value is None or point_name is None:
            raise ValueError('Missing parameter')
        self.on_value = on_value
        self.off_value = off_value
        self.point_name = point_name
        self.current_status = False

    def evaluate(self):
        if self.current_status:
            value = self.on_value
        else:
            value = self.off_value
        return value

    def ingest_data(self, time_stamp, data):
        self.current_status = bool(data[self.point_name])


@register_criterion('constant')
class ConstantCriterion(BaseCriterion):
    def __init__(self, value=None, off_value=0.0, point_name=None, **kwargs):
        super(ConstantCriterion, self).__init__(**kwargs)
        if value is None:
            raise ValueError('Missing parameter')
        self.value = value

    def evaluate(self):
        return self.value


@register_criterion('formula')
class FormulaCriterion(BaseCriterion):
    def __init__(self, operation=None, operation_args=None, **kwargs):
        super(FormulaCriterion, self).__init__(**kwargs)
        if operation is None or operation_args is None:
            raise ValueError('Missing parameter')

        # backward compatibility with older configuration files
        if isinstance(operation_args, list):
            operation_args = {arg: "always" for arg in operation_args}

        operation_points = operation_args.keys()
        self.operation_parms = operation_args.values()
        print operation_args.keys(), operation_args.values()
        self.operation_args = parse_sympy(operation_points)
        self.points = symbols(self.operation_args)
        self.expr = parse_expr(parse_sympy(operation))
        self.point_list = []
        self.status = False

    def evaluate(self):
        if self.point_list:
            value = self.expr.subs(self.point_list)
        else:
            value = self.minimum
        return value

    def ingest_data(self, time_stamp, data):
        point_list = []
        for point, parm in zip(self.operation_args, self.operation_parms):
            if parm.lower() == "nc" and self.status:
                point_list.append([item for item in self.point_list if item[0] == point].pop())
                _log.debug("device is curtailed use old value: {} -- {} -- {}".format(point, data[point], point_list))
            else:
                _log.debug("device is normal use current value: {} - {}".format(point, data[point]))
                point_list.append((point, data[point]))
        self.point_list = point_list

    def criteria_status(self, status):
        self.status = status


@register_criterion('mapper')
class MapperCriterion(BaseCriterion):
    def __init__(self, dict_name=None, map_key=None, **kwargs):
        super(MapperCriterion, self).__init__(**kwargs)
        if dict_name is None or map_key is None:
            raise ValueError('Missing parameter')
        self.value = mappers[dict_name][map_key]

    def evaluate(self):
        return self.value


@register_criterion('history')
class HistoryCriterion(BaseCriterion):
    def __init__(self, comparison_type=None, point_name=None, previous_time=None, **kwargs):
        super(HistoryCriterion, self).__init__(**kwargs)
        if comparison_type is None or point_name is None or previous_time is None:
            raise ValueError('Missing parameter')
        self.history = deque()
        self.comparison_type = comparison_type
        self.point_name = point_name
        self.previous_time_delta = td(minutes=previous_time)
        self.current_value = None
        self.history_time = None

    def linear_interpolation(self, date1, value1, date2, value2, target_date):
        end_delta_t = (date2 - date1).total_seconds()
        target_delta_t = (target_date - date1).total_seconds()
        return (value2 - value1) * (target_delta_t / end_delta_t) + value1

    def evaluate(self):
        if self.current_value is None:
            return self.minimum

        pre_timestamp, pre_value = self.history.pop()

        if pre_timestamp > self.history_time:
            self.history.append((pre_timestamp, pre_value))
            return self.minimum

        post_timestamp, post_value = self.history.pop()

        while post_timestamp < self.history_time:
            pre_value, pre_timestamp = post_value, post_timestamp
            post_timestamp, post_value = self.history.pop()

        self.history.append((post_timestamp, post_value))
        prev_value = self.linear_interpolation(pre_timestamp, pre_value, post_timestamp, post_value, self.history_time)
        if self.comparison_type == 'direct':
            value = abs(prev_value - self.current_value)
        elif self.comparison_type == 'inverse':
            value = 1 / abs(prev_value - self.current_value)
        return value

    def ingest_data(self, time_stamp, data):
        self.history_time = time_stamp - self.previous_time_delta
        self.current_value = data[self.point_name]
        self.history.appendleft((time_stamp, self.current_value))
