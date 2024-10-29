from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from kubernetes.dynamic.resource import ResourceInstance
from ocp_resources.cluster_claim import ClusterClaim, NamespacedResource
from ocp_resources.cluster_pool import ClusterPool
from ocp_resources.cluster_deployment import ClusterDeployment
from ocp_resources.secret import Secret
from ocp_utilities.infra import base64
import os

import shortuuid

from claims_db import ClaimsDB
from app import app, ocp_client


HIVE_CLUSTER_NAMESPACE: str = os.environ["HIVE_CLAIM_FLASK_APP_NAMESPACE"]


def get_all_claims() -> List[Dict[str, str]]:
    def _claims(_claim: NamespacedResource) -> List[Dict[str, str]]:
        if not _claim.exists:
            return []

        _res = []

        _instance = _claim.instance
        _namespace = _instance.spec.namespace
        _name = _instance.metadata.name
        _created_at = datetime.strptime(_instance.metadata.creationTimestamp, "%Y-%m-%dT%H:%M:%SZ")
        _cluster_info = {
            "name": _name,
            "created_at": (
                f"{_created_at.strftime('%H')}:{_created_at.strftime('%M')} "
                f"{_created_at.strftime('%d')}-{_created_at.strftime('%m')}-{_created_at.year}"
            ),
            "namespace": _namespace or "Not Ready",
            "pool": _instance.spec.clusterPoolName,
            "info": [],
        }
        if _namespace:
            _info_dict = {"name": _name}
            with ThreadPoolExecutor() as _executor:
                _futures = []
                for _func in (
                    get_claimed_cluster_web_console,
                    get_claimed_cluster_kubeconfig,
                    get_claimed_cluster_creds,
                    get_claimed_cluster_login_command,
                ):
                    _futures.append(_executor.submit(_func, _name))

                for _future in as_completed(_futures):
                    _info_dict.update(_future.result())

        else:
            _info_dict = {
                "console": "Not Ready",
                "kubeconfig": "Not Ready",
                "creds": "Not Ready",
                "login_cmd": "Not Ready",
                "name": _name,
            }

        _cluster_info["info"].append(_info_dict)

        _res.append(_cluster_info)
        return _res

    with ThreadPoolExecutor() as executor:
        futures = []
        res = []
        for claim in ClusterClaim.get(dyn_client=ocp_client, namespace=HIVE_CLUSTER_NAMESPACE):
            futures.append(executor.submit(_claims, claim))

        for future in as_completed(futures):
            if future.result():
                res.extend(future.result())

        _exists_claim = [_cl["name"] for _cl in res]
        for _delete_in_progress in ClaimsDB().get_deleted_claims():
            if _delete_in_progress not in _exists_claim:
                app.logger.info(f"Removing claim from delete in progress list: {_delete_in_progress}")
                ClaimsDB().remove_claim_from_deleted_claims(_delete_in_progress)

        return res


def get_cluster_pools() -> List[Dict[str, str]]:
    res = []

    def _get_pool_info(pool: NamespacedResource) -> Dict[str, str]:
        _instance = pool.instance
        _name = _instance.metadata.name
        _size = _instance.spec.size
        _status = _instance.status
        _pool = {
            "name": _name,
            "size": _size,
            "claimed": get_num_cluster_pool_claims(pool_name=_name),
            "available": _status.size if _status else 0,
        }
        return _pool

    with ThreadPoolExecutor() as executor:
        futures = []
        for cp in ClusterPool.get(dyn_client=ocp_client, namespace=HIVE_CLUSTER_NAMESPACE):
            futures.append(executor.submit(_get_pool_info, cp))

        for future in as_completed(futures):
            res.append(future.result())

    return res


def claim_cluster(user: str, pool: str) -> Dict[str, str]:
    res: Dict[str, str] = {"error": "", "name": ""}
    _claim: Any = ClusterClaim(
        name=f"{user}-{shortuuid.uuid()[0:5].lower()}",
        namespace=HIVE_CLUSTER_NAMESPACE,
        cluster_pool_name=pool,
    )
    try:
        _claim.deploy()
    except Exception as exp:
        res["error"] = exp.summary()  # type: ignore[attr-defined]
    res["name"] = _claim.name
    return res


def claim_cluster_delete(claim_name: str) -> None:
    _claim = ClusterClaim(
        name=claim_name,
        namespace=HIVE_CLUSTER_NAMESPACE,
    )
    _claim.clean_up(wait=False)
    ClaimsDB().add_claim_to_deleted_claims(claim_name)


