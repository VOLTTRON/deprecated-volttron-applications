# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2017, Battelle Memorial Institute
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

from datetime import datetime, timedelta
import gevent
import isodate
import json
import logging
import os
import pytest
import requests
import sqlite3
import time

from volttron.platform import get_services_core
from volttron.platform.agent import utils
from volttrontesting.platform.test_platform_web import _build_web_agent
from volttrontesting.utils.platformwrapper import start_wrapper_platform

utils.setup_logging()
_log = logging.getLogger(__name__)

DB_PATH = '$VOLTTRON_HOME/data/test_openadr.sqlite'
VEN_AGENT_ID = 'venagent'
REFERENCE_APP_ID = 'referenceappagent'
POLL_INTERVAL_SECS = 5

XML_DIR = "/home/ubuntu/repos/volttron-applications/kisensum/ReferenceAppAgent/test/xml/"
CANCEL_FILE = 'test_vtn_cancel_event'

ACTUATOR_ID = 'simulation.actuator'
TEST_AGENT_ID = 'test_agent'
SIMULATION_DRIVER_ID = 'simulation.driver'
SIMULATION_CLOCK_ID = 'simulationclock'

REPORT_INTERVAL_SECS = 2

VEN_AGENT_CONFIG = {
    "ven_id": "0",
    "ven_name": "ven01",
    "vtn_id": "vtn01",
    # Configure an unreachable VTN address to avoid disturbing real VTNs with test behavior
    "vtn_address": "http://unreachable:8000",
    #
    # Other VEN parameters
    #
    "db_path": DB_PATH,
    "send_registration": "False",
    "security_level": "standard",
    "poll_interval_secs": POLL_INTERVAL_SECS,
    "log_xml": "True",
    "opt_in_timeout_secs": 3600,
    "opt_in_default_decision": "optOut",
    "request_events_on_startup": "False",
    #
    # VEN reporting configuration
    #
    "report_parameters": {
        "telemetry": {
            "report_name": "TELEMETRY_USAGE",
            "report_name_metadata": "METADATA_TELEMETRY_USAGE",
            "report_specifier_id": "telemetry",
            "report_interval_secs_default": "30",
            "telemetry_parameters": {
                "baseline_power_kw": {
                    "r_id": "baseline_power",
                    "report_type": "baseline",
                    "reading_type": "Direct Read",
                    "units": "powerReal",
                    "method_name": "get_baseline_power",
                    "min_frequency": 30,
                    "max_frequency": 60
                },
                "current_power_kw": {
                    "r_id": "actual_power",
                    "report_type": "reading",
                    "reading_type": "Direct Read",
                    "units": "powerReal",
                    "method_name": "get_current_power",
                    "min_frequency": 30,
                    "max_frequency": 60
                }
            }
        }
    }
}

REFERENCE_APP_CONFIG = {
    "actuator_id": ACTUATOR_ID,
    "agent_id": "reference_app",
    "heartbeat_period": 5,
    "positive_dispatch_kw": 150.0,
    "negative_dispatch_kw": -150.0,
    "go_positive_if_below": 0.1,
    "go_negative_if_above": 0.9,
    "sim_start": "2017-04-30 13:00:00",
    "sim_end": None,
    "sim_speed": 1.0,
    "report_interval": REPORT_INTERVAL_SECS,
    "report_file_path": "$VOLTTRON_HOME/run/simulation_out.csv",
    "load_csv_file_path": "~/repos/volttron-applications/kisensum/ReferenceAppAgent/data/load_and_pv.csv",
    "load_timestamp_column_header": "local_date",
    "load_power_column_header": "load_kw",
    "load_data_frequency_min": 15,
    "load_data_year": "2015",
    "pv_csv_file_path": "~/repos/volttron-applications/kisensum/ReferenceAppAgent/data/nrel_pv_readings.csv",
    "pv_panel_area": 1000.0,
    "pv_efficiency": 0.75,
    "pv_data_frequency_min": 30,
    "pv_data_year": "2015",
    "storage_max_charge_kw": 150.0,
    "storage_max_discharge_kw": 150.0,
    "storage_max_soc_kwh": 500.0,
    "storage_soc_kwh": 450.0,
    "storage_reduced_charge_soc_threshold": 0.8,
    "storage_reduced_discharge_soc_threshold": 0.2,
    "sim_driver_list": [
        "campus1/building1/simload",
        "campus1/building1/simpv",
        "campus1/building1/simstorage"],
    "venagent_id": "venagent",
    "opt_type": "optIn",
    "report_interval_secs": 30,
    "baseline_power_kw": 500
}

