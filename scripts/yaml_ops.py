#!/usr/bin/env python3
"""
YAML operations for the config-change Jenkins pipeline.

Handles:
  check-vault-path  — exit 0 if path is provisioned, 1 if not
  add-vault-path    — append secret path to resource-provisioner vault.yaml
  add-env-var       — append a plain key/value under generic-application.env
  add-secret-ref    — append a Vault secret reference under the vault.vaultSecrets block
"""

import argparse
import sys
from pathlib import Path

try:
    from ruamel.yaml import YAML
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "ruamel.yaml"],
                          stdout=subprocess.DEVNULL)
    from ruamel.yaml import YAML

yaml = YAML()
yaml.preserve_quotes = True
yaml.width = 4096  # prevent line-wrapping


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------

# Sub-environments that share a resource-provisioner config directory
_ENV_TO_CONFIG_SUFFIX = {
    "dev":       "dev",
    "dev01":     "dev",
    "pre-dev01": "dev",
    "qa":        "qa",
    "qa1":       "qa",
    "stage":     "stage",
    "prod":      "prod",
}


def _app_prefix(app):
    return "gova-pay" if app == "govapay" else "gpay-b2b"


def _vault_config_path(repo_dir, app, env):
    """
    Path to resource-provisioner configurations/<app-prefix>-<env-group>/vault.yaml.
    dev01 and pre-dev01 share the -dev directory (they use separate service keys inside).
    """
    suffix = _ENV_TO_CONFIG_SUFFIX.get(env, env)
    config_dir = f"{_app_prefix(app)}-{suffix}"
    return Path(repo_dir) / "configurations" / config_dir / "vault.yaml"


def _vault_service_key(service, env):
    """
    Key inside vault.yaml under vault:
      dev      -> "transaction"
      dev01    -> "transaction-dev01"
      pre-dev01-> "transaction-pre-dev01"
    """
    return service if env == "dev" else f"{service}-{env}"


def _helm_values_path(repo_dir, app, service, env):
    """
    Path to the helm values file inside a checked-out helm-charts/<app> repo.
    Repo root is expected to contain service subdirectories directly.
    """
    if app == "govapay":
        filename = f"values-gova-pay-{env}-ire.yaml"
    else:
        filename = f"values-gpay-b2b-{env}-ire.yaml"
    return Path(repo_dir) / service / filename


def _load(path):
    with open(path, "r") as fh:
        return yaml.load(fh)


def _save(path, data):
    with open(path, "w") as fh:
        yaml.dump(data, fh)


# ---------------------------------------------------------------------------
# vault section locator for helm values
# govapay: generic-application.vault
# b2b:     generic-application.ingress.vault  (vault is nested inside ingress)
# ---------------------------------------------------------------------------

def _find_vault_block(app_data):
    """
    Return (vault_dict, parent_dict) so callers can both read and write.
    Checks top-level first, then inside ingress (b2b layout).
    Returns (None, app_data) if no vault section exists yet.
    """
    if "vault" in app_data:
        return app_data["vault"], app_data

    ingress = app_data.get("ingress")
    if isinstance(ingress, dict) and "vault" in ingress:
        return ingress["vault"], ingress

    return None, app_data


def _ensure_vault_block(app_data, app):
    """
    Create a minimal vault block if absent.
    govapay -> attaches to app_data root.
    b2b     -> attaches inside ingress (matching existing layout).
    """
    if app == "govapay":
        if "vault" not in app_data:
            app_data["vault"] = {"role": "", "vaultSecrets": []}
        return app_data["vault"], app_data
    else:
        ingress = app_data.setdefault("ingress", {})
        if "vault" not in ingress:
            ingress["vault"] = {"role": "", "vaultSecrets": []}
        return ingress["vault"], ingress


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_check_vault_path(args):
    """Exit 0 if the secret path is already provisioned, 1 if it must be created."""
    vpath = _vault_config_path(args.repo_dir, args.app, args.env)
    if not vpath.exists():
        print(f"ERROR: vault config not found: {vpath}", file=sys.stderr)
        sys.exit(2)

    data = _load(vpath)
    svc_key = _vault_service_key(args.service, args.env)
    secret_path = args.secret_path.strip("/")

    existing_paths = data.get("vault", {}).get(svc_key, {}).get("secret-path", [])
    for p in existing_paths:
        p = p.strip("/")
        # match: exact, env-prefixed, or trailing suffix
        if p == secret_path or p == f"{args.env}/{secret_path}" or p.endswith(f"/{secret_path}"):
            print(f"Found: {p} in vault.{svc_key}.secret-path")
            sys.exit(0)

    print(f"Not found: '{secret_path}' not in vault.{svc_key}.secret-path ({vpath})")
    sys.exit(1)


