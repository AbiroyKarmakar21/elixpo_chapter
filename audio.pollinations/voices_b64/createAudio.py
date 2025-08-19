import requests
import urllib.parse
from dotenv import load_dotenv
import os 
load_dotenv()

text = """
Speak this sentence out to me -- 'Sometimes, when we take a step back from the rush of everyday life, we realize that the small,
ordinary moments — like the sound of rain falling gently on the window, the warmth of a cup of tea 
held between our hands, or the quiet comfort of sitting with someone we care about without needing 
to say a word — are actually the moments that shape our memories the most, reminding us that happiness
is often found not in great achievements or loud celebrations, but in the subtle, almost invisible 
threads that weave our days together.'
"""



voices = ["alloy","echo","fable","onyx","nova","shimmer","coral","verse","ballad","ash","sage","amuch","dan"]
model = "openai-audio"
token = os.getenv("POLLI_TOKEN")
base_url = "https://text.pollinations.ai/"
encoded_text = urllib.parse.quote(text.strip().replace('\n', ' '))
for voice in voices:
    print(f"Generating audio for voice: {voice}")
    url = f"{base_url}{encoded_text}?model={model}&voice={voice}&token={token}&seed=24"
    response = requests.get(url)
    if response.status_code == 200:
        with open(f"voices_b64/raw_wav/{voice}.wav", "wb") as f:
            f.write(response.content)
    else:
        print(f"Request failed with status code {response.status_code}")
print("Audio generation completed for all voices.")