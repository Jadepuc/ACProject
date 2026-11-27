import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from acproject.cli import main


class CLITests(unittest.TestCase):
    def run_cli(self, args, inputs):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'faultslog.txt'
            with patch('builtins.input', side_effect=inputs), patch('acproject.cli.time.sleep') as sleep, redirect_stdout(io.StringIO()) as output:
                code = main([*args, '--log-file', str(log)])
            return code, output.getvalue(), log.read_text(), sleep.call_args_list

    def test_full_mode(self):
        code, output, log, sleeps = self.run_cli([], ['R410A','18.93','9.83','10','10','18.93','9.83','20','22.2','q'])
        self.assertEqual(code,0)
        self.assertIn('Superheat: 10.0',output)
        self.assertIn('Subcooling: 10.0',output)
        self.assertIn('No charge-related deviation',log)
        self.assertFalse(sleeps)

    def test_pressure_only_and_invalid_input(self):
        code, output, log, sleeps = self.run_cli(['--pressure-only'], ['nan','20','5','oops','30','5','','30','5','','30','5','q'])
        self.assertEqual(code,0)
        self.assertEqual(output.count('Enter a finite number'),2)
        self.assertIn('Persistent pressure deviation (3 readings)',log)
        self.assertFalse(sleeps)

    def test_timed_mode(self):
        code, output, log, sleeps = self.run_cli(['--pressure-only','--timed'], ['20','5','-1','0.5','20','5','','20','5','q'])
        self.assertEqual(code,0)
        self.assertEqual(len(sleeps),1)
        self.assertEqual(sleeps[0].args,(1800.0,))

    def test_eof_stops(self):
        with tempfile.TemporaryDirectory() as directory, patch('builtins.input', side_effect=EOFError), redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--log-file',str(Path(directory)/'log.txt')]),0)
