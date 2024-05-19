import json
import random
import requests
from get_config import Config

bartender = random.choice(Config("bartender", "sample_sentences.yaml").get())
api_config = Config("api", "api_config.yaml").get()
headers = api_config["headers"]
base_url = api_config["url_template"]
req_url = base_url.replace("port", str(api_config["mixology"]["port"])).replace("target_name", api_config["mixology"]["target_name"]["mixology"])

def client():
    print("\n[%s (bartender)]\nWelcome to the World Mixology.\nFeel free to talk about anything." % (bartender))
    
    while True:
        user_input = input("\n[You]\n")
        if user_input.lower() == "quit" or user_input.lower() == "exit":
            print("\n[%s (bartender)]\nWish you have a good time!\n" % (bartender))
            break
        
        print("\n[%s (bartender)]\n%s" % (bartender, requests.post(req_url, data=json.dumps({"text": str(user_input)}), headers=headers).json()["resp"]))

if __name__ == "__main__":
    client()
