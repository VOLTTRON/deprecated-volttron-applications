# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}
import csv
import logging
import sys
import re
import itertools
import datetime as dt
import gevent
from dateutil.parser import parse
import numpy as np
from scipy.stats import norm
import pkgutil

from volttron.platform.agent import utils
from volttron.platform.agent.utils import setup_logging
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.messaging import (headers as headers_mod, topics)

__version__ = "0.1.0"
__author1__ = 'Woohyun Kim <woohyun.kim@pnnl.gov>'
__author2__ = 'Robert Lutes <robert.lutes@pnnl.gov>'
__copyright__ = 'Copyright (c) 2016, Battelle Memorial Institute'
__license__ = 'FreeBSD'
DATE_FORMAT = '%m-%d-%y %H:%M'

setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.info,
                    format='%(asctime)s   %(levelname)-8s %(message)s',
                    datefmt=DATE_FORMAT)


def z_normalization(time_series, data_mean, std_dev):
    if np.prod(data_mean.shape) == 0  or np.prod(std_dev.shape) == 0:
        data_mean = time_series[0].mean(axis=0)
        std_dev = time_series[0].std(axis=0)
    return ((time_series[0] - data_mean) / std_dev), data_mean, std_dev


def paa_transform(ts, n_pieces):
    splitted = np.array_split(ts, n_pieces) ## along columns as we want
    return np.asarray(map(lambda xs: xs.mean(axis=0), splitted))


def sax_transform(ts, alphabet, data_mean, std_dev):
    n_pieces = ts[0].size
    alphabet_sz = len(alphabet)
    thresholds = norm.ppf(np.linspace(1./alphabet_sz, 1-1./alphabet_sz, alphabet_sz-1))

    def translate(ts_values):
        return np.asarray([(alphabet[0] if ts_value < thresholds[0]
                            else (alphabet[-1]
                                  if ts_value > thresholds[-1]
                                  else alphabet[np.where(thresholds <= ts_value)[0][-1]+1]))
                           for ts_value in ts_values])
    normalized_ts, data_mean, std_dev = z_normalization(ts, data_mean, std_dev)
    paa_ts = paa_transform(normalized_ts, n_pieces)
    return np.apply_along_axis(translate, 0, paa_ts), data_mean, std_dev


def compare(s1, s2):
    for i, j in zip(s1, s2):
        if abs(ord(i) - ord(j)) >= 2:
            return abs(ord(i) - ord(j))
        else:
            return 0


def norm_area(n):
    if n == 2:
        return np.power(norm.ppf(0.25), 2)
    elif n == 3:
        return np.power(2*norm.ppf(0.25), 2)
    else:
        return


def create_alphabet_dict(alphabet):
    alphabet_dict = {}
    alphabet_length = len(alphabet)
    for item in xrange(alphabet_length):
        if item <= (alphabet_length - 1)/2:
            alphabet_dict[alphabet[item]] = 0
        else:
            alphabet_dict[alphabet[item]] = 1
    return alphabet_dict


def compare_detected_reference(current_reference, _time, status_array):
    reference_time = [timestamp[0] for timestamp in current_reference]
    reference_status = [status[1] for status in current_reference]
    start_range = reference_time.index(_time[0])
    end_range = reference_time.index(_time[-1]) + 1
    reference_status = reference_status[start_range:end_range]
    compared_status = []
    for ind in xrange(len(status_array)):
        if status_array[ind] == reference_status[ind]:
            compared_status.append(0)
        else:
            compared_status.append(1)
    return [_time, status_array, reference_status, compared_status]
    

def create_confusion_array(detected_series, reference_series):
    occupied = [0, 0]
    unoccupied = [0, 0]
    for reference, detected in zip(reference_series, detected_series):
        if reference == 1:
            if reference == detected:
                occupied[0] += 1
            else:
                occupied[1] += 1
        else:
            if reference == detected:
                unoccupied[0] += 1
            else:
                unoccupied[1] += 1
    return np.array([occupied, unoccupied])


def create_confusion_figure(cm, file_name, title='Confusion occupancy matrix'):
    import matplotlib.pyplot as plt
    cmap=plt.cm.Blues
    plt.imshow(cm, interpolation='nearest', cmap=cmap)
    plt.title(title)

    plt.colorbar()

    target_names = ['occupancy', 'unoccupancy']
    tick_marks = np.arange(len(target_names))

    plt.xticks(tick_marks, target_names)
    plt.yticks(tick_marks, target_names)

    plt.tight_layout()
    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    plt.savefig(file_name)
    plt.close()


