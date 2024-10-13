import cv2
import numpy as np
import os
from datetime import datetime, timedelta
from ext_signals import *
import sys


class ai_detector:

    def __init__(self, stream_input,
                 file_to_save,
                 frames_to_save=20*5):

        self.stream_input = stream_input
        self.file_to_save = file_to_save
        self.frames_to_save = frames_to_save
        self.record_frame_acc = 0

    def write_video(self):

        cap = cv2.VideoCapture(self.stream_input)
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        video_writer = cv2.VideoWriter(self.file_to_save, 0x7634706d, 20.0, (int(w), int(h)))

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            self.record_frame_acc = self.record_frame_acc + 1
            if self.record_frame_acc < self.frames_to_save:
                video_writer.write(frame)
            else:
                video_writer.release()
                if os.path.exists(os.path.join(self.internal_fold, EXT_SIGNAL_RECORD)):
                    os.remove(os.path.join(self.internal_fold, EXT_SIGNAL_RECORD))
                self.telebot.send_video(open(video_path, "rb"))
                self.record_flg = False
                self.record_start_time = None
                self.record_frame_acc = 0