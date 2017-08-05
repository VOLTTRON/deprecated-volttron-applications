'''
Copyright (c) 2016, Battelle Memorial Institute
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

This material was prepared as an account of work sponsored by an
agency of the United States Government.  Neither the United States
Government nor the United States Department of Energy, nor Battelle,
nor any of their employees, nor any jurisdiction or organization
that has cooperated in the development of these materials, makes
any warranty, express or implied, or assumes any legal liability
or responsibility for the accuracy, completeness, or usefulness or
any information, apparatus, product, software, or process disclosed,
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
'''

import math
from .common import check_date, create_table_key, pre_conditions, check_run_status, setpoint_control_check
from volttron.platform.agent.math_utils import mean

INCONSISTENT_DATE = -89.0
INSUFFICIENT_DATA = -79.0
DUCT_STC_RCX = 'Duct Static Pressure Set Point Control Loop Dx'
DUCT_STC_RCX1 = 'Low Duct Static Pressure Dx'
DUCT_STC_RCX2 = 'High Duct Static Pressure Dx'
DX = '/diagnostic message'
DX_LIST = [DUCT_STC_RCX, DUCT_STC_RCX1, DUCT_STC_RCX2]


class DuctStaticAIRCx(object):
    """Air-side HVAC Self-Correcting Diagnostic: Detect and correct
    duct static pressure problems.
    """
    def __init__(self, no_req_data, auto_correct_flag, stpt_deviation_thr,
                 max_stcpr_stpt, stcpr_retuning, zn_high_dmpr_thr,
                 zn_low_dmpr_thr, hdzn_dmpr_thr, min_stcpr_stpt,
                 analysis, stcpr_stpt_cname):
        # Initialize data arrays
        self.table_key = None
        self.zn_dmpr_array = []
        self.stcpr_stpt_array = []
        self.stcpr_array = []
        self.timestamp_array = []

        # Initialize configurable thresholds
        self.analysis = analysis
        self.stcpr_stpt_cname = stcpr_stpt_cname
        self.no_req_data = no_req_data
        self.stpt_deviation_thr = stpt_deviation_thr
        self.max_stcpr_stpt = max_stcpr_stpt
        self.stcpr_retuning = stcpr_retuning
        self.zn_high_dmpr_thr = zn_high_dmpr_thr
        self.zn_low_dmpr_thr = zn_low_dmpr_thr

        self.auto_correct_flag = auto_correct_flag
        self.min_stcpr_stpt = float(min_stcpr_stpt)
        self.hdzn_dmpr_thr = hdzn_dmpr_thr
        self.dx_offset = 0.0

        self.low_msg = ('The supply fan is running at nearly 100% of full '
                        'speed, data corresponding to {} will not be used.')
        self.high_msg = ('The supply fan is running at the minimum speed, '
                         'data corresponding to {} will not be used.')

    def reinitialize(self):
        """Reinitialize data arrays"""
        self.table_key = None
        self.zn_dmpr_array = []
        self.stcpr_stpt_array = []
        self.stcpr_array = []
        self.timestamp_array = []
        self.data = {}
        self.dx_table = {}

    def duct_static(self, current_time, stcpr_stpt_data, stcpr_data,
                    zn_dmpr_data, low_dx_cond, high_dx_cond, dx_result):
        """
        Check duct static pressure AIRCx pre-requisites and manage analysis data set.
        :param current_time:
        :param stcpr_stpt_data:
        :param stcpr_data:
        :param zn_dmpr_data:
        :param low_dx_cond:
        :param high_dx_cond:
        :param dx_result:
        :return:
        """
        try:
            if check_date(current_time, self.timestamp_array):
                dx_result = pre_conditions(INCONSISTENT_DATE, DX_LIST, self.analysis, current_time, dx_result)
                self.reinitialize()
                return dx_result

            if low_dx_cond:
                dx_result.log(self.low_msg.format(current_time))

            if high_dx_cond:
                dx_result.log(self.high_msg.format(current_time))

            run_status = check_run_status(self.timestamp_array, current_time, self.no_req_data)

            if run_status is None:
                dx_result.log("{} - Insufficient data to produce a valid diagnostic result.".format(current_time))
                dx_result = pre_conditions(INSUFFICIENT_DATA, DX_LIST, self.analysis, current_time, dx_result)
                self.reinitialize()
                return dx_result

            if run_status:
                self.table_key = create_table_key(self.analysis, self.timestamp_array[-1])
                avg_stcpr_stpt, dx_table, dx_result = setpoint_control_check(self.stcpr_stpt_array, self.stcpr_array,
                                                                             self.stpt_deviation_thr, DUCT_STC_RCX,
                                                                             self.dx_offset, dx_result)

                self.dx_table.update(dx_table)
                dx_result = self.low_stcpr_dx(dx_result, avg_stcpr_stpt)
                dx_result = self.high_stcpr_dx(dx_result, avg_stcpr_stpt)
                dx_result.insert_table_row(self.table_key, self.dx_table)
                self.reinitialize()
                return dx_result
        finally:
            self.stcpr_stpt_array.append(mean(stcpr_data))
            self.stcpr_array.append(mean(stcpr_stpt_data))
            self.zn_dmpr_array.append(mean(zn_dmpr_data))
            self.timestamp_array.append(current_time)

    def low_stcpr_dx(self, dx_result, avg_stcpr_stpt):
        """
        Diagnostic to identify and correct low duct static pressure

        (correction by modifying duct static pressure set point).
        :param dx_result:
        :param avg_stcpr_stpt:
        :return:
        """
        zn_dmpr = self.zn_dmpr_array[:]
        zn_dmpr.sort(reverse=False)
        dmpr_low_temps = zn_dmpr[:int(math.ceil(len(self.zn_dmpr_array)*0.5)) if len(self.zn_dmpr_array) != 1 else 1]
        dmpr_low_avg = mean(dmpr_low_temps)

        dmpr_high_temps = zn_dmpr[int(math.ceil(len(self.zn_dmpr_array)*0.5)) - 1 if len(self.zn_dmpr_array) != 1 else 0:]
        dmpr_high_avg = mean(dmpr_high_temps)
        thresholds = zip(self.zn_high_dmpr_thr.items(), self.zn_low_dmpr_thr.items())
        diagnostic_msg = {}

        for (key, zn_high_dmpr_thr), (key2, zn_low_dmpr_thr) in thresholds:
            if dmpr_high_avg > zn_high_dmpr_thr and dmpr_low_avg > zn_low_dmpr_thr:
                if avg_stcpr_stpt is None:
                    # Create diagnostic message for fault
                    # when duct static pressure set point
                    # is not available.
                    msg = "{} - duct static pressure is too low but set point data is not available.".format(key)
                    result = 14.1
                elif self.auto_correct_flag:
                    aircx_stcpr_stpt = avg_stcpr_stpt + self.stcpr_retuning
                    if aircx_stcpr_stpt <= self.max_stcpr_stpt:
                        dx_result.command(self.stcpr_stpt_cname, aircx_stcpr_stpt)
                        stcpr_stpt = '%s' % float("%.2g" % aircx_stcpr_stpt)
                        stcpr_stpt = stcpr_stpt + " in. w.g."
                        msg = "{} - duct static pressure is too low. Set point increased to: {}".format(key,
                                                                                                        stcpr_stpt)
                        result = 11.1
                    else:
                        dx_result.command(self.stcpr_stpt_cname, self.max_stcpr_stpt)
                        stcpr_stpt = '%s' % float("%.2g" % self.max_stcpr_stpt)
                        stcpr_stpt = stcpr_stpt + " in. w.g."
                        msg = "{} - duct static pressure is too low. Auto-correcting to max set point {}.".format(key,
                                                                                                                  stcpr_stpt)
                        result = 12.1
                else:
                    msg = "{} - duct static pressure is too low but auto-correction is not enabled.".format(key)
                    result = 13.1
            else:
                msg = "{} - No retuning opportunities detected for Low duct static pressure diagnostic.".format(key)
                result = 10.0
            diagnostic_msg.update({key: result})
            dx_result.log(msg)

        dx_result.insert_table_row(self.table_key, {DUCT_STC_RCX1 + DX: diagnostic_msg})
        return dx_result

    def high_stcpr_dx(self, dx_result, avg_stcpr_stpt):
        """
        Diagnostic to identify and correct high duct static pressure

        (correction by modifying duct static pressure set point)
        :param dx_result:
        :param avg_stcpr_stpt:
        :return:
        """
        zn_dmpr = self.zn_dmpr_array[:]
        zn_dmpr.sort(reverse=True)
        zn_dmpr = zn_dmpr[:int(math.ceil(len(self.zn_dmpr_array)*0.5)) if len(self.zn_dmpr_array) != 1 else 1]
        avg_zn_damper = mean(zn_dmpr)
        diagnostic_msg = {}

        for key, hdzn_dmpr_thr in self.hdzn_dmpr_thr.items():
            if avg_zn_damper <= hdzn_dmpr_thr:
                if avg_stcpr_stpt is None:
                    # Create diagnostic message for fault
                    # when duct static pressure set point
                    # is not available.
                    msg = "{} - duct static pressure is too high but set point data is not available.".format(key)
                    result = 24.1
                elif self.auto_correct_flag:
                    aircx_stcpr_stpt = avg_stcpr_stpt - self.stcpr_retuning
                    if aircx_stcpr_stpt >= self.min_stcpr_stpt:
                        dx_result.command(self.stcpr_stpt_cname, aircx_stcpr_stpt)
                        stcpr_stpt = '%s' % float("%.2g" % aircx_stcpr_stpt)
                        stcpr_stpt = stcpr_stpt + " in. w.g."
                        msg = "{} - duct static pressure is too low. Set point increased to: {}".format(key,
                                                                                                        stcpr_stpt)
                        result = 21.1
                    else:
                        dx_result.command(self.stcpr_stpt_cname, self.min_stcpr_stpt)
                        stcpr_stpt = '%s' % float("%.2g" % self.min_stcpr_stpt)
                        stcpr_stpt = stcpr_stpt + " in. w.g."
                        msg = "{} - duct static pressure is too high. Auto-correcting to max set point {}.".format(key,
                                                                                                                   stcpr_stpt)
                        result = 22.1
                else:
                    msg = "{} - duct static pressure is too high but auto-correction is not enabled.".format(key)
                    result = 23.1
            else:
                msg = "{} - No retuning opportunities detected for high duct static pressure diagnostic.".format(key)
                result = 20.0
            diagnostic_msg.update({key: result})
            dx_result.log(msg)

        dx_result.insert_table_row(self.table_key, {DUCT_STC_RCX2 + DX: diagnostic_msg})
        return dx_result
