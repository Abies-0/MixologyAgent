import os
import re
import json
import random
import pickle
import warnings
from flask import Flask, request as req, jsonify
from logger import ConcurrentLogger
from get_config import Config
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from mixology_recommend_inference import make_recommendation

port = Config("api", "api_config.yaml").get()["agent"]["port"]
prompt_template = Config("agent", "langchain_template.yaml").get()
default_drink_list = Config("default_drink", "sample_sentences.yaml").get()
with open ("data/drink_intro.pkl", "rb") as f:
    drink_intro = pickle.load(f)
with open ("data/drink_alc_g.pkl", "rb") as f:
    drink_abv = pickle.load(f)

warnings.filterwarnings("ignore")

app = Flask(__name__)
base_path = "logs"
ag_path = "%s/agent" % (base_path)
ar_path = "%s/after_request" % (base_path)
os.makedirs(ag_path, exist_ok=True)
os.makedirs(ar_path, exist_ok=True)
log_chat = ConcurrentLogger(filename="%s/agent_chat.log" % (ag_path))
log_info = ConcurrentLogger(filename="%s/agent_info.log" % (ag_path))
log_rec = ConcurrentLogger(filename="%s/agent_recommend.log" % (ag_path))
log_iden = ConcurrentLogger(filename="%s/agent_identify.log" % (ag_path))
log_ar = ConcurrentLogger(filename="%s/after_request.log" % (ar_path))

llm = ChatOpenAI(model=prompt_template["model"])

prompt_info = PromptTemplate(input_variables=["user_info"], template=prompt_template["p_info"])
prompt_chat = PromptTemplate(input_variables=["user_input"], template=prompt_template["p_chat"])
prompt_rec = PromptTemplate(input_variables=["recommend_list"], template=prompt_template["p_rec"])
prompt_iden = PromptTemplate(input_variables=["system_msg", "user_msg"], template=prompt_template["p_iden"])

chain_info = LLMChain(llm=llm, prompt=prompt_info)
chain_chat = LLMChain(llm=llm, prompt=prompt_chat)
chain_rec = LLMChain(llm=llm, prompt=prompt_rec)
chain_iden = LLMChain(llm=llm, prompt=prompt_iden)

def _recommend_drink(user_remaining, target=None):

    recommend_list = []

    if not target:
        random.shuffle(default_drink_list)

        for drink in default_drink_list:
            if drink_abv[drink] <= user_remaining:
                if len(recommend_list) >= 3:
                    break
                recommend_list.append(drink)

        for drink, alcohol in drink_abv.items():
            if alcohol <= user_remaining:
                if len(recommend_list) >= 3:
                    break
                recommend_list.append(drink)

    else:
        raw = make_recommendation(target)

        for drink in raw:
            if drink_abv[drink] <= user_remaining:
                if len(recommend_list) >= 3:
                    break
                recommend_list.append(drink)

    for item in range(len(recommend_list)):
        recommend_list[item] = "%s (%s)" % (recommend_list[item], drink_intro[recommend_list[item]])

    return recommend_list


@app.route("/api/v1/agent_chat", methods=["POST"])
def chat_with_user():

    try:
        req_body = req.get_json()
        log_chat.info(req_body)

    except Exception as e:
        log_chat.error(e)

    resp = chain_chat.run(req_body["text"])
    log_chat.info(resp)
    return jsonify({"result": resp})


@app.route("/api/v1/agent_info", methods=["POST"])
def get_user_info():

    try:
        req_body = req.get_json()
        log_info.info(req_body)

    except Exception as e:
        log_info.error(e)

    resp = chain_info.run(req_body["text"])
    log_info.info(resp)
    user_info = json.loads("{%s}" % (re.findall(r'\{(.*?)\}', resp.replace("'", '"'), re.DOTALL)[0]))
    return jsonify({"result": user_info})


@app.route("/api/v1/agent_recommend", methods=["POST"])
def recommend_cocktail():

    try:
        req_body = req.get_json()
        log_rec.info(req_body)

    except Exception as e:
        log_rec.error(e)

    remaining = req_body["remaining"] - drink_abv[req_body["text"]] if req_body["text"] != None else req_body["remaining"]
    candidate_list = _recommend_drink(remaining, req_body["text"])
    resp = chain_rec.run(str(candidate_list))
    log_rec.info(resp)
    return jsonify({"remaining": remaining, "result": resp})


@app.route("/api/v1/agent_identify", methods=["POST"])
def identify_cocktail():

    try:
        req_body = req.get_json()
        log_iden.info(req_body)

    except Exception as e:
        log_iden.error(e)

    resp = chain_iden.run(system_msg=req_body["system"], user_msg=req_body["user"])
    log_iden.info(resp)
    return jsonify({"result": resp})


@app.after_request
def after_request(resp):

    log_ar.info("\t%s - - [%s] %s %d -" % (req.remote_addr, req.method, req.path, resp.status_code))
    return resp


if __name__ == "__main__":

    app.run(debug=False, port=port)