class ScheduleDetection(Agent):
    """Symbolic schedule detection.
    """

    def __init__(self, config_path, **kwargs):
        """
        Initializes agent
        :param kwargs: Any driver specific parameters"""

        super(ScheduleDetection, self).__init__(**kwargs)
        config = utils.load_config(config_path)
        self.device = dict((key, config[key]) for key in ['campus', 'building', 'unit'])

        vip_destination = config.get('vip_destination', None)

        self.device_topic = topics.DEVICES_VALUE(campus=self.device.get('campus'),
                                                 building=self.device.get('building'),
                                                 unit=self.device.get('unit'),
                                                 path='',
                                                 point='all')
        self.p_name = config.get('point_name')
        self.no_required_data = 25
        sample = config.get('sample_rate', '30Min')
        self.sample = int(sample[0:2])
        self.sample_str = sample
        self.alphabet = config.get('alphabet', 'abcd')
        self.alphabet_dict = create_alphabet_dict(self.alphabet)
        self.output_directory = config.get('output_directory', './')
        self.data_mean = np.empty(0)
        self.std_dev = np.empty(0)
        def date_parse(dates):
            return [parse(timestamp).time() for timestamp in dates]

        operational_schedule = config.get('operational_schedule')
        self.reference_schedule = None
        if operational_schedule is not None:
            self.operational_schedule = {parse(key).weekday(): date_parse(value) for key, value in operational_schedule.items()}
            self.reference_schedule = self.create_reference_schedule()
        self.initialize()

    def initialize(self):
        self.data_array = []
        self.timestamp_array = []

    def weekly_reset(self):
        self.data_mean = np.empty(0)
        self.std_dev = np.empty(0)

    def check_run_status(self, current_time, no_required_data):
        last_time = self.timestamp_array[-1]
        if self.timestamp_array and last_time.day != current_time.day:
            if len(self.timestamp_array) < no_required_data:
                return None
            return True
        return False 

    @Core.receiver('onstart')
    def starup(self, sender, **kwargs):
        """
        Starts up the agent and subscribes to device topics
        based on agent configuration.
        :param sender:
        :param kwargs: Any driver specific parameters
        :type sender: str"""
        self.initialize()
        _log.info('Subscribing to: {campus}/{building}/{unit}'.format(**self.device))
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.device_topic,
                                  callback=self.new_data)

    def new_data(self, peer, sender, bus, topic, headers, message):
        """Call back method for device data subscription."""
        _log.info('Receiving new data.')
        current_time = parse(headers.get('Date'))
        check_run = False
        data = message[0]
        data_point = data[self.p_name]
        if self.timestamp_array:
            check_run = self.check_run_status(current_time, self.no_required_data)
        if check_run:
            self.timeseries_to_sax()
            self.initialize()
            _log.info('Daily reinitialization.')
        self.timestamp_array.append(current_time)
        self.data_array.append(data_point)

    def timeseries_to_sax(self):
        """Convert time series data to symbolic form."""
        _log.info('Creating SAX from time series.')

        timestamp_array, data_array = self._resample()
        _log.debug('Resampled timestamp: {}'.format(timestamp_array))
        _log.debug('Resampled data array: {}'.format(data_array))

        sax_array = np.array([data_array, timestamp_array])
        index_header = ['Time', 'Detected Status']
        sax_time = [item.time() for item in timestamp_array]
        sax_data, self.data_mean, self.std_dev = sax_transform(sax_array, self.alphabet, self.data_mean, self.std_dev)
        symbolic_array = [item[0] for item in sax_data]
        status_array = [self.alphabet_dict[symbol] for symbol in symbolic_array]
        list_output = [sax_time, status_array]
        file_name = self.output_directory + "SAX-" + str(timestamp_array[0].date())

        if self.reference_schedule is not None:
            current_reference = self.reference_schedule[timestamp_array[0].weekday()]
            list_output = compare_detected_reference(current_reference, sax_time, status_array)
            list_output.append(symbolic_array)
            index_header = ['Time', 'Detected Status', 'Reference Schedule', 'Comparison', 'Alphabet']
            confusion_array = create_confusion_array(list_output[1], list_output[2])
            confusion_loader = pkgutil.find_loader('matplotlib')
            found = confusion_loader is not None
            if found:
                create_confusion_figure(confusion_array, file_name + ".png")

        if timestamp_array[0].weekday() == 6:
            self.weekly_reset()
            _log.info('Weekly reset.')
        _log.info('Logged status: {}'.format(list_output))
        file_name =  file_name + ".csv"
        with open(file_name, 'wb') as f_handle:
            writer = csv.DictWriter(f_handle, fieldnames=index_header, delimiter=',')
            writer.writeheader()
            for val in itertools.izip_longest(*list_output):
                wr = csv.writer(f_handle, dialect='excel')
                wr.writerow(val)
        f_handle.close()

    def _resample(self):
        resampled_timestamp = []
        resampled_data = []
        data_accumulator = []
        first_time = self.timestamp_array[0]
        offset = first_time.minute%self.sample
        first_append = first_time - dt.timedelta(minutes=offset)
        resampled_timestamp.append(first_append)

        while resampled_timestamp[-1] < self.timestamp_array[-1]:
            next_timestamp = resampled_timestamp[-1] + dt.timedelta(minutes=self.sample)
            if next_timestamp.day != self.timestamp_array[-1].day:
                break
            resampled_timestamp.append(next_timestamp)

        _index = 0
        for ts in range(1, len(resampled_timestamp)):
            while self.timestamp_array[_index].replace(second=0, microsecond=0) < resampled_timestamp[ts].replace(second=0, microsecond=0):
                data_accumulator.append(self.data_array.pop(0))
                _index += 1
            resampled_data.append(np.mean(data_accumulator))
            data_accumulator = []
        resampled_data.append(np.mean(self.data_array))

        return resampled_timestamp, resampled_data

    def create_reference_schedule(self):
        match = re.match(r"([0-9]+)([a-z]+)", self.sample_str, re.I)
        match = match.groups()
        reference_schedule = {key: [] for key in self.operational_schedule}
        unoccupied_token = dt.time(hour=0, minute=0)
        sample_per_hour = 60/int(match[0])
        for _day, sched in self.operational_schedule.items():
            for _hours in xrange(24):
                for _minutes in xrange(sample_per_hour):
                    current_time = dt.time(hour=_hours, minute=_minutes*int(match[0]))
                    if sched[0] == unoccupied_token and sched[1] == unoccupied_token:
                        status = 0
                    elif current_time < sched[0] or current_time > sched[1]:
                        status = 0
                    else:
                        status = 1
                    status_tuple = (current_time, status)
                    reference_schedule[_day].append(status_tuple)
        return reference_schedule


def main(argv=sys.argv):
    """ Main method."""
    utils.vip_main(ScheduleDetection)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
