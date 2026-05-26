from __future__ import annotations

import os

from flask import Flask, jsonify, redirect, render_template, request, url_for

from bond_agent import BondAnalystAgent


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")


@app.route("/")
def index():
    return redirect(url_for("agent_page"))


@app.route("/agent", methods=["GET", "POST"])
def agent_page():
    result = None
    question = ""
    data_mode = request.values.get("data_mode", os.environ.get("BOND_DATA_MODE", "auto"))
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        result = BondAnalystAgent(data_mode=data_mode).answer(question)
    return render_template("agent.html", result=result, question=question, data_mode=data_mode)


@app.route("/api/agent/query", methods=["POST"])
def agent_query():
    payload = request.get_json(silent=True) or {}
    question = payload.get("question") or request.form.get("question", "")
    data_mode = payload.get("data_mode") or request.form.get("data_mode") or os.environ.get("BOND_DATA_MODE", "auto")
    result = BondAnalystAgent(data_mode=data_mode).answer(question)
    return jsonify(result)


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_RUN_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_ENV") == "development",
    )
