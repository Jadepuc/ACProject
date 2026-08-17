import time
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

# Tolerance

TOLERANCE_PERCENTAGE = 0.05 # Enter percentage in decimal

def tolerance(measured, setpoint, percentage=TOLERANCE_PERCENTAGE):
    #returns true if measured within the setpoint
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


def get_refrigerant():
    # Take in refrigerant used for sustem
    valid = ", ".join(PT_TABLES.keys())
    while True:
        entry = input(f"Enter refrigerant type ({valid}): ")
        entry = entry.strip().upper().replace("-", "").replace(" ", "")
        if entry in PT_TABLES:
            return entry
        print(f"Unrecognised refrigerant. Please enter one of: {valid}")


def saturation_temp(pressure, pt_table):
    # Take saturation temperature in degC and make sure the pressure matches
    for (t1, p1), (t2, p2) in zip(pt_table, pt_table[1:]):
        if p1 <= pressure <= p2:
            return t1 + (pressure - p1) * (t2 - t1) / (p2 - p1)
    return None  # pressure fell outside the table's range


def get_pt_table(refrigerant, purpose):
    # take correct PT curve for this refrigerant
    # used in calculation for superheat and subcooling
    tables = PT_TABLES[refrigerant]
    if "single" in tables:
        return tables["single"]
    return tables["dew"] if purpose == "superheat" else tables["bubble"]


# client name/address get saved to a file so we don't type them in every run
CLIENT_INFO_FILE = "client_info.txt"


def load_client_info():
    # load the saved client name/address if there is one
    try:
        with open(CLIENT_INFO_FILE, "r") as f:
            lines = f.read().splitlines()
        if len(lines) >= 2:
            return lines[0], lines[1]
    except FileNotFoundError:
        pass
    return None, None


def save_client_info(name, address):
    # save client name/address so it sticks around for next time
    with open(CLIENT_INFO_FILE, "w") as f:
        f.write(name + "\n")
        f.write(address + "\n")


def get_client_info(force_new=False):
    # get the client name/address, reuse the saved one unless force_new is set
    saved_name, saved_address = load_client_info()
    if saved_name and saved_address and not force_new:
        print(f"Using saved client: {saved_name}, {saved_address}")
        return saved_name, saved_address

    name = input("Enter Client Name: ")
    address = input("Enter Client Address: ")
    save_client_info(name, address)
    return name, address


# target superheat/subcooling get saved to a file too, same idea as client info
TARGET_SH_SC_FILE = "target_sh_sc.txt"


def load_target_sh_sc():
    # load the saved target superheat/subcooling if there is one
    try:
        with open(TARGET_SH_SC_FILE, "r") as f:
            lines = f.read().splitlines()
        if len(lines) >= 2:
            return float(lines[0]), float(lines[1])
    except (FileNotFoundError, ValueError):
        pass
    return None, None


def save_target_sh_sc(target_superheat, target_subcooling):
    # save target superheat/subcooling so it sticks around for next time
    with open(TARGET_SH_SC_FILE, "w") as f:
        f.write(f"{target_superheat}\n")
        f.write(f"{target_subcooling}\n")


# high/low pressure setpoints get saved to a file too, same idea
PRESSURE_SETPOINTS_FILE = "pressure_setpoints.txt"


def load_pressure_setpoints():
    # load the saved high/low pressure setpoints if there is one
    try:
        with open(PRESSURE_SETPOINTS_FILE, "r") as f:
            lines = f.read().splitlines()
        if len(lines) >= 2:
            return float(lines[0]), float(lines[1])
    except (FileNotFoundError, ValueError):
        pass
    return None, None


def save_pressure_setpoints(high_pres, low_pres):
    # save high/low pressure setpoints so they stick around for next time
    with open(PRESSURE_SETPOINTS_FILE, "w") as f:
        f.write(f"{high_pres}\n")
        f.write(f"{low_pres}\n")


# check interval gets saved to a file too, same idea
INTERVAL_FILE = "interval.txt"


def load_interval():
    # load the saved interval (in hours) if there is one
    try:
        with open(INTERVAL_FILE, "r") as f:
            lines = f.read().splitlines()
        if len(lines) >= 1:
            return float(lines[0])
    except (FileNotFoundError, ValueError):
        pass
    return None


