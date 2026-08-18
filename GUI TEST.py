import logging
import sys
from dataclasses import dataclass
from datetime import datetime
import tkinter as tk
from tkinter import ttk


#logs every change and puts it in a txt file
logging.basicConfig(
    filename="faults.log",
    level = logging.INFO,
    format = "%(asctime)s - %(message)s"
)


# print to the terminal and write the same line to the log file
def log_and_print(message, level=logging.INFO):
    print(message)
    logging.log(level, message)


# Tolerance

TOLERANCE_PERCENTAGE = 0.05 # Enter percentage in decimal

#returns true if measured within the setpoint
def tolerance(measured, setpoint, percentage=TOLERANCE_PERCENTAGE):
    tol = abs(setpoint) * percentage
    return abs(measured - setpoint) <= tol

#input validation for the values
def get_float(prompt):
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("Please enter a valid number.")


# PT tables for each refrigerant, already in bar/degC
# R404A has glide so it needs 2 curves: bubble for subcooling, dew for superheat
# everything else just uses one curve under "single"
PT_TABLES = {
    "R410A": {
        "single": [
            (-40.0, 0.74), (-34.4, 1.22), (-28.9, 1.81), (-23.3, 2.5), (-17.8, 3.32),
            (-12.2, 4.29), (-6.7, 5.41), (-1.1, 6.69), (4.4, 8.16), (10.0, 9.83),
            (15.6, 11.73), (21.1, 13.87), (26.7, 16.25), (32.2, 18.93), (37.8, 21.9),
            (43.3, 25.19), (48.9, 28.84), (54.4, 32.87), (60.0, 37.34), (65.6, 42.26),
        ],
    },
    "R22": {
        "single": [
            (-40.0, 0.04), (-34.4, 0.34), (-28.9, 0.7), (-23.3, 1.14), (-17.8, 1.65),
            (-12.2, 2.26), (-6.7, 2.97), (-1.1, 3.79), (4.4, 4.73), (10.0, 5.8),
            (15.6, 7.01), (21.1, 8.37), (26.7, 9.9), (32.2, 11.61), (37.8, 13.51),
            (43.3, 15.61), (48.9, 17.93), (54.4, 20.47), (60.0, 23.26), (65.6, 26.32),
        ],
    },
    "R134A": {
        "single": [
            (-40.0, -0.5), (-34.4, -0.33), (-28.9, -0.12), (-23.3, 0.13), (-17.8, 0.45),
            (-12.2, 0.82), (-6.7, 1.27), (-1.1, 1.8), (4.4, 2.41), (10.0, 3.13),
            (15.6, 3.96), (21.1, 4.9), (26.7, 5.98), (32.2, 7.19), (37.8, 8.56),
            (43.3, 10.09), (48.9, 11.8), (54.4, 13.7), (60.0, 15.8), (65.6, 18.13),
        ],
    },
    "R404A": {
        "bubble": [  # liquid point -- use for subcooling
            (-40.0, 0.34), (-34.4, 0.71), (-28.9, 1.16), (-23.3, 1.7), (-17.8, 2.32),
            (-12.2, 3.05), (-6.7, 3.9), (-1.1, 4.87), (4.4, 5.99), (10.0, 7.26),
            (15.6, 8.69), (21.1, 10.29), (26.7, 12.09), (32.2, 14.1), (37.8, 16.33),
            (43.3, 18.8), (48.9, 21.52), (54.4, 24.52), (60.0, 27.83), (65.6, 31.5),
        ],
        "dew": [  # vapor point -- use for superheat
            (-40.0, 0.3), (-34.4, 0.66), (-28.9, 1.1), (-23.3, 1.63), (-17.8, 2.25),
            (-12.2, 2.97), (-6.7, 3.81), (-1.1, 4.78), (4.4, 5.89), (10.0, 7.14),
            (15.6, 8.56), (21.1, 10.16), (26.7, 11.96), (32.2, 13.95), (37.8, 16.18),
            (43.3, 18.64), (48.9, 21.37), (54.4, 24.38), (60.0, 27.7), (65.6, 31.37),
        ],
    },
}


# Take saturation temperature in degC and make sure the pressure matches
def saturation_temp(pressure, pt_table):
    for (t1, p1), (t2, p2) in zip(pt_table, pt_table[1:]):
        if p1 <= pressure <= p2:
            return t1 + (pressure - p1) * (t2 - t1) / (p2 - p1)
    return None  # pressure fell outside the table's range


