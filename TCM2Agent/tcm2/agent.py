# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

import os
import sys
import logging
import datetime
from dateutil import parser

from volttron.platform.vip.agent import Agent, Core, PubSub, RPC, compat
from volttron.platform.agent import utils
from volttron.platform.agent.utils import (get_aware_utc_now,
                                           format_timestamp)

import pandas as pd
import statsmodels.formula.api as sm

utils.setup_logging()
_log = logging.getLogger(__name__)


class TCMAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(TCMAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.site = self.config.get('campus')
        self.building = self.config.get('building')
        self.unit = self.config.get('unit')

        self.static_pressure_name = self.config.get('static_pressure_name')
        self.air_flow_rate_name = self.config.get('air_flow_rate_name')
        self.aggregate_in_min = self.config.get('aggregate_in_min')
        self.aggregate_freq = str(self.aggregate_in_min) + 'Min'
        self.ts_name = self.config.get('ts_name')
        self.fan_power_name = self.config.get('fan_power_name')

        self.window_size_in_day = int(self.config.get('window_size_in_day'))
        self.min_required_window_size_in_percent = float(self.config.get('min_required_window_size_in_percent'))
        self.interval_in_min = int(self.config.get('interval_in_min'))
        self.no_of_recs_needed = self.window_size_in_day * 24 * (60 / self.interval_in_min)
        self.min_no_of_records_needed_after_aggr = int(self.min_required_window_size_in_percent/100 *
                                            self.no_of_recs_needed/self.aggregate_in_min)
        self.schedule_run_in_sec = int(self.config.get('schedule_run_in_day')) * 86400

        # Testing
        #self.no_of_recs_needed = 200
        #self.min_no_of_records_needed_after_aggr = self.no_of_recs_needed/self.aggregate_in_min


    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        self.core.periodic(self.schedule_run_in_sec, self.calculate_latest_coeffs)

    def calculate_latest_coeffs(self):
        unit_topic_tmpl = "{campus}/{building}/{unit}/{point}"
        unit_points = [self.fan_power_name, self.static_pressure_name, self.air_flow_rate_name]
        df = None

        for point in unit_points:
            unit_topic = unit_topic_tmpl.format(campus=self.site,
                                                building=self.building,
                                                unit=self.unit,
                                                point=point)
            result = self.vip.rpc.call('platform.historian',
                                       'query',
                                       topic=unit_topic,
                                       count=self.no_of_recs_needed,
                                       order="LAST_TO_FIRST").get(timeout=1000)
            df2 = pd.DataFrame(result['values'], columns=[self.ts_name, point])
            self.convert_units_to_SI(df2, point, result['metadata']['units'])
            df2[self.ts_name] = pd.to_datetime(df2[self.ts_name])
            df2 = df2.groupby([pd.TimeGrouper(key=self.ts_name, freq=self.aggregate_freq)]).mean()
            #df2[self.ts_name] = df2[self.ts_name].apply(lambda dt: dt.replace(second=0, microsecond=0))
            df = df2 if df is None else pd.merge(df, df2, how='outer', left_index=True, right_index=True)

        #print(df)
        coeffs = self.calculate_coeffs(df)
        # Publish coeffs to store
        if coeffs is not None:
            self.save_coeffs(coeffs)

    def convert_units_to_SI(self, df, point, unit):
        if unit == 'kilowatts':
            df[point] = df[point] * 1000
        if unit == 'inchesOfWater':
            df[point] = df[point] * 249.088908333
        if unit == 'cubicFeetPerMinute':
            df[point] = df[point] * 0.00047194745

    def calculate_coeffs(self, df):
        # check if there is enough data
        l = len(df.index)
        if l < self.min_no_of_records_needed_after_aggr:
            _log.exception('Not enough data to process')
            return None

        df = df.dropna(subset=[self.air_flow_rate_name, self.static_pressure_name])

        df[self.air_flow_rate_name+'2'] = (df[self.air_flow_rate_name] * df[self.air_flow_rate_name])
        df[self.air_flow_rate_name+'3'] = (df[self.air_flow_rate_name+'2'] * df[self.air_flow_rate_name])
        df[self.static_pressure_name+'2'] = (df[self.static_pressure_name] * df[self.static_pressure_name])

        # calculate model coefficients
        formula = "{power} ~ {flow} + {flow2} + {flow3} + {pressure} + {pressure2}".format(
            power=self.fan_power_name,
            flow=self.air_flow_rate_name,
            flow2=self.air_flow_rate_name+'2',
            flow3=self.air_flow_rate_name+'3',
            pressure=self.static_pressure_name,
            pressure2=self.static_pressure_name+'2'
        )
        coeffs = sm.ols(formula=formula, data=df).fit()

        return coeffs

    def save_coeffs(self, coeffs):
        topic_tmpl = "analysis/TCM2/{campus}/{building}/{unit}/"
        topic = topic_tmpl.format(campus=self.site,
                                  building=self.building,
                                  unit=self.unit)

        headers = {'Date': format_timestamp(get_aware_utc_now())}
        for idx in xrange(0,6):
            FP_topic = topic + "FanPower_c" + str(idx)
            self.vip.pubsub.publish(
                'pubsub', FP_topic, headers, coeffs.params[idx])

        _log.debug(coeffs.params)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(TCMAgent)
    except Exception as e:
        _log.exception('unhandled exception')


def test_ols():
    '''To compare result of pandas and R's linear regression'''
    import os

    test_csv = '../test_data/tcm_ZONE_VAV_150_data.csv'
    df = pd.read_csv(test_csv)

    config_path = os.environ.get('AGENT_CONFIG')
    tcm = TCMAgent(config_path)
    coeffs = tcm.calculate_coeffs(df)
    if coeffs is not None:
        T_coeffs = coeffs["T_fit"]
        Q_coeffs = coeffs["Q_fit"]
        _log.debug(T_coeffs.params)
        _log.debug(Q_coeffs.params)


def test_api():
    '''To test Volttron APIs'''
    import os

    topic_tmpl = "{campus}/{building}/{unit}/{subdevice}/{point}"
    tcm = TCMAgent(os.environ.get('AGENT_CONFIG'))

    topic1 = topic_tmpl.format(campus='PNNL',
                               building='SEB',
                               unit='AHU1',
                               subdevice='VAV123A',
                               point='MaximumZoneAirFlow')
    result = tcm.vip.rpc.call('platform.historian',
                              'query',
                              topic=topic1,
                              count=20,
                              order="LAST_TO_FIRST").get(timeout=100)
    assert result is not None

if __name__ == '__main__':
    # Entry point for script
    sys.exit(main())
    #test_api()
