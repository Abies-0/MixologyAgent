import os
import warnings
from spacy_llm.util import assemble
from flask import Flask, request as req, jsonify
from logger import ConcurrentLogger
from get_config import Config

warnings.filterwarnings("ignore")

app = Flask(__name__)
nlp = assemble("classify_question.cfg")
base_path = "logs"
nlp_path = "%s/spacy" % (base_path)
ar_path = "%s/after_request" % (base_path)
os.makedirs(nlp_path, exist_ok=True)
os.makedirs(ar_path, exist_ok=True)
log_nlp = ConcurrentLogger(filename="%s/spacy_llm.log" % (nlp_path))
log_ar = ConcurrentLogger(filename="%s/after_request.log" % (ar_path))

port = Config("api", "api_config.yaml").get()["nlp"]["port"]


@app.route("/api/v1/classify_question", methods=["POST"])
def procrss_text():

    try:
        req_data = req.get_json()
        log_nlp.info(req_data)

    except Exception as e:
        log_nlp.error(e)

    doc = nlp(req_data["text"])
    ent = [(ent.text, ent.label_) for ent in doc.ents]
    labels = {}

    for i in ent:
        print(i)
        labels[i[1]] = labels.get(i[1], 0) + 1

    labels = {name: count * 1.5 if name in {"ask_for_recommend", "choose"} else count for name, count in labels.items()}
    predicted = max(labels, key=labels.get) if labels else "unknown"
    log_nlp.info(predicted)
    return jsonify({"type": predicted})


@app.after_request
def after_request(resp):

    log_ar.info("\t%s - - [%s] %s %d -" % (req.remote_addr, req.method, req.path, resp.status_code))
    return resp


if __name__ == "__main__":

    app.run(debug=False, port=port)