SIMULATION_CLOCK_CONFIG = {
    "agentid": "simulationclock"
}


ACTUATOR_CONFIG = {
    "schedule_publish_interval": 10,
    "schedule_state_file": "actuator_state.test",
    "driver_vip_identity": SIMULATION_DRIVER_ID
}

SIM_LOAD_DRIVER_TYPE = 'simload'
SIM_PV_DRIVER_TYPE = 'simpv'
SIM_STORAGE_DRIVER_TYPE = 'simstorage'

SIM_STORAGE_DRIVER_ID = 'campus1/building1/{}'.format(SIM_STORAGE_DRIVER_TYPE)

SIM_LOAD_CONFIG = """{{
    "driver_config": {{
        "csv_file_path" : "",
        "timestamp_column_header" : "local_date",
        "power_column_header" : "load_kw",
        "data_frequency_min" : 15,
        "data_year" : "2015"
    }},
    "driver_type": "simload",
    "registry_config": "config://{}.csv",
    "interval": 6,
    "timezone": "US/Pacific",
    "heart_beat_point": "Heartbeat"
}}""".format(SIM_LOAD_DRIVER_TYPE)

SIM_PV_CONFIG = """{{
    "driver_config": {{
        "csv_file_path" : "",
        "max_power_kw" : 10.0,
        "panel_area" : 50.0,
        "efficiency" : 0.75,
        "data_frequency_min" : 30,
        "data_year" : "2015"
    }},
    "driver_type": "simpv",
    "registry_config":"config://{}.csv",
    "interval": 6,
    "timezone": "US/Pacific",
    "heart_beat_point": "Heartbeat"
}}""".format(SIM_PV_DRIVER_TYPE)

SIM_STORAGE_CONFIG = """{{
    "driver_config": {{
        "max_charge_kw": 15.0,
        "max_discharge_kw": 15.0,
        "max_soc_kwh": 50.0,
        "soc_kwh": 25.0,
        "reduced_charge_soc_threshold": 0.8,
        "reduced_discharge_soc_threshold": 0.2
    }},
    "driver_type": "simstorage",
    "registry_config": "config://{}.csv",
    "interval": 6,
    "timezone": "US/Pacific",
    "heart_beat_point": "Heartbeat"
}}""".format(SIM_STORAGE_DRIVER_TYPE)

SIM_LOAD_POINTS = """Volttron Point Name,Type,Units,Starting Value,Writable,Notes
Heartbeat,boolean,On/Off,0,TRUE,Point for heartbeat toggle
power_kw,float,Float,0.0,TRUE,
last_timestamp,time,Timestamp,,TRUE,
csv_file_path,string,String,,TRUE,
timestamp_column_header,string,String,local_date,TRUE,
power_column_header,string,String,load_kw,TRUE,
data_frequency_min,integer,Integer,15,TRUE,
data_year,string,String,2015,TRUE"""

SIM_PV_POINTS = """Volttron Point Name,Type,Units,Starting Value,Writable,Notes
Heartbeat,boolean,On/Off,0,TRUE,Point for heartbeat toggle
power_kw,float,Float,0.0,TRUE,
last_timestamp,time,Timestamp,,TRUE,
csv_file_path,string,String,,TRUE,
max_power_kw,float,Float,10.0,TRUE,
panel_area,float,Float,50.0,TRUE,
efficiency,float,Float,0.75,TRUE,
data_frequency_min,integer,Integer,30,TRUE,
data_year,string,String,2015,TRUE"""

SIM_STORAGE_POINTS = """Volttron Point Name,Type,Units,Starting Value,Writable,Notes
Heartbeat,boolean,On/Off,0,TRUE,Point for heartbeat toggle
dispatch_kw,float,Float,0.0,TRUE,
power_kw,float,Float,0.0,TRUE,
last_timestamp,time,Timestamp,,TRUE,
soc_kwh,float,Float,25.0,TRUE,
max_soc_kwh,float,Float,50.0,TRUE,
max_charge_kw,float,Float,15.0,TRUE,
max_discharge_kw,float,Float,15.0,TRUE,
reduced_charge_soc_threshold,float,Float,0.8,TRUE,
reduced_discharge_soc_threshold,float,Float,0.2,TRUE"""