def cmd_add_vault_path(args):
    """Add <env>/<secret-path> to resource-provisioner vault.yaml for the given service."""
    vpath = _vault_config_path(args.repo_dir, args.app, args.env)
    if not vpath.exists():
        print(f"ERROR: vault config not found: {vpath}", file=sys.stderr)
        sys.exit(2)

    data = _load(vpath)
    svc_key = _vault_service_key(args.service, args.env)
    new_entry = f"{args.env}/{args.secret_path.strip('/')}"

    if "vault" not in data:
        data["vault"] = {}

    if svc_key not in data["vault"]:
        # Build a new service block modelled on the first existing entry
        template = next(iter(data["vault"].values()), {})
        data["vault"][svc_key] = {
            "role_name":                svc_key,
            "service_account_name":     svc_key,
            "service_account_namespace": template.get("service_account_namespace",
                                                        _app_prefix(args.app)),
            "prefix":                   template.get("prefix", _app_prefix(args.app)),
            "secret-path":              [new_entry],
        }
        print(f"Created vault.{svc_key} and added path: {new_entry}")
    else:
        paths = data["vault"][svc_key].setdefault("secret-path", [])
        if new_entry in paths:
            print(f"Path '{new_entry}' already exists under vault.{svc_key} — nothing to do.")
        else:
            paths.append(new_entry)
            print(f"Added '{new_entry}' to vault.{svc_key}.secret-path")

    _save(vpath, data)
    print(f"Updated: {vpath}")


def cmd_add_env_var(args):
    """Append a plain key/value to generic-application.env."""
    hpath = _helm_values_path(args.repo_dir, args.app, args.service, args.env)
    if not hpath.exists():
        print(f"ERROR: helm values file not found: {hpath}", file=sys.stderr)
        sys.exit(2)

    data = _load(hpath)
    app_data = data.get("generic-application", data)

    if "env" not in app_data:
        app_data["env"] = {}

    if args.var_name in app_data["env"]:
        print(f"WARNING: '{args.var_name}' already exists in env block — overwriting.")

    app_data["env"][args.var_name] = args.var_value
    print(f"Set env.{args.var_name} = {args.var_value}")

    _save(hpath, data)
    print(f"Updated: {hpath}")


def cmd_add_secret_ref(args):
    """
    Append a Vault secret reference under vault.vaultSecrets.
    If the secretPath entry already exists, appends the new secret to its secrets list.
    If the secretPath is new, adds a fresh vaultSecrets entry.
    """
    hpath = _helm_values_path(args.repo_dir, args.app, args.service, args.env)
    if not hpath.exists():
        print(f"ERROR: helm values file not found: {hpath}", file=sys.stderr)
        sys.exit(2)

    data = _load(hpath)
    app_data = data.get("generic-application", data)

    vault_block, _ = _find_vault_block(app_data)
    if vault_block is None:
        vault_block, _ = _ensure_vault_block(app_data, args.app)

    vault_secrets = vault_block.setdefault("vaultSecrets", [])

    new_secret = {
        "envVariable": args.var_name,
        "vaultSecret": args.vault_secret_key,
    }

    # Find existing secretPath entry
    for entry in vault_secrets:
        if entry.get("secretPath") == args.secret_path:
            for s in entry.get("secrets", []):
                if s.get("envVariable") == args.var_name:
                    print(f"ERROR: envVariable '{args.var_name}' already exists "
                          f"under secretPath '{args.secret_path}'", file=sys.stderr)
                    sys.exit(1)
            entry.setdefault("secrets", []).append(new_secret)
            print(f"Added '{args.var_name}' to existing secretPath '{args.secret_path}'")
            _save(hpath, data)
            print(f"Updated: {hpath}")
            return

    # secretPath not found — add a new entry
    vault_secrets.append({
        "secretPath": args.secret_path,
        "secrets": [new_secret],
    })
    print(f"Added new secretPath '{args.secret_path}' with secret '{args.var_name}'")

    _save(hpath, data)
    print(f"Updated: {hpath}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="YAML config operations for config-change pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--repo-dir",  required=True, help="Root of the checked-out repo")
        p.add_argument("--app",       required=True, choices=["govapay", "gpay-b2b"])
        p.add_argument("--env",       required=True)
        p.add_argument("--service",   required=True)

    p = sub.add_parser("check-vault-path")
    common(p)
    p.add_argument("--secret-path", required=True)

    p = sub.add_parser("add-vault-path")
    common(p)
    p.add_argument("--secret-path", required=True)

    p = sub.add_parser("add-env-var")
    common(p)
    p.add_argument("--var-name",  required=True)
    p.add_argument("--var-value", required=True)

    p = sub.add_parser("add-secret-ref")
    common(p)
    p.add_argument("--var-name",         required=True, help="envVariable name the app will see")
    p.add_argument("--vault-secret-key", required=True, help="Key name inside the Vault secret")
    p.add_argument("--secret-path",      required=True, help="Vault secret path (e.g. api-keys/focal)")

    args = parser.parse_args()
    dispatch = {
        "check-vault-path": cmd_check_vault_path,
        "add-vault-path":   cmd_add_vault_path,
        "add-env-var":      cmd_add_env_var,
        "add-secret-ref":   cmd_add_secret_ref,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
