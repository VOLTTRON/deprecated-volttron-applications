"""
File used to unit test EconimizerRC
"""
import unittest
import os
import sys
from datetime import timedelta as td
from .diagnostics.TemperatureSensor import TemperatureSensor
from .diagnostics.TemperatureSensor import DamperSensorInconsistency
from .diagnostics.EconCorrectlyOff import EconCorrectlyOff
from .diagnostics.EconCorrectlyOn import EconCorrectlyOn
from datetime import datetime


class TestDiagnosticsTempSensor(unittest.TestCase):
    """
    Contains all the tests for Temperature Diagnostic
    """

    def test_temp_sensor_dx_creation(self):
        """test the creation of temp sensor diagnostic class"""
        temp_sensor = TemperatureSensor()
        if isinstance(temp_sensor, TemperatureSensor):
            assert True
        else:
            assert False

    def test_temp_sensor_dx_set_values(self):
        """test the temp sensor set values method"""
        temp_sensor = TemperatureSensor()
        data_window = td(minutes=1)
        temp_sensor.set_class_values("test", data_window, 1, 4.0, 0,90.0)
        assert temp_sensor.data_window == td(minutes=1)
        assert temp_sensor.no_required_data == 1
        assert temp_sensor.analysis_name == "test"

    def test_temp_sensor_algorithm(self):
        """test the temp sensor algorithm"""
        temp_sensor = TemperatureSensor()
        data_window = td(minutes=1)
        temp_sensor.set_class_values("test", data_window, 1, 4.0, 0, 90.0)
        oat = 50
        rat = 50
        mat = 50
        oad = 50
        cur_time = datetime.fromtimestamp(1036)
        sensor_problem = temp_sensor.temperature_algorithm(oat, rat, mat, oad, cur_time)
        assert sensor_problem is None

    def test_temp_sensor_dx(self):
        """test the temp sensor dx"""
        temp_sensor = TemperatureSensor()
        data_window = td(minutes=1)
        temp_sensor.set_class_values("test", data_window, 1, 4.0, 0, 90.0)
        oat = 50
        rat = 50
        mat = 25
        cur_time = datetime.fromtimestamp(1036)
        temp_sensor.timestamp.append(cur_time)
        temp_sensor.oat_values.append(oat)
        temp_sensor.mat_values.append(mat)
        temp_sensor.rat_values.append(rat)
        temp_sensor.temperature_sensor_dx()
        assert temp_sensor.temp_sensor_problem is None

    def test_temp_sensor_dx_no_error(self):
        """test the temp sensor dx for happy state"""
        temp_sensor = TemperatureSensor()
        data_window = td(minutes=1)
        temp_sensor.set_class_values("test", data_window, 1, 4.0, 0, 90.0)
        oat = 50
        rat = 50
        mat = 50
        cur_time = datetime.fromtimestamp(1036)
        temp_sensor.timestamp.append(cur_time)
        temp_sensor.oat_values.append(oat)
        temp_sensor.mat_values.append(mat)
        temp_sensor.rat_values.append(rat)
        temp_sensor.temperature_sensor_dx()
        assert temp_sensor.temp_sensor_problem is False

    def test_temp_sensor_aggregate_data(self):
        """test the temp sensor aggregate data method"""
        temp_sensor = TemperatureSensor()
        data_window = td(minutes=1)
        temp_sensor.set_class_values("test", data_window, 1, 4.0, 0, 90.0)
        temp_sensor.oat_values.append(50)
        temp_sensor.mat_values.append(25)
        temp_sensor.rat_values.append(50)
        temp_sensor.oat_values.append(100)
        temp_sensor.mat_values.append(50)
        temp_sensor.rat_values.append(100)
        avg_oa_ma, avg_ra_ma, avg_ma_oa, avg_ma_ra = temp_sensor.aggregate_data()
        assert avg_oa_ma == 37.5
        assert avg_ra_ma == 37.5
        assert avg_ma_oa == -37.5
        assert avg_ma_ra == -37.5

    def test_temp_sensor_clear_data(self):
        """test the temp sensor clear data"""
        temp_sensor = TemperatureSensor()
        data_window = td(minutes=1)
        temp_sensor.set_class_values("test", data_window, 1, 4.0, 0, 90.0)
        temp_sensor.oat_values.append(50)
        temp_sensor.mat_values.append(25)
        temp_sensor.rat_values.append(50)
        temp_sensor.oat_values.append(100)
        temp_sensor.mat_values.append(50)
        temp_sensor.rat_values.append(100)
        temp_sensor.temp_sensor_problem = True
        assert len(temp_sensor.oat_values) == 2
        assert len(temp_sensor.mat_values) == 2
        assert len(temp_sensor.rat_values) == 2
        assert temp_sensor.temp_sensor_problem is True
        temp_sensor.clear_data()
        assert len(temp_sensor.oat_values) == 0
        assert len(temp_sensor.mat_values) == 0
        assert len(temp_sensor.rat_values) == 0
        assert temp_sensor.temp_sensor_problem is None