def save_interval(interval_hours):
    # save the interval so it sticks around for next time
    with open(INTERVAL_FILE, "w") as f:
        f.write(f"{interval_hours}\n")


def get_reading_time():
    # get the current date, hour and minute
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def parse_and_validate_temp_inputs(suction_str, liquid_str):
    # check the raw temp popup values, returns (values_dict, error_message)
    try:
        suction_temp = float(suction_str)
        liquid_temp = float(liquid_str)
    except ValueError:
        return None, "Suction/Liquid temperature must be numbers."
    return {"suction_temp": suction_temp, "liquid_temp": liquid_temp}, None


def collect_temperature_readings_gui():
    # small popup for suction/liquid line temp, shown once per reading cycle
    # (analogue pressure stays on the terminal for now -- real sensor later)
    result = {}

    root = tk.Tk()
    root.title("Temperature Reading")
    pad = {"padx": 10, "pady": 6}

    tk.Label(root, text="Suction Line Temperature (C):").grid(row=0, column=0, sticky="e", **pad)
    suction_entry = tk.Entry(root, width=20)
    suction_entry.grid(row=0, column=1, **pad)
    suction_entry.focus()

    tk.Label(root, text="Liquid Line Temperature (C):").grid(row=1, column=0, sticky="e", **pad)
    liquid_entry = tk.Entry(root, width=20)
    liquid_entry.grid(row=1, column=1, **pad)

    error_label = tk.Label(root, text="", fg="red")
    error_label.grid(row=2, column=0, columnspan=2)

    def on_submit():
        values, error = parse_and_validate_temp_inputs(suction_entry.get(), liquid_entry.get())
        if error:
            error_label.config(text=error)
            return
        result.update(values)
        root.destroy()

    tk.Button(root, text="Submit", command=on_submit).grid(row=3, column=0, columnspan=2, pady=10)

    root.mainloop()

    if not result:
        raise SystemExit("Temperature reading cancelled.")

    return result["suction_temp"], result["liquid_temp"]


def take_readings():
    ## Take in the readings for both high and low pressure
    ## and suction and liquid temperature for calcculations
    analogue_high = get_float("Enter the Analogue High Input value (bar): ")
    analogue_low = get_float("Enter the Analogue Low value (bar): ")
    suction_temp, liquid_temp = collect_temperature_readings_gui()
    return analogue_high, analogue_low, suction_temp, liquid_temp

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


@dataclass
class SystemConfig:
    # holds all the setup settings so we're not passing a ton of args around
    refrigerant: str
    high_pres: float
    low_pres: float
    sh_range: tuple
    sc_range: tuple
    client_name: str
    client_address: str


def fault_alarm(analogue_high, analogue_low, config):
    high_state = classify(analogue_high, config.high_pres)
    low_state = classify(analogue_low, config.low_pres)
    message = FAULTS.get((high_state, low_state), "No fault detected")
    print(message)
    logging.info(message)
    return message


# how far off target SH/SC can be before its called low or high, change if needed
SH_SC_TOLERANCE = 2.0  # degC


def take_target_sh_sc():
    # Take target superheat/subcooling for this system which varies by system
    # isnt universal but is applied per system from relevant sources
    target_superheat = get_float("Enter the target Superheat value for this system (C): ")
    target_subcooling = get_float("Enter the target Subcooling value for this system (C): ")
    return target_superheat, target_subcooling


def build_range(target, tolerance=SH_SC_TOLERANCE):
    ##take the sh/sc tolerance value and calculate the accepted ranges
    return (target - tolerance, target + tolerance)


def calc_superheat(suction_temp, low_pressure, refrigerant):
    # calculate superheat
    pt_table = get_pt_table(refrigerant, "superheat")
    sat_temp = saturation_temp(low_pressure, pt_table)
    if sat_temp is None:
        return None
    return suction_temp - sat_temp


