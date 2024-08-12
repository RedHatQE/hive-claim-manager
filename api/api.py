import os
from typing import Tuple
from flask import Response, request, send_file
from flask import jsonify, session

from users_db import UsersDB
from claims_db import ClaimsDB
from app import app
from utils import (
    claim_cluster,
    claim_cluster_delete,
    delete_all_claims,
    get_all_claims,
    get_all_user_claims_names,
    get_cluster_pools,
)
from app import bcrypt


@app.route("/api/healthcheck")
def healthcheck() -> Tuple[Response, int]:
    return jsonify({"status": "ok"}), 200


@app.route("/api/@me")
def get_current_user() -> Tuple[Response, int]:
    _error = {"error": "Unauthorized", "id": "", "admin": False, "name": ""}
    user_id = session.get("user_id")

    if not user_id:
        app.logger.info("no USER ID")
        return jsonify(_error), 401

    user = UsersDB().get_user_by_id(user_id=user_id)

    if not user:
        app.logger.error("No USER")
        return jsonify(_error), 401

    return jsonify({"id": user.id, "name": user.name, "admin": user.admin, "error": ""}), 200


@app.route("/api/login", methods=["POST"])
def login_user() -> Tuple[Response, int]:
    name = request.json["name"]
    password = request.json["password"]

    user = UsersDB().get_user_by_name(name=name)

    if user is None:
        return jsonify({"error": "Unauthorized"}), 401

    if not bcrypt.check_password_hash(user.password, password):
        app.logger.error(f"User `{name}` with password `{password}` failed to log in.")
        return jsonify({"error": "Unauthorized"}), 401

    session["user_id"] = user.id

    return jsonify({"id": user.id, "name": user.name}), 200


@app.route("/api/logout", methods=["POST"])
def logout_user() -> Tuple[Response, int]:
    session.pop("user_id")
    return jsonify({"status": "ok"}), 200


@app.route("/api/cluster-pools", methods=["GET"])
def cluster_pools_endpoint() -> Tuple[Response, int]:
    return jsonify(get_cluster_pools()), 200


@app.route("/api/cluster-claims", methods=["GET"])
def cluster_claims_endpoint() -> Tuple[Response, int]:
    return jsonify(get_all_claims()), 200


@app.route("/api/claim-cluster", methods=["POST"])
def claim_cluster_endpoint() -> Tuple[Response, int]:
    _user: str = request.args.get("user", "")
    _pool_name: str = request.args.get("name", "")
    if not _user or not _pool_name:
        return jsonify({"error": "User or Pool name missing", "name": ""}), 401

    return jsonify(claim_cluster(user=_user, pool=_pool_name)), 200


@app.route("/api/delete-claim", methods=["POST"])
def delete_claim_endpoint() -> Tuple[Response, int]:
    _claim_name: str = request.args.get("name", "")
    _user: str = request.args.get("user", "")
    if _user in _claim_name or _user == os.getenv("HIVE_CLAIM_MANAGER_SUPERUSER_NAME"):
        claim_cluster_delete(claim_name=_claim_name.strip())
        return jsonify({"deleted": _claim_name}), 200

    return jsonify({"error": "User is not allowed to delete this claim", "name": ""}), 401


@app.route("/api/all-user-claims-names", methods=["GET"])
def all_user_claims_names_endpoint() -> Tuple[Response, int]:
    _user: str = request.args.get("user", "")
    return jsonify(get_all_user_claims_names(user=_user)), 200


@app.route("/api/delete-all-claims", methods=["POST"])
def delete_all_claims_endpoint() -> Tuple[Response, int]:
    _user: str = request.args.get("user", "")
    return jsonify(delete_all_claims(user=_user)), 200


@app.route("/api/kubeconfig/<filename>", methods=["GET"])
def download_kubeconfig_endpoint(filename: str) -> Tuple[Response, int]:
    return send_file(f"/tmp/{filename}", download_name=filename, as_attachment=True), 200


@app.route("/api/claims-delete-in-progress-endpoint", methods=["GET"])
def claims_delete_in_progress_endpoint() -> Tuple[Response, int]:
    _cliams_delete_in_progress_from_file = ClaimsDB().get_deleted_claims()
    return jsonify(_cliams_delete_in_progress_from_file), 200


def main() -> None:
    app.logger.info(f"Starting {app.name} app")
    app.run(
        port=5000,
        host="0.0.0.0",
        use_reloader=bool(os.getenv("HIVE_CLAIM_FLASK_APP_RELOAD", False)),
        debug=bool(os.getenv("HIVE_CLAIM_FLASK_APP_DEBUG", False)),
    )


if __name__ == "__main__":
    main()
