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
from simulation import SimulationRegister, SimulationInterface

from volttron.platform.agent import utils

_log = logging.getLogger(__name__)


class SimulationStorageRegister(SimulationRegister):
    """Simulated Storage (Battery) Register."""

    attribute_list = ['last_timestamp',
                      'dispatch_kw',
                      'power_kw',
                      'soc_kwh',
                      'max_soc_kwh',
                      'reduced_charge_soc_threshold',
                      'reduced_discharge_soc_threshold',
                      'max_charge_kw',
                      'max_discharge_kw']


class Interface(SimulationInterface):
    """
        Simulated Storage (Battery) Interface.

        Model the charging/discharging behavior of an electrical storage device (battery) over time.
        Publish charge/discharge power readings, and state-of-charge (SOC) values, in response to get_point requests.
    """

    registers_from_config = ['soc_kwh',
                             'max_soc_kwh',
                             'reduced_charge_soc_threshold',
                             'reduced_discharge_soc_threshold',
                             'max_charge_kw',
                             'max_discharge_kw']

    def __init__(self, **kwargs):
        super(Interface, self).__init__(**kwargs)
        self.soc_kwh = 0
        self.max_soc_kwh = 0
        self.reduced_charge_soc_threshold = 0.0
        self.reduced_discharge_soc_threshold = 0.0
        self.max_charge_kw = 0
        self.max_discharge_kw = 0
        self.old_timestamp = None

    def update(self):
        """Update the device driver's state in advance of a periodic scrape request."""
        super(Interface, self).update()
        power_kw = self.calculate_power()
        self.set_register_by_name('power_kw', power_kw)
        sim_time = self.get_register_value('last_timestamp')
        soc = self.calculate_soc(sim_time, power_kw)
        self.set_register_by_name('soc_kwh', soc)
        self.old_timestamp = sim_time

    def calculate_power(self):
        """
            Calculate and return the current power in kW.

            Calculated power is based on the dispatch power value in kW,
            the current SOC %,
            and the device's max charge/discharge power thresholds.

            If the device's SOC is close to its max_soc or its min_soc (assumed to be 0.0),
            the available charge/discharge power is "stepped down" in a straight line.
        """
        dispatch_power = self.get_register_value('dispatch_kw')
        current_soc = self.get_register_value('soc_kwh')
        max_soc = self.get_register_value('max_soc_kwh')
        max_charge_kw = self.get_register_value('max_charge_kw')
        max_discharge_kw = self.get_register_value('max_discharge_kw')
        reduced_charge_soc_threshold = self.get_register_value('reduced_charge_soc_threshold')
        reduced_discharge_soc_threshold = self.get_register_value('reduced_discharge_soc_threshold')

        soc_percent = float(current_soc) / max_soc
        if dispatch_power >= 0:                         # Charging
            if soc_percent <= reduced_charge_soc_threshold:
                adjustment_fraction = 1.0
            else:
                # Reduce charging power in a straight line -- 100% at SOC_CHARGE_THRESHOLD, 0% at max_charge_kw
                adjustment_fraction = (max_soc - current_soc) / (max_soc - (reduced_charge_soc_threshold * max_soc))
            power_kw = min(adjustment_fraction * dispatch_power, max_charge_kw)
        else:                                           # Discharging
            if soc_percent >= reduced_discharge_soc_threshold:
                adjustment_fraction = 1.0
            else:
                # Reduce discharging power in a straight line -- 100% at SOC_DISCHARGE_THRESHOLD, 0% at 0
                adjustment_fraction = current_soc / (reduced_discharge_soc_threshold * max_soc)
            power_kw = max(adjustment_fraction * dispatch_power, -max_discharge_kw)
        power_kw = int(1000 * power_kw) / 1000.0        # Round to nearest thousandth
        return power_kw

    def calculate_soc(self, sim_time, power_kw):
        """
            Calculate and return the current state of charge (SOC).

            The new SOC is based on SOC, current power, elapsed time and max SOC.

        :param sim_time: (str) Current time on the simulation clock.
        :param power_kw: (float) Current charge/discharge power.
        :return: (float) The new SOC value in kWh.
        """
        elapsed_time_hrs = 0.0
        if sim_time and self.old_timestamp:
            try:
                new_time = utils.parse_timestamp_string(sim_time)
                old_time = utils.parse_timestamp_string(self.old_timestamp)
                if new_time > old_time:
                    elapsed_time_hrs = (new_time - old_time).total_seconds() / 3600.0
            except ValueError:
                pass
        new_soc = self.get_register_value('soc_kwh') + (power_kw * elapsed_time_hrs)
        new_soc = min(max(new_soc, 0.0), self.get_register_value('max_soc_kwh'))
        new_soc = int(1000 * new_soc) / 1000.0          # Round to nearest thousandth
        return new_soc