# take correct PT curve for this refrigerant
# used in calculation for superheat and subcooling
def get_pt_table(refrigerant, purpose):
    tables = PT_TABLES[refrigerant]
    if "single" in tables:
        return tables["single"]
    return tables["dew"] if purpose == "superheat" else tables["bubble"]


# all the one-time setup values (client info, setpoints, targets, interval)
# get saved together in one file so they only need typing in once
SETUP_FILE = "setup_config.txt"
SETUP_FIELDS = [
    "client_name", "client_address", "high_pres", "low_pres",
    "target_superheat", "target_subcooling", "interval_hours",
]
SETUP_NUMERIC_FIELDS = {"high_pres", "low_pres", "target_superheat", "target_subcooling", "interval_hours"}


# load whatever setup values were saved last time, as a dict
# missing/corrupt fields are just left out, so the GUI leaves them blank
def load_setup():
    try:
        with open(SETUP_FILE, "r") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return {}

    saved = {}
    for field, value in zip(SETUP_FIELDS, lines):
        if field in SETUP_NUMERIC_FIELDS:
            try:
                saved[field] = float(value)
            except ValueError:
                continue
        else:
            saved[field] = value
    return saved


# save all the setup values together so they stick around for next time
def save_setup(values):
    with open(SETUP_FILE, "w") as f:
        for field in SETUP_FIELDS:
            f.write(f"{values[field]}\n")


# get the current date, hour and minute
def get_reading_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


## Take in the readings for both high and low pressure
## and suction and liquid temperature for calcculations
def take_readings():
    analogue_high = get_float("Enter the Analogue High Input value (bar): ")
    analogue_low = get_float("Enter the Analogue Low value (bar): ")
    suction_temp = get_float("Enter the Analogue Suction Line Temperature (C): ")
    liquid_temp = get_float("Enter the Analogue Liquid Line Temperature (C): ")
    return analogue_high, analogue_low, suction_temp, liquid_temp


# says if a value is equal to, above, or below the setpoint
def classify(value, setpoint):
    if tolerance(value, setpoint):
        return "equal"
    elif value > setpoint:
        return "above"
    else:
        return "below"


FAULTS = {
    ("equal", "above"): "TEV Failure",
    ("above", "below"): "Fault Alarm: High Pressure Exceeded",
    ("below", "above"): "Refrigerant Leak Detected/Evaporator Airflow Restricted",
    ("below", "below"): "Inefficient Compressor Detected",
    ("above", "above"): "Condenser Airflow Restricted",
    ("equal", "equal"): "No fault detected",
    ("below", "equal"): "Possible Low-Side Restriction (needs review)",
    ("equal", "below"): "Possible TEV Overfeeding (needs review)",
    ("above", "equal"): "Possible Partial High-Side Fault (needs review)",
}


# holds all the setup settings so we're not passing a ton of args around
@dataclass
class SystemConfig:
    refrigerant: str
    high_pres: float
    low_pres: float
    sh_range: tuple
    sc_range: tuple
    client_name: str
    client_address: str


# check the pressures against setpoints and report any fault
def fault_alarm(analogue_high, analogue_low, config):
    high_state = classify(analogue_high, config.high_pres)
    low_state = classify(analogue_low, config.low_pres)
    message = FAULTS.get((high_state, low_state), "No fault detected")
    log_and_print(message)
    return message


# how far off target SH/SC can be before its called low or high, change if needed
SH_SC_TOLERANCE = 2.0  # degC


##take the sh/sc tolerance value and calculate the accepted ranges
def build_range(target, tolerance=SH_SC_TOLERANCE):
    return (target - tolerance, target + tolerance)


# calculate superheat
def calc_superheat(suction_temp, low_pressure, refrigerant):
    pt_table = get_pt_table(refrigerant, "superheat")
    sat_temp = saturation_temp(low_pressure, pt_table)
    if sat_temp is None:
        return None
    return suction_temp - sat_temp


# calculate subcooling in degC with SatCondensTemp - actualliquidline temp
def calc_subcooling(liquid_temp, high_pressure, refrigerant):
    pt_table = get_pt_table(refrigerant, "subcooling")
    sat_temp = saturation_temp(high_pressure, pt_table)
    if sat_temp is None:
        return None
    return sat_temp - liquid_temp


# determine if superheat/subcooling is in required range or not
def classify_sh_sc(value, normal_range):
    low, high = normal_range
    if value < low:
        return "low"
    elif value > high:
        return "high"
    else:
        return "normal"


