import requests

def fetch(url: str) -> str:
    response = requests.get(url)

    return response.text