def get_all_user_claims_names(user: str) -> List[str]:
    _user_claims: List[str] = []
    _claim: Any
    for _claim in ClusterClaim.get(dyn_client=ocp_client, namespace=HIVE_CLUSTER_NAMESPACE):
        if (
            user in _claim.name or user == os.getenv("HIVE_CLAIM_MANAGER_SUPERUSER_NAME")
        ) and _claim.name not in ClaimsDB().get_deleted_claims():
            _user_claims.append(_claim.name)

    app.logger.info(f"User {user} claims: {_user_claims}")

    return _user_claims


def delete_all_claims(user: str) -> Dict[str, List[str]]:
    deleted_claims = []
    futures = []

    with ThreadPoolExecutor() as executor:
        for _claim in ClusterClaim.get(dyn_client=ocp_client, namespace=HIVE_CLUSTER_NAMESPACE):
            if user in _claim.name or user == os.getenv("HIVE_CLAIM_MANAGER_SUPERUSER_NAME"):
                futures.append(executor.submit(_claim.clean_up, False))
                deleted_claims.append(_claim.name)
                ClaimsDB().add_claim_to_deleted_claims(_claim.name)

    for _ in as_completed(futures):
        # clean_up does not return
        pass

    return {"deleted_claims": deleted_claims}


def get_claimed_cluster_deployment(claim_name: str) -> Optional[ClusterDeployment]:
    _claim: Any = ClusterClaim(client=ocp_client, name=claim_name, namespace=HIVE_CLUSTER_NAMESPACE)

    if not _claim.exists:
        return None

    _instance: ResourceInstance = _claim.instance
    if not _instance.spec.namespace:
        return None

    return ClusterDeployment(
        client=ocp_client,
        name=_instance.spec.namespace,
        namespace=_instance.spec.namespace,
    )


def get_claimed_cluster_web_console(claim_name: str) -> Dict[str, str]:
    _cluster_deployment = get_claimed_cluster_deployment(claim_name=claim_name)
    if not _cluster_deployment:
        return {"console": ""}

    _console_url = _cluster_deployment.instance.status.webConsoleURL
    return {"console": _console_url}


def get_claimed_cluster_login_command(claim_name: str) -> Dict[str, str]:
    _cluster_deployment = get_claimed_cluster_deployment(claim_name=claim_name)
    if not _cluster_deployment:
        return {"login-cmd": ""}

    login_creds = get_claimed_cluster_creds(claim_name=claim_name)
    if not login_creds["creds"]:
        return {"login-cmd": ""}

    username, password = login_creds["creds"].split("#")

    return {"login_cmd": f"oc login --server {_cluster_deployment.instance.status.apiURL} -u {username} -p {password}"}


def get_claimed_cluster_creds(claim_name: str) -> Dict[str, str]:
    _cluster_deployment = get_claimed_cluster_deployment(claim_name=claim_name)
    if not _cluster_deployment:
        return {"creds": ""}

    _secret = Secret(
        name=_cluster_deployment.instance.spec.clusterMetadata.adminPasswordSecretRef.name,
        namespace=_cluster_deployment.namespace,
        client=ocp_client,
    )
    return {
        "creds": f"{base64.b64decode(_secret.instance.data.username).decode()}#{base64.b64decode(_secret.instance.data.password).decode()}"
    }


def get_claimed_cluster_kubeconfig(claim_name: str) -> Dict[str, str]:
    _cluster_deployment = get_claimed_cluster_deployment(claim_name=claim_name)
    if not _cluster_deployment:
        return {"kubeconfig": ""}

    _secret = Secret(
        name=_cluster_deployment.instance.spec.clusterMetadata.adminKubeconfigSecretRef.name,
        namespace=_cluster_deployment.namespace,
        client=ocp_client,
    )
    _kubeconfig_file_name = f"kubeconfig-{claim_name}"
    with open(f"/tmp/{_kubeconfig_file_name}", "w") as fd:
        fd.write(base64.b64decode(_secret.instance.data.kubeconfig).decode())

    return {"kubeconfig": f"/kubeconfig/{_kubeconfig_file_name}"}


def get_num_cluster_pool_claims(pool_name: str) -> int:
    num_claims = 0

    for _claim in ClusterClaim.get(dyn_client=ocp_client, namespace=HIVE_CLUSTER_NAMESPACE):
        if _claim.instance.spec.clusterPoolName == pool_name:
            num_claims += 1

    return num_claims
