import cv2
import os
from ext_signals import *

class CameraStream:

    def __init__(self, camera_name,
                 stream_input,
                 telebot=None,
                 frame_threshold=200,
                 stream_input_sub=None):

        self.stream_input = stream_input
        if stream_input_sub is None:
            self.stream_input_sub = stream_input
        else:
            self.stream_input_sub = stream_input_sub

        self.frame_threshold = frame_threshold
        self.camera_name = camera_name

        self.telebot = telebot

        self.record_flg = False
        self.send_video = False
        self.frames_to_save = 20*15
        self.record_frame_acc = 0

        self.photo_flg = False

        self.alarm_flg = False

        self.internal_fold = os.path.join("Resources", self.camera_name)
        if not os.path.exists(self.internal_fold):
            os.makedirs(self.internal_fold)

        for each_file in os.listdir(self.internal_fold):
            os.remove(os.path.join(self.internal_fold, each_file))

        open(os.path.join(self.internal_fold, EXT_SIGNAL_ALARM), "w").close()

    def update_external_signals(self):
        current_files = os.listdir(self.internal_fold)
        if EXT_SIGNAL_PHOTO in current_files:
            self.photo_flg = True
        if EXT_SIGNAL_ALARM in current_files:
            self.alarm_flg = True
        else:
            self.alarm_flg = False
        if EXT_SIGNAL_RECORD in current_files:
            self.record_flg = True

    def process_rtsp_stream(self, queue=None):
        cap = cv2.VideoCapture(self.stream_input)
        #cap_hr = cv2.VideoCapture(self.stream_input_sub)
        frames_acc = 0
        video_path = f"Resources/{self.camera_name}/video_by_ext_signal.mp4"
        w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        video_writer = None
        while True:
            ret, frame = cap.read()
            #ret_hr, frame_hr = cap_hr.read()
            if not ret:
                break

            if video_writer is None:
                video_writer = cv2.VideoWriter(video_path, 0x7634706d, 15.0, (int(w), int(h)))
            if self.record_frame_acc < self.frames_to_save:
                video_writer.write(frame)
                self.record_frame_acc = self.record_frame_acc + 1
            else:
                video_writer.release()
                video_writer = None
                self.record_frame_acc = 0
                if self.record_flg:
                    if os.path.exists(os.path.join(self.internal_fold, EXT_SIGNAL_RECORD)):
                        os.remove(os.path.join(self.internal_fold, EXT_SIGNAL_RECORD))
                    self.telebot.send_video(open(video_path, "rb"))
                    self.record_flg = False
                os.remove(video_path)



            if self.photo_flg:
                path = os.path.join(self.internal_fold, "image_by_ext_signal.jpg")
                cv2.imwrite(path, frame)
                if os.path.exists(os.path.join(self.internal_fold, EXT_SIGNAL_PHOTO)):
                    os.remove(os.path.join(self.internal_fold, EXT_SIGNAL_PHOTO))
                if self.telebot:
                    self.telebot.send_photo(open(path, "rb"))
                self.photo_flg = False

            frames_acc = frames_acc+1
            if frames_acc > self.frame_threshold:
                self.update_external_signals()
                frames_acc = 0
                if queue is not None:
                    queue.put_nowait((frame, self.camera_name))

            #cv2.imshow('Video', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()