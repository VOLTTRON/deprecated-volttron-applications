import csv
from datetime import datetime, timedelta
import logging
import os
import sys
import time

from volttron.platform.agent import utils
from volttron.platform.agent.utils import parse_timestamp_string
from volttron.platform.vip.agent import Agent, Core, PubSub, errors, RPC
from volttron.platform.messaging import topics
from dateutil.parser import parse
import json

utils.setup_logging()
_log = logging.getLogger(__name__)

SIMULATION_DRIVER_ID = 'simulation.driver'

__version__ = '1.0'

MINIMUM_DISCHARGE_KW = -1.0


class ReferenceAppAgent(Agent):
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

    def __init__(self, config_path, **kwargs):
        super(ReferenceAppAgent, self).__init__(**kwargs)

        default_path = '~/repos/volttron-applications/kisensum/Simulation/SimulationAgent/data/'
        self.default_config = {
            'actuator_id': 'simulation.actuator',
            'agent_id': 'reference_app',
            'heartbeat_period': 5,
            'positive_dispatch_kw': 15.0,
            'negative_dispatch_kw': -15.0,
            'go_positive_if_below': 0.1,
            'go_negative_if_above': 0.9,
            'sim_start': None,
            'sim_end': None,
            'sim_speed': 1.0,                               # Passage-of-time multiplier (1 sec = 3 min)
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
            'sim_driver_list': ['simload', 'simmeter', 'simpv', 'simstorage'],
            "venagent_id": "venagent",      # Volttron ID of the VEN agent
            "opt_type": "optIn",            # optIn or optOut
            "report_interval_secs": 30,     # How often to issue RPCs to the VEN agent
            "baseline_power_kw": 6.2,       # Simulated baseline power measurement (constant)
        }
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")
        self.config = utils.load_config(config_path)

        self.actuator_id = self.config_for('actuator_id')
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
        self.sim_driver_list = self.config_for('sim_driver_list')
        self.venagent_id = self.config_for('venagent_id')
        self.report_interval_secs = self.config_for('report_interval_secs')
        self.baseline_power_kw = self.config_for('baseline_power_kw')
        self.default_opt_type=self.config_for('opt_type')

        self.sim_topics = []                # Which data elements to track and report
        self.sim_power_topics = []          # Which data elements to sum when deriving net power
        self.sim_topics.append('report_time')
        self.sim_topics.append('net_power_kw')

        self.simload = self.simmeter = self.simpv = self.simstorage = None
        for device_path in self.sim_driver_list:
            if 'simload' in device_path:
                self.simload = device_path
                self.sim_topics.append('devices/{}/power_kw'.format(self.simload))
                self.sim_power_topics.append('devices/{}/power_kw'.format(self.simload))
            if 'simmeter' in device_path:
                self.simmeter = device_path
                self.sim_topics.append('devices/{}/power_kw'.format(self.simmeter))
                self.sim_power_topics.append('devices/{}/power_kw'.format(self.simmeter))
            if 'simpv' in device_path:
                self.simpv = device_path
                self.sim_topics.append('devices/{}/power_kw'.format(self.simpv))
                self.sim_power_topics.append('devices/{}/power_kw'.format(self.simpv))
            if 'simstorage' in device_path:
                self.simstorage = device_path
                self.sim_topics.append('devices/{}/power_kw'.format(self.simstorage))
                self.sim_topics.append('devices/{}/soc_kwh'.format(self.simstorage))
                self.sim_topics.append('devices/{}/dispatch_kw'.format(self.simstorage))
                self.sim_power_topics.append('devices/{}/power_kw'.format(self.simstorage))

        self.rpt_headers = {
            'report_time': 'Time',
            'net_power_kw': 'Net Power kW',
            'devices/{}/power_kw'.format(self.simload): 'Load Power kW',
            'devices/{}/power_kw'.format(self.simmeter): 'Meter Power kW',
            'devices/{}/power_kw'.format(self.simpv): 'PV Power kW',
            'devices/{}/power_kw'.format(self.simstorage): 'Storage Power kW',
            'devices/{}/soc_kwh'.format(self.simstorage): 'Storage SOC kWh',
            'devices/{}/dispatch_kw'.format(self.simstorage): 'Dispatch Power kW'}

        self.last_report = None
        self.sim_data = {}
        self.simulation_started = None
        self.validate_config()

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
        if self.sim_start:
            assert type(parse_timestamp_string(self.sim_start)) is datetime
        if self.sim_end:
            assert type(parse_timestamp_string(self.sim_end)) is datetime
        assert type(self.sim_speed) is float
        assert type(self.report_interval) is int
        assert type(self.report_file_path) is str
        self.report_file_path = os.path.expandvars(os.path.expanduser(self.report_file_path))
        assert type(self.sim_driver_list) is list

        if self.simload:
            assert type(self.load_timestamp_column_header) is str
            assert type(self.load_power_column_header) is str
            assert type(self.load_data_frequency_min) is int
            assert type(self.load_data_year) is str
            assert type(self.load_csv_file_path) is str
            self.load_csv_file_path = os.path.expandvars(os.path.expanduser(self.load_csv_file_path))
            _log.debug('Testing for existence of {}'.format(self.load_csv_file_path))
            assert os.path.exists(self.load_csv_file_path)

        if self.simpv:
            assert type(self.pv_panel_area) is float
            assert type(self.pv_efficiency) is float
            assert 0.0 <= self.pv_efficiency <= 1.0
            assert type(self.pv_data_frequency_min) is int
            assert type(self.pv_data_year) is str
            assert type(self.pv_csv_file_path) is str
            _log.debug('Testing for existence of {}'.format(self.pv_csv_file_path))
            self.pv_csv_file_path = os.path.expandvars(os.path.expanduser(self.pv_csv_file_path))
            assert os.path.exists(self.pv_csv_file_path)

        if self.simstorage:
            assert type(self.storage_soc_kwh) is float
            assert type(self.storage_max_soc_kwh) is float
            assert type(self.storage_max_charge_kw) is float
            assert type(self.storage_max_discharge_kw) is float
            assert type(self.storage_reduced_charge_soc_threshold) is float
            assert 0.0 <= self.storage_reduced_charge_soc_threshold <= 1.0
            assert type(self.storage_reduced_discharge_soc_threshold) is float
            assert 0.0 <= self.storage_reduced_discharge_soc_threshold <= 1.0

    def configure(self, config_name, action, contents):
        config = self.default_config.copy()
        config.update(contents)

    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):

        # Subscribe to the VENAgent's event and report parameter publications.
        self.vip.pubsub.subscribe(peer='pubsub', prefix=topics.OPENADR_EVENT, callback=self.receive_event)
        self.vip.pubsub.subscribe(peer='pubsub', prefix=topics.OPENADR_STATUS, callback=self.receive_status)

        self.core.periodic(self.report_interval_secs, self.issue_rpcs)

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

    def reserve_battery(self):
        """
            Grab the battery for an hour, if it's not already reserved.
        """
        result = self.request_new_schedule('control_storage_power',
                                           self.new_schedule(self.simstorage, end_secs=60 * 60))
        if result['result'] == 'FAILURE':
            if result['info'] != 'REQUEST_CONFLICTS_WITH_SELF' and result['info'] != 'TASK_ID_ALREADY_EXISTS':
                # @todo We should raise a more tailored exception type than ValueError here.
                raise ValueError('Failed to request new schedule: {}'.format(result['info']))

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
        if self.simpv:
            self.request_new_schedule('init_simpv', self.new_schedule(self.simpv, end_secs=5))
            self.set_point(self.simpv, 'csv_file_path', '')
            self.set_point(self.simpv, 'power_kw', 0.0)
        if self.simload:
            self.request_new_schedule('init_simload', self.new_schedule(self.simload, end_secs=5))
            self.set_point(self.simload, 'csv_file_path', '')
            self.set_point(self.simload, 'power_kw', 0.0)
        if self.simstorage:
            self.request_new_schedule('init_simstorage', self.new_schedule(self.simstorage, end_secs=5))
            self.set_point(self.simstorage, 'power_kw', 0.0)
            self.set_point(self.simstorage, 'soc_kwh', 0.0)
            self.set_point(self.simstorage, 'dispatch_kw', 0.0)
        if self.simmeter:
            self.request_new_schedule('init_simmeter', self.new_schedule(self.simmeter, end_secs=5))
            self.set_point(self.simmeter, 'power_kw', 0.0)

        self.simulation_started = None

        # Start the new simulation
        while not self.simulation_started:
            curr_time = datetime.now()
            if self.sim_start is None:
                self.sim_start = utils.format_timestamp(curr_time)

            response, err = self.send_clock_request('initialize_clock',
                                                    self.sim_start,
                                                    simulated_stop_time=self.sim_end,
                                                    speed=self.sim_speed)
            if err:
                # Got an error trying to start the clock. Sleep for awhile and then try again
                time.sleep(self.report_interval)
            else:
                _log.info('{} Started clock at sim time {}, end at {}, speed multiplier = {}'.format(
                    curr_time, self.sim_start, self.sim_end, self.sim_speed))
                self.simulation_started = curr_time
                self.last_report = curr_time

        self.initialize_drivers()

        if self.simpv:
            self.cancel_actuator_schedule('init_simpv')
        if self.simload:
            self.cancel_actuator_schedule('init_simload')
        if self.simstorage:
            self.cancel_actuator_schedule('init_simstorage')
        if self.simmeter:
            self.cancel_actuator_schedule('init_simmeter')

        # Request a new actuator schedule for the battery, since it will receive periodic dispatch requests.
        if self.simstorage:
            self.reserve_battery()

        with open(self.report_file_path, 'wb') as report_file:
            col_headers = [self.rpt_headers[topic] for topic in self.sim_topics]
            csv_writer = csv.DictWriter(report_file, fieldnames=col_headers)
            csv_writer.writeheader()
            # _log.debug('in main loop')
            while self.simulation_started:
                # _log.debug('The simulation has started')
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
                        self.calculate_net_power()
                        data_by_col = {self.rpt_headers[topic]: self.sim_data[topic] if topic in self.sim_data else ''
                                       for topic in self.sim_topics}
                        csv_writer.writerow(data_by_col)
                        report_file.flush()                 # Keep the file contents up-to-date on disk
                        _log.debug('{} Reporting at sim time {}'.format(curr_time, sim_time))
                        for key in sorted(self.sim_data):
                            _log.debug('\t{} = {}'.format(key, self.sim_data[key]))
                        self.last_report = curr_time
                        if self.simstorage:
                            event_hrs = self.event_duration_hrs()
                            if event_hrs is not None:
                                if event_hrs > 0:
                                    soc = self.sim_data['devices/{}/soc_kwh'.format(self.simstorage)]

                                    storage_setpoint = -1 * min(soc / event_hrs, self.storage_max_discharge_kw) if soc > 0 else 0.0
                                else:
                                    storage_setpoint = self.storage_max_charge_kw
                            else:
                                storage_setpoint = MINIMUM_DISCHARGE_KW
                            _log.debug('\t\tSetting storage dispatch to {} kW'.format(storage_setpoint))
                            self.reserve_battery()
                            self.set_point(self.simstorage, 'dispatch_kw', storage_setpoint)
                    time.sleep(self.report_interval)

        # The simulation is over -- release the battery's actuator schedule.
        if self.simstorage:
            self.cancel_actuator_schedule('init_simstorage')

    def initialize_drivers(self):
        """
            Send initialization parameters to each driver.
        """
        _log.debug('{} Initializing drivers'.format(datetime.now()))

        if self.simload:
            log_string = '\tInitializing Load: timestamp_column_header={}, power_column_header={}, ' + \
                         'data_frequency_min={}, data_year={}, csv_file_path={}'
            _log.debug(log_string.format(self.load_timestamp_column_header,
                                         self.load_power_column_header,
                                         self.load_data_frequency_min,
                                         self.load_data_year,
                                         self.load_csv_file_path))
            self.set_point(self.simload, 'timestamp_column_header', self.load_timestamp_column_header)
            self.set_point(self.simload, 'power_column_header', self.load_power_column_header)
            self.set_point(self.simload, 'data_frequency_min', self.load_data_frequency_min)
            self.set_point(self.simload, 'data_year', self.load_data_year)
            self.set_point(self.simload, 'csv_file_path', self.load_csv_file_path)

        if self.simmeter:
            _log.debug('\tInitializing Meter:')

        if self.simpv:
            log_string = '\tInitializing PV: panel_area={}, efficiency={}, ' + \
                         'data_frequency_min={}, data_year={}, csv_file_path={}'
            _log.debug(log_string.format(self.pv_panel_area,
                                         self.pv_efficiency,
                                         self.pv_data_frequency_min,
                                         self.pv_data_year,
                                         self.pv_csv_file_path))
            self.set_point(self.simpv, 'panel_area', self.pv_panel_area)
            self.set_point(self.simpv, 'efficiency', self.pv_efficiency)
            self.set_point(self.simpv, 'data_frequency_min', self.pv_data_frequency_min)
            self.set_point(self.simpv, 'data_year', self.pv_data_year)
            self.set_point(self.simpv, 'csv_file_path', self.pv_csv_file_path)

        if self.simstorage:
            log_string = '\tInitializing Storage: soc_kwh={}, max_soc_kwh={}, ' +\
                         'max_charge_kw={}, max_discharge_kw={}, ' +\
                         'reduced_charge_soc_threshold = {}, reduced_discharge_soc_threshold = {}'
            _log.debug(log_string.format(self.storage_soc_kwh,
                                         self.storage_max_soc_kwh,
                                         self.storage_max_charge_kw,
                                         self.storage_max_discharge_kw,
                                         self.storage_reduced_charge_soc_threshold,
                                         self.storage_reduced_discharge_soc_threshold))
            self.set_point(self.simstorage, 'soc_kwh', self.storage_soc_kwh)
            self.set_point(self.simstorage, 'max_soc_kwh', self.storage_max_soc_kwh)
            self.set_point(self.simstorage, 'max_charge_kw', self.storage_max_charge_kw)
            self.set_point(self.simstorage, 'max_discharge_kw', self.storage_max_discharge_kw)
            self.set_point(self.simstorage, 'reduced_charge_soc_threshold', self.storage_reduced_charge_soc_threshold)
            self.set_point(self.simstorage, 'reduced_discharge_soc_threshold',
                           self.storage_reduced_discharge_soc_threshold)

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

    def issue_rpcs(self):
        """Periodically issue RPCs, including report_sample_telemetry, to the VEN agent."""
        self.report_sample_telemetry()
        self.get_events()
        self.get_report_parameters()
        self.set_telemetry_status(online='True', manual_override='False')

    def report_sample_telemetry(self):
        """
            At regular intervals, send sample metrics to the VEN agent as an RPC.

            Send measurements that simulate the following:
                - Constant baseline power
                - Measured power from the simulated devices
        """
        self.calculate_net_power()
        end_time = utils.get_aware_utc_now()
        start_time = end_time - timedelta(seconds=self.report_interval_secs)
        self.report_telemetry({'baseline_power_kw': str(self.baseline_power_kw),
                               'current_power_kw': str(self.sim_data['net_power_kw']),
                               'start_time': start_time.__str__(),
                               'end_time': end_time.__str__()})

    def calculate_net_power(self):
        """Sum the power contribution over the set of devices, storing the result as a sim_data element."""
        power_metrics = [self.sim_data[topic] for topic in self.sim_power_topics if topic in self.sim_data]
        self.sim_data['net_power_kw'] = sum(power_metrics)
        return self.sim_data['net_power_kw']

    def receive_event(self, peer, sender, bus, topic, headers, message):
        """(Subscription callback) Receive a list of active events as JSON."""
        debug_string = 'Received event: ID={}, status={}, start={}, end={}, opt_type={}, all params={}'
        _log.debug(debug_string.format(message['event_id'],
                                       message['status'],
                                       message['start_time'],
                                       message['end_time'],
                                       message['opt_type'],
                                       message))
        if message['opt_type'] != self.default_opt_type:
            # Send an optIn decision to the VENAgent.
            self.respond_to_event(message['event_id'], self.default_opt_type)

    def receive_status(self, peer, sender, bus, topic, headers, message):
        """(Subscription callback) Receive a list of report parameters as JSON."""
        debug_string = 'Received report parameters: request_id={}, status={}, start={}, end={}, all params={}'
        _log.debug(debug_string.format(message['report_request_id'],
                                       message['status'],
                                       message['start_time'],
                                       message['end_time'],
                                       message))
        _log.debug('Received report(s) status: {}'.format(message))

    def respond_to_event(self, event_id, opt_type):
        """
            (Send RPC) Respond to an event, telling the VENAgent whether to opt in or out.

        @param event_id: (String) ID of an event.
        @param opt_type: (String) Whether to optIn or optOut of the event.
        """
        _log.debug('Sending an {} response for event ID {}'.format(opt_type, event_id))
        self.send_ven_rpc('respond_to_event', event_id, opt_type)

    def get_events(self):
        """
            (Send RPC) Request a JSON list of events from the VENAgent.

            An events_list could look like:
                [
                    {
                        u'status': , u'active',
                        u'priority': 1,
                        u'event_id': u'18',
                        u'start_time': u'2017-12-22 21:22:20+00:00',
                        u'creation_time': u'2017-12-22 21:22:22.724847',
                        u'opt_type': u'optIn',
                        u'signals': u'{
                            "null": {
                                "intervals": {
                                    "0": {
                                        "duration": "PT2H58M59S",
                                        "uid": "0",
                                        "payloads": {}
                                    }
                                },
                                "currentLevel": null,
                                "signalID": null
                            }
                        }',
                        u'end_time': u'2017-12-23 00:21:19+00:00'
                    }
                ]

        @return: (JSON) A list of events.
        """
        _log.debug('Requesting an event list')
        events_list = self.send_ven_rpc('get_events')
        if events_list:
            for event_dict in events_list:
                _log.debug('\tevent_id {}:'.format(event_dict.get('event_id')))
                for k, v in event_dict.iteritems():
                    _log.debug('\t\t{}={}'.format(k, v))
        else:
            _log.debug('\tNo active events')

    def event_duration_hrs(self):
        """Fetch events, then calculate and return the current event's duration in hours."""
        now = utils.get_aware_utc_now()
        events_list = self.send_ven_rpc('get_events')
        if events_list:
            for event_dict in events_list:
                start = parse(event_dict.get('start_time'))
                if event_dict.get('end_time') is not None:
                    end = parse(event_dict.get('end_time'))
                    if start < now < end:
                        return (end - start).total_seconds() / 3600.0
                else:
                    return None
        return 0.0

    def get_report_parameters(self):
        """
            (Send RPC) Request a JSON list of report parameters from the VENAgent.

            This method dumps the contents of the returned dictionary of report parameters as debug output.
        """
        _log.debug('Requesting report parameters')
        param_dict = self.send_ven_rpc('get_telemetry_parameters')
        _log.debug('Report parameters: {}'.format(param_dict))

    def set_telemetry_status(self, online=None, manual_override=None):
        """
            (Send RPC) Update the VENAgent's reporting status.

        @param online: (Boolean) Whether the VENAgent's resource is online.
        @param manual_override: (Boolean) Whether resource control has been overridden.
        """
        _log.debug('Setting telemetry status: online={}, manual_override={}'.format(online, manual_override))
        self.send_ven_rpc('set_telemetry_status', online, manual_override)

    def report_telemetry(self, telemetry):
        """
            (Send RPC) Update the VENAgent's report metrics.

        @param telemetry: (JSON) Current value of each report metric.
        """
        _log.debug('Reporting telemetry: {}'.format(telemetry))
        self.send_ven_rpc('report_telemetry', telemetry=telemetry)

    @staticmethod
    def new_schedule(driver_id, start_secs=0, end_secs=2):
        """Create a request payload for a request_new_schedule."""
        now = datetime.now()
        start_time = now + timedelta(seconds=start_secs)
        end_time = now + timedelta(seconds=end_secs)
        return [[driver_id, str(start_time), str(end_time)]]

    def request_new_schedule(self, task_id, request):
        """Ask the ActuatorAgent to request a new schedule for a driver."""
        return self.send_actuator_rpc('request_new_schedule', self.agent_id, task_id, 'LOW', request)

    def cancel_actuator_schedule(self, task_id):
        """Ask the ActuatorAgent to cancel a schedule."""
        return self.send_actuator_rpc('request_cancel_schedule', self.agent_id, task_id)

    def set_point(self, driver_name, point_name, value):
        """Use the ActuatorAgent to issue a driver set_point request."""
        response = None
        err = None
        try:
            # If self.actuator_id is null, issue the request directly to SimulationDriverAgent.
            if self.actuator_id:
                response = self.send_actuator_rpc('set_point', self.agent_id, '{}/{}'.format(driver_name, point_name), value)
            else:
                response = self.send_driver_rpc('set_point', driver_name, point_name, value)
        except Exception, exc:
            err = 'Exception during set_point request = {}'.format(exc)
        return response, err

    def send_actuator_rpc(self, rpc_name, *args):
        """Issue an RPC request to the ActuatorAgent, and return its response (if any)."""
        return self.vip.rpc.call(self.actuator_id, rpc_name, *args).get(timeout=10)

    def send_driver_rpc(self, rpc_name, *args):
        """Issue an RPC request to the ActuatorAgent, and return its response (if any)."""
        return self.vip.rpc.call(SIMULATION_DRIVER_ID, rpc_name, *args).get(timeout=10)

    def send_ven_rpc(self, rpc_name, *args, **kwargs):
        """Send an RPC request to the VENAgent, and return its response (if any)."""
        response = self.vip.rpc.call(self.venagent_id, rpc_name, *args, **kwargs)
        return response.get(30)


def main(argv=sys.argv):
    """Main method called by the platform."""
    utils.vip_main(ReferenceAppAgent)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
