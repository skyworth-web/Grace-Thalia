import requests

url = "http://localhost:8000/stt"
files = {'file': open('recorded_audio.wav', 'rb')}  # replace with your audio file path

response = requests.post(url, files=files)
print(response.json())
