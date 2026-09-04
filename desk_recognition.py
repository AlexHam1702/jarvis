import cv2
import threading
import time
from ultralytics import YOLO

class ThreadedCamera:
    def __init__(self, cam_index=1, width=1920, height=1080, fps=60):
        self.cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        
        self.ret, self.frame = self.cap.read()
        self.stopped = False
        threading.Thread(target=self.update, args=(), daemon=True).start()

    def update(self):
        while not self.stopped:
            self.ret, self.frame = self.cap.read()
            
    def read(self):
        return self.ret, self.frame

    def stop(self):
        self.stopped = True
        self.cap.release()

def main():
    model = YOLO("yolov8s-world.pt")

    custom_items = [
        "white keyboard",
        "black computer mouse",
        "black smartphone",
        "coffee mug",
        "wrist watch",
        "microphone",
        "laptop",
        "headphones",
        "notebook",
        "water bottle",
        "pen"
    ]
    model.set_classes(custom_items)

    print("Warming up camera thread...")
    cam = ThreadedCamera(cam_index=1)
    time.sleep(1.0)

    frame_count = 0
    cached_boxes = []

    print("\n[Vision System Active] Tracking items and streaming frames. Press 'q' to quit.\n")

    while True:
        ret, frame = cam.read()
        if not ret or frame is None:
            continue
            
        display_frame = frame.copy()
        frame_count += 1

        # Run inference on every 2nd frame to maintain high framerates on RTX 3060
        if frame_count % 2 == 0:
            results = model.predict(
                display_frame, 
                conf=0.20, 
                imgsz=640, 
                device=0, 
                verbose=False
            )
            
            cached_boxes.clear()
            for box in results[0].boxes:
                bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = f"{custom_items[cls_id]} {conf:.2f}"
                cached_boxes.append((bx1, by1, bx2, by2, label))

        # Render detected bounding boxes
        for bx1, by1, bx2, by2, label in cached_boxes:
            cv2.rectangle(display_frame, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
            cv2.putText(
                display_frame, 
                label, 
                (bx1, max(by1 - 8, 18)), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.6, 
                (0, 255, 0), 
                2
            )

        # Continually downscale and save the latest frame for voice_agent.py
        small_frame = cv2.resize(display_frame, (640, 360))
        cv2.imwrite("latest_frame.jpg", small_frame)

        cv2.putText(display_frame, "JARVIS VISION: MONITORING", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Desk Assistant - YOLO & Vision", display_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cam.stop()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()