class TestDiagnosticsDamperSensorInconsistency(unittest.TestCase):
    """
    Contains all the tests for Temperature Diagnostic
    """
    def test_damper_sensor_inconsistency_creation(self):
        """test the creation of damper sensor diagnostic class"""
        damp_sensor = DamperSensorInconsistency()
        if isinstance(damp_sensor, DamperSensorInconsistency):
            assert True
        else:
            assert False

    def test_damp_sensor_dx_set_values(self):
        """test the damper sensor set values method"""
        damp_sensor = DamperSensorInconsistency()
        data_window = td(minutes=1)
        open_damp_time= td(minutes=5)
        temp_diff_thr = 4.0
        oat_mat_check = {
            'low': max(temp_diff_thr * 1.5, 6.0),
            'normal': max(temp_diff_thr * 1.25, 5.0),
            'high': max(temp_diff_thr, 4.0)
        }
        damp_sensor.set_class_values("test", data_window, 1, open_damp_time, oat_mat_check, 90.0)
        assert damp_sensor.data_window == td(minutes=1)
        assert damp_sensor.no_required_data == 1
        assert damp_sensor.oad_temperature_threshold == 90
        assert damp_sensor.analysis_name == "test"
        assert damp_sensor.oat_mat_check["low"] == 6.0
        assert damp_sensor.oat_mat_check["normal"] == 5.0
        assert damp_sensor.oat_mat_check["high"] == 4.0

    def test_damper_algorithm(self):
        """test the damper sensor algorithm method"""
        damp_sensor = DamperSensorInconsistency()
        data_window = td(minutes=1)
        open_damp_time = td(minutes=5)
        temp_diff_thr = 4.0
        oat_mat_check = {
            'low': max(temp_diff_thr * 1.5, 6.0),
            'normal': max(temp_diff_thr * 1.25, 5.0),
            'high': max(temp_diff_thr, 4.0)
        }
        first_stamp = datetime.fromtimestamp(1)
        damp_sensor.timestamp.append(first_stamp)
        cur_time = datetime.fromtimestamp(10000)
        damp_sensor.set_class_values("test", data_window, 1, open_damp_time, oat_mat_check, 90.0)
        damp_sensor.oat_values.append(50)
        damp_sensor.mat_values.append(25)
        damp_sensor.steady_state = first_stamp
        damp_sensor.damper_algorithm(50, 25, 100, cur_time)
        assert len(damp_sensor.timestamp) == 0
        assert damp_sensor.steady_state is None
        assert len(damp_sensor.oat_values) == 0
        assert len(damp_sensor.mat_values) == 0

    def test_damp_sensor_clear_data(self):
        """test the damp sensor clear data"""
        damp_sensor = DamperSensorInconsistency()
        data_window = td(minutes=1)
        open_damp_time = td(minutes=5)
        temp_diff_thr = 4.0
        oat_mat_check = {
            'low': max(temp_diff_thr * 1.5, 6.0),
            'normal': max(temp_diff_thr * 1.25, 5.0),
            'high': max(temp_diff_thr, 4.0)
        }
        damp_sensor.set_class_values("test", data_window, 1, open_damp_time, oat_mat_check, 90.0)
        damp_sensor.oat_values.append(50)
        damp_sensor.mat_values.append(25)
        damp_sensor.oat_values.append(100)
        damp_sensor.mat_values.append(50)
        damp_sensor.steady_state = True
        assert len(damp_sensor.oat_values) == 2
        assert len(damp_sensor.mat_values) == 2
        assert damp_sensor.steady_state is True
        damp_sensor.clear_data()
        assert len(damp_sensor.oat_values) == 0
        assert len(damp_sensor.mat_values) == 0
        assert damp_sensor.steady_state is None

