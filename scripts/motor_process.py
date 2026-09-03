import RPi.GPIO as GPIO
import time
import os

# Configuration matching IEEE Paper Table II & Prototype Hardware
MOTOR_PIN    = 18
CMD_FILE     = "/tmp/motor_cmd"
HOLD_SECONDS = 3.0

# Table II Vibrotactile Encoding Scheme:
# Tier 4 (Critical, <50cm): 500ms on, 100ms off
# Tier 3 (High, 50-80cm):   300ms on, 200ms off
# Tier 2 (Moderate, 80-120cm): 200ms on, 400ms off
# Tier 1 (Low, 120-150cm):  100ms on, 800ms off
# Tier 0 (>150cm / clear):  Motor OFF (audio-only informational alerts)
TIER_PROFILES = {
    4: {"on": 0.50, "off": 0.10, "pause": 0.50, "pulses": 3},  # Critical
    3: {"on": 0.30, "off": 0.20, "pause": 0.80, "pulses": 2},  # High
    2: {"on": 0.20, "off": 0.40, "pause": 1.20, "pulses": 2},  # Moderate
    1: {"on": 0.10, "off": 0.80, "pause": 1.50, "pulses": 1},  # Low
}

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(MOTOR_PIN, GPIO.OUT)
GPIO.output(MOTOR_PIN, GPIO.LOW)

# Initialize command file if not existing
if not os.path.exists(CMD_FILE):
    try:
        with open(CMD_FILE, "w") as f:
            f.write("0")
    except Exception:
        pass

print("VisionBridge AI Motor Daemon Running.")

last_nonzero_time = 0
current_tier      = 0

def read_cmd():
    try:
        val = int(open(CMD_FILE).read().strip())
        return val
    except Exception:
        return 0

def execute_haptic(tier):
    profile = TIER_PROFILES.get(tier, TIER_PROFILES[2])
    for _ in range(profile["pulses"]):
        GPIO.output(MOTOR_PIN, GPIO.HIGH)
        time.sleep(profile["on"])
        GPIO.output(MOTOR_PIN, GPIO.LOW)
        time.sleep(profile["off"])
    time.sleep(profile["pause"])

try:
    while True:
        cmd = read_cmd()
        if cmd > 0:
            last_nonzero_time = time.time()
            current_tier      = cmd
            execute_haptic(cmd)
        else:
            # Temporal persistence window: hold motor state for HOLD_SECONDS
            # to smooth rapid detection fluctuations during user movement
            if time.time() - last_nonzero_time < HOLD_SECONDS and current_tier > 0:
                execute_haptic(current_tier)
            else:
                current_tier = 0
                GPIO.output(MOTOR_PIN, GPIO.LOW)
                time.sleep(0.05)
except KeyboardInterrupt:
    pass
finally:
    GPIO.output(MOTOR_PIN, GPIO.LOW)
    GPIO.cleanup()
    print("Motor daemon stopped cleanly.")

