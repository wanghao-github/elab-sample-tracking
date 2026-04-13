#!/usr/bin/env python3

import argparse
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import elabapi_python
from elabapi_python.rest import ApiException


def build_api_client(host: str, api_key: str, verify_ssl: bool = False) -> elabapi_python.ApiClient:
    configuration = elabapi_python.Configuration()
    configuration.api_key["api_key"] = api_key
    configuration.api_key_prefix["api_key"] = "Authorization"
    configuration.host = host
    configuration.debug = False
    configuration.verify_ssl = verify_ssl

    api_client = elabapi_python.ApiClient(configuration)
    api_client.set_default_header(header_name="Authorization", header_value=api_key)
    return api_client


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def model_to_dict(obj: Any) -> Dict[str, Any]:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return {}


def split_tags(tags: Optional[str]) -> List[str]:
    if not tags:
        return []
    return [tag.strip() for tag in tags.split("|") if tag.strip()]


def clean_experiment_dict(experiment_dict: Dict[str, Any]) -> Dict[str, Any]:
    fields_to_remove = {
        "id",
        "created_at",
        "updated_at",
        "description",
    }
    return {k: v for k, v in experiment_dict.items() if k not in fields_to_remove}


def clean_item_patch_data(item: Any) -> Dict[str, Any]:
    return {
        "title": getattr(item, "title", ""),
        "body": getattr(item, "body", ""),
        "rating": getattr(item, "rating", 0),
    }


def create_item(
    items_api: elabapi_python.ItemsApi,
    category_id: int,
    tags: List[str],
) -> int:
    response = items_api.post_item_with_http_info(
        body={
            "category_id": category_id,
            "tags": tags,
        }
    )
    location = response[2].get("Location")
    if not location:
        raise RuntimeError("Could not determine created item ID from response headers.")
    return int(location.split("/").pop())


def create_experiment(
    experiments_api: elabapi_python.ExperimentsApi,
    title: str,
) -> int:
    response = experiments_api.post_experiment_with_http_info(body={"title": title})
    location = response[2].get("Location")
    if not location:
        raise RuntimeError("Could not determine created experiment ID from response headers.")
    return int(location.split("/").pop())


def patch_experiment_fields(
    experiments_api: elabapi_python.ExperimentsApi,
    experiment_id: int,
    experiment_dict: Dict[str, Any],
) -> List[Tuple[str, Any]]:
    problematic_fields: List[Tuple[str, Any]] = []

    for key, value in experiment_dict.items():
        try:
            experiments_api.patch_experiment(experiment_id, body={key: value})
        except ApiException:
            problematic_fields.append((key, value))

    return problematic_fields


def sync_experiments(
    experiments_read_api: elabapi_python.ExperimentsApi,
    experiments_write_api: elabapi_python.ExperimentsApi,
    limit: int,
) -> None:
    experiments_list = experiments_read_api.read_experiments(limit=limit)

    print(f"[INFO] Found {len(experiments_list)} experiments to process.")

    for experiment in experiments_list:
        print("__________________________________")

        experiment_dict = clean_experiment_dict(model_to_dict(experiment))
        title = getattr(experiment, "title", "Untitled Experiment")

        try:
            new_experiment_id = create_experiment(experiments_write_api, title)
            problematic_fields = patch_experiment_fields(
                experiments_write_api,
                new_experiment_id,
                experiment_dict,
            )

            if problematic_fields:
                print(
                    f"[WARN] Experiment {new_experiment_id} had problematic fields: "
                    f"{[key for key, _ in problematic_fields]}"
                )

            print(f"[OK] Experiment created and updated with ID: {new_experiment_id}")

        except ApiException as e:
            print(f"[ERROR] Failed to sync experiment '{title}': {e}")


