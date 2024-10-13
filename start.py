import yaml
import multiprocessing
import telebot
from telebot import types
from telegram_bot import TeleInformer
import os
from ext_signals import *
from time import sleep
import sys
from datetime import datetime
from camera_stream import CameraStream
from ai_detector import AIdetector
import cv2

def mult_proc(stream_name, rtsp_url, telebot, image_queue):

    camera = CameraStream(stream_name, rtsp_url, telebot=telebot)
    camera.process_rtsp_stream(queue=image_queue)

def detector_proc(telebot, image_queue):

    ai_detector = AIdetector()
    camera_sleep_buff = {}

    while True:

        # if image_queue.empty():
        #     print("Очередь пуста")
        #     sleep(0.1)
        #     continue
        # else:
        #     print("Очередь не пуста")

        image, camera_name = image_queue.get()

        result_image = ai_detector.apply_yolo_object_detection(image)

        if result_image is not None:

            camera_sleep_buff[camera_name] = datetime.now()
            image_file_prefix = datetime.now().strftime("%y-%m-%dT-%H-%M-%S")
            image_path = f"Resources/{camera_name}/{image_file_prefix}_captured_object" + ".jpg"
            cv2.imwrite(image_path, image)
            telebot.send_photo(open(image_path, "rb"), text="Обнаружен обьект")
            os.remove(image_path)

            path = os.path.join("Resources", camera_name, EXT_SIGNAL_RECORD)
            if os.path.exists(path) == False:
                open(path, "w").close()


def start_bot(token, chat_id, allowed_users, camera_cfg):
    bot = telebot.TeleBot(token)

    @bot.message_handler(commands=['start'], func=lambda message: message.from_user.id in allowed_users)
    def start(message):

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        #bot.send_message(message.from_user.id, "👋 Привет! Я твой бот-помошник по камерам!", reply_markup=markup)
        btn1 = types.KeyboardButton('Включить режим тревоги')
        btn2 = types.KeyboardButton('Выключить режим тревоги')
        btn3 = types.KeyboardButton('Сделать фото обстановки')
        btn4 = types.KeyboardButton('Сделать запись обстановки')
        markup.add(btn1, btn2, btn3, btn4)
        bot.send_message(message.from_user.id, "👋", reply_markup=markup)

    @bot.message_handler(content_types=['text'], func=lambda message: message.from_user.id in allowed_users)
    def get_text_messages(message):

        if message.text == 'Включить режим тревоги':

            for each_camera_set in camera_cfg:
                open(os.path.join("Resources", each_camera_set, EXT_SIGNAL_ALARM), "w").close()

            bot.send_message(message.from_user.id, 'Режим тревоги включен', parse_mode='Markdown')


        elif message.text == 'Выключить режим тревоги':

            for each_camera_set in camera_cfg:
                path = os.path.join("Resources", each_camera_set, EXT_SIGNAL_ALARM)
                if os.path.exists(path):
                    os.remove(path)

            bot.send_message(message.from_user.id, 'Режим тревоги выключен', parse_mode='Markdown')

        elif message.text == 'Сделать запись обстановки':

            for each_camera_set in camera_cfg:
                open(os.path.join("Resources", each_camera_set, EXT_SIGNAL_RECORD), "w").close()

            bot.send_message(message.from_user.id, 'Сигнал отправлен, ожидайте записи в целевом чате', parse_mode='Markdown')

        elif message.text == 'Сделать фото обстановки':

            for each_camera_set in camera_cfg:
                open(os.path.join("Resources", each_camera_set, EXT_SIGNAL_PHOTO), "w").close()

            bot.send_message(message.from_user.id, 'Сигнал отправлен, ожидайте фото в целевом чате', parse_mode='Markdown')

    bot.polling(none_stop=True, interval=5)

if __name__ == "__main__":

    app_path = os.path.dirname(os.path.abspath(__file__))
    os.chdir(app_path)

    image_queue = multiprocessing.Queue(maxsize=15)

    with open(os.path.join("cfg", "cfg.yml"), "r") as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)

    p_bot = multiprocessing.Process(target=start_bot, args=(cfg['telegram_cfg']['token'],
                                                            cfg['telegram_cfg']['chat_id'],
                                                            cfg['telegram_cfg']['allowed_users'],
                                                            cfg["stream_cfg"]
                                                            ))

    p_bot.start()
    #
    processes = [p_bot]


    bot = TeleInformer(cfg['telegram_cfg']['chat_id'], cfg['telegram_cfg']['token'])
    p_detector = multiprocessing.Process(target=detector_proc, args=(bot, image_queue))

    p_detector.start()
    processes.append(p_detector)


    for each_camera in cfg["stream_cfg"]:
        print(each_camera)

        rtsp_url = cfg["stream_cfg"][each_camera]["stream_detector"]
        #rtsp_url_hr = cfg["stream_cfg"][each_camera]["stream_video"]
        stream_name = each_camera

        p = multiprocessing.Process(target=mult_proc, args=(stream_name, rtsp_url, bot, image_queue))
        p.start()
        processes.append(p)

    while True:
        sleep(30)

        for p in processes:
            if not p.is_alive():  # проверка завершения процесса
                print("One of processes is not alive. Stopping the program")
                p.terminate()
                for p in processes:
                    p.terminate()  # прекращение всех процессов
                sys.exit()
