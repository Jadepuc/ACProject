    import time
import logging

# logs every change and puts it in a txt file
logging.basicConfig(
    filename="faultslog.txt",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

# Tolerance

percentage = 0.05  # Enter percentage in decimal


def tolerance(measured, setpoint, percentage=percentage):
    # returns true if measured within the setpoint
    tol = abs(setpoint) * percentage
    return abs(measured - setpoint) <= tol


# input validation for the values
def get_float(prompt):
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("Please enter a valid number.")

#Refrigerant tables
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


##creates list of refrigerants to be used
def get_refrigerant():
    #creates list of refrigerants to search through
    valid = ", ".join(PT_TABLES.keys())
    while True:
        #take entry of refrigerants
        entry = input(f"Enter refrigerant type ({valid}): ")
        entry = entry.strip().upper().replace("-", "").replace(" ", "")
        #validation
        if entry in PT_TABLES:
            return entry
        print(f"Unrecognised refrigerant/Refrigerant not present in Index. Please enter one of: {valid}")

##calculates the saturation temperature for each refrigerant
def saturation_temp(pressure, pt_table):
    #Calculate saturation temperature for given set datapoint

    for (t1, p1), (t2, p2) in zip(pt_table, pt_table[1:]):
        if p1 <= pressure <= p2:
            return t1 + (pressure - p1) * (t2 - t1) / (p2 - p1)
    return None  # pressure fell outside the table's range


def get_pt_table(refrigerant, purpose):
    """Return the correct PT curve for this refrigerant.
    purpose is 'superheat' or 'subcooling' (only matters for blends)."""
    tables = PT_TABLES[refrigerant]
    if "single" in tables:
        return tables["single"]
    return tables["dew"] if purpose == "superheat" else tables["bubble"] ## this is for later


def take_setpoints():
   #take set pressure points from user
    high_pres = float(input("Enter the High Pressure value: "))
    low_pres = float(input("Enter the Low Pressure value: "))
    return high_pres, low_pres


def take_readings():
    """Get analogue pressures and line temperatures together, in one round,
    since the temperatures are needed to compute superheat/subcooling
    for the same instant as the pressure reading."""
    analogue_high = get_float("Enter the Analogue High Input value (bar): ")
    analogue_low = get_float("Enter the Analogue Low value (bar): ")
    suction_temp = get_float("Enter the Suction Line Temperature (C): ")
    liquid_temp = get_float("Enter the Liquid Line Temperature (C): ")
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


def fault_alarm(analogue_high, analogue_low, high_pres, low_pres):
    high_state = classify(analogue_high, high_pres)
    low_state = classify(analogue_low, low_pres)
    message = FAULTS.get((high_state, low_state), "No fault detected")
    print(message)
    logging.info(message)
    return message


# ---------------------------------------------------------------
# How far a reading is allowed to drift from the user's target
# superheat/subcooling before it's classified as "low" or "high".
# This is a placeholder -- 2 degC is a reasonable starting point,
# but tighten or loosen it to match how precisely your sensors and
# service practice can realistically hold a reading.
# ---------------------------------------------------------------
SH_SC_TOLERANCE = 2.0  # degC


def take_target_sh_sc():
    """Get the target superheat and subcooling for this specific system.
    These come from the manufacturer's charging chart/nameplate data (for
    TXV systems) or a target-superheat chart (for fixed-orifice systems) --
    not a universal constant, since the correct target varies by system."""
    target_superheat = get_float("Enter the target Superheat value for this system (C): ")
    target_subcooling = get_float("Enter the target Subcooling value for this system (C): ")
    return target_superheat, target_subcooling


def build_range(target, tolerance=SH_SC_TOLERANCE):
    """Turn a single target value into a (low, high) acceptable band."""
    return (target - tolerance, target + tolerance)


def calc_superheat(suction_temp, low_pressure, refrigerant):
    """Superheat (degC) = actual suction line temp - saturated evaporating temp."""
    pt_table = get_pt_table(refrigerant, "superheat")
    sat_temp = saturation_temp(low_pressure, pt_table)
    if sat_temp is None:
        return None
    return suction_temp - sat_temp


def calc_subcooling(liquid_temp, high_pressure, refrigerant):
    """Subcooling (degC) = saturated condensing temp - actual liquid line temp."""
    pt_table = get_pt_table(refrigerant, "subcooling")
    sat_temp = saturation_temp(high_pressure, pt_table)
    if sat_temp is None:
        return None
    return sat_temp - liquid_temp


def classify_sh_sc(value, normal_range):
    """Classify a superheat/subcooling reading as low, normal, or high
    relative to the target range."""
    low, high = normal_range
    if value < low:
        return "low"
    elif value > high:
        return "high"
    else:
        return "normal"


# ---------------------------------------------------------------
# Standard superheat/subcooling charge-diagnosis matrix.
# This is the same underlying logic taught across HVACR service
# training: pressure alone can be misleading, but superheat and
# subcooling together reveal whether the evaporator/condenser are
# actually starved or flooded with refrigerant. Combinations not
# listed here don't match a single well-known pattern, so they
# fall back to a generic "inconclusive" message rather than a
# guessed diagnosis.
# ---------------------------------------------------------------
SH_SC_DIAGNOSIS = {
    ("high",
     "low"): "Likely Undercharge or Refrigerant Leak - evaporator starved, condenser under-filled. Find the leak before adding refrigerant.",
    ("low", "high"): "Likely Overcharge or TEV Stuck Open - evaporator flooding, condenser backed up with liquid.",
    ("high",
     "normal"): "Possible Restriction (metering device/filter-drier) or Low Evaporator Airflow - charge appears adequate.",
    ("high", "high"): "Possible Liquid-Line Restriction - refrigerant is backing up before the metering device.",
    ("low", "normal"): "Floodback Risk - evaporator may be overfed; check TEV and sensing bulb.",
    ("normal", "low"): "Borderline Undercharge - TXV masking a low subcooling reading by throttling closed.",
    ("normal", "high"): "Possible Overcharge or Condenser Issue - check for a dirty coil or non-condensables.",
    ("normal", "normal"): "Superheat and subcooling both within normal range - no charge-related fault indicated.",
}


def diagnose_charge(superheat, subcooling, sh_range, sc_range):
    """Look up the standard charge-diagnosis message for this SH/SC pair,
    classified against this system's own target ranges."""
    sh_state = classify_sh_sc(superheat, sh_range)
    sc_state = classify_sh_sc(subcooling, sc_range)
    return SH_SC_DIAGNOSIS.get(
        (sh_state, sc_state),
        f"Inconclusive combination (superheat {sh_state}, subcooling {sc_state}) - recommend manual inspection.",
    )


def report_superheat_subcooling(suction_temp, liquid_temp, low_pressure, high_pressure, refrigerant, sh_range,
                                sc_range):
    """Calculate, print, log, and diagnose superheat and subcooling."""
    superheat = calc_superheat(suction_temp, low_pressure, refrigerant)
    subcooling = calc_subcooling(liquid_temp, high_pressure, refrigerant)

    if superheat is None or subcooling is None:
        print("Superheat/Subcooling: pressure reading is outside the PT table range, cannot calculate.")
        return superheat, subcooling

    print(f"Superheat: {superheat:.1f} C | Subcooling: {subcooling:.1f} C")
    logging.info(f"Superheat: {superheat:.1f} C, Subcooling: {subcooling:.1f} C")

    diagnosis = diagnose_charge(superheat, subcooling, sh_range, sc_range)
    print(f"  Charge Diagnosis: {diagnosis}")
    logging.info(f"Charge Diagnosis: {diagnosis}")

    return superheat, subcooling


def set_interval():
    interval_hours = get_float("Enter the interval value (in hours): ")
    interval_seconds = interval_hours * 3600
    print(f"Interval set to {interval_hours} hours ({interval_seconds:.0f} seconds).")
    return interval_seconds


CONSECUTIVE_READINGS_REQUIRED = 3


def monitor(high_pres, low_pres, interval_seconds, refrigerant, sh_range, sc_range):
    last_message = None
    consecutive_count = 0
    while True:
        analogue_high, analogue_low, suction_temp, liquid_temp = take_readings()

        # Layer 1: hard-limit pressure check against the setpoints
        message = fault_alarm(analogue_high, analogue_low, high_pres, low_pres)
        if message == last_message and message != "No fault detected":
            consecutive_count += 1
        else:
            consecutive_count = 1
        last_message = message
        if consecutive_count == CONSECUTIVE_READINGS_REQUIRED:
            print(f"*** CONFIRMED ALARM: {message} ***")
            logging.warning(f"CONFIRMED ALARM: {message}")

        # Layer 2: superheat/subcooling charge diagnosis (more accurate,
        # since it reflects what's actually happening inside the
        # evaporator/condenser rather than just comparing raw pressure
        # to a fixed setpoint), judged against THIS system's own targets
        report_superheat_subcooling(suction_temp, liquid_temp, analogue_low, analogue_high, refrigerant, sh_range,
                                    sc_range)

        stop = input("Press Enter to continue, or type 'q' to quit: ")
        if stop.strip().lower() == "q":
            print("Monitoring stopped.")
            break


def main():
    refrigerant = get_refrigerant()
    high_pres, low_pres = take_setpoints()
    target_superheat, target_subcooling = take_target_sh_sc()
    sh_range = build_range(target_superheat)
    sc_range = build_range(target_subcooling)
    print(f"Target Superheat: {target_superheat} C (accepting {sh_range[0]:.1f}-{sh_range[1]:.1f} C)")
    print(f"Target Subcooling: {target_subcooling} C (accepting {sc_range[0]:.1f}-{sc_range[1]:.1f} C)")
    interval_seconds = set_interval()
    monitor(high_pres, low_pres, interval_seconds, refrigerant, sh_range, sc_range)


if __name__ == "__main__":
    main()