class TestDiagnosticsEconCorrectlyOff(unittest.TestCase):
    """
    Contains all the tests for Econ Correctly Off Diagnostic
    """
    def test_econ_correctly_off_creation(self):
        """test the creation of econ correctly off diagnostic class"""
        econ = EconCorrectlyOff()
        if isinstance(econ, EconCorrectlyOff):
            assert True
        else:
            assert False

    def test_econ_off_set_values(self):
        """test the econ correctly off set values method"""
        econ = EconCorrectlyOff()
        data_window = td(minutes=1)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        assert econ.data_window == td(minutes=1)
        assert econ.no_required_data == 1
        assert econ.analysis_name == "test"
        assert econ.min_damper_sp == 20.0
        assert econ.desired_oaf == 10.0
        assert econ.cfm == 6000.0
        assert econ.eer == 10.0
        assert econ.excess_damper_threshold["low"] == 40.0
        assert econ.excess_damper_threshold["normal"] == 20.0
        assert econ.excess_damper_threshold["high"] == 10.0

    def test_econ_off_algorithm_one_timestamp(self):
        """test the econ correctly off algorithm method"""
        econ = EconCorrectlyOff()
        data_window = td(minutes=1)
        cur_time = datetime.fromtimestamp(10000)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        econ.economizer_off_algorithm(50.0, 25.0, 50.0, 25.0, 5.0, cur_time, 36)
        assert len(econ.oat_values) == 1
        assert len(econ.mat_values) == 1
        assert len(econ.rat_values) == 1
        assert len(econ.oad_values) == 1
        assert len(econ.fan_spd_values) == 1
        assert len(econ.timestamp) == 1

    def test_econ_off_algorithm_two_timestamp(self):
        """test the econ correctly off algorithm method"""
        econ = EconCorrectlyOff()
        data_window = td(minutes=1)
        first_stamp = datetime.fromtimestamp(1)
        econ.timestamp.append(first_stamp)
        cur_time = datetime.fromtimestamp(10000)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        econ.economizer_off_algorithm(50.0, 25.0, 50.0, 25.0, 5.0, cur_time, 36)
        assert len(econ.oat_values) == 0
        assert len(econ.mat_values) == 0
        assert len(econ.rat_values) == 0
        assert len(econ.oad_values) == 0
        assert len(econ.fan_spd_values) == 0
        assert len(econ.timestamp) == 0

    def test_econ_conditions(self):
        """test the econ conditions method"""
        econ = EconCorrectlyOff()
        data_window = td(minutes=1)
        cur_time = datetime.fromtimestamp(10000)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        first_stamp = datetime.fromtimestamp(1)
        econ.economizing = first_stamp
        econ.oat_values.append(50)
        econ.mat_values.append(25)
        econ.oad_values.append(100)
        econ.rat_values.append(50)
        ret = econ.economizer_conditions(5.0, cur_time)
        assert len(econ.oat_values) == 0
        assert len(econ.mat_values) == 0
        assert len(econ.rat_values) == 0
        assert len(econ.oad_values) == 0
        assert len(econ.fan_spd_values) == 0
        assert len(econ.timestamp) == 0
        assert ret is True

    def test_econ_conditions_no_clear(self):
        """test the econ conditions without clearing method"""
        econ = EconCorrectlyOff()
        data_window = td(minutes=1)
        cur_time = datetime.fromtimestamp(10000)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        first_stamp = datetime.fromtimestamp(100000)
        econ.economizing = first_stamp
        econ.oat_values.append(50)
        econ.mat_values.append(25)
        econ.oad_values.append(100)
        econ.rat_values.append(50)
        econ.fan_spd_values.append(50)
        ret = econ.economizer_conditions(5.0, cur_time)
        assert len(econ.oat_values) == 1
        assert len(econ.mat_values) == 1
        assert len(econ.rat_values) == 1
        assert len(econ.oad_values) == 1
        assert len(econ.fan_spd_values) == 1
        assert len(econ.timestamp) == 0
        assert ret is True

    def test_econ_conditions_false(self):
        """test the econ conditions method returning false"""
        econ = EconCorrectlyOff()
        data_window = td(minutes=1)
        cur_time = datetime.fromtimestamp(10000)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        ret = econ.economizer_conditions(False, cur_time)
        assert ret is False

    def test_econ_when_not_needed(self):
        """test the econ when not needed method"""
        econ = EconCorrectlyOff()
        data_window = td(minutes=1)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        first_stamp = datetime.fromtimestamp(1)
        econ.timestamp.append(first_stamp)
        econ.economizing = first_stamp
        econ.oat_values.append(50)
        econ.mat_values.append(25)
        econ.oad_values.append(100)
        econ.rat_values.append(50)
        econ.economizing_when_not_needed()
        assert len(econ.oat_values) == 0
        assert len(econ.mat_values) == 0
        assert len(econ.rat_values) == 0
        assert len(econ.oad_values) == 0
        assert len(econ.fan_spd_values) == 0
        assert len(econ.timestamp) == 0

    def test_econ_ei_calculation_positive(self):
        """test the econ energy impact method"""
        econ = EconCorrectlyOff()
        data_window = td(minutes=1)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        first_stamp = datetime.fromtimestamp(1)
        econ.timestamp.append(first_stamp)
        econ.economizing = first_stamp
        econ.oat_values.append(10)
        econ.mat_values.append(20)
        econ.oad_values.append(10)
        econ.rat_values.append(10)
        econ.fan_spd_values.append(10)
        ei = econ.energy_impact_calculation(1.0)
        assert ei == 3888.0

    def test_econ_ei_calculation_zero_value(self):
        """test the econ energy impact method with zero value"""
        econ = EconCorrectlyOff()
        data_window = td(minutes=1)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        first_stamp = datetime.fromtimestamp(1)
        econ.timestamp.append(first_stamp)
        econ.economizing = first_stamp
        econ.oat_values.append(1)
        econ.mat_values.append(1)
        econ.oad_values.append(1)
        econ.rat_values.append(1)
        econ.fan_spd_values.append(1)
        ei = econ.energy_impact_calculation(0.0)
        assert ei == 0.0

    def test_econ_ei_calculation_negative_value(self):
        """test the econ energy impact method with a negative value"""
        econ = EconCorrectlyOff()
        data_window = td(minutes=1)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        first_stamp = datetime.fromtimestamp(1)
        econ.timestamp.append(first_stamp)
        econ.economizing = first_stamp
        econ.oat_values.append(10)
        econ.mat_values.append(20)
        econ.oad_values.append(10)
        econ.rat_values.append(10)
        econ.fan_spd_values.append(10)
        ei = econ.energy_impact_calculation(-10.0)
        assert ei == 3888.0

    def test_econ_clear_data(self):
        """test the damp sensor clear data"""
        econ = EconCorrectlyOff()
        data_window = td(minutes=1)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        econ.oat_values.append(50)
        econ.mat_values.append(25)
        econ.oat_values.append(100)
        econ.mat_values.append(50)
        econ.oad_values.append(10)
        econ.fan_spd_values.append(10)
        assert len(econ.oat_values) == 2
        assert len(econ.mat_values) == 2
        assert len(econ.oad_values) == 1
        assert len(econ.fan_spd_values) == 1
        econ.clear_data()
        assert len(econ.oat_values) == 0
        assert len(econ.mat_values) == 0
        assert len(econ.oad_values) == 0
        assert len(econ.fan_spd_values) == 0