# standard SH/SC charge diagnosis combos, from normal HVACR service training
# anything not listed here just falls back to inconclusive
SH_SC_DIAGNOSIS = {
    ("high", "low"): "Likely Undercharge or Refrigerant Leak - evaporator starved, condenser under-filled. Find the leak before adding refrigerant.",
    ("low", "high"): "Likely Overcharge or TXV Stuck Open - evaporator flooding, condenser backed up with liquid.",
    ("high", "normal"): "Possible Restriction (metering device/filter-drier) or Low Evaporator Airflow - charge appears adequate.",
    ("high", "high"): "Possible Liquid-Line Restriction - refrigerant is backing up before the metering device.",
    ("low", "normal"): "Floodback Risk - evaporator may be overfed; check TXV and sensing bulb.",
    ("normal", "low"): "Borderline Undercharge - TXV masking a low subcooling reading by throttling closed.",
    ("normal", "high"): "Possible Overcharge or Condenser Issue - check for a dirty coil or non-condensables.",
    ("normal", "normal"): "Superheat and subcooling both within normal range - no charge-related fault indicated.",
}


# look up the diagnosis for this SH/SC combo against the target ranges
def diagnose_charge(superheat, subcooling, sh_range, sc_range):
    sh_state = classify_sh_sc(superheat, sh_range)
    sc_state = classify_sh_sc(subcooling, sc_range)
    return SH_SC_DIAGNOSIS.get(
        (sh_state, sc_state),
        f"Inconclusive combination (superheat {sh_state}, subcooling {sc_state}) - recommend manual inspection.",
    )


# calculate, print, log and diagnose superheat and subcooling
def report_superheat_subcooling(suction_temp, liquid_temp, low_pressure, high_pressure, config):
    superheat = calc_superheat(suction_temp, low_pressure, config.refrigerant)
    subcooling = calc_subcooling(liquid_temp, high_pressure, config.refrigerant)

    if superheat is None or subcooling is None:
        print("Superheat/Subcooling: pressure reading is outside the PT table range, cannot calculate.")
        return superheat, subcooling

    log_and_print(f"Superheat: {superheat:.1f} C | Subcooling: {subcooling:.1f} C")

    diagnosis = diagnose_charge(superheat, subcooling, config.sh_range, config.sc_range)
    log_and_print(f"  Charge Diagnosis: {diagnosis}")

    return superheat, subcooling


CONSECUTIVE_READINGS_REQUIRED = 3


# main loop -- take a reading, check for faults, repeat until user quits
def monitor(config, interval_seconds):
    last_message = None
    consecutive_count = 0
    while True:
        analogue_high, analogue_low, suction_temp, liquid_temp = take_readings()

        # note down who this reading is for and when it was taken
        reading_time = get_reading_time()
        header = f"Client: {config.client_name}, {config.client_address} | Reading Time: {reading_time}"
        log_and_print(header)

        # check pressure against the setpoints
        message = fault_alarm(analogue_high, analogue_low, config)
        if message == last_message and message != "No fault detected":
            consecutive_count += 1
        else:
            consecutive_count = 1
        last_message = message
        if consecutive_count == CONSECUTIVE_READINGS_REQUIRED:
            log_and_print(f"*** CONFIRMED ALARM: {message} ***", level=logging.WARNING)

        # check superheat/subcooling against this system's own targets
        report_superheat_subcooling(suction_temp, liquid_temp, analogue_low, analogue_high, config)

        stop = input("Press Enter to continue, or type 'q' to quit: ")
        if stop.strip().lower() == "q":
            print("Monitoring stopped.")
            break


# try to parse a list of (field_name, raw_string) pairs as floats
# returns (dict of field_name -> float, None) or (None, error_message)
def parse_floats(pairs, error_message):
    parsed = {}
    for field, value_str in pairs:
        try:
            parsed[field] = float(value_str)
        except ValueError:
            return None, error_message
    return parsed, None


# check the raw GUI field values and turn them into real values
# returns (values_dict, error_message) -- error_message is None if all good
def parse_and_validate_setup_inputs(name, address, refrigerant, high_pres_str, low_pres_str, superheat_str, subcooling_str, interval_str):
    name = name.strip()
    address = address.strip()

    if not name or not address:
        return None, "Name and address cannot be blank."
    if refrigerant not in PT_TABLES:
        return None, "Please select a valid refrigerant."

    pressures, error = parse_floats(
        [("high_pres", high_pres_str), ("low_pres", low_pres_str)],
        "High/Low Pressure must be numbers.",
    )
    if error:
        return None, error

    targets, error = parse_floats(
        [("target_superheat", superheat_str), ("target_subcooling", subcooling_str)],
        "Superheat/Subcooling must be numbers.",
    )
    if error:
        return None, error

    interval, error = parse_floats([("interval_hours", interval_str)], "Interval must be a number.")
    if error:
        return None, error

    values = {
        "client_name": name,
        "client_address": address,
        "refrigerant": refrigerant,
        **pressures,
        **targets,
        **interval,
    }
    return values, None


