import cv2
import numpy as np
import os
from datetime import datetime, timedelta
from ext_signals import *
import sys

class ai_detector:

    def __init__(self, camera_name,
                 stream_input,
                 frame_threshold=3,
                 frame_loop=25,
                 telebot=None,
                 stream_input_sub=None,
                 frame_rate=20):

        self.stream_input = stream_input
        self.frame_rate=frame_rate

        if stream_input_sub is None:
            self.stream_input_sub = stream_input
        else:
            self.stream_input_sub = stream_input_sub

        self.frame_threshold = frame_threshold
        self.camera_name = camera_name
        self.telebot = telebot

        self.frame_loop=frame_loop

        self.net = cv2.dnn.readNetFromDarknet("Resources/yolov4-tiny.cfg",
                                         "Resources/yolov4-tiny.weights")
        self.layer_names = self.net.getLayerNames()
        self.out_layers_indexes = self.net.getUnconnectedOutLayers()
        self.out_layers = [self.layer_names[index - 1] for index in self.out_layers_indexes]

        with open(os.path.join("Resources", "coco.names.txt")) as f:
            self.classes_to_capture = f.read().splitlines()

        classes = [
            "person",
            "bicycle",
            "car",
            "motorbike",
            "aeroplane",
            "bus",
            "train",
            "truck",
            "boat",
            "bird",
            "cat",
            "dog",
            "horse",
            "sheep",
            "cow",
            "elephant",
            "bear"]

        self.classes_to_look_for=classes

        self.frame_threshold = frame_threshold
        #self.frame_threshold_class = {key: self.frame_threshold for key in self.classes_to_look_for}

        self.record_flg = False
        self.record_start_time = None
        self.frames_to_save = 20*5
        self.record_frame_acc=0

        self.photo_flg = False
        self.photo_last_dttm = datetime.now()
        self.photo_delay_duration = 5

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



    def apply_yolo_object_detection(self, image_to_process):
        """
        Recognition and determination of the coordinates of objects on the image
        :param image_to_process: original image
        :return: image with marked objects and captions to them
        """

        if image_to_process is None:
            return

        height, width, _ = image_to_process.shape

        blob = cv2.dnn.blobFromImage(image_to_process, 1/255, (416, 416),
                                     (0, 0, 0), swapRB=True, crop=False)

        net = self.net
        net.setInput(blob)
        outs = net.forward(self.out_layers)
        class_indexes, class_scores, boxes = ([] for i in range(3))


        # Starting a search for objects in an image
        for out in outs:
            for obj in out:
                scores = obj[5:]
                class_index = np.argmax(scores)
                class_score = scores[class_index]
                if class_score > 0:
                    center_x = int(obj[0] * width)
                    center_y = int(obj[1] * height)
                    obj_width = int(obj[2] * width)
                    obj_height = int(obj[3] * height)
                    box = [center_x - obj_width // 2, center_y - obj_height // 2,
                           obj_width, obj_height]
                    boxes.append(box)
                    class_indexes.append(class_index)
                    class_scores.append(float(class_score))

        # Selection
        chosen_boxes = cv2.dnn.NMSBoxes(boxes, class_scores, 0.6, 0.4)
        for box_index in chosen_boxes:
            box = boxes[box_index]
            class_index = class_indexes[box_index]

            # For debugging, we draw objects included in the desired classes
            if self.classes_to_capture[class_index] in self.classes_to_look_for:

                print(f"Found an object. It's a {self.classes_to_capture[class_index]}")

                if datetime.now() - self.photo_last_dttm > timedelta(seconds=self.photo_delay_duration):

                    self.photo_last_dttm = datetime.now()
                    image_to_process = self.draw_object_bounding_box(image_to_process,
                                                                class_index, box)
                    image_path = self.internal_fold + "/captured_object" + ".jpg"
                    cv2.imwrite(image_path, image_to_process)

                    if self.telebot:
                        self.telebot.send_photo(open(image_path, "rb"), text="Обнаружен обьект")
                        self.record_flg = True

        #final_image = draw_object_count(image_to_process, objects_count)
        return image_to_process


    def draw_object_bounding_box(self, image_to_process, index, box):
        """
        Drawing object borders with captions
        :param image_to_process: original image
        :param index: index of object class defined with YOLO
        :param box: coordinates of the area around the object
        :return: image with marked objects
        """

        x, y, w, h = box
        start = (x, y)
        end = (x + w, y + h)
        color = (0, 255, 0)
        width = 1
        final_image = cv2.rectangle(image_to_process, start, end, color, width)

        start = (x, y - 10)
        font_size = 0.8
        font = cv2.FONT_HERSHEY_SIMPLEX
        width = 1
        text = self.classes_to_capture[index]
        final_image = cv2.putText(final_image, text, start, font,
                                  font_size, color, width, cv2.LINE_AA)

        return final_image


    def process_rtsp_stream(self, yolo_mode=False):
        cap = cv2.VideoCapture(self.stream_input)

        video_writer = None
        frame_rate=0
        frame_loop_rate = 0
        while True:

            ret, frame = cap.read()
            if not ret:
                break
            frame_rate=frame_rate+1
            frame_loop_rate=frame_loop_rate+1

            if self.record_flg:
                self.record_frame_acc = self.record_frame_acc + 1
                video_path = f"Resources/{self.camera_name}/video_by_ext_signal.mp4"
                #video_path = f"Resources/{self.camera_name}/video_by_ext_signal.mp4"
                if video_writer is None:
                    w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    video_writer = cv2.VideoWriter(video_path, 0x7634706d, 20.0, (int(w), int(h)))


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

            if self.photo_flg and frame_loop_rate > 20:

                self.update_external_signals()
                path = os.path.join(self.internal_fold, "image_by_ext_signal.jpg")
                cv2.imwrite(path, frame)
                self.photo_flg = False
                if os.path.exists(os.path.join(self.internal_fold, EXT_SIGNAL_PHOTO)):
                    os.remove(os.path.join(self.internal_fold, EXT_SIGNAL_PHOTO))
                if self.telebot:
                    self.telebot.send_photo(open(path, "rb"))

            # if frame_rate > self.frame_threshold:
            #     if self.alarm_flg:
            #         self.apply_yolo_object_detection(frame)
            #     frame_rate = 0


            # if yolo_mode and frame_loop_rate > self.frame_loop and self.record_flg == False:
            #     frame_loop_rate = 0
            #     break

            #cv2.imshow('Video', frame)

            if cv2.waitKey(30) & 0xFF == ord('q'):
                break

        cap.release()
        #sys.exit()