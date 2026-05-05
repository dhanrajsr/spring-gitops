#!/usr/bin/env python3
"""
MS Teams incoming webhook notification for the config-change Jenkins pipeline.

Usage:
  python3 teams_notify.py \
      --webhook  https://company.webhook.office.com/... \
      --srm      SRM-1100 \
      --app      govapay \
      --env      dev \
      --service  user \
      --type     helm-update \
      --mr-url   https://gitlab.company.com/... \
      --message  "Env var NEW_FLAG added. MR raised for review."
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

_THEME_COLORS = {
    "vault-provision":    "FF8C00",  # orange  — action needed
    "helm-update":        "28A745",  # green   — MR raised
    "terraform-complete": "17A2B8",  # teal    — infra change done
    "failure":            "DC3545",  # red     — pipeline failed
    "info":               "6C757D",  # grey    — informational
}

_TITLES = {
    "vault-provision":    "Vault Provision MR Raised",
    "helm-update":        "Helm Chart MR Raised",
    "terraform-complete": "Terraform Apply Complete",
    "failure":            "Pipeline Failed",
    "info":               "Pipeline Update",
}


def send(args):
    color = _THEME_COLORS.get(args.type, "6C757D")
    title = f"[{args.srm}] {_TITLES.get(args.type, 'Update')}"

    facts = [
        {"name": "Application", "value": args.app},
        {"name": "Environment", "value": args.env},
        {"name": "Service",     "value": args.service},
    ]

    actions = []
    if args.mr_url:
        facts.append({"name": "Merge Request", "value": args.mr_url})
        actions.append({
            "@type": "OpenUri",
            "name":  "Open MR",
            "targets": [{"os": "default", "uri": args.mr_url}],
        })

    # MS Teams legacy connector card (MessageCard) — works without Graph API consent
    card = {
        "@type":      "MessageCard",
        "@context":   "http://schema.org/extensions",
        "themeColor": color,
        "summary":    title,
        "sections": [
            {
                "activityTitle":    f"**{title}**",
                "activitySubtitle": args.message,
                "facts":            facts,
                "markdown":         True,
            }
        ],
        "potentialAction": actions,
    }

    data = json.dumps(card).encode()
    req = urllib.request.Request(
        args.webhook,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"Teams notification sent (HTTP {resp.status})")
    except urllib.error.HTTPError as exc:
        print(f"Teams webhook error {exc.code}: {exc.read().decode()}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Send MS Teams notification")
    parser.add_argument("--webhook",  required=True)
    parser.add_argument("--srm",      required=True)
    parser.add_argument("--app",      required=True)
    parser.add_argument("--env",      required=True)
    parser.add_argument("--service",  required=True)
    parser.add_argument("--type",     required=True, choices=list(_THEME_COLORS))
    parser.add_argument("--message",  required=True)
    parser.add_argument("--mr-url",   default="")
    args = parser.parse_args()
    send(args)


if __name__ == "__main__":
    main()