# open one form for client info, refrigerant, pressure setpoints, and target SH/SC
# returns the same values the CLI prompts for these would have
def collect_setup_gui(force_new_client=False):
    saved = load_setup()
    if force_new_client:
        saved.pop("client_name", None)
        saved.pop("client_address", None)

    result = {}
    entries = {}
    pad = {"padx": 10, "pady": 6}

    root = tk.Tk()
    root.title("System Setup")

    # builds one label+entry row for the form, and remembers the widget
    # so on_submit can read its value back later
    def add_text_field(row, key, label):
        tk.Label(root, text=label).grid(row=row, column=0, sticky="e", **pad)
        entry = tk.Entry(root, width=30)
        entry.grid(row=row, column=1, **pad)
        if saved.get(key) is not None:
            entry.insert(0, str(saved[key]))
        entries[key] = entry

    row = 0
    for key, label in [("client_name", "Client Name:"), ("client_address", "Client Address:")]:
        add_text_field(row, key, label)
        row += 1

    tk.Label(root, text="Refrigerant:").grid(row=row, column=0, sticky="e", **pad)
    refrigerant_var = tk.StringVar(value=list(PT_TABLES.keys())[0])
    ttk.Combobox(
        root, textvariable=refrigerant_var, values=list(PT_TABLES.keys()),
        state="readonly", width=27,
    ).grid(row=row, column=1, **pad)
    row += 1

    for key, label in [
        ("high_pres", "High Pressure limit (bar):"),
        ("low_pres", "Low Pressure limit (bar):"),
        ("target_superheat", "Target Superheat (C):"),
        ("target_subcooling", "Target Subcooling (C):"),
        ("interval_hours", "Interval (hours):"),
    ]:
        add_text_field(row, key, label)
        row += 1

    error_label = tk.Label(root, text="", fg="red")
    error_label.grid(row=row, column=0, columnspan=2)
    row += 1

    # validates the form; shows an error and stops here if something's
    # wrong, otherwise stores the values and closes the window
    def on_submit():
        values, error = parse_and_validate_setup_inputs(
            entries["client_name"].get(), entries["client_address"].get(), refrigerant_var.get(),
            entries["high_pres"].get(), entries["low_pres"].get(),
            entries["target_superheat"].get(), entries["target_subcooling"].get(),
            entries["interval_hours"].get(),
        )
        if error:
            error_label.config(text=error)
            return
        result.update(values)
        root.destroy()

    tk.Button(root, text="Continue", command=on_submit).grid(row=row, column=0, columnspan=2, pady=10)

    root.mainloop()

    if not result:
        raise SystemExit("Setup cancelled.")

    save_setup(result)
    return (
        result["client_name"],
        result["client_address"],
        result["refrigerant"],
        result["high_pres"],
        result["low_pres"],
        result["target_superheat"],
        result["target_subcooling"],
        result["interval_hours"],
    )


# entry point -- runs the setup form, then starts monitoring
def main():
    force_new_client = "--new-client" in sys.argv
    client_name, client_address, refrigerant, high_pres, low_pres, target_superheat, target_subcooling, interval_hours = collect_setup_gui(force_new_client)
    sh_range = build_range(target_superheat)
    sc_range = build_range(target_subcooling)
    interval_seconds = interval_hours * 3600
    print(f"Target Superheat: {target_superheat} C (accepting {sh_range[0]:.1f}-{sh_range[1]:.1f} C)")
    print(f"Target Subcooling: {target_subcooling} C (accepting {sc_range[0]:.1f}-{sc_range[1]:.1f} C)")
    print(f"Interval set to {interval_hours} hours ({interval_seconds:.0f} seconds).")

    config = SystemConfig(
        refrigerant=refrigerant,
        high_pres=high_pres,
        low_pres=low_pres,
        sh_range=sh_range,
        sc_range=sc_range,
        client_name=client_name,
        client_address=client_address,
    )
    monitor(config, interval_seconds)


if __name__ == "__main__":
    main()