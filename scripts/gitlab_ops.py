#!/usr/bin/env python3
"""
GitLab API helper for the config-change Jenkins pipeline.

Usage:
  python3 gitlab_ops.py create-mr \
      --gitlab-url https://gitlab.company.com \
      --token <PRIVATE-TOKEN> \
      --project devops/helmcharts/govapay \
      --source-branch SRM-1100 \
      --target-branch main \
      --title "[SRM-1100] Add env var NEW_FLAG to user/dev" \
      --description "..."

Prints the MR web URL to stdout on success.
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def create_mr(args):
    project_encoded = urllib.parse.quote(args.project, safe="")
    url = f"{args.gitlab_url}/api/v4/projects/{project_encoded}/merge_requests"

    payload = {
        "source_branch":        args.source_branch,
        "target_branch":        args.target_branch,
        "title":                args.title,
        "description":          args.description,
        "remove_source_branch": True,
        "squash":               False,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type":  "application/json",
            "PRIVATE-TOKEN": args.token,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            mr_url = result.get("web_url", "")
            print(mr_url)
            return mr_url
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        print(f"GitLab API error {exc.code}: {body}", file=sys.stderr)
        # 409 = MR already exists for this branch
        if exc.code == 409:
            detail = json.loads(body)
            existing = detail.get("message", [""])[0] if isinstance(detail.get("message"), list) else ""
            print(f"MR already exists: {existing}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="GitLab API operations")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-mr")
    p.add_argument("--gitlab-url",     required=True)
    p.add_argument("--token",          required=True)
    p.add_argument("--project",        required=True, help="GitLab project path, e.g. devops/helmcharts/govapay")
    p.add_argument("--source-branch",  required=True)
    p.add_argument("--target-branch",  required=True)
    p.add_argument("--title",          required=True)
    p.add_argument("--description",    default="")

    args = parser.parse_args()
    if args.command == "create-mr":
        create_mr(args)


if __name__ == "__main__":
    main()
  
