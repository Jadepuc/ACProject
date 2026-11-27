import itertools
import unittest
from acproject.models import Reading, Settings
from acproject.diagnostics import classify_pressure, classify_temperature, diagnose, PRESSURE_PATTERNS, CHARGE_PATTERNS
from acproject.refrigerants import PRESSURES, TEMPERATURES, saturation_temperature
from acproject.monitor import Monitor


class RefrigerantTests(unittest.TestCase):
    def test_every_table_point(self):
        for name, curves in PRESSURES.items():
            for curve, pressures in curves.items():
                purpose = 'subcooling' if curve == 'bubble' else 'superheat'
                self.assertEqual(len(pressures), len(TEMPERATURES))
                self.assertTrue(all(a < b for a, b in zip(pressures, pressures[1:])))
                for p, t in zip(pressures, TEMPERATURES):
                    self.assertEqual(saturation_temperature(p, name, purpose), t)
                for i in range(len(pressures) - 1):
                    self.assertAlmostEqual(saturation_temperature((pressures[i] + pressures[i+1])/2, name, purpose), (TEMPERATURES[i]+TEMPERATURES[i+1])/2)
                self.assertIsNone(saturation_temperature(pressures[0] - 1, name, purpose))
                self.assertIsNone(saturation_temperature(pressures[-1] + 1, name, purpose))

    def test_blend_curve(self):
        self.assertEqual(saturation_temperature(7.14, 'r-404a', 'superheat'), 10)
        self.assertEqual(saturation_temperature(7.26, 'R404A', 'subcooling'), 10)
        self.assertNotEqual(saturation_temperature(7.14, 'R404A', 'subcooling'), 10)

    def test_invalid_inputs(self):
        for p, ref, purpose in [(float('nan'), 'R22', 'superheat'), (1, 'R999', 'superheat'), (1, 'R22', 'other')]:
            with self.assertRaises(ValueError):
                saturation_temperature(p, ref, purpose)


class DiagnosticsTests(unittest.TestCase):
    def test_pressure_boundaries(self):
        for value, target, expected in [(95,100,'equal'), (105,100,'equal'), (94,100,'below'), (106,100,'above'), (0,0,'equal'), (-105,-100,'equal')]:
            self.assertEqual(classify_pressure(value, target), expected)

    def test_temperature_boundaries(self):
        for value, expected in [(7.9,'low'),(8,'normal'),(12,'normal'),(12.1,'high')]:
            self.assertEqual(classify_temperature(value,10),expected)

    def test_all_pressure_patterns(self):
        states = {'below': 80, 'equal': 100, 'above': 120}
        for a,b in itertools.product(states, repeat=2):
            result = diagnose(Reading(states[a], states[b]), Settings(100,100))
            self.assertEqual(result.pressure_state,(a,b))
            self.assertEqual(result.pressure_message, PRESSURE_PATTERNS[a,b])

    def test_all_charge_patterns(self):
        settings = Settings(18.93, 9.83, 'R410A', 10, 10)
        for sh,sc in itertools.product((5,10,15), repeat=2):
            result = diagnose(Reading(18.93,9.83,10+sh,32.2-sc),settings)
            self.assertAlmostEqual(result.superheat,sh)
            self.assertAlmostEqual(result.subcooling,sc)
            states = (classify_temperature(sh,10),classify_temperature(sc,10))
            self.assertEqual(result.charge_state,states)
            self.assertEqual(result.charge_message,CHARGE_PATTERNS.get(states,'Inconclusive charge pattern; manual inspection needed'))

    def test_out_of_range_and_missing(self):
        settings = Settings(18.93,9.83,'R410A',10,10)
        result = diagnose(Reading(18.93,100,20,22.2),settings)
        self.assertIsNone(result.superheat)
        self.assertAlmostEqual(result.subcooling,10)
        self.assertIsNone(result.charge_state)
        self.assertIsNone(diagnose(Reading(18.93,9.83),settings).charge_state)

    def test_invalid_config_and_readings(self):
        for kwargs in ({'pressure_tolerance':-1},{'interval_seconds':-1},{'consecutive_required':0},{'refrigerant':'R22'},{'target_superheat':10}):
            with self.assertRaises(ValueError):
                Settings(20,5,**kwargs)
        with self.assertRaises(ValueError):
            Reading(float('inf'),5)


class AlarmTests(unittest.TestCase):
    def test_persistence_recovery_and_change(self):
        monitor = Monitor(Settings(20,5))
        fault, normal, different = Reading(30,5), Reading(20,5), Reading(10,5)
        sequence = [fault,fault,fault,fault,normal,fault,fault,different,different,different,normal,fault,fault,fault]
        self.assertEqual([monitor.process(r)[1] for r in sequence], [False,False,True,False,False,False,False,False,False,True,False,False,False,True])

    def test_threshold_one(self):
        monitor = Monitor(Settings(20,5,consecutive_required=1))
        self.assertTrue(monitor.process(Reading(30,5))[1])
        self.assertFalse(monitor.process(Reading(30,5))[1])
        self.assertFalse(monitor.process(Reading(20,5))[1])

if __name__ == '__main__':
    unittest.main()
