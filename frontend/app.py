"""
Flask frontend for ComplianceEngine smart contract.
Connects to Algorand via algokit_utils typed client.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
from flask import Flask, render_template, request, jsonify, redirect, url_for

import algokit_utils
from smart_contracts.artifacts.compliance_engine.compliance_engine_client import (
    ComplianceEngineClient,
)

app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# ── Algorand connection ────────────────────────────────────────────────────────
def get_client() -> ComplianceEngineClient:
    algorand = algokit_utils.AlgorandClient.from_environment()
    app_id = int(os.environ.get("APP_ID", "0"))
    sender = os.environ.get("SENDER_ADDRESS", "")
    return ComplianceEngineClient(
        algorand=algorand,
        app_id=app_id,
        default_sender=sender,
    )


STATUS_LABELS = {0: "CREATED", 1: "APPROVED", 2: "CERTIFIED", 99: "NOT FOUND"}
ROLE_LABELS   = {0: "ADMIN",   1: "VENDOR",   2: "INSPECTOR", 99: "NONE"}


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Dashboard: show app ID and quick status."""
    app_id = int(os.environ.get("APP_ID", "0"))
    return render_template("index.html", app_id=app_id)


@app.route("/create", methods=["GET", "POST"])
def create():
    result = None
    error = None
    if request.method == "POST":
        batch_id = request.form.get("batch_id", "").strip()
        if not batch_id:
            error = "Batch ID is required"
        else:
            try:
                client = get_client()
                response = client.send.create_batch_v2(
                    args=(batch_id.encode(),)
                )
                result = {
                    "batch_id": batch_id,
                    "status": "CREATED",
                    "tx_id": response.tx_id,
                }
            except Exception as e:
                error = str(e)
    return render_template("create.html", result=result, error=error)


@app.route("/approve", methods=["GET", "POST"])
def approve():
    result = None
    error = None
    if request.method == "POST":
        batch_id = request.form.get("batch_id", "").strip()
        if not batch_id:
            error = "Batch ID is required"
        else:
            try:
                client = get_client()
                response = client.send.approve_batch_v2(
                    args=(batch_id.encode(),)
                )
                result = {
                    "batch_id": batch_id,
                    "status": "APPROVED",
                    "tx_id": response.tx_id,
                }
            except Exception as e:
                error = str(e)
    return render_template("approve.html", result=result, error=error)


@app.route("/certify", methods=["GET", "POST"])
def certify():
    result = None
    error = None
    if request.method == "POST":
        batch_id = request.form.get("batch_id", "").strip()
        if not batch_id:
            error = "Batch ID is required"
        else:
            try:
                client = get_client()
                response = client.send.certify_batch(
                    args=(batch_id.encode(),)
                )
                # Fetch minted ASA ID
                asa_response = client.send.get_batch_asset(
                    args=(batch_id.encode(),)
                )
                result = {
                    "batch_id": batch_id,
                    "status": "CERTIFIED",
                    "asa_id": asa_response.abi_return,
                    "tx_id": response.tx_id,
                }
            except Exception as e:
                error = str(e)
    return render_template("certify.html", result=result, error=error)


@app.route("/vendor/<address>")
def vendor(address: str):
    batches = []
    error = None
    role = "UNKNOWN"
    try:
        client = get_client()
        # Get vendor batches
        batches_response = client.send.get_vendor_batches(
            args=(address,)
        )
        raw = batches_response.abi_return or ""
        batches = [b for b in raw.split("|") if b]

        # Get role
        role_response = client.send.get_role(args=(address,))
        role = ROLE_LABELS.get(role_response.abi_return, "UNKNOWN")
    except Exception as e:
        error = str(e)
    return render_template(
        "vendor.html",
        address=address,
        batches=batches,
        role=role,
        error=error,
    )


@app.route("/api/batch/<batch_id>")
def api_batch_status(batch_id: str):
    """JSON API endpoint for batch status + ASA."""
    try:
        client = get_client()
        status_resp = client.send.get_batch_status_v2(args=(batch_id.encode(),))
        asset_resp  = client.send.get_batch_asset(args=(batch_id.encode(),))
        status_code = status_resp.abi_return
        return jsonify({
            "batch_id": batch_id,
            "status_code": status_code,
            "status_label": STATUS_LABELS.get(status_code, "UNKNOWN"),
            "asa_id": asset_resp.abi_return,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")