# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
"""
Copyright (c) 2015, Battelle Memorial Institute
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the FreeBSD Project.
'''
'''
This material was prepared as an account of work sponsored by an
agency of the United States Government.  Neither the United States
Government nor the United States Department of Energy, nor Battelle,
nor any of their employees, nor any jurisdiction or organization
that has cooperated in the development of these materials, makes
any warranty, express or implied, or assumes any legal liability
or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed
or represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or
service by trade name, trademark, manufacturer, or otherwise does
not necessarily constitute or imply its endorsement, recommendation,
r favoring by the United States Government or any agency thereof,
or Battelle Memorial Institute. The views and opinions of authors
expressed herein do not necessarily state or reflect those of the
United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY
operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
"""
import logging
import sys
from datetime import timedelta as td, datetime as dt
from dateutil import parser
import numpy as np
from volttron.platform.messaging import headers as headers_mod, topics
from volttron.platform.agent.utils import setup_logging
from volttron.platform.vip.agent import Agent, Core, RPC
from volttron.platform.agent import utils

__author__ = 'Robert Lutes <robert.lutes@pnnl.gov>'
__copyright__ = 'Copyright (c) 2015, Battelle Memorial Institute'
__license__ = 'FreeBSD'
INCONCLUSIVE = 'inconclusive'
SENSOR_DX = 'Temperature Sensor Dx'
ECON1 = 'Not economizing when unit should'
ECON2 = 'Economizing when unit should not'
VENTILATION_DX = 'Insufficient ventilation diagnostic'
WEATHER_BASE_TOPIC = 'weather/response/temperature/'

setup_logging()
_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.debug,
                    format='%(asctime)s   %(levelname)-8s %(message)s',
                    datefmt='%m-%d-%y %H:%M:%S')



