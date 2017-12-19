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
import logging
import sys

from volttron.platform.agent import utils
from volttron.platform.vip.agent import Agent, RPC

_log = logging.getLogger(__name__)
utils.setup_logging()

__version__ = "1.0"


def simulation_clock_agent(config_path, **kwargs):
    """
        Parse the configuration and use it to create and return a SimulationClockAgent instance.

    @param config_path: Path to a configuration file (str).
    @return: The Agent
    """
    try:
        config = utils.load_config(config_path)
    except StandardError:
        config = {}
    if not config:
        _log.info('Using Agent defaults as starting configuration.')
    return SimulationClockAgent(config_path, **kwargs)


class SimulationClockAgent(Agent):
    """
        Manage a simulation's clock.

        Maintain a synchronized clock for all agents participating in the simulation.
        Allow the simulated clock to start at a time other than the actual (wall clock) time,
        and to progress at a different rate.

        Agents participating in a simulation should issue an RPC get_time() call to
        this agent whenever they need a simulated time.
    """

    def __init__(self, config_path, **kwargs):
        """
            Initialize the Agent instance.

        @param config_path: Path to a configuration file (str).
        """
        super(SimulationClockAgent, self).__init__(**kwargs)
        _log.debug('vip_identity: ' + self.core.identity)
        config = utils.load_config(config_path)
        self.default_config = {'agentid': config.get('agentid', 'simulationclock')}
        self.vip.config.set_default('config', self.default_config)
        self.vip.config.subscribe(self.configure, actions=['NEW', 'UPDATE'], pattern='config')

        self.actual_start_time = None
        self.simulated_start_time = None
        self.simulated_stop_time = None
        self.speed = None

    def configure(self, config_name, action, contents):
        """
            Initialize the agent configuration.

        @param config_name: Not used.
        @param action: Not used.
        @param contents:
        """
        _log.debug('Configuring SimulationClockAgent')
        config = self.default_config.copy()
        config.update(contents)
        try:
            # No configuration parameters are currently needed. If they were, use this:
            # self.config_property_tbd = str(config['config_property_tbd'])
            # _log.debug('config_property_tbd: {}'.format(self.config_property_tbd))
            pass
        except ValueError as e:
            _log.error('ERROR PROCESSING CONFIGURATION: {}'.format(e))

    @RPC.export
    def initialize_clock(self, simulated_start_time, simulated_stop_time=None, speed=None):
        """
            Start a simulation by furnishing start/stop times and a clock speed.

            If no simulated_stop_time is supplied, the simulation will run
            until another simulation is started or the agent is stopped.

            If no speed is supplied, the simulated clock speed will be the same as
            the wall clock (real-time) speed.

            The confirmation message that is returned indicates the wall clock (real)
            time when the simulation started.

        @param simulated_start_time: The simulated-clock time at which the simulation will start.
        @param simulated_stop_time: The simulated-clock time at which the simulation will stop (can be None).
        @param speed: A multiplier (float) that makes the simulation run faster or slower than real time.
        @return: A string, either an error message or a confirmation that the simulation has started.
        """
        try:
            parsed_start_time = utils.parse_timestamp_string(simulated_start_time)
        except ValueError:
            _log.debug('Failed to parse simulated_start_time {}'.format(simulated_start_time))
            return 'Invalid simulated_start_time'

        if simulated_stop_time:
            try:
                parsed_stop_time = utils.parse_timestamp_string(simulated_stop_time)
            except ValueError:
                _log.debug('Failed to parse simulated_stop_time {}'.format(simulated_stop_time))
                return 'Invalid simulated_stop_time'
        else:
            parsed_stop_time = None

        if speed is not None:
            try:
                parsed_speed = float(speed)
            except ValueError:
                _log.debug('Failed to parse speed {}'.format(speed))
                return 'Invalid speed'
            if speed <= 0.0:
                _log.debug('Asked to initialize with a zero or negative speed')
                return 'Asked to initialize with a zero or negative speed'
        else:
            parsed_speed = 1.0

        if parsed_stop_time and (parsed_stop_time < parsed_start_time):
            _log.debug('Asked to initialize with out-of-order start/stop times')
            return 'simulated_stop_time is earlier than simulated_start_time'

        self.actual_start_time = utils.get_aware_utc_now()
        self.simulated_start_time = parsed_start_time
        self.simulated_stop_time = parsed_stop_time
        self.speed = parsed_speed
        _log.debug('Initializing clock at {} to start at: {}'.format(self.actual_start_time, self.simulated_start_time))
        _log.debug('Initializing clock to stop at:  {}'.format(self.simulated_stop_time))
        _log.debug('Initializing clock to run at: {} times normal'.format(self.speed))
        return 'Simulation started at {}'.format(self.actual_start_time)

    @RPC.export
    def get_time(self):
        """
            Get the current simulated clock time.

        @return: A Datetime string.
        """
        if not (self.actual_start_time and self.simulated_start_time and self.speed):
            return 'No simulation is in progress'
        elapsed_seconds = (utils.get_aware_utc_now() - self.actual_start_time).seconds
        elapsed_simulated_seconds = elapsed_seconds * self.speed
        simulation_timestamp = self.simulated_start_time + timedelta(seconds=elapsed_simulated_seconds)
        if self.simulated_stop_time and simulation_timestamp > self.simulated_stop_time:
            return 'Past the simulation stop time'
        else:
            return str(simulation_timestamp)

    @RPC.export
    def stop_simulation(self):
        """
            Stop the current simulation.

        @return: A confirmation message.
        """
        _log.debug('Stopping simulation')
        self.actual_start_time = None
        self.simulated_start_time = None
        self.simulated_stop_time = None
        self.speed = None
        return 'Simulation stopped'


def main():
    """Main method called to start the agent."""
    utils.vip_main(simulation_clock_agent,
                   identity='simulationclock',
                   version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
