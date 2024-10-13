import requests


class TeleInformer:

    def __init__(self, chat_id, token):
        self.baseurl = "https://api.telegram.org/bot"
        self.chat_id = chat_id
        self.token = token

    def send_mess(self, text):
        params = {'chat_id': self.chat_id, 'text': text}
        response = requests.post(self.baseurl + self.token + "/" + 'sendMessage', data=params)
        return response

    def send_photo(self, photo, text=None):
        params = {'chat_id': self.chat_id}
        if text:
            params.update({'text': text})
        files = {'photo': photo}
        response = requests.post(self.baseurl + self.token + "/" + 'sendPhoto', data=params, files=files)
        return response

    def send_video(self, video, text=None):
        params = {'chat_id': self.chat_id}
        if text:
            params.update({'text': text})
        files = {'video': video}
        response = requests.post(self.baseurl + self.token + "/" + 'sendVideo', data=params, files=files)
        return response