import RPi.GPIO as GPIO
import time
import os

MOTOR_PIN    = 18
BUZZ_ON      = 0.5
BUZZ_OFF     = 0.1
BUZZ_PAUSE   = 1.5
CMD_FILE     = "/tmp/motor_cmd"
HOLD_SECONDS = 3.0

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(MOTOR_PIN, GPIO.OUT)
GPIO.output(MOTOR_PIN, GPIO.LOW)

# Write default command
if not os.path.exists(CMD_FILE):
    open(CMD_FILE,"w").write("0")

print("Motor process running.")

last_nonzero_time = 0
current_count     = 0

def read_cmd():
    try:
        val = int(open(CMD_FILE).read().strip())
        return val
    except Exception:
        return 0

def buzz(times):
    for _ in range(times):
        GPIO.output(MOTOR_PIN, GPIO.HIGH)
        time.sleep(BUZZ_ON)
        GPIO.output(MOTOR_PIN, GPIO.LOW)
        time.sleep(BUZZ_OFF)

try:
    while True:
        cmd = read_cmd()
        if cmd > 0:
            last_nonzero_time = time.time()
            current_count     = cmd
            buzz(cmd)
            time.sleep(BUZZ_PAUSE)
        else:
            # Hold motor for HOLD_SECONDS after last command
            if time.time() - last_nonzero_time < HOLD_SECONDS and current_count > 0:
                buzz(current_count)
                time.sleep(BUZZ_PAUSE)
            else:
                current_count = 0
                GPIO.output(MOTOR_PIN, GPIO.LOW)
                time.sleep(0.05)
except KeyboardInterrupt:
    pass
finally:
    GPIO.output(MOTOR_PIN, GPIO.LOW)
    GPIO.cleanup()
    print("Motor process stopped.")
