import requests


class Summarizer:

    def __init__(self, endpoint, model):
        self.endpoint = endpoint
        self.model = model

    def summarize(self, text):
        pass