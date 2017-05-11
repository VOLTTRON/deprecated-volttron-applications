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
from datetime import datetime, timedelta
import gevent
import pytest
import time

from volttron.platform.agent import utils

DEBUGGER_CONFIG = {
    "agent": {
        "exec": "simulationclockagent-1.0-py2.7.egg --config \"%c\" --sub \"%s\" --pub \"%p\""
    },
    "agentid": "simulationclock",
}


@pytest.fixture(scope='module')
def agent(request, volttron_instance):
    master_uuid = volttron_instance.install_agent(agent_dir='applications/kisensum/Simulation/SimulationClockAgent',
                                                  config_file=DEBUGGER_CONFIG,
                                                  start=True)
    gevent.sleep(2)
    clock_agent = volttron_instance.build_agent()
    gevent.sleep(20)  # wait for the agent to start

    def stop():
        volttron_instance.stop_agent(master_uuid)
        clock_agent.core.stop()

    request.addfinalizer(stop)
    return clock_agent


@pytest.mark.usefixtures('agent')
class TestSimulationClock:
    """
        Regression tests for SimulationClockAgent.
    """

    def test_start_simulation(self, agent):
        """Test initializing a simulation clock and getting a simulated time from it."""
        response = self.start_simulation(agent, '2017-01-01 08:00', '2017-01-01 10:00', '10.0')
        assert 'started' in response
        parsed_time = self.get_time(agent)
        assert type(parsed_time) != str

    def test_elapsed_time(self, agent):
        """Confirm that correct simulated times are returned."""
        sim_start_time = utils.parse_timestamp_string('2017-01-01 08:00')
        sim_stop_time = utils.parse_timestamp_string('2017-01-01 10:00')
        clock_speed = 10.0
        response = self.start_simulation(agent, str(sim_start_time), str(sim_stop_time), str(10.0))
        actual_start_time = datetime.now()
        assert 'started' in response

        time.sleep(2)
        response = self.get_time(agent)
        assert type(response) != str
        elapsed_simulated_seconds = (datetime.now() - actual_start_time).seconds * clock_speed
        simulation_timestamp = sim_start_time + timedelta(seconds=elapsed_simulated_seconds)
        assert str(response) == str(simulation_timestamp)

        time.sleep(2)
        response = self.get_time(agent)
        assert type(response) != str
        elapsed_simulated_seconds = (datetime.now() - actual_start_time).seconds * clock_speed
        simulation_timestamp = sim_start_time + timedelta(seconds=elapsed_simulated_seconds)
        assert str(response) == str(simulation_timestamp)

    def test_stop_simulation(self, agent):
        """Test stopping a simulation; confirm that getting a time from a stopped simulation returns an error."""
        response = self.stop_simulation(agent)
        assert response == 'Simulation stopped'
        response = self.get_time(agent)
        assert response == 'No simulation is in progress'

    def test_invalid_dates(self, agent):
        """Confirm errors returned when trying to initialize a simulation with an invalid start or stop datetime."""
        response = self.start_simulation(agent, '2017-00-01 08:00', '2017-01-01 10:00', '10.0')
        assert response == 'Invalid simulated_start_time'
        response = self.start_simulation(agent, '2017-01-01 08:00', '20175-01-01 10:00', '10.0')
        assert response == 'Invalid simulated_stop_time'
        response = self.start_simulation(agent, '2017-01-01 10:00', '2017-01-01 08:00', '10.0')
        assert response == 'simulated_stop_time is earlier than simulated_start_time'

    def test_invalid_speed(self, agent):
        """Confirm error returned when trying to initialize a simulation with an invalid clock speed."""
        response = self.start_simulation(agent, '2017-01-01 08:00', '2017-01-01 10:00', 'XX')
        assert response == 'Invalid speed'

    def test_forever_simulation(self, agent):
        """Test running a simulation with no defined stop time."""
        response = self.start_forever_simulation(agent, '2017-01-01 08:00', '10.0')
        assert 'started' in response

    def test_one_for_one_simulation(self, agent):
        """Test running a simulation for which the speed of the simulation clock is the speed of the wall clock."""
        response = self.start_one_for_one_simulation(agent, '2017-01-01 08:00', '2017-01-01 10:00')
        assert 'started' in response

    def start_simulation(self, agt, start_time, stop_time, speed):
        """Issue an RPC call to initialize a simulation."""
        return self.issue_rpc_call(agt, 'initialize_clock', start_time, simulated_stop_time=stop_time, speed=speed)

    def start_forever_simulation(self, agt, start_time, speed):
        """Issue an RPC call to initialize a simulation without specifying a stop time."""
        return self.issue_rpc_call(agt, 'initialize_clock', start_time, speed=speed)

    def start_one_for_one_simulation(self, agt, start_time, stop_time):
        """Issue an RPC call to initialize a simulation without specifying a clock speed."""
        return self.issue_rpc_call(agt, 'initialize_clock', start_time, simulated_stop_time=stop_time)

    def get_time(self, agt):
        """Issue an RPC call to get the current simulated clock time."""
        response = self.issue_rpc_call(agt, 'get_time')
        try:
            parsed_response = utils.parse_timestamp_string(response)
        except ValueError:
            parsed_response = response
        return parsed_response

    def stop_simulation(self, agt):
        """Issue an RPC call to stop the current simulation."""
        return self.issue_rpc_call(agt, 'stop_simulation')

    @staticmethod
    def issue_rpc_call(agt, rpc_name, *args, **kwargs):
        """Issue an RPC call to the SimulatedClockAgent."""
        return agt.vip.rpc.call('simulationclock', rpc_name, *args, **kwargs).get(timeout=30)
