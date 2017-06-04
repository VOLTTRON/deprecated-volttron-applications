# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, SLAC National Laboratory / Kisensum Inc.
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
# Government nor the United States Department of Energy, nor SLAC / Kisensum,
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
# SLAC / Kisensum. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# }}}
import csv
from datetime import datetime
import logging
import os

from simulation import SimulationRegister, SimulationInterface

_log = logging.getLogger(__name__)


class SimulationLoadRegister(SimulationRegister):
    """Simulated Load Register."""

    attribute_list = ['power_kw',
                      'last_timestamp',
                      'csv_file_path',
                      'timestamp_column_header',
                      'power_column_header',
                      'data_frequency_min',
                      'data_year']


class Interface(SimulationInterface):
    """
        Simulated Load Interface.

        Model the behavior of generic load on a circuit, using power data as a function of time,
        pulled from a sample data file. Publish the power readings in response to get_point requests.
    """

    registers_from_config = ['csv_file_path',
                             'timestamp_column_header',
                             'power_column_header',
                             'data_frequency_min',
                             'data_year']

    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.power_dict = None

    def update(self):
        """Update the device driver's state in advance of a periodic scrape request."""
        super(Interface, self).update()
        if not self.power_dict:
            csv_file_path = self.get_register_value('csv_file_path')
            if csv_file_path:
                self.power_dict = self.load_power_dict(csv_file_path)

        if self.power_dict:
            power_kw = self.calculate_power()
        else:
            _log.info('No Load simulation data has been loaded')
            power_kw = None

        if power_kw:
            self.set_register_by_name('power_kw', power_kw)

    def calculate_power(self):
        """Return the reference data's power value for the current simulated time."""
        power_kw = None
        if not self.power_dict:
            _log.info('No simulation is in progress')
        else:
            sim_time = self.sim_time()
            if sim_time:
                data_year = self.get_register_value('data_year')
                data_frequency_min = self.get_register_value('data_frequency_min')
                adjusted_time = self.adjusted_sim_time(data_year, data_frequency_min)
                try:
                    time_string = adjusted_time.strftime('%-m/%-d/%y %-H:%M')    # The keys are formatted as M/D/YY H:MM
                    power_kw = self.power_dict[time_string]
                    _log.debug('Load at {} = {} kw'.format(sim_time, power_kw))
                except AttributeError:
                    _log.warning('Unable to look up Load value for {} (adjusted to {})'.format(sim_time, adjusted_time))
            else:
                _log.info('No simulation is in progress')
        return power_kw

    def load_power_dict(self, csv_file_path):
        """
            Load reference data from a CSV-formatted file into a dictionary indexed by timestamp.

            The reference file should include a calendar year's worth of data, gathered at a regular frequency.

            CSV file info can be furnished as simulation initialization parameters,
            either in the driver configuration or via set_point calls to the running driver.
            The following parameters are configurable:

                csv_file_path
                reference_data_year
                reference_data_frequency_mins
                timestamp_column_header
                power_column_header

        :param csv_file_path: Pathname of the CSV file containing power data by time.
        :return: A dictionary of power data read from the CSV file.
        """
        _log.info('{} Starting to load circuit-load data.'.format(datetime.now()))
        power_dict = {}
        expanded_path = os.path.expandvars(os.path.expanduser(csv_file_path))
        with open(expanded_path, 'rb') as csv_file:
            timestamp_column = self.get_register_value('timestamp_column_header')
            power_column = self.get_register_value('power_column_header')
            csv_reader = csv.DictReader(csv_file)
            for row in csv_reader:
                try:
                    time_string = row[timestamp_column]
                    if time_string:
                        power_dict[time_string] = row[power_column]
                    else:
                        _log.warning('Missing timestamp during Load data file load')
                except ValueError:
                    _log.warning('Skipping row during Load data file load')
        _log.info('{} Finished loading circuit-load data.'.format(datetime.now()))
        return power_dict