def calc_subcooling(liquid_temp, high_pressure, refrigerant):
    # calculate subcooling in degC with SatCondensTemp - actualliquidline temp
    pt_table = get_pt_table(refrigerant, "subcooling")
    sat_temp = saturation_temp(high_pressure, pt_table)
    if sat_temp is None:
        return None
    return sat_temp - liquid_temp


def classify_sh_sc(value, normal_range):
    # determine if superheat/subcooling is in required range or not
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


def diagnose_charge(superheat, subcooling, sh_range, sc_range):
    # look up the diagnosis for this SH/SC combo against the target ranges
    sh_state = classify_sh_sc(superheat, sh_range)
    sc_state = classify_sh_sc(subcooling, sc_range)
    return SH_SC_DIAGNOSIS.get(
        (sh_state, sc_state),
        f"Inconclusive combination (superheat {sh_state}, subcooling {sc_state}) - recommend manual inspection.",
    )


def report_superheat_subcooling(suction_temp, liquid_temp, low_pressure, high_pressure, config):
    # calculate, print, log and diagnose superheat and subcooling
    superheat = calc_superheat(suction_temp, low_pressure, config.refrigerant)
    subcooling = calc_subcooling(liquid_temp, high_pressure, config.refrigerant)

    if superheat is None or subcooling is None:
        print("Superheat/Subcooling: pressure reading is outside the PT table range, cannot calculate.")
        return superheat, subcooling

    print(f"Superheat: {superheat:.1f} C | Subcooling: {subcooling:.1f} C")
    logging.info(f"Superheat: {superheat:.1f} C, Subcooling: {subcooling:.1f} C")

    diagnosis = diagnose_charge(superheat, subcooling, config.sh_range, config.sc_range)
    print(f"  Charge Diagnosis: {diagnosis}")
    logging.info(f"Charge Diagnosis: {diagnosis}")

    return superheat, subcooling


CONSECUTIVE_READINGS_REQUIRED = 3


def monitor(config, interval_seconds):
    last_message = None
    consecutive_count = 0
    while True:
        analogue_high, analogue_low, suction_temp, liquid_temp = take_readings()

        # note down who this reading is for and when it was taken
        reading_time = get_reading_time()
        header = f"Client: {config.client_name}, {config.client_address} | Reading Time: {reading_time}"
        print(header)
        logging.info(header)

        # check pressure against the setpoints
        message = fault_alarm(analogue_high, analogue_low, config)
        if message == last_message and message != "No fault detected":
            consecutive_count += 1
        else:
            consecutive_count = 1
        last_message = message
        if consecutive_count == CONSECUTIVE_READINGS_REQUIRED:
            print(f"*** CONFIRMED ALARM: {message} ***")
            logging.warning(f"CONFIRMED ALARM: {message}")

        # check superheat/subcooling against this system's own targets
        report_superheat_subcooling(suction_temp, liquid_temp, analogue_low, analogue_high, config)

        stop = input("Press Enter to continue, or type 'q' to quit: ")
        if stop.strip().lower() == "q":
            print("Monitoring stopped.")
            break

def parse_and_validate_setup_inputs(name, address, refrigerant, high_pres_str, low_pres_str, superheat_str, subcooling_str, interval_str):
    # check the raw GUI field values and turn them into real values
    # returns (values_dict, error_message) -- error_message is None if all good
    name = name.strip()
    address = address.strip()

    if not name or not address:
        return None, "Name and address cannot be blank."
    if refrigerant not in PT_TABLES:
        return None, "Please select a valid refrigerant."
    try:
        high_pres = float(high_pres_str)
        low_pres = float(low_pres_str)
    except ValueError:
        return None, "High/Low Pressure must be numbers."
    try:
        target_superheat = float(superheat_str)
        target_subcooling = float(subcooling_str)
    except ValueError:
        return None, "Superheat/Subcooling must be numbers."
    try:
        interval_hours = float(interval_str)
    except ValueError:
        return None, "Interval must be a number."

    values = {
        "client_name": name,
        "client_address": address,
        "refrigerant": refrigerant,
        "high_pres": high_pres,
        "low_pres": low_pres,
        "target_superheat": target_superheat,
        "target_subcooling": target_subcooling,
        "interval_hours": interval_hours,
    }
    return values, None


