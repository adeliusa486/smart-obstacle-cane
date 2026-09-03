"""
VisionBridge AI - Quantized INT8 TensorFlow Lite Inference Pipeline
Multimodal Embedded Assistive Mobility Cane for Visually Impaired Users

Runs 100% offline on Raspberry Pi Zero 2W.
Implements:
  1. Picamera2 RGB frame acquisition (320x240)
  2. Fixed modulo-3 frame skipping (finfer ≈ 2-3 FPS)
  3. TensorFlow Lite INT8 Quantized SSD MobileNet V1 inference
  4. ST VL53L0X Time-of-Flight (ToF) distance polling (20 Hz)
  5. 4-Tier proximity-to-haptic encoding (Table II) via tmpfs IPC
  6. Concise verbal object/distance notifications via espeak-ng and Bluetooth
"""

import time
import subprocess
import threading
import os
import smbus2
import numpy as np
from picamera2 import Picamera2

# Try importing tflite_runtime first (preferred on embedded Pi), fallback to full tf.lite
try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    try:
        import tensorflow.lite as tflite
    except ImportError:
        tflite = None

# Model & Threshold Configuration
MODEL_PATH            = "/home/pi/model/ssd_mobilenet_v1_coco_quant_postprocess.tflite"
CONFIDENCE_THRESHOLD  = 0.50
SPEAK_COOLDOWN        = 4.0
DISTANCE_MIN_CM       = 5
DISTANCE_MAX_CM       = 200
BLIND_OBSTACLE_CM     = 80
OBSTACLE_COOLDOWN     = 4.0
VL53L0X_ADDRESS       = 0x29
I2C_BUS               = 1
CMD_FILE              = "/tmp/motor_cmd"

# Standard COCO 90 Class Labels
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

def set_motor_tier(tier):
    """Write haptic tier (0-4) to volatile tmpfs file for motor daemon."""
    try:
        with open(CMD_FILE, "w") as f:
            f.write(str(tier))
    except Exception:
        pass

def get_haptic_tier(distance_cm):
    """
    Formal Vibrotactile Encoding Scheme (Paper Table II):
      <50 cm:     Tier 4 (Critical)
      50-80 cm:   Tier 3 (High)
      80-120 cm:  Tier 2 (Moderate)
      120-150 cm: Tier 1 (Low)
      >150 cm:    Tier 0 (Audio only / Informational)
    """
    if distance_cm <= 0:
        return 0
    if distance_cm < 50:
        return 4
    elif distance_cm < 80:
        return 3
    elif distance_cm < 120:
        return 2
    elif distance_cm <= 150:
        return 1
    return 0

