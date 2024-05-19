import os
import re
import json
import random
import warnings
import requests
from flask import Flask, request as req, jsonify
from logger import ConcurrentLogger
from get_config import Config

warnings.filterwarnings("ignore")

app = Flask(__name__)
base_path = "logs"
input_path = "%s/user_input" % (base_path)
ar_path = "%s/after_request" % (base_path)
os.makedirs(input_path, exist_ok=True)
os.makedirs(ar_path, exist_ok=True)
log_input = ConcurrentLogger(filename="%s/user_input.log" % (input_path))
log_ar = ConcurrentLogger(filename="%s/after_request.log" % (ar_path))

api_config = Config("api", "api_config.yaml").get()
main_port, nlp_port, agent_port = api_config["mixology"]["port"], api_config["nlp"]["port"], api_config["agent"]["port"]
headers = api_config["headers"]
base_url = api_config["url_template"]
req_classify_url = base_url.replace("port", str(nlp_port)).replace("target_name", api_config["nlp"]["target_name"]["classify"])
req_info_url = base_url.replace("port", str(agent_port)).replace("target_name", api_config["agent"]["target_name"]["info"])
req_rec_url = base_url.replace("port", str(agent_port)).replace("target_name", api_config["agent"]["target_name"]["rec"])
req_choose_url = base_url.replace("port", str(agent_port)).replace("target_name", api_config["agent"]["target_name"]["choose"])
req_chat_url = base_url.replace("port", str(agent_port)).replace("target_name", api_config["agent"]["target_name"]["chat"])

choice_list = Config("choice", "sample_sentences.yaml").get()
info_err_list = Config("info_err", "sample_sentences.yaml").get()
info_succ_list = Config("info_succ", "sample_sentences.yaml").get()
drunk_over_list = Config("drunk_over", "sample_sentences.yaml").get()

messages = {"system": [], "user": []}
general_limit = 0.03
user_info = {}
user_drunk = []
user_remaining = 0


def _max_bac(user_info):

    if user_info["age"] < 18 or user_info["age"] >= 65:
        return 0

    alcohol_density = 0.789
    widmark_factor = {"Male": 0.9, "Female": 0.85}
    age_coef = 0.01 * user_info["age"] + 0.2
    return round(general_limit * widmark_factor[user_info["gender"]] * user_info["weight"] / age_coef / alcohol_density, 2)


def _validate_user_info(user_info):

    lack = []
    age_pattern = re.compile(r'^[1-9][0-9]?$|^1[01][0-9]$|^12[0-9]$')
    gender_pattern = re.compile(r'^Male$|^Female$')
    weight_pattern = re.compile(r'^[1-9][0-9]{0,2}$|^5[0-9][0-9]$|^600$')

    if 'age' not in user_info or not isinstance(user_info['age'], int) or not age_pattern.match(str(user_info['age'])):
        lack.append('age')
    if 'gender' not in user_info or not isinstance(user_info['gender'], str) or not gender_pattern.match(user_info['gender']):
        lack.append('gender')
    if 'weight' not in user_info or not isinstance(user_info['weight'], int) or not weight_pattern.match(str(user_info['weight'])):
        lack.append('weight')

    if lack:
        string = ", ".join("%s" % (i) for i in lack)
        return False, " and".join(string.rsplit(",", maxsplit=1)) if "," in string else string

    return True, None


@app.route("/api/v1/mixology", methods=["POST"])
def mixology():

    global messages, user_info, user_drunk, user_remaining

    try:
        req_body = req.get_json()
        log_input.info(req_body)

    except Exception as e:
        log_input.error(e)

    resp_classify = requests.post(req_classify_url, data=json.dumps({"text": req_body["text"]}), headers=headers).json()
    log_input.info(resp_classify)

    if resp_classify["type"] == "age_and_gender":
        whole_user_info, err_msg = _validate_user_info(user_info)

        if not whole_user_info:
            resp_info = requests.post(req_info_url, data=json.dumps({"text": req_body["text"]}), headers=headers).json()
            user_info = {"age": resp_info["result"]["age"], "gender": resp_info["result"]["gender"], "weight": resp_info["result"]["weight"]}
            _whole_user_info, _err_msg = _validate_user_info(user_info)

            if not _whole_user_info:
                return jsonify({"resp": random.choice(info_err_list).replace("target", err_msg)})

            user_remaining = _max_bac(user_info)

        return jsonify({"resp": random.choice(info_succ_list)})

    elif resp_classify["type"] == "ask_for_recommend":
        whole_user_info, err_msg = _validate_user_info(user_info)

        if not whole_user_info:
            return jsonify({"resp": random.choice(info_err_list).replace("target", err_msg)})

        if len(messages["system"]) == 0 and len(messages["user"]) == 0:
            resp = requests.post(req_rec_url, data=json.dumps({"remaining": user_remaining, "text": None}), headers=headers).json()
            messages["system"].append(resp["result"])
            return jsonify({"resp": resp["result"]})

        else:

            if len(messages["system"]) == len(messages["user"]):
                print("user_drunk: %s" % (user_drunk))

                if len(user_drunk) >= 3:
                    return jsonify({"resp": random.choice(drunk_over_list)})

                resp = requests.post(req_rec_url, data=json.dumps({"remaining": user_remaining, "text": user_drunk[-1]}), headers=headers).json()
                messages["system"].append(resp["result"])
                user_remaining = resp["remaining"]
                return jsonify({"resp": resp["result"]})

            else:
                messages["user"].append(req_body["text"])
                choice = requests.post(req_choose_url, data=json.dumps({"system": messages["system"][-1], "user": messages["user"][-1]}), headers=headers).json()["result"]
                print("user choice: %s" % (choice))
                user_drunk.append(choice)
                return jsonify({"resp": random.choice(choice_list).replace("target", choice)})

    elif resp_classify["type"] == "choose":
        messages["user"].append(req_body["text"])
        choice = requests.post(req_choose_url, data=json.dumps({"system": messages["system"][-1], "user": messages["user"][-1]}), headers=headers).json()["result"]
        print("user choice: %s" % (choice))
        user_drunk.append(choice)
        return jsonify({"resp": random.choice(choice_list).replace("target", choice)})

    else:
        resp = requests.post(req_chat_url, data=json.dumps({"text": req_body["text"]}), headers=headers).json()
        return jsonify({"resp": resp["result"]})


@app.after_request
def after_request(resp):

    log_ar.info("\t%s - - [%s] %s %d -" % (req.remote_addr, req.method, req.path, resp.status_code))
    return resp


if __name__ == "__main__":

    app.run(debug=False, port=main_port)