DRIVER_PARAMS = [
    {'id': SIM_LOAD_DRIVER_TYPE, 'config': SIM_LOAD_CONFIG, 'points': SIM_LOAD_POINTS},
    {'id': SIM_PV_DRIVER_TYPE, 'config': SIM_PV_CONFIG, 'points': SIM_PV_POINTS},
    {'id': SIM_STORAGE_DRIVER_TYPE, 'config': SIM_STORAGE_CONFIG, 'points': SIM_STORAGE_POINTS}
]

web_server_address = None


@pytest.fixture(scope="module")
def test_agent(request, get_volttron_instances):
    """
        Fixture that initializes VOLTTRON agents for ReferenceAppAgent test cases.

        Start a VOLTTRON instance running a web agent,
        then install and start an OpenADRVenAgent, a ReferenceAppAgent, a SimulationDriverAgent,
        an ActuatorAgent, and a test agent.
    """
    instance = get_volttron_instances(1, should_start=False)
    start_wrapper_platform(instance, with_http=True)

    # Install and start a WebAgent.
    web_agent = _build_web_agent(instance.volttron_home)
    gevent.sleep(1)
    web_agent_uuid = instance.install_agent(agent_dir=web_agent)

    global web_server_address
    web_server_address = instance.bind_web_address

    global volttron_home
    volttron_home = instance.volttron_home

    def issue_config_rpc(test_agt, config_request, *args):
        return test_agt.vip.rpc.call('config.store', config_request, SIMULATION_DRIVER_ID, *args).get(timeout=10)

    def start_agent(id, dir, config):
        return instance.install_agent(vip_identity=id, agent_dir=dir, config_file=config, start=True)

    test_agt = instance.build_agent(identity=TEST_AGENT_ID)

    issue_config_rpc(test_agt, 'manage_delete_store')
    for param_dict in DRIVER_PARAMS:
        device_id = param_dict['id']
        issue_config_rpc(test_agt, 'manage_store', 'devices/campus1/building1/{}'.format(device_id), param_dict['config'], 'json')
        issue_config_rpc(test_agt, 'manage_store', '{}.csv'.format(device_id), param_dict['points'], 'csv')

    clock_uuid = start_agent(SIMULATION_CLOCK_ID, 'applications/kisensum/Simulation/SimulationClockAgent', SIMULATION_CLOCK_CONFIG)
    sim_driver_uuid = start_agent(SIMULATION_DRIVER_ID, 'applications/kisensum/Simulation/SimulationDriverAgent', {})
    actuator_uuid = start_agent(ACTUATOR_ID, get_services_core('ActuatorAgent'), ACTUATOR_CONFIG)
    ven_uuid = start_agent(VEN_AGENT_ID, get_services_core('OpenADRVenAgent'), VEN_AGENT_CONFIG)
    ref_app_uuid = start_agent(REFERENCE_APP_ID, 'applications/kisensum/ReferenceAppAgent', REFERENCE_APP_CONFIG)

    def stop():
        instance.stop_agent(actuator_uuid)
        instance.stop_agent(ref_app_uuid)
        instance.stop_agent(sim_driver_uuid)
        instance.stop_agent(ven_uuid)
        instance.stop_agent(clock_uuid)
        instance.stop_agent(web_agent_uuid)
        test_agt.core.stop()
        instance.shutdown_platform()

    gevent.sleep(10)

    request.addfinalizer(stop)

    yield test_agt


@pytest.fixture(scope="function")
def cancel_schedules(request, test_agent):
    """
        Fixture that cleans up after test cases.

        Cancel active schedules so that the device and time slot can be re-used by later test cases.
    """

    def cleanup():
        for schedule in cleanup_parameters:
            print('Requesting cancel for task:', schedule['taskid'], 'from agent:', schedule['agentid'])
            result = issue_actuator_rpc(test_agent, 'request_cancel_schedule', schedule['agentid'], schedule['taskid'])
            # sleep so that the message is sent to pubsub before next
            gevent.sleep(1)
            # test monitors callback method calls
            print ("result of cancel ", result)

    cleanup_parameters = []
    request.addfinalizer(cleanup)
    return cleanup_parameters


