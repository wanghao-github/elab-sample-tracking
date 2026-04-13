from flask import Flask, request, render_template
import elabapi_python
from elabftw_api import (
    generate_summary_rows_by_sample_id_full_text,
    save_summary_as_item,
    generate_qr_code_data_url,
)

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("sample_id.html")


@app.route("/process_input", methods=["POST"])
def process_input():
    sample_id = request.form.get("sample_id")
    data_type = request.form.get("data_type")
    generate_summary = request.form.get("generate_summary")
    api_key = request.form.get("api_key")
    full_text = bool(request.form.get("full_text_match"))

    print(f"[DEBUG] sample_id input: '{sample_id}'", flush=True)
    print(
        f"[DEBUG] data_type: '{data_type}', full_text: {full_text}, generate_summary: {generate_summary}",
        flush=True,
    )

    configuration = elabapi_python.Configuration()
    configuration.api_key["api_key"] = api_key
    configuration.api_key_prefix["api_key"] = "Authorization"
    configuration.host = "https://eln01-t.ca.hrz.tu-darmstadt.de/api/v2"
    configuration.debug = False
    configuration.verify_ssl = False

    api_client = elabapi_python.ApiClient(configuration)
    api_client.set_default_header(header_name="Authorization", header_value=api_key)

    items = elabapi_python.ItemsApi(api_client)
    experiments_api = elabapi_python.ExperimentsApi(api_client)

    opts = {
        "limit": 9999,
        "offset": 0,
        "_preload_content": False,
    }

    if data_type == "experiment":
        data = experiments_api.read_experiments(**opts).json()
        base_url = "https://eln01-t.ca.hrz.tu-darmstadt.de/experiments.php?mode=view&id="
    else:
        data = items.read_items(**opts).json()
        base_url = "https://eln01-t.ca.hrz.tu-darmstadt.de/database.php?mode=view&id="

    print(f"[DEBUG] Total items received from API: {len(data)}", flush=True)

    summary_rows = generate_summary_rows_by_sample_id_full_text(
        sample_id,
        data,
        base_url=base_url,
        full_text=full_text,
    )

    print(f"[DEBUG] Matching items found: {len(summary_rows)}", flush=True)
    for row in summary_rows:
        print(
            f"[MATCH] ID: {row['id']}, Title: {row['title']}, Sample-ID: '{row['sample_id']}', Match source: {row['match_source']}",
            flush=True,
        )

    new_item_id = None
    if generate_summary == "on" and summary_rows:
        new_item_id = save_summary_as_item(items, sample_id, summary_rows)
        print(f"[DEBUG] Summary item created with ID: {new_item_id}", flush=True)

    return render_template(
        "result_table.html",
        rows=summary_rows,
        new_item_id=new_item_id,
        generate_qr_code=generate_qr_code_data_url,
    )


def process_input_old():
    sample_id = request.form.get("sample_id")
    data_type = request.form.get("data_type")
    generate_summary = request.form.get("generate_summary")
    api_key = request.form.get("api_key")
    full_text = bool(request.form.get("full_text_match"))

    configuration = elabapi_python.Configuration()
    configuration.api_key["api_key"] = api_key
    configuration.api_key_prefix["api_key"] = "Authorization"
    configuration.host = "https://eln01-t.ca.hrz.tu-darmstadt.de/api/v2"
    configuration.debug = False
    configuration.verify_ssl = False

    api_client = elabapi_python.ApiClient(configuration)
    api_client.set_default_header(header_name="Authorization", header_value=api_key)

    items = elabapi_python.ItemsApi(api_client)
    experiments_api = elabapi_python.ExperimentsApi(api_client)

    opts = {
        "limit": 1000,
        "offset": 0,
        "_preload_content": False,
    }

    if data_type == "experiment":
        data = experiments_api.read_experiments(**opts).json()
        base_url = "https://eln01-t.ca.hrz.tu-darmstadt.de/experiments.php?mode=view&id="
    else:
        data = items.read_items(**opts).json()
        base_url = "https://eln01-t.ca.hrz.tu-darmstadt.de/database.php?mode=view&id="

    summary_rows = generate_summary_rows_by_sample_id_full_text(
        sample_id,
        data,
        base_url=base_url,
        full_text=full_text,
    )

    new_item_id = None
    if generate_summary == "on" and summary_rows:
        new_item_id = save_summary_as_item(items, sample_id, summary_rows)

    return render_template(
        "result_table.html",
        rows=summary_rows,
        new_item_id=new_item_id,
        generate_qr_code=generate_qr_code_data_url,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)