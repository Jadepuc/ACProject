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
            (-40, 10.7), (-30, 17.7), (-20, 26.2), (-10, 36.3), (0, 48.2),
            (10, 62.2), (20, 78.4), (30, 97.0), (40, 118.4), (50, 142.6),
            (60, 170.1), (70, 201.1), (80, 235.7), (90, 274.5), (100, 317.6),
            (110, 365.4), (120, 418.3), (130, 476.8), (140, 541.5), (150, 613.0),
        ]
    },
    "R22": {
        "single": [
            (-40, 0.6), (-30, 4.9), (-20, 10.2), (-10, 16.5), (0, 24.0),
            (10, 32.8), (20, 43.1), (30, 55.0), (40, 68.6), (50, 84.1),
            (60, 101.6), (70, 121.4), (80, 143.6), (90, 168.4), (100, 195.9),
            (110, 226.4), (120, 260.0), (130, 296.9), (140, 337.4), (150, 381.7),
        ]
    },
    "R134A": {
        "single": [
            (-40, -7.3), (-30, -4.8), (-20, -1.8), (-10, 1.9), (0, 6.5),
            (10, 11.9), (20, 18.4), (30, 26.1), (40, 35.0), (50, 45.4),
            (60, 57.4), (70, 71.1), (80, 86.7), (90, 104.3), (100, 124.2),
            (110, 146.4), (120, 171.2), (130, 198.7), (140, 229.2), (150, 262.9),
        ]
    }
}


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


def take_analogue_input():
    # Take analaogue input from user
    analogue_high = float(input("Enter the Analogue High Input value: "))
    analogue_low = float(input("Enter the Analogue Low value: "))
    return analogue_high, analogue_low


def take_temperature_readings():
    # Get the suction line and liquid line temperatures for SH/SC calcs
    suction_temp = get_float("Enter the Suction Line Temperature (F): ")
    liquid_temp = get_float("Enter the Liquid Line Temperature (F): ")
    return suction_temp, liquid_temp


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


## change for target subcoolig and superheat
TYPICAL_SH_SC_RANGE = (8, 12)


def calc_superheat(suction_temp, low_pressure, refrigerant):
    """Superheat = actual suction line temp - saturated evaporating temp."""
    pt_table = get_pt_table(refrigerant, "superheat")
    sat_temp = saturation_temp(low_pressure, pt_table)
    if sat_temp is None:
        return None
    return suction_temp - sat_temp


def calc_subcooling(liquid_temp, high_pressure, refrigerant):
    """Subcooling = saturated condensing temp - actual liquid line temp."""
    pt_table = get_pt_table(refrigerant, "subcooling")
    sat_temp = saturation_temp(high_pressure, pt_table)
    if sat_temp is None:
        return None
    return sat_temp - liquid_temp


def report_superheat_subcooling(suction_temp, liquid_temp, low_pressure, high_pressure, refrigerant):
    """Calculate, print, log, and sanity-check superheat and subcooling."""
    superheat = calc_superheat(suction_temp, low_pressure, refrigerant)
    subcooling = calc_subcooling(liquid_temp, high_pressure, refrigerant)

    if superheat is None or subcooling is None:
        print("Superheat/Subcooling: pressure reading is outside the PT table range, cannot calculate.")
        return superheat, subcooling

    print(f"Superheat: {superheat:.1f} F | Subcooling: {subcooling:.1f} F")
    logging.info(f"Superheat: {superheat:.1f} F, Subcooling: {subcooling:.1f} F")

    low, high = TYPICAL_SH_SC_RANGE
    if not (low <= superheat <= high):
        print(f"  Note: Superheat is outside the common {low}-{high} F teaching range - check manufacturer spec.")
    if not (low <= subcooling <= high):
        print(f"  Note: Subcooling is outside the common {low}-{high} F teaching range - check manufacturer spec.")

    return superheat, subcooling


def set_interval():
    interval_hours = get_float("Enter the interval value (in hours): ")
    interval_seconds = interval_hours * 3600
    print(f"Interval set to {interval_hours} hours ({interval_seconds:.0f} seconds).")
    return interval_seconds


CONSECUTIVE_READINGS_REQUIRED = 3


def monitor(high_pres, low_pres, interval_seconds, refrigerant):
    last_message = None
    consecutive_count = 0
    while True:
        analogue_high, analogue_low = take_analogue_input()
        message = fault_alarm(analogue_high, analogue_low, high_pres, low_pres)
        if message == last_message and message != "No fault detected":
            consecutive_count += 1
        else:
            consecutive_count = 1
        last_message = message
        if consecutive_count == CONSECUTIVE_READINGS_REQUIRED:
            print(f"*** CONFIRMED ALARM: {message} ***")
            logging.warning(f"CONFIRMED ALARM: {message}")

        suction_temp, liquid_temp = take_temperature_readings()
        report_superheat_subcooling(suction_temp, liquid_temp, analogue_low, analogue_high, refrigerant)

        stop = input("Press Enter to continue, or type 'q' to quit: ")
        if stop.strip().lower() == "q":
            print("Monitoring stopped.")
            break


def main():
    refrigerant = get_refrigerant()
    high_pres, low_pres = take_setpoints()
    interval_seconds = set_interval()
    monitor(high_pres, low_pres, interval_seconds, refrigerant)


if __name__ == "__main__":
    main()

