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
from datetime import datetime, timedelta
import logging
import os
import sys
import time

from volttron.platform.agent import utils
from volttron.platform.agent.utils import parse_timestamp_string
from volttron.platform.vip.agent import Agent, Core, PubSub, errors

utils.setup_logging()
_log = logging.getLogger(__name__)

__version__ = '1.0'


class SimulationAgent(Agent):
    """
        Manage a simulation.

        This agent works in concert with SimulationDriverAgent and SimulationClockAgent.

        Load the configuration.
        Start/stop the simulation.
        Subscribe to points from simulation drivers.
        Dispatch setpoints to the simulated storage device (battery).
        Periodically report the status of each driver in log trace.
        Write a CSV output file showing the progress of each scraped point.

        For further information about configuring and customizing simulations,
        please see the user guide in volttron/docs/source/devguides/agent_development/Simulated-Drivers.rst
    """

    rpt_headers = {
        'report_time': 'Time',
        'net_power_kw': 'Net Power kW',
        'devices/simload/power_kw': 'Load Power kW',
        'devices/simmeter/power_kw': 'Meter Power kW',
        'devices/simpv/power_kw': 'PV Power kW',
        'devices/simstorage/power_kw': 'Storage Power kW',
        'devices/simstorage/soc_kwh': 'Storage SOC kWh',
        'devices/simstorage/dispatch_kw': 'Dispatch Power kW'}

    def __init__(self, config_path, **kwargs):
        super(SimulationAgent, self).__init__(**kwargs)

        default_path = '~/repos/volttron-applications/kisensum/Simulation/SimulationAgent/data/'
        self.default_config = {
            'agent_id': 'simulation',
            'heartbeat_period': 5,
            'positive_dispatch_kw': 15.0,
            'negative_dispatch_kw': -15.0,
            'go_positive_if_below': 0.1,
            'go_negative_if_above': 0.9,
            'sim_start': '2017-02-02 13:00:00',             # Start at 1:00 pm on Feb 2, 2017
            'sim_end': None,
            'sim_speed': 180.0,                             # Passage-of-time multiplier (1 sec = 3 min)
            'report_interval': 14,                          # Seconds
            'report_file_path': '$VOLTTRON_HOME/run/simulation_out.csv',
            'load_timestamp_column_header': 'local_date',
            'load_power_column_header': 'load_kw',
            'load_data_frequency_min': 15,
            'load_data_year': '2015',
            'load_csv_file_path': default_path + 'load_and_pv.csv',
            'pv_panel_area': 50.0,
            'pv_efficiency': 0.75,
            'pv_data_frequency_min': 30,
            'pv_data_year': '2015',
            'pv_csv_file_path': default_path + 'nrel_pv_readings.csv',
            'storage_soc_kwh': 30.0,
            'storage_max_soc_kwh': 50.0,
            'storage_max_charge_kw': 15.0,
            'storage_max_discharge_kw': 12.0,
            'storage_reduced_charge_soc_threshold': 0.80,           # Charging is reduced if SOC % > this value
            'storage_reduced_discharge_soc_threshold': 0.20,        # Discharging is reduced if SOC % < this value
            'storage_setpoint_rule': 'oscillation',
            'sim_driver_list': ['simload', 'simmeter', 'simpv', 'simstorage']
        }
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")
        self.config = utils.load_config(config_path)

        self.agent_id = self.config_for('agent_id')
        self.heartbeat_period = self.config_for('heartbeat_period')
        self.positive_dispatch_kw = self.config_for('positive_dispatch_kw')
        self.negative_dispatch_kw = self.config_for('negative_dispatch_kw')
        self.go_positive_if_below = self.config_for('go_positive_if_below')
        self.go_negative_if_above = self.config_for('go_negative_if_above')
        self.sim_start = self.config_for('sim_start')
        self.sim_end = self.config_for('sim_end')
        self.sim_speed = self.config_for('sim_speed')
        self.report_interval = self.config_for('report_interval')
        self.report_file_path = self.config_for('report_file_path')
        self.load_timestamp_column_header = self.config_for('load_timestamp_column_header')
        self.load_power_column_header = self.config_for('load_power_column_header')
        self.load_data_frequency_min = self.config_for('load_data_frequency_min')
        self.load_data_year = self.config_for('load_data_year')
        self.load_csv_file_path = self.config_for('load_csv_file_path')
        self.pv_panel_area = self.config_for('pv_panel_area')
        self.pv_efficiency = self.config_for('pv_efficiency')
        self.pv_data_frequency_min = self.config_for('pv_data_frequency_min')
        self.pv_data_year = self.config_for('pv_data_year')
        self.pv_csv_file_path = self.config_for('pv_csv_file_path')
        self.storage_soc_kwh = self.config_for('storage_soc_kwh')
        self.storage_max_soc_kwh = self.config_for('storage_max_soc_kwh')
        self.storage_max_charge_kw = self.config_for('storage_max_charge_kw')
        self.storage_max_discharge_kw = self.config_for('storage_max_discharge_kw')
        self.storage_reduced_charge_soc_threshold = self.config_for('storage_reduced_charge_soc_threshold')
        self.storage_reduced_discharge_soc_threshold = self.config_for('storage_reduced_discharge_soc_threshold')
        self.storage_setpoint_rule = self.config_for('storage_setpoint_rule')
        self.sim_driver_list = self.config_for('sim_driver_list')
        self.validate_config()

        self.sim_topics = []                # Which data elements to track and report
        self.sim_power_topics = []          # Which data elements to sum when deriving net power
        self.sim_topics.append('report_time')
        self.sim_topics.append('net_power_kw')
        if 'simload' in self.sim_driver_list:
            self.sim_topics.append('devices/simload/power_kw')
            self.sim_power_topics.append('devices/simload/power_kw')
        if 'simmeter' in self.sim_driver_list:
            self.sim_topics.append('devices/simmeter/power_kw')
            self.sim_power_topics.append('devices/simmeter/power_kw')
        if 'simpv' in self.sim_driver_list:
            self.sim_topics.append('devices/simpv/power_kw')
            self.sim_power_topics.append('devices/simpv/power_kw')
        if 'simstorage' in self.sim_driver_list:
            self.sim_topics.append('devices/simstorage/power_kw')
            self.sim_topics.append('devices/simstorage/soc_kwh')
            self.sim_topics.append('devices/simstorage/dispatch_kw')
            self.sim_power_topics.append('devices/simstorage/power_kw')

        self.last_report = None
        self.sim_data = {}
        self.simulation_started = None

    def config_for(self, parameter_name):
        """
            Fetch the value of a named config parameter, or use the default if no config value was furnished.

        @param parameter_name: The config parameter's name.
        @return: The value.
        """
        return self.config.get(parameter_name) or self.default_config[parameter_name]

    def validate_config(self):
        """
            Validate the data types and, in some cases, the value ranges or values of the config parameters.

            This is mostly just validation, but it also has a side-effect of expanding shell
            variables or user directory references (~) in the configured pathnames.
        """
        assert type(self.agent_id) is str
        assert type(self.heartbeat_period) is int
        assert type(self.positive_dispatch_kw) is float
        assert self.positive_dispatch_kw >= 0.0
        assert type(self.negative_dispatch_kw) is float
        assert self.negative_dispatch_kw <= 0.0
        assert type(self.go_positive_if_below) is float
        assert 0.0 <= self.go_positive_if_below <= 1.0
        assert type(self.go_negative_if_above) is float
        assert 0.0 <= self.go_negative_if_above <= 1.0
        assert type(parse_timestamp_string(self.sim_start)) is datetime
        if self.sim_end:
            assert type(parse_timestamp_string(self.sim_end)) is datetime
        assert type(self.sim_speed) is float
        assert type(self.report_interval) is int
        assert type(self.report_file_path) is str
        self.report_file_path = os.path.expandvars(os.path.expanduser(self.report_file_path))
        assert type(self.sim_driver_list) is list

        if 'simload' in self.sim_driver_list:
            assert type(self.load_timestamp_column_header) is str
            assert type(self.load_power_column_header) is str
            assert type(self.load_data_frequency_min) is int
            assert type(self.load_data_year) is str
            assert type(self.load_csv_file_path) is str
            self.load_csv_file_path = os.path.expandvars(os.path.expanduser(self.load_csv_file_path))
            _log.debug('Testing for existence of {}'.format(self.load_csv_file_path))
            assert os.path.exists(self.load_csv_file_path)

        if 'simpv' in self.sim_driver_list:
            assert type(self.pv_panel_area) is float
            assert type(self.pv_efficiency) is float
            assert 0.0 <= self.pv_efficiency <= 1.0
            assert type(self.pv_data_frequency_min) is int
            assert type(self.pv_data_year) is str
            assert type(self.pv_csv_file_path) is str
            _log.debug('Testing for existence of {}'.format(self.pv_csv_file_path))
            self.pv_csv_file_path = os.path.expandvars(os.path.expanduser(self.pv_csv_file_path))
            assert os.path.exists(self.pv_csv_file_path)

        if 'simstorage' in self.sim_driver_list:
            assert type(self.storage_soc_kwh) is float
            assert type(self.storage_max_soc_kwh) is float
            assert type(self.storage_max_charge_kw) is float
            assert type(self.storage_max_discharge_kw) is float
            assert type(self.storage_reduced_charge_soc_threshold) is float
            assert 0.0 <= self.storage_reduced_charge_soc_threshold <= 1.0
            assert type(self.storage_reduced_discharge_soc_threshold) is float
            assert 0.0 <= self.storage_reduced_discharge_soc_threshold <= 1.0
            assert type(self.storage_setpoint_rule) is str

    def configure(self, config_name, action, contents):
        config = self.default_config.copy()
        config.update(contents)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        if self.heartbeat_period != 0:
            self.vip.heartbeat.start_with_period(self.heartbeat_period)
        self.core.spawn(self.run_simulation)

    @PubSub.subscribe('pubsub', '')
    def on_match(self, peer, sender, bus, topic, headers, message):
        """
            Respond to a driver scrape. Capture data from each simulated point.

        @param topic: The point name.
        @param message: The point's scraped value.
        """
        if self.simulation_started and topic in self.sim_topics:
            self.sim_data[topic] = message[0]

    def run_simulation(self):
        """
            Main gevent thread that runs the simulation.

            First, stop any previous simulation that's still running.
            Then send initialization parameters to each configured driver.
            Then start the clock.
            At regular intervals, write a line to a CSV output file with the latest scraped point values.
            When the clock stops, close the output file.
        """
        # Stop the previous simulation, if any, forcing data files to be reloaded.
        # Also zero out registers that might otherwise be carried over from prior simulations.
        self.send_clock_request('stop_simulation')
        if 'simpv' in self.sim_driver_list:
            self.set_point('simpv', 'csv_file_path', '')
            self.set_point('simpv', 'power_kw', 0.0)
        if 'simload' in self.sim_driver_list:
            self.set_point('simload', 'csv_file_path', '')
            self.set_point('simload', 'power_kw', 0.0)
        if 'simstorage' in self.sim_driver_list:
            self.set_point('simstorage', 'power_kw', 0.0)
            self.set_point('simstorage', 'soc_kwh', 0.0)
            self.set_point('simstorage', 'dispatch_kw', 0.0)
        if 'simmeter' in self.sim_driver_list:
            self.set_point('simmeter', 'power_kw', 0.0)

        self.simulation_started = None

        # Start the new simulation
        while not self.simulation_started:
            curr_time = datetime.now()
            response, err = self.send_clock_request('initialize_clock',
                                                    self.sim_start,
                                                    simulated_stop_time=self.sim_end,
                                                    speed=self.sim_speed)
            if err:
                # Got an error trying to start the clock. Slee for awhile and then try again
                time.sleep(self.report_interval)
            else:
                _log.info('{} Started clock at sim time {}, end at {}, speed multiplier = {}'.format(
                    curr_time, self.sim_start, self.sim_end, self.sim_speed))
                self.simulation_started = curr_time
                self.last_report = curr_time

        self.initialize_drivers()

        with open(self.report_file_path, 'wb') as report_file:
            col_headers = [self.rpt_headers[topic] for topic in self.sim_topics]
            csv_writer = csv.DictWriter(report_file, fieldnames=col_headers)
            csv_writer.writeheader()
            while self.simulation_started:
                # Periodically wake up and report simulation driver status.
                # Also dispatch an updated power setting to the storage simulation driver.
                curr_time = datetime.now()
                if self.last_report is None or self.last_report < curr_time - timedelta(seconds=self.report_interval):

                    # Report on scraped simulation data.
                    sim_time, err = self.send_clock_request('get_time')
                    if err:
                        _log.warning('Unable to get a simulated time, stopping the simulation.')
                        self.simulation_started = None
                        report_file.close()
                        break
                    elif sim_time == 'Past the simulation stop time':
                        # The simulation has ended. Close the file and exit.
                        _log.info('The simulation has ended.')
                        self.simulation_started = None
                        report_file.close()
                        break
                    else:
                        self.sim_data['report_time'] = sim_time
                        self.sim_data['net_power_kw'] = sum(self.sim_data[topic] if topic in self.sim_data else 0.0
                                                            for topic in self.sim_power_topics)
                        data_by_col = {self.rpt_headers[topic]: self.sim_data[topic] if topic in self.sim_data else ''
                                       for topic in self.sim_topics}
                        csv_writer.writerow(data_by_col)
                        report_file.flush()                 # Keep the file contents up-to-date on disk
                        _log.debug('{} Reporting at sim time {}'.format(curr_time, sim_time))
                        for key in sorted(self.sim_data):
                            _log.debug('\t{} = {}'.format(key, self.sim_data[key]))
                        self.last_report = curr_time

                        if 'simstorage' in self.sim_driver_list:
                            # Send a new dispatch setpoint to the storage simulation
                            if self.storage_setpoint_rule == 'oscillation':
                                storage_setpoint = self.oscillation_setpoint()
                            else:
                                # By default, send the storage/battery a command to charge up at max power
                                storage_setpoint = self.storage_max_charge_kw
                            _log.debug('\t\tSetting storage dispatch to {} kW'.format(storage_setpoint))
                            self.set_point('simstorage', 'dispatch_kw', storage_setpoint)

                    time.sleep(self.report_interval)

    def initialize_drivers(self):
        """
            Send initialization parameters to each driver.
        """
        _log.debug('{} Initializing drivers'.format(datetime.now()))

        if 'simload' in self.sim_driver_list:
            log_string = '\tInitializing Load: timestamp_column_header={}, power_column_header={}, ' + \
                         'data_frequency_min={}, data_year={}, csv_file_path={}'
            _log.debug(log_string.format(self.load_timestamp_column_header,
                                         self.load_power_column_header,
                                         self.load_data_frequency_min,
                                         self.load_data_year,
                                         self.load_csv_file_path))
            self.set_point('simload', 'timestamp_column_header', self.load_timestamp_column_header)
            self.set_point('simload', 'power_column_header', self.load_power_column_header)
            self.set_point('simload', 'data_frequency_min', self.load_data_frequency_min)
            self.set_point('simload', 'data_year', self.load_data_year)
            self.set_point('simload', 'csv_file_path', self.load_csv_file_path)

        if 'simmeter' in self.sim_driver_list:
            _log.debug('\tInitializing Meter:')

        if 'simpv' in self.sim_driver_list:
            log_string = '\tInitializing PV: panel_area={}, efficiency={}, ' + \
                         'data_frequency_min={}, data_year={}, csv_file_path={}'
            _log.debug(log_string.format(self.pv_panel_area,
                                         self.pv_efficiency,
                                         self.pv_data_frequency_min,
                                         self.pv_data_year,
                                         self.pv_csv_file_path))
            self.set_point('simpv', 'panel_area', self.pv_panel_area)
            self.set_point('simpv', 'efficiency', self.pv_efficiency)
            self.set_point('simpv', 'data_frequency_min', self.pv_data_frequency_min)
            self.set_point('simpv', 'data_year', self.pv_data_year)
            self.set_point('simpv', 'csv_file_path', self.pv_csv_file_path)

        if 'simstorage' in self.sim_driver_list:
            log_string = '\tInitializing Storage: soc_kwh={}, max_soc_kwh={}, ' +\
                         'max_charge_kw={}, max_discharge_kw={}, ' +\
                         'reduced_charge_soc_threshold = {}, reduced_discharge_soc_threshold = {}'
            _log.debug(log_string.format(self.storage_soc_kwh,
                                         self.storage_max_soc_kwh,
                                         self.storage_max_charge_kw,
                                         self.storage_max_discharge_kw,
                                         self.storage_reduced_charge_soc_threshold,
                                         self.storage_reduced_discharge_soc_threshold))
            self.set_point('simstorage', 'soc_kwh', self.storage_soc_kwh)
            self.set_point('simstorage', 'max_soc_kwh', self.storage_max_soc_kwh)
            self.set_point('simstorage', 'max_charge_kw', self.storage_max_charge_kw)
            self.set_point('simstorage', 'max_discharge_kw', self.storage_max_discharge_kw)
            self.set_point('simstorage', 'reduced_charge_soc_threshold', self.storage_reduced_charge_soc_threshold)
            self.set_point('simstorage', 'reduced_discharge_soc_threshold',
                           self.storage_reduced_discharge_soc_threshold)

    def oscillation_setpoint(self):
        """
            Default algorithm for calculating dispatch power to send to the storage simulation (battery).

            Oscillate between charging/discharging:
            . If SOC < x%, dispatch_kw is a positive constant
            . If SOC > y%, dispatch_kw is a negative constant
            . Otherwise dispatch_kw is a +/- constant, with the sign unchanged from its previous value.
            . The effect is a slow oscillation in the battery's dispatch power and SOC.
        """
        if 'devices/simstorage/soc_kwh' in self.sim_data:
            soc = self.sim_data['devices/simstorage/soc_kwh']
            prior_dispatch = self.sim_data['devices/simstorage/dispatch_kw']
            if soc < self.go_positive_if_below * self.storage_max_soc_kwh:
                dispatch_kw = self.positive_dispatch_kw
            elif soc > self.go_negative_if_above * self.storage_max_soc_kwh:
                dispatch_kw = self.negative_dispatch_kw
            else:
                if prior_dispatch >= 0.0:
                    dispatch_kw = self.positive_dispatch_kw
                else:
                    dispatch_kw = self.negative_dispatch_kw
        else:
            dispatch_kw = self.positive_dispatch_kw
        return dispatch_kw

    def set_point(self, driver_name, point_name, value):
        response = None
        err = None
        try:
            response = self.vip.rpc.call('simulation.driver', 'set_point', driver_name, point_name, value).get(timeout=30)
        except errors.Unreachable:
            _log.warning('\t\tSimulationDriverAgent is not running')
            err = 'No SimulationDriverAgent'
        except Exception, exc:
            err = 'Exception during set_point request = {}'.format(exc)
        return response, err

    def send_clock_request(self, request, *args, **kwargs):
        response = None
        err = None
        try:
            response = self.vip.rpc.call('simulationclock', request, *args, **kwargs).get(timeout=10)
        except errors.Unreachable:
            _log.warning('\t\tSimulationClockAgent is not running')
            err = 'No clock'
        except Exception, exc:
            err = 'Exception during clock request = {}'.format(exc)
        return response, err

def main(argv=sys.argv):
    """Main method called by the platform."""
    utils.vip_main(SimulationAgent)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
