from ai_detector import AIdetector
from datetime import datetime, timedelta



detector = AIdetector()

start = datetime.now()

detector.process_video("Resources/camera_1/23-12-26T-14-48-32_video_by_ext_signal.mp4")

print(datetime.now() - start)