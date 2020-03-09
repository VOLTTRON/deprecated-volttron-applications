"""
Copyright (c) 2017, Battelle Memorial Institute
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
This material was prepared as an account of work sponsored by an agency of the
United States Government. Neither the United States Government nor the United
States Department of Energy, nor Battelle, nor any of their employees, nor any
jurisdiction or organization that has cooperated in the development of these
materials, makes any warranty, express or implied, or assumes any legal
liability or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed, or
represents that its use would not infringe privately owned rights.
Reference herein to any specific commercial product, process, or service by
trade name, trademark, manufacturer, or otherwise does not necessarily
constitute or imply its endorsement, recommendation, or favoring by the
United States Government or any agency thereof, or Battelle Memorial Institute.
The views and opinions of authors expressed herein do not necessarily state or
reflect those of the United States Government or any agency thereof.
PACIFIC NORTHWEST NATIONAL LABORATORY
operated by
BATTELLE
for the
UNITED STATES DEPARTMENT OF ENERGY
under Contract DE-AC05-76RL01830
"""
import logging
from datetime import timedelta as td
from volttron.platform.agent.math_utils import mean
from volttron.platform.agent.utils import setup_logging
from .. import constants

setup_logging()
_log = logging.getLogger(__name__)

class TemperatureSensor(object):
    """
    Air-side HVAC temperature sensor diagnostic for AHU/RTU systems.
    TempSensorDx uses metered data from a BAS or controller to
    diagnose if any of the temperature sensors for an AHU/RTU are accurate and
    reliable.
    """

    def __init__(self):
        # Initialize data arrays
        self.oat_values = []
        self.rat_values = []
        self.mat_values = []
        self.timestamp = []

        self.temp_sensor_problem = None
        self.max_dx_time = None

        # Application thresholds (Configurable)
        self.data_window = None
        self.no_required_data = None
        self.oat_mat_check = None
        self.temp_diff_thr = None
        self.inconsistent_date = None
        self.sensor_damper_dx = DamperSensorInconsistency()




    def set_class_values(self, data_window, no_required_data, temp_diff_thr, open_damper_time, oat_mat_check, temp_damper_threshold):
        """Set the values needed for doing the diagnostics"""
        self.max_dx_time = td(minutes=60) if td(minutes=60) > data_window else data_window * 3 / 2
        self.data_window = data_window
        self.no_required_data = no_required_data
        self.oat_mat_check = oat_mat_check
        self.temp_diff_thr = temp_diff_thr
        self.inconsistent_date = {key: 3.2 for key in self.temp_diff_thr}
        self.sensor_damper_dx.set_class_values(data_window, no_required_data, open_damper_time, oat_mat_check, temp_damper_threshold)




class DamperSensorInconsistency(object):
    """
    Air-side HVAC temperature sensor diagnostic for AHU/RTU systems.
    TempSensorDx uses metered data from a BAS or controller to
    diagnose if any of the temperature sensors for an AHU/RTU are accurate and
    reliable.
    """

