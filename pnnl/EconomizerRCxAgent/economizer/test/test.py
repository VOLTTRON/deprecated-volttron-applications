"""
File used to unit test EconimizerRC
"""
import unittest
import os
import sys
from datetime import timedelta as td
sys.path.append("..")
from diagnostics.temperature_sensor_dx import TempSensorDx
from volttron.platform.agent.driven import Results
from datetime import datetime


class TestDiagnostics(unittest.TestCase):
    """
    Contains all the tests for diagnostics
    """

    def test_temp_sensor_dx_creation(self):
        """test the  creation of temp sensor diagnostic class"""
        oat_mat_check = {
            'low': 6.0,
            'normal': 5.0,
            'high': 4.0
        }
        temp_difference_threshold = {
            'low': 6.0,
            'normal': 4.0,
            'high': 2.0 }
        data_window = td(minutes=30)
        temp_sensor = TempSensorDx(data_window, 15, temp_difference_threshold, 5,
                 oat_mat_check, 90, 'Test')
        if isinstance(temp_sensor, TempSensorDx):
            assert True
        else:
            assert False

    def test_temp_sensor_dx_econ_alg1(self):
        """test the  econ_alg1 method"""
        oat_mat_check = {
            'low': 6.0,
            'normal': 5.0,
            'high': 4.0
        }
        temp_difference_threshold = {
            'low': 6.0,
            'normal': 4.0,
            'high': 2.0}
        data_window = td(minutes=30)
        temp_sensor = TempSensorDx(data_window, 15, temp_difference_threshold, 5,
                 oat_mat_check, 90, 'Test')
        temp_sensor.timestamp.append(datetime.fromtimestamp(1000))
        oat = 5
        rat = 5
        mat = 5
        oad = 5
        cur_time = datetime.fromtimestamp(1036)
        dx_result = Results()
        result1, result2 = temp_sensor.econ_alg1(dx_result, oat, rat, mat, oad, cur_time)
        if isinstance(result1, Results):
            assert True
        else:
            assert False
        assert result2 == None

    def test_temp_sensor_dx_econ_alg1_err(self):
        """test the  econ_alg1 method"""
        oat_mat_check = {
            'low': 6.0,
            'normal': 5.0,
            'high': 4.0
        }
        temp_difference_threshold = {
            'low': 6.0,
            'normal': 4.0,
            'high': 2.0}
        data_window = td(minutes=30)
        temp_sensor = TempSensorDx(data_window, 15, temp_difference_threshold, 5,
                 oat_mat_check, 90, 'Test')
        temp_sensor.timestamp.append(datetime.fromtimestamp(1000))
        oat = 50
        rat = 50
        mat = 50
        oad = 50
        cur_time = datetime.fromtimestamp(1036)
        dx_result = Results()
        result1, result2 = temp_sensor.econ_alg1(dx_result, oat, rat, mat, oad, cur_time)
        assert result2 == None

    def test_temp_sensor_dx_aggregate_data(self):
        """test the aggreate data method"""
        oat_mat_check = {
            'low': 6.0,
            'normal': 5.0,
            'high': 4.0
        }
        temp_difference_threshold = {
            'low': 6.0,
            'normal': 4.0,
            'high': 2.0}
        data_window = td(minutes=30)
        temp_sensor = TempSensorDx(data_window, 15, temp_difference_threshold, 5,
                                   oat_mat_check, 90, 'Test')
        temp_sensor.oat_values.append(2)
        temp_sensor.mat_values.append(1)
        temp_sensor.rat_values.append(2)
        temp_sensor.oat_values.append(4)
        temp_sensor.mat_values.append(3)
        temp_sensor.rat_values.append(4)
        avg_oa_ma, avg_ra_ma, avg_ma_oa, avg_ma_ra = temp_sensor.aggregate_data()
        assert avg_oa_ma == 1
        assert avg_ra_ma == 1
        assert avg_ma_oa == -1
        assert avg_ma_ra == -1

    def test_temp_sensor_diagnostic(self):
        """Testing the temp sensor diagnostic"""
        oat_mat_check = {
            'low': 6.0,
            'normal': 5.0,
            'high': 4.0
        }
        temp_difference_threshold = {
            'low': 6.0,
            'normal': 4.0,
            'high': 2.0}
        data_window = td(minutes=30)
        temp_sensor = TempSensorDx(data_window, 15, temp_difference_threshold, 5,
                                   oat_mat_check, 90, 'Test')
        temp_sensor.oat_values.append(2)
        temp_sensor.mat_values.append(1)
        temp_sensor.rat_values.append(2)
        temp_sensor.oat_values.append(4)
        temp_sensor.mat_values.append(3)
        temp_sensor.rat_values.append(4)
        temp_sensor.timestamp.append(datetime.fromtimestamp(1000))
        table_key = "&".join([temp_sensor.analysis, temp_sensor.timestamp[-1].isoformat()])
        dx_result = Results()
        result = temp_sensor.temperature_sensor_dx(dx_result, table_key)
        if isinstance(result, Results):
            assert True
        else:
            assert False

    def test_temp_sensor_clear_data(self):
        """Testing clear data method"""
        oat_mat_check = {
            'low': 6.0,
            'normal': 5.0,
            'high': 4.0
        }
        temp_difference_threshold = {
            'low': 6.0,
            'normal': 4.0,
            'high': 2.0}
        data_window = td(minutes=30)
        temp_sensor = TempSensorDx(data_window, 15, temp_difference_threshold, 5,
                                   oat_mat_check, 90, 'Test')
        temp_sensor.clear_data()
        assert temp_sensor.oat_values == []
        assert temp_sensor.rat_values == []
        assert temp_sensor.mat_values == []
        assert temp_sensor.timestamp == []
        assert temp_sensor.temp_sensor_problem is None
