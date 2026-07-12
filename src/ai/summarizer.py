import requests


class Summarizer:

    def __init__(self, endpoint, model):
        self.endpoint = endpoint
        self.model = model

    def summarize(self, text):

        prompt = f"""
You are NEMO.

Summarise this markdown note in exactly one sentence.

Return ONLY the summary.
Do not explain your reasoning.
Do not show thinking.

{text}
"""

        print("Sending request...")

        response = requests.post(
            f"{self.endpoint}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
            },
            timeout=60,
        )

        print("Status Code:", response.status_code)
        print("Raw Response:")
        print(response.text)

        response.raise_for_status()

        return response.json()["response"].strip()