class SccEconomizerDx(Agent):
    def __init__(self, config_path, **kwargs):
        super(SccEconomizerDx, self).__init__(**kwargs)
        config = utils.load_config(config_path)

        device_path = dict((key, config[key])
                           for key in ['campus', 'building', 'unit'])
        units = config.get('Temperature Units', 'temp_f')
        if units == "F":
            units = "temp_f"
        if units == "C":
            units = "temp_C"
        self.weather_topic = 'weather/response/temperature/' + units

        self.config_error = False
        self.mat_issing = False
        self.lock_timer = None
        self.lock_acquired = False
        self.is_running = False
        self.previous_mode = None
        self.temp_fault = False
        self.mat_missing = False

        self.agent_id = config.get('agentid')
        self.econ_type = config.get('ECONOMIZER TYPE').lower()
        self.zip_code = config.get('zip_code', None)
        points = config.get('points')
        self.temp_sensors = points['Temperature Sensors']
        self.commands = points['CommandStatus']
        self.device_topic = topics.DEVICES_VALUE(point='all', path='', **device_path)

        # Read in configurable thresholds.
        if self.econ_type.lower() == 'hl':
            self.econ_highlimit = float(config.get('HIGH LIMIT', 65.0))
        self.validate_oat = "UNVALIDATED"
        self.oat_sensor_threshold = config.get('OAT SENSOR THRESHOLD', 10.0)
        self.oat_high = config.get('OAT HIGH', 100.0)
        self.oat_low = config.get('OAT LOW', 40.0)
        dx_time = int(config.get('MINIMUM Dx TIME', 10))
        self.min_dx_time = dx_time if dx_time >= 10 else 10
        steady_time = int(config.get('STEADY STATE TIME', 5))
        self.steady_time = steady_time if steady_time >= 5 else 5
        self.temp_threshold = float(config.get('TEMPERATURE THRESHOLD', 8.0))
        self.min_oad = float(config.get('Minimum OAD set point', 15.0))
        self.dband = float(config.get('BAND', 1.0))
        self.sensitivity = float(config.get('DX Sensitivity', 0))

        # Initialize data arrays.
        self._validate_oat = []
        self.mat_arr = []
        self.oat_arr = []
        self.rat_arr = []
        self.oad_arr = []
        self.steady_state = []
        self.mode_op_time = []
        # Required points for economizer analytics

        self.oat_name = self.temp_sensors.get('OutsideAirTemperature', 'not-measured').lower()
        self.fan_status_name = self.commands.get('SupplyFanStatus', 'not-measured').lower()

        if self.oat_name == 'not-measured' or self.fan_status_name == 'not-measured':
            _log.info('Outdoor-air temperature and supply fan status must be provided for diagnostic.')
            sys.exit()

        self.mat_name = self.temp_sensors.get('MixedAirTemperature', 'not-measured').lower()
        self.dat_name = self.temp_sensors.get('DischargeAirTemperature', 'not-measured').lower()

        if self.mat_name == 'not-measured':
            self.mat_name = self.dat_name
            self.compressor_off_time = []
            self.mat_missing = True

        if self.mat_name == 'not-measured' and self.dat_name == 'not-measured':
            _log.info('Mixed-air temperature or discharge-air temperature must be provided for diagnostic.')
            sys.exit()

        self.cool_call_missing = False
        self.cool_call_name = self.commands.get('ThermostatCoolCall', 'not-measured').lower()
        self.cooling_op = None
        if self.cool_call_name == 'not-measured':
            self.cool_call_missing = True
            self.zone_temp = self.temp_sensors.get('ZoneTemperature', 'not-measured').lower()
            self.cool_temp_sp = self.temp_sensors.get('CoolingTemperatureSetPoint', 'not-measured').lower()
            self.heat_temp_sp = self.temp_sensors.get('HeatingTemperatureSetPoint', 'not-measured').lower()
            if self.zone_temp == 'not-measured' or self.zone_temp_sp == 'not-measured':
                self.cooling_op = INCONCLUSIVE

        self.rat_name = self.temp_sensors.get('ReturnAirTemperature', 'not-measured').lower()
        if self.rat_name == 'not-measured':
            self.zone_temp = self.temp_sensors.get('ZoneTemperature', 'not-measured').lower()
            if self.zone_temp == 'not-measured':
                _log.debug('Diagnostic requires either return- or zone-air temperature.')
                sys.exit()
            self.rat_name = self.zone_temp
        self.compressor_name = self.commands.get('CompressorCommand', 'not-measured').lower()
        if self.compressor_name == 'not-measured' and self.dat_name == 'not-measured':
            self.comp_status = INCONCLUSIVE
            if self.cooling_op is not None and self.cooling_op == INCONCLUSIVE:
                _log.debug('Cannot determine unit mode:  Please view '
                           'readme txt to verify diagnostic data '
                           'requirements.')
                sys.exit()

        self.oad_name = self.commands.get('OutsideAirDamper', 'not-measured').lower()
        self.fan_speed = self.commands.get('SupplyFanSpeed', None)
        self.heat_name = self.commands.get('HeatingCommand', None)

    def initialize_dataset(self):
        '''Reinitialize data for next operational mode'''
        self._validate_oat = []
        self.mat_arr = []
        self.oat_arr = []
        self.rat_arr = []
        self.oad_arr = []
        self.steady_state = []
        self.mode_op_time = []
        self.previous_mode = None
        return

    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        self.is_running = True

    @Core.receiver('onstart')
    def starting_base(self, sender, **kwargs):
        _log.debug('Subscribing to '+self.weather_topic)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.weather_topic,
                                  callback=self.weather_response)
        _log.debug('Subscribing to '+self.device_topic)
        self.vip.pubsub.subscribe(peer='pubsub',
                                  prefix=self.device_topic,
                                  callback=self.on_new_data)
                     
    @Core.periodic(900)
    def weather_request(self):
        '''Request weather data for device location'''
        # TODO: add check to verify agent is running use subprocess.call()
        if self.config_error:
            return
