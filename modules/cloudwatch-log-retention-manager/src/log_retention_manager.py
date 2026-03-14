import json
import os

import boto3


def _load_log_group_prefixes():
    raw_prefixes = os.environ.get("LOG_GROUP_PREFIXES", "[]")
    prefixes = json.loads(raw_prefixes)

    if not isinstance(prefixes, list) or not all(isinstance(prefix, str) for prefix in prefixes):
        raise ValueError("LOG_GROUP_PREFIXES must be a JSON-encoded list of strings")

    return [prefix for prefix in prefixes if prefix]


def _should_scan_all_regions():
    return os.environ.get("SCAN_ALL_REGIONS", "false").lower() == "true"


def _get_regions(session, default_region, scan_all_regions):
    if not scan_all_regions:
        return [default_region]

    client = session.client("ec2", region_name=default_region)
    return [region["RegionName"] for region in client.describe_regions()["Regions"]]


def lambda_handler(event, context):
    default_region = os.environ.get("AWS_REGION", "us-east-1")
    retain_days = int(os.environ.get("RETENTION_IN_DAYS", "90"))
    log_group_prefixes = _load_log_group_prefixes()
    scan_all_regions = _should_scan_all_regions()

    session = boto3.Session()

    for region in _get_regions(session, default_region, scan_all_regions):
        print("Scanning region:", region)
        logs = session.client("logs", region_name=region)
        paginator = logs.get_paginator("describe_log_groups")

        for page in paginator.paginate():
            for log_group in page["logGroups"]:
                log_group_name = log_group["logGroupName"]

                if not any(log_group_name.startswith(prefix) for prefix in log_group_prefixes):
                    continue

                current_retention = log_group.get("retentionInDays")

                if current_retention == retain_days:
                    print(region, log_group_name, current_retention, "days")
                    continue

                print(region, log_group_name, current_retention, "->", retain_days, "days **PUT**")
                logs.put_retention_policy(
                    logGroupName=log_group_name,
                    retentionInDays=retain_days,
                )

    return "CloudWatchLogRetention.Success"


if __name__ == '__main__':
    lambda_handler({}, {})
