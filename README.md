# ACProject — modular refactor

Experimental manual-input HVAC/refrigeration diagnostic monitor. Python 3.10+; standard library only.

## Run

```sh
python main.py                  # Full pressure + SH/SC analysis
python main.py --pressure-only  # Original basic monitoring workflow
python main.py --timed          # Ask for an interval; wait between manual prompts
python -m unittest discover -s tests -v
```

The legacy `Pressure sensor wPT Table.py` filename remains as a launcher. The full mode is now the default for `main.py`; pass `--pressure-only` for its previous function. By default, readings are manually entered with no artificial delay. `--timed` waits after the user chooses to continue; it does not acquire data automatically. Enter `q` at the continuation prompt or use Ctrl+C to stop. Logs are appended to `faultslog.txt` in the current working directory; override with `--log-file PATH`.

## Structure

- `main.py`, `Pressure sensor wPT Table.py`: entry points.
- `acproject/models.py`: settings and measurements, including finite-number checks.
- `acproject/refrigerants.py`: original PT values and interpolation.
- `acproject/diagnostics.py`: pure pressure and charge calculations.
- `acproject/monitor.py`: persistent pressure alarm tracking.
- `acproject/cli.py`: prompts, output, timing and file logging.
- `tests/`: unit and CLI regression tests.

## Design choices and limitations

- Kept original PT numerical data, all nine pressure state combinations and the eight explicit SH/SC combinations. Diagnostic wording was softened or made more descriptive; the unmatched charge combination is inconclusive. These legacy rule mappings have **not** been professionally validated; some (including pressure-only leak and TEV rules) may be misleading. No claim of confirmed equipment faults is made.
- Defaults are 5% relative pressure tolerance, ±2 °C temperature tolerance and three consecutive matching abnormal pressure readings. An alarm is emitted once per uninterrupted run at its threshold, with reset after a normal or different pattern. Charge assessment is still reported per reading, not debounced.
- Presumed pressure basis is bar gauge because the source tables include negative values. Confirm units and every PT curve against manufacturer or reliable refrigerant-property data before real use. R410A retains the source's single-curve approximation; R404A uses dew for superheat and bubble for subcooling. No extrapolation beyond the table. Targets are system-specific, not universal.
- This is a diagnostic prototype, not a safety controller. Setpoints are comparison targets, not maximum permissible pressures. Do not use the software as a substitute for independent pressure cutouts, manufacturer's procedures or qualified service. No real sensor or equipment integration has been tested.
- Invalid and non-finite inputs are rejected, logging only begins when the CLI is run, and partial SH/SC calculations are displayed if a pressure is outside the PT range. A zero target retains the original zero-width relative tolerance. Internal legacy function signatures are not kept; both script entry points are.
- Generated logs are ignored and the previously tracked log is removed from the branch (historical contents remain in Git). Back up local logs before switching branches. Existing IDE metadata is retained.