def collect_setup_gui(force_new_client=False):
    # open one form for client info, refrigerant, pressure setpoints, and target SH/SC
    # returns the same values the CLI prompts for these would have
    saved_name, saved_address = load_client_info()
    if force_new_client:
        saved_name, saved_address = None, None
    saved_high_pres, saved_low_pres = load_pressure_setpoints()
    saved_superheat, saved_subcooling = load_target_sh_sc()
    saved_interval = load_interval()

    result = {}

    root = tk.Tk()
    root.title("System Setup")
    pad = {"padx": 10, "pady": 6}

    tk.Label(root, text="Client Name:").grid(row=0, column=0, sticky="e", **pad)
    name_entry = tk.Entry(root, width=30)
    name_entry.grid(row=0, column=1, **pad)
    if saved_name:
        name_entry.insert(0, saved_name)

    tk.Label(root, text="Client Address:").grid(row=1, column=0, sticky="e", **pad)
    address_entry = tk.Entry(root, width=30)
    address_entry.grid(row=1, column=1, **pad)
    if saved_address:
        address_entry.insert(0, saved_address)

    tk.Label(root, text="Refrigerant:").grid(row=2, column=0, sticky="e", **pad)
    refrigerant_var = tk.StringVar(value=list(PT_TABLES.keys())[0])
    refrigerant_menu = ttk.Combobox(
        root, textvariable=refrigerant_var, values=list(PT_TABLES.keys()),
        state="readonly", width=27,
    )
    refrigerant_menu.grid(row=2, column=1, **pad)

    tk.Label(root, text="High Pressure limit (bar):").grid(row=3, column=0, sticky="e", **pad)
    high_pres_entry = tk.Entry(root, width=30)
    high_pres_entry.grid(row=3, column=1, **pad)
    if saved_high_pres is not None:
        high_pres_entry.insert(0, str(saved_high_pres))

    tk.Label(root, text="Low Pressure limit (bar):").grid(row=4, column=0, sticky="e", **pad)
    low_pres_entry = tk.Entry(root, width=30)
    low_pres_entry.grid(row=4, column=1, **pad)
    if saved_low_pres is not None:
        low_pres_entry.insert(0, str(saved_low_pres))

    tk.Label(root, text="Target Superheat (C):").grid(row=5, column=0, sticky="e", **pad)
    superheat_entry = tk.Entry(root, width=30)
    superheat_entry.grid(row=5, column=1, **pad)
    if saved_superheat is not None:
        superheat_entry.insert(0, str(saved_superheat))

    tk.Label(root, text="Target Subcooling (C):").grid(row=6, column=0, sticky="e", **pad)
    subcooling_entry = tk.Entry(root, width=30)
    subcooling_entry.grid(row=6, column=1, **pad)
    if saved_subcooling is not None:
        subcooling_entry.insert(0, str(saved_subcooling))

    tk.Label(root, text="Interval (hours):").grid(row=7, column=0, sticky="e", **pad)
    interval_entry = tk.Entry(root, width=30)
    interval_entry.grid(row=7, column=1, **pad)
    if saved_interval is not None:
        interval_entry.insert(0, str(saved_interval))

    error_label = tk.Label(root, text="", fg="red")
    error_label.grid(row=8, column=0, columnspan=2)

    def on_submit():
        values, error = parse_and_validate_setup_inputs(
            name_entry.get(), address_entry.get(), refrigerant_var.get(),
            high_pres_entry.get(), low_pres_entry.get(),
            superheat_entry.get(), subcooling_entry.get(),
            interval_entry.get(),
        )
        if error:
            error_label.config(text=error)
            return
        result.update(values)
        root.destroy()

    tk.Button(root, text="Continue", command=on_submit).grid(row=9, column=0, columnspan=2, pady=10)

    root.mainloop()

    if not result:
        raise SystemExit("Setup cancelled.")

    save_client_info(result["client_name"], result["client_address"])
    save_pressure_setpoints(result["high_pres"], result["low_pres"])
    save_target_sh_sc(result["target_superheat"], result["target_subcooling"])
    save_interval(result["interval_hours"])
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