# Launch standalone motor daemon as an isolated process
print("[INIT] Launching isolated haptic motor daemon...")
motor_proc = subprocess.Popen(
    ["python3", "/home/pi/motor_process.py"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

# Initialize VL53L0X Distance Sensor over I2C
bus = smbus2.SMBus(I2C_BUS)
time.sleep(0.5)
try:
    mid = bus.read_byte_data(VL53L0X_ADDRESS, 0xC0)
    if mid != 0xEE:
        print(f"[WARN] Unexpected VL53L0X ID: 0x{mid:02X}")
    else:
        print("[INIT] VL53L0X ToF laser distance sensor verified (0xEE).")
except Exception as e:
    print(f"[ERROR] VL53L0X sensor communication failure: {e}")

def read_distance_cm():
    """Poll ST VL53L0X Time-of-Flight sensor via direct I2C register access."""
    global bus
    try:
        bus.write_byte_data(VL53L0X_ADDRESS, 0x00, 0x01)
        for _ in range(100):
            if bus.read_byte_data(VL53L0X_ADDRESS, 0x13) & 0x07:
                break
            time.sleep(0.005)
        data = bus.read_i2c_block_data(VL53L0X_ADDRESS, 0x14, 12)
        bus.write_byte_data(VL53L0X_ADDRESS, 0x0B, 0x01)
        cm = ((data[10] << 8) + data[11]) / 10.0
        if cm < DISTANCE_MIN_CM or cm > DISTANCE_MAX_CM:
            return -1
        return int(cm)
    except Exception:
        try:
            bus.close()
            time.sleep(0.2)
            bus = smbus2.SMBus(I2C_BUS)
        except Exception:
            pass
        return -1

# Load TFLite Model
interpreter = None
input_details = None
output_details = None

if tflite is not None and os.path.exists(MODEL_PATH):
    print(f"[INIT] Loading quantized INT8 TFLite model from {MODEL_PATH}...")
    interpreter = tflite.Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()
    input_details  = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    print("[INIT] TFLite INT8 inference pipeline initialized successfully.")
else:
    print(f"[WARN] TFLite runtime or model at {MODEL_PATH} not found. Running in proximity-only fallback mode.")

# Audio Feedback Engine (Thread-Safe espeak-ng)
speak_lock = threading.Lock()

def speak(text):
    def _worker():
        env = {
            "PATH": "/usr/bin:/bin",
            "PULSE_RUNTIME_PATH": "/run/user/1000/pulse",
            "XDG_RUNTIME_DIR": "/run/user/1000",
            "HOME": "/home/pi"
        }
        with speak_lock:
            try:
                subprocess.run(["pkill", "-9", "espeak-ng"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(0.05)
                subprocess.run(["espeak-ng", "-a", "200", "-s", "130", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, timeout=8)
            except Exception as ex:
                print(f"[AUDIO] Speech error: {ex}")
    threading.Thread(target=_worker, daemon=True).start()

# Camera Initialization
print("[INIT] Initializing Picamera2...")
picam2 = None
for attempt in range(10):
    try:
        cams = Picamera2.global_camera_info()
        if len(cams) == 0:
            time.sleep(2)
            continue
        picam2 = Picamera2()
        cfg = picam2.create_preview_configuration(main={"format": "RGB888", "size": (320, 240)})
        picam2.configure(cfg)
        picam2.start()
        time.sleep(3)
        print("[INIT] Camera module ready.")
        break
    except Exception as e:
        time.sleep(2)

if picam2 is None:
    print("[ERROR] Camera initialization failed.")

# Main Perception & Feedback Loop
last_spoken          = {}
last_obstacle_spoken = 0
frame_count          = 0

speak("Vision Bridge AI Ready")
set_motor_tier(0)

try:
    while True:
        distance_cm = read_distance_cm()

        if picam2 is not None:
            try:
                frame = picam2.capture_array()
            except Exception:
                frame = None
        else:
            frame = None

        frame_count += 1
        obj_detected = False

        # Modulo-3 inference scheduling to reduce CPU thermal load
        if frame is not None and interpreter is not None and frame_count % 3 == 0:
            in_shape = input_details[0]['shape']
            # Resize and prepare tensor
            import cv2
            resized = cv2.resize(frame, (in_shape[2], in_shape[1]))
            input_data = np.expand_dims(resized, axis=0)

            # Check if model requires UINT8 or FLOAT32
            if input_details[0]['dtype'] == np.float32:
                input_data = (np.float32(input_data) - 127.5) / 127.5
            else:
                input_data = np.uint8(input_data)

            interpreter.set_tensor(input_details[0]['index'], input_data)
            interpreter.invoke()

            boxes   = interpreter.get_tensor(output_details[0]['index'])[0]
            classes = interpreter.get_tensor(output_details[1]['index'])[0]
            scores  = interpreter.get_tensor(output_details[2]['index'])[0]

            for i in range(len(scores)):
                if scores[i] > CONFIDENCE_THRESHOLD:
                    cid = int(classes[i])
                    if 0 < cid < len(CLASSES):
                        label = CLASSES[cid]
                        obj_detected = True
                        now = time.time()

                        if now - last_spoken.get(label, 0) > SPEAK_COOLDOWN:
                            msg = f"{label} {distance_cm} centimeters" if distance_cm > 0 else label
                            print(f"[DETECT] {label} | {distance_cm} cm | Conf: {scores[i]:.2f}")
                            speak(msg)
                            last_spoken[label] = now

                        # Compute tiered haptic feedback
                        tier = get_haptic_tier(distance_cm)
                        set_motor_tier(tier if tier > 0 else 2)

        # Standalone proximity failsafe: runs even when AI model stalls or doesn't detect
        if not obj_detected:
            if distance_cm > 0 and distance_cm <= BLIND_OBSTACLE_CM:
                tier = get_haptic_tier(distance_cm)
                set_motor_tier(max(tier, 2))
                now = time.time()
                if now - last_obstacle_spoken > OBSTACLE_COOLDOWN:
                    msg = f"Obstacle {distance_cm} centimeters"
                    print(f"[FAILSAFE] Obstacle detected at {distance_cm} cm")
                    speak(msg)
                    last_obstacle_spoken = now
            else:
                set_motor_tier(0)

        time.sleep(0.05)

except KeyboardInterrupt:
    print("[STOP] Stopped by user.")
finally:
    set_motor_tier(0)
    if motor_proc is not None:
        motor_proc.kill()
    if picam2 is not None:
        try:
            picam2.stop()
            picam2.close()
        except Exception:
            pass
    try:
        bus.close()
    except Exception:
        pass
    print("[CLEANUP] System halted cleanly.")
