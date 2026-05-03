import cv2
import numpy as np
import subprocess
import time
import smbus2
import threading
import os
from picamera2 import Picamera2

CLASSES = [
    "background", "person", "bicycle", "car", "motorcycle",
    "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "street sign", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse",
    "sheep", "cow", "elephant", "bear", "zebra", "giraffe",
    "hat", "backpack", "umbrella", "shoe", "eye glasses",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle",
    "plate", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli",
    "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "mirror", "dining table",
    "window", "desk", "toilet", "door", "tv", "laptop",
    "mouse", "remote", "keyboard", "cell phone", "microwave",
    "oven", "toaster", "sink", "refrigerator", "blender",
    "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush"
]

MODEL_DIR             = "/home/pi/model/ssd_mobilenet_v1_coco_2017_11_17"
FROZEN_GRAPH          = MODEL_DIR + "/frozen_inference_graph.pb"
CONFIG_FILE           = MODEL_DIR + "/ssd_mobilenet_v1_coco.pbtxt"
CONFIDENCE_THRESHOLD  = 0.5
SPEAK_COOLDOWN        = 4.0
DISTANCE_MIN_CM       = 5
DISTANCE_MAX_CM       = 200
KNOWN_OBJECT_CLOSE_CM = 150
BLIND_OBSTACLE_CM     = 80
OBSTACLE_COOLDOWN     = 4.0
VL53L0X_ADDRESS       = 0x29
I2C_BUS               = 1
CMD_FILE              = "/tmp/motor_cmd"

# Motor command file - motor process reads this
def set_motor(count):
    try:
        open(CMD_FILE,"w").write(str(count))
    except Exception:
        pass