def sync_items(
    items_read_api: elabapi_python.ItemsApi,
    items_write_api: elabapi_python.ItemsApi,
    links_api_read: elabapi_python.LinksToItemsApi,
    steps_api_read: elabapi_python.StepsApi,
    limit: int,
    only_fullname: Optional[str],
    default_category_id: int,
) -> None:
    items_list = items_read_api.read_items(limit=limit)

    print(f"[INFO] Found {len(items_list)} items to process.")

    for item in items_list:
        item_id_src = getattr(item, "id", None)
        custom_id = getattr(item, "custom_id", None)
        fullname = getattr(item, "fullname", None)

        print("----------------------")
        print(item_id_src)
        print(custom_id)
        print("----------------------")

        if only_fullname and fullname != only_fullname:
            continue

        new_item_data = clean_item_patch_data(item)
        separated_tags = split_tags(getattr(item, "tags", None))

        try:
            new_item_id = create_item(
                items_write_api,
                category_id=default_category_id,
                tags=separated_tags,
            )

            items_write_api.patch_item_with_http_info(new_item_id, body=new_item_data)
            print(f"[OK] Item created and updated with ID: {new_item_id}")

            try:
                source_links = links_api_read.read_entity_items_links("items", item_id_src)
                print("[INFO] Source links:", source_links)
            except ApiException as e:
                print(f"[WARN] Could not read links for source item {item_id_src}: {e}")

            try:
                source_steps = steps_api_read.read_steps_with_http_info("items", item_id_src)
                print("[INFO] Source steps:", source_steps)
            except ApiException as e:
                print(f"[WARN] Could not read steps for source item {item_id_src}: {e}")

        except ApiException as e:
            title = getattr(item, "title", "Untitled Item")
            print(f"[ERROR] Failed to sync item '{title}': {e}")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync items and experiments between two eLabFTW instances.")
    parser.add_argument(
        "--sync",
        choices=["items", "experiments", "all"],
        default="all",
        help="What to sync.",
    )
    parser.add_argument(
        "--item-limit",
        type=int,
        default=100,
        help="Maximum number of items to read from the source server.",
    )
    parser.add_argument(
        "--experiment-limit",
        type=int,
        default=10,
        help="Maximum number of experiments to read from the source server.",
    )
    parser.add_argument(
        "--only-fullname",
        default=None,
        help="Only sync items created by this full name.",
    )
    parser.add_argument(
        "--category-id",
        type=int,
        default=1,
        help="Default category_id used when creating new items on the target server.",
    )
    parser.add_argument(
        "--verify-ssl",
        action="store_true",
        help="Enable SSL certificate verification.",
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    source_host = get_required_env("ELAB_SOURCE_HOST")
    source_api_key = get_required_env("ELAB_SOURCE_API_KEY")
    target_host = get_required_env("ELAB_TARGET_HOST")
    target_api_key = get_required_env("ELAB_TARGET_API_KEY")

    api_client_read = build_api_client(
        host=source_host,
        api_key=source_api_key,
        verify_ssl=args.verify_ssl,
    )
    api_client_write = build_api_client(
        host=target_host,
        api_key=target_api_key,
        verify_ssl=args.verify_ssl,
    )

    items_read_api = elabapi_python.ItemsApi(api_client_read)
    items_write_api = elabapi_python.ItemsApi(api_client_write)

    links_api_read = elabapi_python.LinksToItemsApi(api_client_read)
    steps_api_read = elabapi_python.StepsApi(api_client_read)

    experiments_read_api = elabapi_python.ExperimentsApi(api_client_read)
    experiments_write_api = elabapi_python.ExperimentsApi(api_client_write)

    if args.sync in ("experiments", "all"):
        sync_experiments(
            experiments_read_api=experiments_read_api,
            experiments_write_api=experiments_write_api,
            limit=args.experiment_limit,
        )

    if args.sync in ("items", "all"):
        sync_items(
            items_read_api=items_read_api,
            items_write_api=items_write_api,
            links_api_read=links_api_read,
            steps_api_read=steps_api_read,
            limit=args.item_limit,
            only_fullname=args.only_fullname,
            default_category_id=args.category_id,
        )


if __name__ == "__main__":
    main()