#            _log.debug('weather request for sending')
        if self._validate_oat and self.zip_code is not None:
            _log.debug('weather request for {}'.format(self.zip_code))
            headers = {
                'Content-Type': 'text/plain',
                'requesterID': self.agent_id
            }
            msg = {'zipcode': str(self.zip_code)}
            self.vip.pubsub.publish('pubsub', 'weather/request', headers, msg)    

    def weather_response(self, peer, sender, bus, topic, headers, message):
        data = float(message[0])
        self.validate(data)

    def validate(self, ws_oat):
        '''
        check averaged oat from building sensor with
        oat reading from weather station (WeatherUnderground)
        '''
        avg_oat = np.mean(self._validate_oat)
        self._validate_oat = []
        if abs(avg_oat - ws_oat) > (self.oat_sensor_threshold):
            _log.debug('Outdoor-air temperature sensor is not consistent '
                       'with weather station.')
            self.validate_oat = "FAULT"
            return
        self.validate_oat = "GOOD"

    def favorable_for_economizing(self, oat, reference):
        if reference - oat > self.dband:
            return True
        return False

    def on_new_data(self, peer, sender, bus, topic, headers, message):
        '''Subscribe to device data from message bus and determine mode

        of operation.  When mode changes call economizer diagnostic.
        '''
        if self.config_error:
            _log.info('Error when reading configuration file.')
            return
        data = {}
        for key, value in message[0].items():
            data[key.lower()] = value

        if not int(data[self.fan_status_name]):
            _log.info('UNIT IS OFF.')
            return

        current_time = parser.parse(headers.get('Date'))

        _log.info('Data Collection in Progress.')

        cur_oat = float(data.get(self.oat_name))
        cur_rat = float(data.get(self.rat_name))
        cur_mat = float(data.get(self.mat_name))
        cur_oad = None
        if self.oad_name != 'not-measured':
            try:
                cur_oad = float(data.get(self.oad_name))
            except KeyError:
                cur_oad = None

        if self.dat_name != 'not-measured':
            cur_dat = float(data.get(self.dat_name))

        if cur_oat > self.oat_high or cur_oat < self.oat_low:
            _log.info('Outdoor air temperature is outside high/low'
                      'bounds for diagnostic.'+' at ' + str(current_time))
            return

        if abs(cur_oat - cur_rat) < self.temp_threshold:
            _log.debug('Outside and return-air temperatures are too '
                       'close for a conclusive diagnostic for timetamp: {}.'.format(current_time))
            return

        cooling_mode = INCONCLUSIVE
        if not self.cool_call_missing:
            cooling_mode = int(data[self.cool_call_name])
        else:
            if self.cooling_op != INCONCLUSIVE:
                zone_temp = float(data[self.zone_temp])
                cool_temp_sp = float(data[self.cool_temp_sp])
                heat_temp_sp = float(data[self.heat_temp_sp])
                if zone_temp - cool_temp_sp > self.dband:
                    cooling_mode = True
                elif heat_temp_sp - zone_temp > self.dband:
                    cooling_mode = False

        if self.compressor_name != 'not-measured':
            comp_status = int(data.get(self.compressor_name))
        elif self.dat_name != 'not-measured':
            if (cur_oat - cur_dat) > self.temp_threshold and (cur_rat - cur_dat) > self.temp_threshold:
                comp_status = 1
            else:
                comp_status = 0
        else:
            comp_status = INCONCLUSIVE

        if self.mat_missing and (comp_status == INCONCLUSIVE or comp_status):
            _log.debug('Cannot use discharge-air temperature for diagnostics while compressor is running.')
            self.compressor_off_time = []
            return
        elif self.mat_missing and not comp_status:
            self.compressor_off_time.append(current_time)
            if self.compressor_off_time[-1] - self.compressor_off_time[0]  < td(minutes=self.steady_time):
                _log.debug('Waiting for steady state conditions for use of discharge-air temperature in diagnostics.')
                return
            
        if cooling_mode == INCONCLUSIVE and comp_status != INCONCLUSIVE:
            if comp_status:
                cooling_mode = True
            else:
                cooling_mode = False

        if self.econ_type == 'hl':
            econ_cond = self.favorable_for_economizing(cur_oat, self.econ_highlimit)
        elif self.econ_type == 'ddb':
            econ_cond = self.favorable_for_economizing(cur_oat, cur_rat)
        else:
            _log.debug('Economizer type is not configured correctly.')
            return

        if cooling_mode == INCONCLUSIVE:
            _log.debug('Could not determine operating mode at time: {}.'.format(current_time))
            return
        if cooling_mode != INCONCLUSIVE and not cooling_mode:
            current_mode = 0
        elif cooling_mode and (comp_status != INCONCLUSIVE and comp_status) and econ_cond:
            current_mode = 1
        elif cooling_mode and (comp_status != INCONCLUSIVE and not comp_status) and econ_cond:
            current_mode = 2
        elif cooling_mode or (comp_status != INCONCLUSIVE and comp_status) and not econ_cond:
            current_mode = 3
        else:
            _log.debug('Unable to determine mode of operation for unit.')
            return

        _log.debug('Operating Mode: {} ---- For timestamp: {}.'.format(current_mode, current_time))
        if (self.previous_mode == current_mode or self.previous_mode is None) and (not self.mode_op_time or (self.mode_op_time[-1] - self.mode_op_time[0] < td(minutes=self.min_dx_time))):
            self.steady_state.append(current_time)
            if self.steady_state[-1] - self.steady_state[0] < td(minutes=self.steady_time):
                return
            _log.debug('Steady state conditions reached at: {}.'.format(current_time))
            self.previous_mode = current_mode
            self.oat_arr.append(cur_oat)
            self._validate_oat.append(cur_oat)
            self.mat_arr.append(cur_mat)
            self.rat_arr.append(cur_rat)
            self.mode_op_time.append(current_time)
            if cur_oad is not None:
                self.oad_arr.append(float(data.get(self.oad_name)))
            return
        elif self.mode_op_time:
            if self.mode_op_time[-1] - self.mode_op_time[0] >= td(minutes=self.min_dx_time):
                _log.debug('Running Diagnostics algorithms.')
                temp_dx = self.temp_sensor_dx()
                result = {SENSOR_DX: temp_dx}
                if temp_dx > 0:
                    _log.debug('Problem detected during temperature at timestamp: {}'.format(current_time))

                self.temp_fault = True
                if current_mode == 1 or current_mode == 2:
                    econ_dx1 = self.economizer_damper_dx1(current_mode)
                    result.update({ECON1: econ_dx1})
                if current_mode == 0 or current_mode == 3:
                    econ_dx2 = self.economizer_damper_dx2(current_mode)
                    result.update({ECON2: econ_dx2})
                econ_dx3 = self.ventilation_dx(current_mode)
                result.update({VENTILATION_DX: econ_dx3})
                _log.debug('Current result dict: {}'.format(result))
        self.initialize_dataset()

    def proactive_sensor_dx(self):
        '''Add proactive temperature sensor method.'''
        return 0.0

    def temp_sensor_dx(self):
        '''
        Diagnostic to detect problems with temperature sensor used
        for control of packaged rooftop air-conditioners (RTUs) or
        air-handlers (AHUs).

        required inputs: outdoor-air temperature, discharge-air
        temperature, return(space)-air temperature.

        user_configurable: self.temp_threshold

        Data collection pre-requisite:  The AHU or RTU has not been
        mechanically cooling or heating for at least five minutes.
        '''
        mat_oat_diff = np.mean(
            [mat - oat for mat, oat in zip(self.mat_arr, self.oat_arr)])
        mat_rat_diff = np.mean(
            [mat - rat for mat, rat in zip(self.mat_arr, self.rat_arr)])

        oat_mat_diff = np.mean(
            [oat - mat for mat, oat in zip(self.mat_arr, self.oat_arr)])
        rat_mat_diff = np.mean(
            [rat - mat for mat, rat in zip(self.mat_arr, self.rat_arr)])

        if mat_rat_diff > self.temp_threshold and mat_oat_diff > self.temp_threshold:
            _log.info('Temperature sensor inconsistency detected.  {} reading is significantly higher than the outside-air temperature and return-air temperature.'.format(self.mat_name))
            return 1
        if rat_mat_diff > self.temp_threshold and oat_mat_diff > self.temp_threshold:
            _log.info('Temperature sensor inconsistency detected.  {} reading is significantly lower than the outside-air temperature and return-air temperature.'.format(self.mat_name))
            return 1
        return 0

    def economizer_damper_dx1(self, mode):
        '''
        Diagnostic to detect problems with the outside-air damper being
        near the minimum position, when unit is in a cooling mode and
        outside conditions are favorable for economization.

        required inputs: outdoor-air temperature, mixed-air temperature
        (or discharge-air temperature), return(space)-air temperature

        user_configurable: self.temp_threshold

        Data collection pre-requisite:

        1.  There is a call for cooling from the space(s) served by the
            RTU/AHU.
                cooling call is "ON"

        2.  IF the DAT is used for the diagnostic (rather than the MAT)
            then the  AHU or RTU must not have been mechanically cooling
            or heating for at least five minutes:

                compressor command is "OFF"
                heating call (command) is "OFF"
        '''
        rat_mat_diff = np.mean(
            [rat - mat for mat, rat in zip(self.mat_arr, self.rat_arr)])
        oat_mat_diff = np.mean(
            [mat - oat for mat, oat in zip(self.mat_arr, self.oat_arr)])
        oat_avg = np.mean(self.oat_arr)
        oad_avg = np.mean(self.oad_arr) if self.oad_arr else None

        if self.temp_fault or oat_avg < 50 and (self.mat_missing and mode == 1):
            if oad_avg is None:
                return 17
            if oad_avg <= self.min_oad:
                _log.debug('Data indicates that the OAD is incorrectly '
                           'commanded to the minimum position.')
                return 16

        if oat_mat_diff - rat_mat_diff > self.temp_threshold:
            if oad_avg is not None and oad_avg > self.min_oad:
                _log.debug('The OAD is commanded open '
                           'but data indicates the damper may '
                           'be stuck near the minimum position')
                return 11
            elif oad_avg is not None and mode == 1:
                _log.debug('Data indicates that the OAD '
                           'is commanded to the minimum position and '
                           'the unit is mechanically cooling. '
                           'This unit may have a non-integrated '
                           'economizer. An integrated economizer can '
                           'reduce energy consumption')
                return 12
            elif oad_avg is not None and mode == 2:
                _log.debug('The OAD is commanded to the minimum '
                           'position when there is a call for '
                           'cooling, conditions are favorable for '
                           'economizing and mechanical cooling is '
                           'off. The OAD should be commanded to a '
                           'position greater than the minimum '
                           '(ideally nearly fully open) to take '
                           'advantage of cool outside air')
                return 13
            elif mode == 1:
                _log.debug('Data indicates the OAD is near minimum '
                           'position. This can be due to unit not '
                           'utilizing an integrated economizer, '
                           'an incorrect command sent to the OAD, '
                           'or a mechanical problem with OAD motor.')
                return 14
            elif mode == 2:
                _log.debug('Data indicates the OAD is near minimum '
                           'position. This can be due to an '
                           'incorrect command sent to the OAD, '
                           'or a mechanical problem with OAD motor.')
                return 15
        return 10

    def economizer_damper_dx2(self, mode):
        '''
        Diagnostic to detect problems with the outside-air damper being
        stuck near the fully open position, not allowing unit to take
        advantage of cool outside air when conditions permit economization.

        required inputs: outdoor-air temperature, mixed-air temperature or
        discharge-air temperature, return(space)-air temperature, and
        cooling mode.

        user_configurable: self.temp_threshold

        Data collection pre-requisite:

        1.  There is not a call for cooling from the space(s) served by the
            RTU/AHU or there is a call for cooling from space(s) but
            conditions are not favorable for economization.
                cooling call is "OFF" or economizing is "OFF"

        2.  IF the DAT is used for the diagnostic (rather than the MAT)
            then the  AHU or RTU must not have been mechanically cooling
            or heating for at least five minutes:

                compressor command is "OFF"
                heating call (command) is "OFF"
        '''
        rat_mat_diff = np.mean(
            [rat - mat for mat, rat in zip(self.mat_arr, self.rat_arr)])
        oat_mat_diff = np.mean(
            [mat - oat for mat, oat in zip(self.mat_arr, self.oat_arr)])
        oad_avg = np.mean(self.oad_arr) if self.oad_arr else None
        if self.temp_fault or (self.mat_missing and mode == 3):
            if oad_avg is None:
                return 27
            if oad_avg - self.min_oad > 10.0:
                _log.debug('Data indicates that the OAD is incorrectly '
                           'commanded significantly above the minimum '
                           'position.')
                return 26

        if rat_mat_diff > oat_mat_diff:
            if oad_avg is not None and oad_avg - self.min_oad < 10.0:
                _log.debug('The OAD is commanded correctly to the '
                           'minimum position but data indicates the '
                           'outdoor-air damper is  open significantly '
                           'more than this.')
                return 21
            elif oad_avg is not None and mode == 3:
                _log.debug('Data indicates that the OAD is '
                           'commanded significantly above the '
                           'minimum damper command when conditions '
                           'are not favorable for economizing and '
                           'the unit is in a cooling mode.')
                return 22
            elif oad_avg is not None and mode == 0:
                _log.debug('Data indicates that the OAD is commanded '
                           'significantly above the minimum damper '
                           'command when conditions are not favorable '
                           'for economizing and the unit is in '
                           'ventilation only mode.')
                return 23
            else:
                _log.debug('Data indicates that there may be a '
                           'problem with the OAD being open more '
                           'than the minimum when conditions call '
                           'for it to be at its minimum position. '
                           'This could be due to an incorrect command '
                           'to the OAD or a mechanical problem with '
                           'the OAD actuator.')
                return 24
        return 20

    def ventilation_dx(self, current_mode):
        '''
            Diagnostic to detect ventilation problems.

            user_configurable: self.temp_threshold

            Data collection pre-requisite:

            1.  There is not a call for cooling from the space(s) served by the
                RTU/AHU or there is a call for cooling from space(s) but
                conditions are not favorable for economization.
                    cooling call is "OFF" or economizing is "OFF"

            2.  IF the DAT is used for the diagnostic (rather than the MAT)
                then the  AHU or RTU must not have been mechanically cooling
                or heating for at least five minutes:

                    compressor command is "OFF"
                    heating call (command) is "OFF"
        '''
        oaf = [(m - r) / (o - r) for o, r, m in zip(self.oat_arr, self.rat_arr, self.mat_arr)]
        oaf = [item if (item < 1.25 and item > 0) else 0 for item in oaf]
        if not oaf:
            _log.debug('OAF calculation resulted in unexpected value.')
            return 31
        oaf_pr = np.mean(oaf)*100.0
        if current_mode == 0 or current_mode == 3:
            if oaf_pr > self.min_oad * (1.0 + (1.0 - self.sensitivity/2)):
                _log.debug('RTU is bringing in excess OA when OAD should be at the minimum position.')
                return 32
        if oaf_pr < self.min_oad/(3.0 - self.sensitivity):
            _log.debug('RTU is brining in insufficient ventilation.')
            return 33
        _log.debug('RTU is meeting ventilation requirements.')
        return 30

def main():
    '''Main method'''
    utils.vip_main(SccEconomizerDx)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
