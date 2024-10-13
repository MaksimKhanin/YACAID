import cv2
import numpy as np
import os

class AIdetector:

    def __init__(self):

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
        chosen_boxes = cv2.dnn.NMSBoxes(boxes, class_scores, 0.5, 0.4)
        for box_index in chosen_boxes:
            box = boxes[box_index]
            class_index = class_indexes[box_index]

            # For debugging, we draw objects included in the desired classes
            if self.classes_to_capture[class_index] in self.classes_to_look_for:

                print(f"Found an object. It's a {self.classes_to_capture[class_index]}")

                image_to_process = self.draw_object_bounding_box(image_to_process,
                                                            class_index, box)
                return image_to_process
            else:
                return None


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

    def process_video(self, input_path):

        cap = cv2.VideoCapture(input_path)
        frame_hb = 20
        frame_acc = 0
        while True:
            ret, frame = cap.read()

            if not ret:
                break
            frame_acc = frame_acc + 1
            if frame_acc > frame_hb:
                self.apply_yolo_object_detection(frame)
                frame_acc = 0

                cv2.imshow('Video', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        cap.release()