# Start motor process as completely separate process
print("Starting motor process...")
motor_proc = subprocess.Popen(
    ["python3", "/home/pi/motor_process.py"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)
print("Motor process started.")

# Sensor
bus = smbus2.SMBus(I2C_BUS)
time.sleep(0.5)
try:
    mid = bus.read_byte_data(VL53L0X_ADDRESS, 0xC0)
    if mid != 0xEE:
        print(f"Sensor ID wrong: 0x{mid:02X}")
        motor_proc.kill()
        bus.close()
        exit(1)
    print("Distance sensor ready.")
except Exception as e:
    print(f"Sensor error: {e}")
    motor_proc.kill()
    exit(1)

def read_distance_cm():
    global bus
    try:
        bus.write_byte_data(VL53L0X_ADDRESS, 0x00, 0x01)
        for _ in range(100):
            if bus.read_byte_data(VL53L0X_ADDRESS, 0x13) & 0x07:
                break
            time.sleep(0.01)
        data = bus.read_i2c_block_data(VL53L0X_ADDRESS, 0x14, 12)
        bus.write_byte_data(VL53L0X_ADDRESS, 0x0B, 0x01)
        cm = ((data[10] << 8) + data[11]) / 10.0
        if cm < DISTANCE_MIN_CM or cm > DISTANCE_MAX_CM:
            return -1
        return int(cm)
    except Exception:
        try:
            bus.close()
            time.sleep(0.5)
            bus = smbus2.SMBus(I2C_BUS)
        except Exception:
            pass
        return -1

# Load model
print("Loading AI model...")
net = cv2.dnn.readNetFromTensorflow(FROZEN_GRAPH, CONFIG_FILE)
print("AI model loaded.")

# Camera
print("Opening camera...")
picam2 = None
for attempt in range(15):
    try:
        cams = Picamera2.global_camera_info()
        if len(cams) == 0:
            print(f"No camera found ({attempt+1}/15), waiting...")
            time.sleep(3)
            continue
        picam2 = Picamera2()
        cfg = picam2.create_preview_configuration(
            main={"format": "RGB888", "size": (320, 240)}
        )
        picam2.configure(cfg)
        picam2.start()
        time.sleep(5)
        good = 0
        for _ in range(30):
            try:
                f = picam2.capture_array()
                if f is not None and f.size > 0:
                    good += 1
                if good >= 5:
                    break
            except Exception:
                pass
            time.sleep(0.2)
        if good == 0:
            raise RuntimeError("No good frames")
        print(f"Camera ready. Warmup frames: {good}")
        break
    except Exception as e:
        print(f"Camera attempt {attempt+1}/15: {e}")
        try:
            picam2.stop()
            picam2.close()
        except Exception:
            pass
        picam2 = None
        time.sleep(4)

if picam2 is None:
    print("Camera failed. Exiting.")
    motor_proc.kill()
    try: bus.close()
    except Exception: pass
    exit(1)

# Speech - one at a time
speak_lock = threading.Lock()

def speak(text):
    def _run():
        env = {
            "PATH": "/usr/bin:/bin",
            "PULSE_RUNTIME_PATH": "/run/user/1000/pulse",
            "XDG_RUNTIME_DIR": "/run/user/1000",
            "HOME": "/home/pi"
        }
        with speak_lock:
            try:
                subprocess.run(
                    ["pkill","-9","espeak-ng"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                time.sleep(0.05)
            except Exception:
                pass
            try:
                subprocess.run(
                    ["espeak-ng","-a","200","-s","130",text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    timeout=8
                )
            except Exception as e:
                print(f"Speech error: {e}")
    threading.Thread(target=_run, daemon=True).start()

last_spoken          = {}
last_obstacle_spoken = 0
consecutive_errors   = 0
last_detect_time     = 0
frame_count          = 0

print("System ready. Detection starting.")
speak("Smart cane ready")
set_motor(0)

try:
    while True:
        try:
            distance_cm = read_distance_cm()

            try:
                frame = picam2.capture_array()
                if frame is None or frame.size == 0:
                    raise ValueError("Empty frame")
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                print(f"Frame error {consecutive_errors}: {e}")
                if consecutive_errors >= 15:
                    print("Camera unrecoverable. Exiting.")
                    break
                time.sleep(0.5)
                continue

            # Only run AI every 3rd frame to save memory and CPU
            frame_count += 1
            obj_detected = False

            if frame_count % 3 == 0:
                blob = cv2.dnn.blobFromImage(
                    frame, size=(300,300), swapRB=False, crop=False
                )
                net.setInput(blob)
                detections = net.forward()

                for i in range(detections.shape[2]):
                    conf = detections[0,0,i,2]
                    if conf > CONFIDENCE_THRESHOLD:
                        cid = int(detections[0,0,i,1])
                        if 0 < cid < len(CLASSES):
                            label        = CLASSES[cid]
                            obj_detected = True
                            last_detect_time = time.time()
                            now          = time.time()
                            if now - last_spoken.get(label,0) > SPEAK_COOLDOWN:
                                msg = f"{label} {distance_cm} centimeters" if distance_cm > 0 else label
                                print(f"[DETECT] {label} | {distance_cm} cm | {conf:.2f}")
                                speak(msg)
                                last_spoken[label] = now
                            if distance_cm > 0 and distance_cm <= KNOWN_OBJECT_CLOSE_CM:
                                set_motor(4)
                            else:
                                set_motor(2)

                if not obj_detected:
                    if distance_cm > 0 and distance_cm <= BLIND_OBSTACLE_CM:
                        set_motor(2)
                        now = time.time()
                        if now - last_obstacle_spoken > OBSTACLE_COOLDOWN:
                            msg = f"Obstacle {distance_cm} centimeters"
                            print(f"[OBSTACLE] {distance_cm} cm")
                            speak(msg)
                            last_obstacle_spoken = now
                    else:
                        # Nothing detected - turn motor off
                        set_motor(0)

            time.sleep(0.05)

        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(0.5)

except KeyboardInterrupt:
    print("Stopped by user.")

finally:
    set_motor(0)
    time.sleep(0.5)
    motor_proc.kill()
    try: picam2.stop(); picam2.close()
    except Exception: pass
    try: bus.close()
    except Exception: pass
    print("Stopped cleanly.")
