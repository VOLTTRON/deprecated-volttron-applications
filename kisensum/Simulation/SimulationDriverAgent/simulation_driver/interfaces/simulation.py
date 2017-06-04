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
import logging

from volttron.platform.agent import utils
from volttron.platform.agent.utils import parse_timestamp_string

from . import BaseInterface, BaseRegister, BasicRevert

_log = logging.getLogger(__name__)

type_mapping = {'string': str,
                'int': int,
                'integer': int,
                'float': float,
                'bool': bool,
                'boolean': bool}


class SimulationRegister(BaseRegister):
    """Abstract superclass for simulation Registers."""

    attribute_list = ['last_timestamp']

    def __init__(self, read_only, point_name, units, reg_type, default_value=None, description=''):
        """
            Initialize the instance.

        :param read_only: True = Read-only, False = Read/Write.
        :param point_name: Name of point.
        :param units: Required by parent class. Units for register value.
        :param reg_type: Python type of register. Used to cast value field.
        :param default_value: Default value of register.
        :param description: Basic description of register.
        """
        super(SimulationRegister, self).__init__("byte", read_only, point_name, units, description)
        self.reg_type = reg_type
        try:
            self._value = reg_type(default_value) if default_value else None
        except ValueError:
            self._value = None
            _log.error("{0} cannot be cast to {1}".format(default_value, reg_type))

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, x):
        self._value = x


class SimulationInterface(BasicRevert, BaseInterface):
    """
        Abstract superclass for simulation Interfaces.

        A SimulationInterface has behavior that, in most respects, matches the behavior of an
        interface managed by the MasterDriverAgent. A key difference is that a
        SimulationInterface is aware of its simulated timestamp, which doesn't necessarily
        match the current wallclock time.
    """

    registers_from_config = []                  # This definition should be overridden in subclasses

    def __init__(self, vip=None, core=None, **kwargs):
        super(SimulationInterface, self).__init__(vip=vip, core=core, **kwargs)

    def configure(self, config_dict, registry_config):
        if registry_config:
            self.parse_config(registry_config)
        for entry in config_dict.keys():
            setattr(self, entry, config_dict[entry])
        for reg in self.registers_from_config:
            property_val = getattr(self, reg)
            _log.debug('from config: {} = {}'.format(reg, property_val))
            self.set_register_by_name(reg, property_val)

    def get_point(self, point_name, **kwargs):
        register = self.get_register_by_name(point_name)
        result = register.value if hasattr(register, 'value') else None
        _log.debug('Getting {} value for {}'.format(result, point_name))
        return result

    def _set_point(self, point_name, value):
        result = self.set_register_by_name(point_name, value)
        return result

    def set_register_by_name(self, point_name, value):
        register = self.get_register_by_name(point_name)
        if register.read_only:
            raise IOError('Trying to write to a point configured read only: {}'.format(point_name))
        # Use the register.value() setter method to set the register value by name
        register.value = register.reg_type(value)
        # _log.debug('Set {} to {}'.format(point_name, value))
        return register.value

    def get_register_value(self, register_name):
        register = self.get_register_by_name(register_name)
        return register.value if hasattr(register, 'value') else None

    def _scrape_all(self, sim_time):
        self.set_register_by_name('last_timestamp', sim_time)
        self.update()               # update() is overridden in each interface subclass
        read_registers = self.get_registers_by_type('byte', True)
        write_registers = self.get_registers_by_type('byte', False)
        return {r.point_name: r.value for r in read_registers + write_registers}

    def parse_config(self, registry_config_str):
        for regDef in registry_config_str:
            default_value = regDef.get('Starting Value', None)
            register = SimulationRegister(regDef['Writable'].lower() != 'true',
                                          regDef['Volttron Point Name'],
                                          regDef.get('Units', ''),
                                          type_mapping.get(regDef.get("Type", 'string'), str),
                                          default_value=default_value if default_value != '' else None,
                                          description=regDef.get('Notes', ''))
            self.insert_register(register)

    def update(self):
        """
            Update the device driver's state in advance of a periodic scrape request.

            This method should be overridden in subclasses to implement behavior that
            needs to happen in advance of the scrape request, such as calculating new power values.
        """
        pass

    def sim_time(self):
        """
            Return the current simulated timestamp.

            The current simulated timestamp (as a string) was requested from the SimulationClockAgent
            via an RPC call (see BasicRevert.scrape_all()) and stored in a register.
            Get that value from the register, parse the string, and return the datetime.

            If a simulated timestamp cannot be returned, log the reason and return None.

        :return: (datetime) The current simulated timestamp.
        """
        sim_time = None
        timestamp_string = self.get_register_value('last_timestamp')
        try:
            sim_time = utils.parse_timestamp_string(timestamp_string)
        except TypeError:
            _log.warning('No timestamp returned by simulated time agent')
        except ValueError:
            if timestamp_string == 'Past the simulation stop time':
                _log.info(timestamp_string)
            elif timestamp_string is not None:
                _log.warning('Invalid timestamp format returned by simulated time agent: {}'.format(timestamp_string))
        return sim_time

    def adjusted_sim_time(self, data_year, minute_boundary):
        """
            Return an adjusted version of the current simulated timestamp.

            This version of the time is suitable for use during a CSV/dictionary lookup
            in which each row is normalized to a certain frequency in minutes (e.g. every 15 minutes),
            and the simulation's lookup must be adjusted to happen during the reference
            data's year.

            If an adjusted simulated timestamp cannot be returned, return None.

        :param data_year: (int) The year of the reference data.
        :param minute_boundary: (int) The reference data's frequency in minutes, e.g. 15 or 30.
        :return: (datetime) The adjusted timestamp.
        """
        normalized_time = None
        sim_time = self.sim_time()
        if sim_time:
            adjusted_minutes = (minute_boundary * (sim_time.minute / minute_boundary + 1)) % 60
            timestamp_string = '{}/{}/{} {}:{}:00'.format(sim_time.month,
                                                          sim_time.day,
                                                          data_year,
                                                          sim_time.hour,
                                                          adjusted_minutes)
            try:
                normalized_time = parse_timestamp_string(timestamp_string)
            except ValueError:
                _log.warning('Unable to parse the adjusted simulation timestamp: {}'.format(timestamp_string))
        return normalized_time
