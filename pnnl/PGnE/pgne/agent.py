# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2016, Battelle Memorial Institute
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


class PGnEAgent(Agent):
    def __init__(self, config_path, **kwargs):
        super(PGnEAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.site = self.config.get('campus')
        self.building = self.config.get('building')
        self.temp_unit = self.config.get('temp_unit')
        self.power_unit = self.config.get('power_unit')
        self.out_temp_name = self.config.get('out_temp_name')
        self.power_name = self.config.get('power_name')
        self.aggregate_in_min = self.config.get('aggregate_in_min')
        self.aggregate_freq = str(self.aggregate_in_min) + 'Min'
        self.ts_name = self.config.get('ts_name')

        self.window_size_in_day = int(self.config.get('window_size_in_day'))
        self.min_required_window_size_in_percent = float(self.config.get('min_required_window_size_in_percent'))
        self.interval_in_min = int(self.config.get('interval_in_min'))
        self.no_of_recs_needed = 10 # self.window_size_in_day * 24 * (60 / self.interval_in_min)
        self.min_no_of_records_needed_after_aggr = int(self.min_required_window_size_in_percent/100 *
                                            self.no_of_recs_needed/self.aggregate_in_min)
        self.schedule_run_in_sec = int(self.config.get('schedule_run_in_hr')) * 3600


        # Testing
        #self.no_of_recs_needed = 200
        #self.min_no_of_records_needed_after_aggr = self.no_of_recs_needed/self.aggregate_in_min


    @Core.receiver('onstart')
    def onstart(self, sender, **kwargs):
        self.core.periodic(self.schedule_run_in_sec, self.calculate_latest_coeffs)

    def calculate_latest_coeffs(self):
        unit_topic_tmpl = "{campus}/{building}/{unit}/{point}"
        unit_points = [self.power_name]
        df = None

        #Get data
        unit = self.temp_unit
        for point in unit_points:
            if point == self.power_name:
                unit = self.power_unit
            unit_topic = unit_topic_tmpl.format(campus=self.site,
                                                building=self.building,
                                                unit=unit,
                                                point=point)
            result = self.vip.rpc.call('platform.historian',
                                       'query',
                                       topic=unit_topic,
                                       count=self.no_of_recs_needed,
                                       order="LAST_TO_FIRST").get(timeout=10000)
            df2 = pd.DataFrame(result['values'], columns=[self.ts_name, point])
            df2[self.ts_name] = pd.to_datetime(df2[self.ts_name])
            df2 = df2.groupby([pd.TimeGrouper(key=self.ts_name, freq=self.aggregate_freq)]).mean()
            # df2[self.ts_name] = df2[self.ts_name].apply(lambda dt: dt.replace(second=0, microsecond=0))
            df = df2 if df is None else pd.merge(df, df2, how='outer', left_index=True, right_index=True)

        #Calculate coefficients
        result_df = self.calculate_coeffs(df)


        # Publish coeffs to store
        #if coeffs is not None:
        #    self.save_coeffs(coeffs, subdevice)

    def convert_units_to_SI(self, df, point, unit):
        if unit == 'degreesFahrenheit':
            df[point] = (df[point]-32) * 5/9
        # Air state assumption: http://www.remak.eu/en/mass-air-flow-rate-unit-converter
        # 1cfm ~ 0.00055kg/s
        if unit == 'cubicFeetPerMinute':
            df[point] = df[point] * 0.00055

    def calculate_coeffs(self, dP):
        dP['time'] = dP['posttime']
        dP = dP.set_index(['posttime'])

        dP.index = pd.to_datetime(dP.index)
        dP['time'] = pd.to_datetime(dP['time'])

        #### Delete the weekend
        dP.columns = ["Tout", "wbe", "Weekday", "time"]
        dP['year'] = dP.index.year
        dP['month'] = dP.index.month
        dP['hour'] = dP.index.hour
        dP['day'] = dP.index.day
        dP = dP[dP.Weekday != 'Sun']
        dP = dP[dP.Weekday != 'Sat']

        ####  Hourly average value
        df = dP.resample('60min').mean()
        dP2 = dP.resample('60min').mean()

        dP = dP[dP.Tout < 150]
        dP = dP[dP.Tout > 20]
        dP = dP.dropna()

        df = df.pivot_table(index=["year", "month", "day"], columns=["hour"], values=["wbe", "Tout"])

        # ### Average using high five outdoor temperature data based on 10 day moving windows

        leng = len(df.index)
        for i in range(0, leng):
            for j in range(0, 24):
                df['power', j] = df.ix[i:i + 10, :].sort([('Tout', j)], ascending=False).head(5).ix[:,
                                 j + 24:j + 25].mean()

        for i in range(0, leng):
            for j in range(0, 24):
                df['power', j][i:i + 1] = df.ix[i:i + 10, :].sort([('Tout', j)], ascending=False).head(5).ix[:,
                                          j + 24:j + 25].mean()

        # ### Average based on 10 day moving windows

        for i in range(0, 24):
            df['Tout_avg', i] = df.ix[:, i:i + 1].rolling(window=10, min_periods=10).mean()

        for i in range(0, 24):
            df['Pow_avg', i] = df.ix[:, i + 24:i + 25].rolling(window=10, min_periods=10).mean()

        df = df.stack(level=['hour'])
        df.power = df.power.shift(216)
        df = df.dropna()
        dq = df.reset_index()
        dq['Data'] = pd.to_datetime(
            dq.year.astype(int).apply(str) + '/' + dq.month.astype(int).apply(str) + '/' + dq.day.astype(int).apply(
                str) + ' ' + dq.hour.astype(int).apply(str) + ":00", format='%Y/%m/%d %H:%M')
        dq = dq.set_index(['Data'])
        dq = dq.drop(['year', 'month', 'day', 'hour'], axis=1)
        dk = dq

        ### Adjusted average using high five outdoor temperature data based on 10 day moving windows
        lengnth = len(dq.index)
        lengnth = lengnth - 4
        dq["Adj"] = 1.0
        for i in range(0, lengnth):
            dq['Adj'][i + 4] = (dq['wbe'][i:i + 4].mean()) / (dq['Pow_avg'][i:i + 4].mean())

        dq['Pow_adj'] = dq['Pow_avg'] * dq['Adj']

        #### Adjusted average based on 10 day moving windows
        lengnth = len(dq.index)
        lengnth = lengnth - 4
        dq["Adj2"] = 1.0
        for i in range(0, lengnth):
            dq['Adj2'][i + 4] = (dq['wbe'][i:i + 4].mean()) / (dq['power'][i:i + 4].mean())

        dq['Adj2'] = dq.Adj2.shift(2)
        dq['power_adj'] = dq['power'] * dq['Adj2']

        return dq

    def save_coeffs(self, coeffs, subdevice):
        topic_tmpl = "analysis/TCM/{campus}/{building}/{unit}/{subdevice}/"
        topic = topic_tmpl.format(campus=self.site,
                                  building=self.building,
                                  unit=self.unit,
                                  subdevice=subdevice)
        T_coeffs = coeffs["T_fit"]
        Q_coeffs = coeffs["Q_fit"]
        headers = {'Date': format_timestamp(get_aware_utc_now())}
        for idx in xrange(0,5):
            T_topic = topic + "T_c" + str(idx)
            Q_topic = topic + "Q_c" + str(idx)
            self.vip.pubsub.publish(
                'pubsub', T_topic, headers, T_coeffs.params[idx])
            self.vip.pubsub.publish(
                'pubsub', Q_topic, headers, Q_coeffs.params[idx])

        _log.debug(T_coeffs.params)
        _log.debug(Q_coeffs.params)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(PGnEAgent)
    except Exception as e:
        _log.exception('unhandled exception')


def test_ols():
    '''To compare result of pandas and R's linear regression'''
    import os

    test_csv = '../test_data/tcm_ZONE_VAV_150_data.csv'
    df = pd.read_csv(test_csv)

    config_path = os.environ.get('AGENT_CONFIG')
    tcm = PGnEAgent(config_path)
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
    tcm = PGnEAgent(os.environ.get('AGENT_CONFIG'))

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
