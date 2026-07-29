
import time
import logging


#logs every change and puts it in a txt file
logging.basicConfig(
    filename="faultslog.txt",
    level = logging.INFO,
    format = "%(asctime)s - %(message)s"
)


# Tolerance

percentage = 0.05 # Enter percentage in decimal

def tolerance(measured, setpoint, percentage=percentage):
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


def take_setpoints():
    """Get the high and low pressure setpoints from the user."""
    high_pres = float(input("Enter the High Pressure value: "))
    low_pres = float(input("Enter the Low Pressure value: "))
    return high_pres, low_pres


def take_analogue_input():
    """Get the current measured (analogue) high and low pressure readings."""
    analogue_high = float(input("Enter the Analogue High Input value: "))
    analogue_low = float(input("Enter the Analogue Low value: "))
    return analogue_high, analogue_low

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
    # Needs to take into account enthalpy of system, subcooling and superheat
    ("below", "above"): "Refrigerant Leak Detected/Evaporator Airflow Restricted",
    ("below", "below"): "Inefficient Compressor Detected",
    ("above", "above"): "Condenser Airflow Restricted",
    ("equal", "equal"): "No fault detected",
    ("below", "equal"): "Possible Low-Side Restriction (needs review)",
    ("equal", "below"): "Possible TEV Overfeeding (needs review)",
    ("above", "equal"): "Possible Partial High-Side Fault (needs review)",
}


def fault_alarm(analogue_high, analogue_low, high_pres, low_pres):
    """Compare measured values against setpoints and report any fault."""
    high_state = classify(analogue_high, high_pres)
    low_state = classify(analogue_low, low_pres)

    message = FAULTS.get((high_state, low_state), "No fault detected")
    print(message)
    logging.info(message)
    return message


def set_interval():
    """Get how often (in hours) the system should re-check for faults."""
    interval_hours = get_float("Enter the interval value (in hours): ")
    interval_seconds = interval_hours * 3600
    print(f"Interval set to {interval_hours} hours ({interval_seconds:.0f} seconds).")
    return interval_seconds

#so that the alarm doesnt flare up unless its a consistent issue
CONSECUTIVE_READINGS_REQUIRED = 3


def monitor(high_pres, low_pres, interval_seconds):
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
            print(f"*** Potential Issue: {message} ***")
            logging.warning(f"*** Potential Issue: {message} ***")

        stop = input("Press Enter to continue, or type 'q' to quit: ")
        if stop.strip().lower() == "q":
            print("Monitoring stopped.")
            break

        # time.sleep(interval_seconds)   # uncomment for real timed monitoring


def main():
    high_pres, low_pres = take_setpoints()
    interval_seconds = set_interval()
    monitor(high_pres, low_pres, interval_seconds)


if __name__ == "__main__":
    main()


    
    