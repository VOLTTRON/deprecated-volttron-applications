#
# Copyright 2013, Battelle Memorial Institute
# All rights reserved.
#
# 1. Battelle Memorial Institute (hereinafter Battelle) hereby grants permission
# to any person or entity lawfully obtaining a copy of this software and
# associated documentation files (hereinafter "the Software") to redistribute
# and use the Software in source and binary forms, with or without modification.
# Such person or entity may use, copy, modify, merge, publish, distribute,
# sublicense, and/or sell copies of the Software, and may permit others to do so,
# subject to the following conditions:
#   - Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimers.
#   - Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#   - Other than as used herein, neither the name Battelle Memorial Institute
#     or Battelle may be used in any form whatsoever without
#     the express written consent of Battelle.
# 2. THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL BATTELLE OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR
# TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# 3. The Software was produced by Battelle under Contract No. DE-AC05-76RL01830
# with the Department of Energy.  For five (5) years from September 30, 2013
# the Government is granted for itself and others acting on
# its behalf a nonexclusive, paid-up, irrevocable worldwide license
# in this data to reproduce, prepare derivative works, and perform publicly
# and display publicly, by or on behalf of the Government.  There is provision
# for the possible extension of the term of this license.  Subsequent to that
# period or any extension granted, the Government is granted for itself and
# others acting on its behalf a nonexclusive, paid-up, irrevocable worldwide
# license in this data to reproduce, prepare derivative works, distribute copies
# to the public, perform publicly and display publicly, and to permit others
# to do so.  The specific term of the license can be identified by inquiry made
# to Battelle or DOE.
# Neither the United States nor the United States Department of Energy,
# nor any of their employees, makes any warranty, express or implied,
# or assumes any legal liability or responsibility for the accuracy,
# completeness or usefulness of any data, apparatus, product or
# process disclosed, or represents that its use would not infringe privately
# owned rights.
#

import os
import sqlite3
import ConfigParser

import wu_helper
import sqlite_helper


class Wbe:
    """Whole building energy diagnostics
    To predict energy usage (dependent variable) by analyzing historical data using OutdoorTemp, Humidity, etc.
    Note:
        - Currently supports only 1 independent variable (e.g. OAT)
        - Removed prediction validation code
        - To add HourOfWeek OR Weekday to configuration file later
    """
    def __init__(self, config_file='../config.ini'):
        config = ConfigParser.ConfigParser()
        config.read(config_file)
        self.object = config.get('WBE', 'object')
        self.variable = config.get('WBE', 'variable')
        self.n_degrees = config.get('WBE', 'n_degrees')
        self.deviation = config.get('WBE', 'deviation')
        self.cost_limit = config.get('WBE', 'cost_limit')
        self.price = config.get('WBE', 'price')
        self.threshold = config.get('WBE', 'threshold')
        self.time_diff_tol = config.get('WBE', 'time_diff_tol')
        self.oat_diff_tol = config.get('WBE', 'oat_diff_tol')
        self.actual_start = config.get('WBE', 'actual_start')
        self.actual_stop = config.get('WBE', 'actual_stop')
        self.model_start = config.get('WBE', 'model_start')
        self.model_stop = config.get('WBE', 'model_stop')

    def create_result_table(self, con):
        print("Create result table...")
        # TODO: add other configurable inputs as in output tables
        cur = con.cursor()
        sql = """CREATE TABLE IF NOT EXISTS Results
                    (ObjectId INT, VariableId INT, PostTime DATETIME,
                        dependent_val REAL, Rmse REAL, Mbe REAL, Samples INT,
                        PRIMARY KEY (ObjectId, VariableId, PostTime));"""
        cur.execute(sql)

        time_cond = """AND (ABS((strftime('%H',actual.PostTime)
            +{deviation}*strftime('%w',actual.PostTime))
            -(strftime('%H',model.PostTime)
            +{deviation}*strftime('%w',model.PostTime))))
            <={time_tol}""".format(deviation=self.deviation,
                                   time_tol=self.time_diff_tol)
        # Weekday & weekend cond
        # Weekday & Sat & Sun cond
        # HourOfWeek cond
        first_dependence_cond = "AND ABS(actual.independent_val1-model.independent_val1)<={}".format(self.oat_diff_tol)
        sql = """
                SELECT actual.ObjectId, actual.VariableId, actual.PostTime,
                        median(model.dependent_val),
                        rmse(model.dependent_val, {n_degrees}),
                        mbe(model.dependent_val, {n_degrees}),
                        count(*)
                FROM wbe_data AS actual, wbe_data AS model
                WHERE actual.ObjectId = {object} AND actual.VariableId = {variable}
                    AND model.ObjectId = {object} AND model.VariableId = {variable}
                    AND actual.PostTime BETWEEN '{actual_start}'  AND '{actual_stop}'
                    AND model.PostTime BETWEEN '{model_start}' AND '{model_stop}'
                    {schedule_cond} {conditions}
                GROUP BY strftime('%Y',actual.PostTime),
                        strftime('%m',actual.PostTime),
                        strftime('%d',actual.PostTime),
                        strftime('%H',actual.PostTime);""".format(n_degrees=self.n_degrees,
                                                                  object=self.object,
                                                                  variable=self.variable,
                                                                  actual_start=self.actual_start,
                                                                  actual_stop=self.actual_stop,
                                                                  model_start=self.model_start,
                                                                  model_stop=self.model_stop,
                                                                  schedule_cond=time_cond,
                                                                  conditions=first_dependence_cond)
        cur.execute(sql)
        rows = []
        for row in cur:
            rows.append(row)
        cur.executemany("""INSERT INTO Results (ObjectId, VariableId, PostTime, dependent_val, Rmse, Mbe, Samples)
                            VALUES(?,?,?,?,?,?,?)""", rows)

    def add_forecast_data(self, con):
        # Pull weather underground info
        forecast_weather_rows = wu_helper.get_forecast_temp_10day()
        cur = con.cursor()
        cur.executemany("""INSERT INTO wbe_data (ObjectId, VariableId, PostTime, dependent_val, independent_val1)
                            VALUES(1,3,?,null,?)""", forecast_weather_rows)

    def process(self, db_file, out_dir):
        self.out_dir = out_dir
        con = sqlite3.connect(db_file)

        with con:
            sqlite_helper.create_funcs(con)  # Create necessary functions
            self.add_forecast_data(con)  # Add weather forecast
            self.create_result_table(con)  # Create result table

if __name__ == "__main__":
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    out_dir = os.path.join(cur_dir, "../testcases/disk")
    data_file = os.path.join(out_dir, "sample_data.csv")
    var_file = os.path.join(out_dir, "variables.csv")
    db_file = os.path.join(out_dir, "building1.sqlite")

    # Delete existing db
    if os.path.isfile(db_file):
        os.remove(db_file)

    # Create db file
    sqlite_helper.make_db(data_file, var_file, db_file)

    # Do diagnostics
    wbe = Wbe()
    wbe.process(db_file, out_dir)
    #wbe.process("../testcases/sample_data.csv","../testcases/variables.csv","../testcases")

    print('DONE.')