class TestDiagnosticsEconCorrectlyOn(unittest.TestCase):
    """
    Contains all the tests for Econ Correctly On Diagnostic
    """
    def test_econ_correctly_on_creation(self):
        """test the creation of econ correctly on diagnostic class"""
        econ = EconCorrectlyOn()
        if isinstance(econ, EconCorrectlyOn):
            assert True
        else:
            assert False

    def test_econ_on_set_values(self):
        """test the econ correctly On set values method"""
        econ = EconCorrectlyOn()
        data_window = td(minutes=1)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        assert econ.data_window == td(minutes=1)
        assert econ.no_required_data == 1
        assert econ.analysis_name == "test"
        assert econ.min_damper_sp == 20.0
        assert econ.desired_oaf == 10.0
        assert econ.cfm == 6000.0
        assert econ.eer == 10.0
        assert econ.excess_damper_threshold["low"] == 40.0
        assert econ.excess_damper_threshold["normal"] == 20.0
        assert econ.excess_damper_threshold["high"] == 10.0

    def test_econ_On_algorithm_one_timestamp(self):
        """test the econ correctly On algorithm method"""
        econ = EconCorrectlyOn()
        data_window = td(minutes=1)
        cur_time = datetime.fromtimestamp(10000)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        econ.economizer_On_algorithm(50.0, 25.0, 50.0, 25.0, 5.0, cur_time, 36)
        assert len(econ.oat_values) == 1
        assert len(econ.mat_values) == 1
        assert len(econ.rat_values) == 1
        assert len(econ.oad_values) == 1
        assert len(econ.fan_spd_values) == 1
        assert len(econ.timestamp) == 1

    def test_econ_On_algorithm_two_timestamp(self):
        """test the econ correctly On algorithm method"""
        econ = EconCorrectlyOn()
        data_window = td(minutes=1)
        first_stamp = datetime.fromtimestamp(1)
        econ.timestamp.append(first_stamp)
        cur_time = datetime.fromtimestamp(10000)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        econ.economizer_On_algorithm(50.0, 25.0, 50.0, 25.0, 5.0, cur_time, 36)
        assert len(econ.oat_values) == 0
        assert len(econ.mat_values) == 0
        assert len(econ.rat_values) == 0
        assert len(econ.oad_values) == 0
        assert len(econ.fan_spd_values) == 0
        assert len(econ.timestamp) == 0

    def test_econ_on_conditions(self):
        """test the econ conditions method"""
        econ = EconCorrectlyOn()
        data_window = td(minutes=1)
        cur_time = datetime.fromtimestamp(10000)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        first_stamp = datetime.fromtimestamp(1)
        econ.economizing = first_stamp
        econ.oat_values.append(50)
        econ.mat_values.append(25)
        econ.oad_values.append(100)
        econ.rat_values.append(50)
        ret = econ.economizer_conditions(5.0, cur_time)
        assert len(econ.oat_values) == 0
        assert len(econ.mat_values) == 0
        assert len(econ.rat_values) == 0
        assert len(econ.oad_values) == 0
        assert len(econ.fan_spd_values) == 0
        assert len(econ.timestamp) == 0
        assert ret is True

    def test_econ_on_conditions_no_clear(self):
        """test the econ conditions without clearing method"""
        econ = EconCorrectlyOn()
        data_window = td(minutes=1)
        cur_time = datetime.fromtimestamp(10000)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        first_stamp = datetime.fromtimestamp(100000)
        econ.economizing = first_stamp
        econ.oat_values.append(50)
        econ.mat_values.append(25)
        econ.oad_values.append(100)
        econ.rat_values.append(50)
        econ.fan_spd_values.append(50)
        ret = econ.economizer_conditions(5.0, cur_time)
        assert len(econ.oat_values) == 1
        assert len(econ.mat_values) == 1
        assert len(econ.rat_values) == 1
        assert len(econ.oad_values) == 1
        assert len(econ.fan_spd_values) == 1
        assert len(econ.timestamp) == 0
        assert ret is True

    def test_econ_on_conditions_false(self):
        """test the econ conditions method returning false"""
        econ = EconCorrectlyOn()
        data_window = td(minutes=1)
        cur_time = datetime.fromtimestamp(10000)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        ret = econ.economizer_conditions(False, cur_time)
        assert ret is False

    def test_econ_on_when_not_needed(self):
        """test the econ when not needed method"""
        econ = EconCorrectlyOn()
        data_window = td(minutes=1)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        first_stamp = datetime.fromtimestamp(1)
        econ.timestamp.append(first_stamp)
        econ.economizing = first_stamp
        econ.oat_values.append(50)
        econ.mat_values.append(25)
        econ.oad_values.append(100)
        econ.rat_values.append(50)
        econ.economizing_when_not_needed()
        assert len(econ.oat_values) == 0
        assert len(econ.mat_values) == 0
        assert len(econ.rat_values) == 0
        assert len(econ.oad_values) == 0
        assert len(econ.fan_spd_values) == 0
        assert len(econ.timestamp) == 0

    def test_econ_on_ei_calculation_positive(self):
        """test the econ energy impact method"""
        econ = EconCorrectlyOn()
        data_window = td(minutes=1)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        first_stamp = datetime.fromtimestamp(1)
        econ.timestamp.append(first_stamp)
        econ.economizing = first_stamp
        econ.oat_values.append(10)
        econ.mat_values.append(20)
        econ.oad_values.append(10)
        econ.rat_values.append(10)
        econ.fan_spd_values.append(10)
        ei = econ.energy_impact_calculation(1.0)
        assert ei == 3888.0

    def test_econ_on_ei_calculation_zero_value(self):
        """test the econ energy impact method with zero value"""
        econ = EconCorrectlyOn()
        data_window = td(minutes=1)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        first_stamp = datetime.fromtimestamp(1)
        econ.timestamp.append(first_stamp)
        econ.economizing = first_stamp
        econ.oat_values.append(1)
        econ.mat_values.append(1)
        econ.oad_values.append(1)
        econ.rat_values.append(1)
        econ.fan_spd_values.append(1)
        ei = econ.energy_impact_calculation(0.0)
        assert ei == 0.0

    def test_econ_on_ei_calculation_negative_value(self):
        """test the econ energy impact method with a negative value"""
        econ = EconCorrectlyOn()
        data_window = td(minutes=1)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        first_stamp = datetime.fromtimestamp(1)
        econ.timestamp.append(first_stamp)
        econ.economizing = first_stamp
        econ.oat_values.append(10)
        econ.mat_values.append(20)
        econ.oad_values.append(10)
        econ.rat_values.append(10)
        econ.fan_spd_values.append(10)
        ei = econ.energy_impact_calculation(-10.0)
        assert ei == 3888.0

    def test_econ_on_clear_data(self):
        """test the damp sensor clear data"""
        econ = EconCorrectlyOn()
        data_window = td(minutes=1)
        econ.set_class_values("test", data_window, 1, 20.0, 10.0, 6000.0, 10.0)
        econ.oat_values.append(50)
        econ.mat_values.append(25)
        econ.oat_values.append(100)
        econ.mat_values.append(50)
        econ.oad_values.append(10)
        econ.fan_spd_values.append(10)
        assert len(econ.oat_values) == 2
        assert len(econ.mat_values) == 2
        assert len(econ.oad_values) == 1
        assert len(econ.fan_spd_values) == 1
        econ.clear_data()
        assert len(econ.oat_values) == 0
        assert len(econ.mat_values) == 0
        assert len(econ.oad_values) == 0
        assert len(econ.fan_spd_values) == 0