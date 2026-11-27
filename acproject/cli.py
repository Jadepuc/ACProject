"""Manual readings now; a sensor adapter can later feed Monitor.process."""
import argparse
import logging
import time
from math import isfinite
from .models import Reading, Settings
from .monitor import Monitor
from .refrigerants import PRESSURES, normalize_refrigerant


def get_float(prompt: str, *, nonnegative: bool = False) -> float:
    while True:
        try:
            value = float(input(prompt))
            if not isfinite(value) or (nonnegative and value < 0):
                raise ValueError
            return value
        except ValueError:
            print('Enter a finite number' + (' of zero or greater.' if nonnegative else '.'))


def get_refrigerant() -> str:
    while True:
        try:
            return normalize_refrigerant(input(f"Refrigerant ({', '.join(PRESSURES)}): "))
        except ValueError as exc:
            print(exc)


def read_settings(pressure_only: bool, timed: bool) -> Settings:
    refrigerant = None if pressure_only else get_refrigerant()
    high = get_float('High pressure target (bar gauge): ')
    low = get_float('Low pressure target (bar gauge): ')
    sh = sc = None
    if refrigerant is not None:
        sh = get_float('Target superheat (°C): ')
        sc = get_float('Target subcooling (°C): ')
    hours = get_float('Monitoring interval (hours): ', nonnegative=True) if timed else 0.0
    if not isfinite(hours * 3600):
        raise ValueError('Interval is too large')
    return Settings(high, low, refrigerant, sh, sc, interval_seconds=hours * 3600)


def read_measurements(pressure_only: bool) -> Reading:
    high = get_float('Measured high pressure (bar gauge): ')
    low = get_float('Measured low pressure (bar gauge): ')
    if pressure_only:
        return Reading(high, low)
    return Reading(high, low, get_float('Suction line temperature (°C): '),
                   get_float('Liquid line temperature (°C): '))


def main(argv=None, *, default_pressure_only=False) -> int:
    parser = argparse.ArgumentParser(description='Experimental HVAC diagnostic monitor')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--pressure-only', action='store_true', dest='pressure_only')
    mode.add_argument('--full', action='store_false', dest='pressure_only')
    parser.set_defaults(pressure_only=default_pressure_only)
    parser.add_argument('--timed', action='store_true', help='Wait between manual reading prompts')
    parser.add_argument('--log-file', default='faultslog.txt')
    args = parser.parse_args(argv)
    logger = logging.getLogger('acproject')
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = None
    try:
        handler = logging.FileHandler(args.log_file, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
        print('Experimental diagnostics only. Verify PT data and fault rules; not a safety controller.')
        monitor = Monitor(read_settings(args.pressure_only, args.timed))
        while True:
            reading = read_measurements(args.pressure_only)
            result, alarm = monitor.process(reading)
            print(result.pressure_message)
            logger.info('Reading=%s; pressure=%s', reading, result.pressure_message)
            if not args.pressure_only:
                sh = 'unavailable' if result.superheat is None else f'{result.superheat:.1f} °C'
                sc = 'unavailable' if result.subcooling is None else f'{result.subcooling:.1f} °C'
                print(f'Superheat: {sh} | Subcooling: {sc}')
                print(result.charge_message)
                logger.info('SH=%s; SC=%s; %s', sh, sc, result.charge_message)
            if alarm:
                message = f'Persistent pressure deviation ({monitor.alarms.count} readings): {result.pressure_message}'
                print(f'*** {message} ***')
                logger.warning(message)
            if input("Enter to continue, or 'q' to quit: ").strip().lower() == 'q':
                break
            if args.timed:
                time.sleep(monitor.settings.interval_seconds)
    except (KeyboardInterrupt, EOFError):
        print('\nMonitoring stopped.')
        return 0
    except (OSError, ValueError, OverflowError) as exc:
        print(f'Cannot continue: {exc}')
        return 1
    finally:
        if handler is not None:
            logger.removeHandler(handler)
            handler.close()
    print('Monitoring stopped.')
    return 0
