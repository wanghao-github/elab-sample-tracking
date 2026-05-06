from flask import Flask, request, render_template
import elabapi_python

from elabftw_api import (
    generate_summary_rows_by_sample_id_full_text,
    generate_qr_code_data_url,
    save_summary_as_item,
    build_transfer_graph,
    build_timeline_rows,
    collect_extra_field_names,
)

app = Flask(__name__)

ELAB_API_HOST = "https://eln01-t.ca.hrz.tu-darmstadt.de/api/v2"
ELAB_WEB_BASE = "https://eln01-t.ca.hrz.tu-darmstadt.de"


def build_api_client(api_key: str) -> elabapi_python.ApiClient:
    """Create an authenticated eLabFTW API client."""
    configuration = elabapi_python.Configuration()
    configuration.api_key["api_key"] = api_key
    configuration.api_key_prefix["api_key"] = "Authorization"
    configuration.host = ELAB_API_HOST
    configuration.debug = False
    configuration.verify_ssl = False

    api_client = elabapi_python.ApiClient(configuration)
    api_client.set_default_header("Authorization", api_key)
    return api_client


def read_all_records(api, read_func_name: str, page_size: int = 1000):
    """Read all records from eLabFTW using offset-based pagination."""
    all_rows = []
    offset = 0
    read_func = getattr(api, read_func_name)

    while True:
        rows = read_func(
            limit=page_size,
            offset=offset,
            _preload_content=False,
        ).json()

        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < page_size:
            break

        offset += page_size

    return all_rows


@app.route("/")
def index():
    return render_template("sample_id.html")


@app.route("/process_input", methods=["POST"])
def process_input():
    query = request.form.get("query", "").strip()
    search_mode = request.form.get("search_mode", "sample")
    graph_center = request.form.get("graph_center", "sample")
    data_type = request.form.get("data_type", "item")
    api_key = request.form.get("api_key", "").strip()
    full_text = bool(request.form.get("full_text_match"))
    generate_summary = request.form.get("generate_summary")

    print(f"[INFO] Query: {query}", flush=True)
    print(f"[INFO] Search mode: {search_mode}", flush=True)
    print(f"[INFO] Graph layout: {graph_center}", flush=True)
    print(f"[INFO] Data type: {data_type}", flush=True)
    print(f"[INFO] Full-text matching: {full_text}", flush=True)

    api_client = build_api_client(api_key)

    items_api = elabapi_python.ItemsApi(api_client)
    experiments_api = elabapi_python.ExperimentsApi(api_client)

    if data_type == "experiment":
        data = read_all_records(experiments_api, "read_experiments")
        base_url = f"{ELAB_WEB_BASE}/experiments.php?mode=view&id="
    else:
        data = read_all_records(items_api, "read_items")
        base_url = f"{ELAB_WEB_BASE}/database.php?mode=view&id="

    print(f"[INFO] Total records loaded: {len(data)}", flush=True)

    if search_mode == "sample":
        rows = generate_summary_rows_by_sample_id_full_text(
            query,
            data,
            base_url=base_url,
            full_text=full_text,
        )
    else:
        all_rows = generate_summary_rows_by_sample_id_full_text(
            "",
            data,
            base_url=base_url,
            full_text=True,
        )
        rows = [
            row for row in all_rows
            if query.lower() in str(row.get("fullname", "")).lower()
        ]

    rows = sorted(rows, key=lambda r: r.get("created_at", ""))

    print(f"[INFO] Matching records found: {len(rows)}", flush=True)

    for row in rows:
        print(
            f"[MATCH] ID={row.get('id')} | "
            f"Sample-ID={row.get('sample_id')} | "
            f"Created by={row.get('fullname')} | "
            f"Created at={row.get('created_at')} | "
            f"Title={row.get('title')}",
            flush=True,
        )

    new_item_id = None
    if generate_summary == "on" and rows and search_mode == "sample":
        new_item_id = save_summary_as_item(items_api, query, rows)
        print(f"[INFO] Summary item created: {new_item_id}", flush=True)

    timeline_rows = build_timeline_rows(rows)
    graph_data = build_transfer_graph(
        rows=rows,
        query=query,
        graph_center=graph_center,
    )

    extra_field_names = collect_extra_field_names(rows)

    return render_template(
        "result_table.html",
        query=query,
        search_mode=search_mode,
        graph_center=graph_center,
        rows=rows,
        timeline_rows=timeline_rows,
        graph_data=graph_data,
        extra_field_names=extra_field_names,
        new_item_id=new_item_id,
        generate_qr_code=generate_qr_code_data_url,
    )


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