class TestReferenceApp:
    """Regression tests for the ReferenceAppAgent."""

    test_agt = None
    cancel_schd = None

    def init_test(self, test_agt, cancel_schd):
        self.test_agt = test_agt
        self.cancel_schd = cancel_schd

    def test_event_opt_in(self, test_agent, cancel_schedules):
        """
            Test a VEN control agent's event optIn.

            Create an event, then send an RPC that opts in. Get the event and confirm its optIn status.

        @param test_agent: This test agent.

        """
        self.init_test(test_agent, cancel_schedules)
        self.vtn_request('EiEvent', 'test_vtn_distribute_event')
        self.send_rpc(test_agent, 'respond_to_event', '4', 'optIn')
        assert self.get_event_dict(test_agent, '4').get('opt_type') == 'optIn'
        self.cancel_event(test_agent, '4')

    def test_event_opt_out(self, test_agent, cancel_schedules):
        """
            Test a VEN control agent's event optOut.

            Create an event, then send an RPC that opts out. Get the event and confirm its optOut status.

        @param test_agent: This test agent.

        """
        self.init_test(test_agent, cancel_schedules)
        self.vtn_request('EiEvent', 'test_vtn_distribute_event')
        self.send_rpc(test_agent, 'respond_to_event', '4', 'optOut')
        assert self.get_event_dict(test_agent, '4').get('opt_type') == 'optOut'
        self.cancel_event(test_agent, '4')

    def test_event_activation(self, test_agent, cancel_schedules):
        """
            Test event activation at its start_time.

            Time the test so that the event's start_time arrives. Confirm the event's state change.

        @param test_agent: This test agent.
        """
        self.init_test(test_agent, cancel_schedules)
        self.vtn_request_variable_event('6', utils.get_aware_utc_now(), 60 * 60 * 24)
        assert self.get_event_dict(test_agent, '6').get('status') == 'active'
        self.cancel_event(test_agent, '6')

    def test_event_completion(self, test_agent, cancel_schedules):
        """
            Test event completion at its end_time.

            Time the test so that the event's end_time arrives. Confirm the event's state change.

        @param test_agent: This test agent.
        """
        self.init_test(test_agent, cancel_schedules)
        self.vtn_request_variable_event('7', utils.get_aware_utc_now(), 1)
        assert self.get_event_dict(test_agent, '7').get('status') == 'completed'

    def test_event_cancellation(self, test_agent, cancel_schedules):
        """
            Test event cancellation by the VTN.

            Create an event, then send an XML request to cancel it. Confirm the event's status change.

        @param test_agent: This test agent.
        """
        self.init_test(test_agent, cancel_schedules)
        self.vtn_request('EiEvent', 'test_vtn_distribute_event_no_end')
        self.vtn_request('EiEvent', 'test_vtn_cancel_event')
        assert self.get_event_dict(test_agent, '5').get('status') == 'cancelled'

    def test_report_creation(self, test_agent, cancel_schedules):
        """
            Test report creation by the VTN.

            Create a report by sending an XML request. Confirm that the report is active.
        """
        self.init_test(test_agent, cancel_schedules)
        self.vtn_request('EiReport', 'test_vtn_registered_report')
        response = self.send_rpc(test_agent, 'get_telemetry_parameters')
        report_param_string = response.get('report parameters')
        report_params = json.loads(report_param_string)
        assert report_params.get('status') == 'active'

    def test_battery_discharge(self, test_agent, cancel_schedules):
        """
            Confirm that battery discharges after an event has started.

            Create an (active) event. Confirm that the battery discharges.
        """
        self.init_test(test_agent, cancel_schedules)
        before_discharge_kw = self.get_point(SIM_STORAGE_DRIVER_ID, 'dispatch_kw')
        self.vtn_request_variable_event('9', utils.get_aware_utc_now(), 60 * 60 * 24)
        time.sleep(REPORT_INTERVAL_SECS + 1)
        assert self.get_event_dict(test_agent, '9').get('status') == 'active'
        assert self.get_point(SIM_STORAGE_DRIVER_ID, 'dispatch_kw') < before_discharge_kw
        self.cancel_event(test_agent, '9')

    def test_battery_recharge(self, test_agent, cancel_schedules):
        """
            Confirm that battery recharges after an event, for which it has discharged,
            has ended.

            Create an (active) event. Confirm that battery recharges after event is over.
        """
        self.init_test(test_agent, cancel_schedules)
        before_discharge_kw = self.get_point(SIM_STORAGE_DRIVER_ID, 'dispatch_kw')
        self.vtn_request_variable_event('22', utils.get_aware_utc_now(), 30)
        time.sleep(REPORT_INTERVAL_SECS + 1)
        assert self.get_event_dict(test_agent, '22').get('status') == 'active'
        assert self.get_point(SIM_STORAGE_DRIVER_ID, 'dispatch_kw') < before_discharge_kw
        self.cancel_event(test_agent, '22')
        time.sleep(REPORT_INTERVAL_SECS + 1)
        assert self.get_point(SIM_STORAGE_DRIVER_ID, 'dispatch_kw') == REFERENCE_APP_CONFIG['storage_max_charge_kw']

    def test_battery_power(self, test_agent, cancel_schedules):
        """
            Confirm that the battery's power decreases after the battery has started discharging.
        """
        self.init_test(test_agent, cancel_schedules)
        time.sleep(REPORT_INTERVAL_SECS + 1)
        before_power = self.get_point(SIM_STORAGE_DRIVER_ID, 'power_kw')
        self.vtn_request_variable_event('23', utils.get_aware_utc_now(), 60 * 60 * 24)
        time.sleep(REPORT_INTERVAL_SECS + 1)
        assert self.get_event_dict(test_agent, '23').get('status') == 'active'
        assert self.get_point(SIM_STORAGE_DRIVER_ID, 'power_kw') < before_power
        self.cancel_event(test_agent, '23')

    def test_battery_soc(self, test_agent, cancel_schedules):
        """
            Confirm that the battery's SOC decreases after the battery has started discharging.
        """
        self.init_test(test_agent, cancel_schedules)
        time.sleep(REPORT_INTERVAL_SECS + 1)
        before_discharge_soc = self.get_point(SIM_STORAGE_DRIVER_ID, 'soc_kwh')
        self.vtn_request_variable_event('24', utils.get_aware_utc_now(), 60 * 60 * 24)
        time.sleep(REPORT_INTERVAL_SECS + 1)
        assert self.get_event_dict(test_agent, '24').get('status') == 'active'
        assert self.get_point(SIM_STORAGE_DRIVER_ID, 'soc_kwh') < before_discharge_soc
        self.cancel_event(test_agent, '24')

    def test_sim_report(self, test_agent, cancel_schedules):
        """
            Confirm that the simulation report is created.
        """
        self.init_test(test_agent, cancel_schedules)
        global volttron_home
        assert os.path.exists("{}/run/simulation_out.csv".format(volttron_home))

    def get_event_dict(self, agt, event_id):
        """
            Issue an RPC call to the VEN agent, getting a dictionary describing the test event.

        @param agt: This test agent.
        @param event_id: ID of the test event.
        """
        events_string = self.send_rpc(agt, 'get_events', event_id=event_id)
        print('events returned from get_events RPC call: {}'.format(events_string))
        events_list = json.loads(events_string)
        assert len(events_list) > 0
        assert events_list[0].get('event_id') == event_id
        return events_list[0]

    @staticmethod
    def send_rpc(agt, rpc_name, *args, **kwargs):
        """
            Send an RPC request to the VENAgent and return its response.

        @param agt: This test agent.
        @param rpc_name: The name of the RPC request.
        """
        response = agt.vip.rpc.call(VEN_AGENT_ID, rpc_name, *args, **kwargs)
        return response.get(30)

    def cancel_event(self, test_agent, event_id):
        """
            Push an oadrCancelEvent VTN request in which the event's id is an adjustable parameter.
        :param test_agent:
        :param event_id: (String) The event'd ID
        :return:
        """
        _log.debug("Cancelling event {}".format(event_id))
        self.vtn_request_cancel(CANCEL_FILE, event_id=event_id)
        assert self.get_event_dict(test_agent, event_id).get('status') == 'cancelled'

    def vtn_request_variable_event(self, event_id, start_time, duration_secs):
        """
            Push an oadrDistributeEvent VTN request in which the event's start_time and duration
            are adjustable parameters.

        @param event_id: (String) The event's ID.
        @param start_time: (DateTime) The event's start_time.
        @param duration_secs: (Integer seconds) The event's duration.
        """
        self.vtn_request('EiEvent',
                         'test_vtn_distribute_event_variable',
                         event_id=event_id,
                         event_start_time=isodate.datetime_isoformat(start_time),
                         event_duration=isodate.duration_isoformat(timedelta(seconds=duration_secs)))
        # Sleep for an extra cycle to give the event time to change status to active, completed, etc.
        time.sleep(POLL_INTERVAL_SECS + 1)

    @staticmethod
    def vtn_request(service_name, xml_filename, event_id=None, event_start_time=None, event_duration=None):
        """
            Push a VTN request to the VEN, sending the contents of the indicated XML file.

        @param service_name: The service name as it appears in the URL.
        @param xml_filename: The distinguishing part of the sample data file name.
        @param event_id: The event ID.
        @param event_start_time: The time that the test event should become active. Modifies the XML string.
        @param event_duration: The test event's duration. Modifies the XML string.
        """
        global web_server_address
        xml_filename = get_services_core("OpenADRVenAgent/test/xml/{}.xml".format(xml_filename))
        with open(xml_filename, 'rb') as xml_file:
            xml_string = xml_file.read()
            if event_id:
                # Modify the XML, substituting in a custom event ID, start_time and duration.
                xml_string = xml_string.format(event_id=event_id,
                                               event_start_time=event_start_time,
                                               event_duration=event_duration)
            requests.post('{}/OpenADR2/Simple/2.0b/{}'.format(web_server_address, service_name),
                          data=xml_string,
                          headers={'content-type': 'application/xml'})
        time.sleep(POLL_INTERVAL_SECS + 1)           # Wait for the request to be dequeued and handled.

    @staticmethod
    def vtn_request_cancel(xml_filename, event_id=None):
        """
            Cancel an event.

        @param xml_filename: The distinguishing part of the sample data file name.
        @param event_id: (String) The event ID.
        """
        global web_server_address
        xml_filename = "{}{}.xml".format(XML_DIR,xml_filename)
        with open(xml_filename, 'rb') as xml_file:
            xml_string = xml_file.read()
            if event_id:
                # Modify the XML, substituting in a custom event ID, start_time and duration.
                xml_string = xml_string.format(event_id=event_id)
            requests.post('{}/OpenADR2/Simple/2.0b/{}'.format(web_server_address, 'EiEvent'),
                          data=xml_string,
                          headers={'content-type': 'application/xml'})
        time.sleep(POLL_INTERVAL_SECS + 1)  # Wait for the request to be dequeued and handled.


    @staticmethod
    def database_connection():
        """
            Initialize a connection to the sqlite database, and return the connection.
        """
        # This method isn't currently used. It's held in reserve in case tests need to look directly at db objects.
        return sqlite3.connect(os.path.expandvars(DB_PATH))

    @staticmethod
    def new_schedule(driver_id, start_secs=0, end_secs=2):
        """Create a request payload for a request_new_schedule."""
        now = datetime.now()
        start_time = now + timedelta(seconds=start_secs)
        end_time = now + timedelta(seconds=end_secs)
        return [[driver_id, str(start_time), str(end_time)]]

    def request_new_schedule(self, task_id, request):
        """Use the ActuatorAgent to request a new schedule for a driver."""
        self.cancel_schd.append({'agentid': TEST_AGENT_ID, 'taskid': task_id})
        return issue_actuator_rpc(self.test_agt, 'request_new_schedule', TEST_AGENT_ID, task_id, 'LOW', request)

    def get_point(self, driver_name, point):
        """Use the ActuatorAgent to issue a driver get_point request."""
        return issue_actuator_rpc(self.test_agt, 'get_point', '{}/{}'.format(driver_name, point))

    def set_point(self, driver_name, point, val):
        """Use the ActuatorAgent to issue a driver set_point request."""
        result = issue_actuator_rpc(self.test_agt, 'set_point', TEST_AGENT_ID, '{}/{}'.format(driver_name, point), val)
        assert result == val
        return result


def issue_actuator_rpc(test_agent, request, *args):
    """Issue an RPC request to the ActuatorAgent."""
    return test_agent.vip.rpc.call(ACTUATOR_ID, request, *args).get(timeout=10)