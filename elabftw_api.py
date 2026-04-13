import json
import base64
from io import BytesIO

import elabapi_python
import qrcode
from bs4 import BeautifulSoup
from flask import Flask, render_template

my_api_key = "your_api_key_here"
configuration = elabapi_python.Configuration()
configuration.api_key["api_key"] = my_api_key
configuration.api_key_prefix["api_key"] = "Authorization"
configuration.host = "https://your-elab-url/api/v2/items"
configuration.debug = False
configuration.verify_ssl = False

api_client = elabapi_python.ApiClient(configuration)
api_client.set_default_header(header_name="Authorization", header_value=my_api_key)
items = elabapi_python.ItemsApi(api_client)
experiments_api = elabapi_python.ExperimentsApi(api_client)

app = Flask(__name__)


def get_extra_field(metadata, field):
    if not metadata:
        return ""

    try:
        parsed = json.loads(metadata) if isinstance(metadata, str) else metadata
        fields = parsed.get("extra_fields", {})
        if field in fields:
            value = fields[field].get("value", "")
            if isinstance(value, list):
                return " ".join(v.strip() for v in value if v)
            if isinstance(value, str):
                return value.strip()
            return str(value)
    except Exception:
        pass

    return ""


def sample_id_matches_field(sample_id_input, sample_id_field):
    sample_id_input = sample_id_input.strip().lower()
    return any(
        sid.strip().lower().startswith(sample_id_input)
        for sid in sample_id_field.split()
    )


def generate_qr_code_data_url(link):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=6,
        border=2,
    )
    qr.add_data(link)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"


def generate_summary_rows_by_sample_id_full_text(sample_id, data, base_url, full_text=False):
    important_extra_fields = [
        "Sample Type",
        "Experiment Performed",
        "Sample Composition",
        "CRC-Project",
    ]

    summary_rows = []
    sample_id_lower = sample_id.strip().lower()

    for item in data:
        metadata = item.get("metadata", {})
        title = item.get("title", "") or ""
        body = item.get("body", "") or ""
        sample_id_field = get_extra_field(metadata, "Sample-ID").strip()
        body_fixed = item.get("body") or ""

        sample_id_tokens = [sid.strip().lower() for sid in sample_id_field.split()]

        matched = False
        match_source = ""

        if full_text:
            if sample_id_lower in title.lower():
                matched = True
                match_source = "title"
            elif sample_id_lower in body.lower():
                matched = True
                match_source = "body"
            elif any(sid.startswith(sample_id_lower) for sid in sample_id_tokens):
                matched = True
                match_source = "Sample-ID"
        else:
            if any(sid.startswith(sample_id_lower) for sid in sample_id_tokens):
                matched = True
                match_source = "Sample-ID"

        if not matched:
            continue

        extra_info = {
            field: get_extra_field(metadata, field)
            for field in important_extra_fields
        }
        link = base_url + str(item["id"])

        row = {
            "id": item.get("id"),
            "title": item.get("title", "N/A"),
            "fullname": item.get("fullname", "N/A"),
            "created_at": item.get("created_at", "N/A"),
            "category_id": item.get("category_id", "N/A"),
            "custom_id": item.get("custom_id", "N/A"),
            "sample_id": sample_id_field,
            "link": link,
            "body_html": item.get("body_html", ""),
            "body": body_fixed,
            "extra_info": extra_info,
            "match_source": match_source,
            "qr_code": generate_qr_code_data_url(link),
        }

        summary_rows.append(row)

    return summary_rows


def generate_summary_rows_by_sample_id_full_texti_1(sample_id, data, base_url, full_text=False):
    important_extra_fields = [
        "Sample Type",
        "Temperature",
        "Sample Composition",
        "CRC-Project",
    ]

    summary_rows = []
    sample_id_lower = sample_id.strip().lower()

    for item in data:
        metadata = item.get("metadata", {})
        title = item.get("title", "")
        body = item.get("body", "")
        sample_id_field = get_extra_field(metadata, "Sample-ID").strip()

        matched = False
        match_source = ""

        if full_text:
            if sample_id_lower in title.lower():
                matched = True
                match_source = "title"
            elif sample_id_lower in body.lower():
                matched = True
                match_source = "body"
            elif sample_id_matches_field(sample_id_lower, sample_id_field):
                matched = True
                match_source = "Sample-ID"
        else:
            if sample_id_matches_field(sample_id_lower, sample_id_field):
                matched = True
                match_source = "Sample-ID"

        if not matched:
            continue

        extra_info = {
            field: get_extra_field(metadata, field)
            for field in important_extra_fields
        }
        link = base_url + str(item["id"])

        summary_rows.append(
            {
                "id": item.get("id"),
                "title": title,
                "fullname": item.get("fullname", "N/A"),
                "created_at": item.get("created_at", "N/A"),
                "category_id": item.get("category_id", "N/A"),
                "custom_id": item.get("custom_id", "N/A"),
                "sample_id": sample_id_field,
                "link": link,
                "body_html": fix_image_paths(item.get("body_html", ""), base_url),
                "body": fix_image_paths(item.get("body", ""), base_url),
                "extra_info": extra_info,
                "match_source": match_source,
                "qr_code": generate_qr_code_data_url(link),
            }
        )

    return summary_rows


def save_summary_as_item(items_api, sample_id, summary_rows):
    title = f"{sample_id} summary"
    html_table = render_template("summary_body.html", rows=summary_rows)

    response = items_api.post_item_with_http_info(
        body={
            "title": title,
            "category_id": 2,
            "tags": ["summary"],
            "body": "<h1>Section title</h1><p>Main text of resource</p>",
        }
    )

    location = response[2].get("Location")
    item_id = int(location.split("/").pop())

    items_api.patch_item_with_http_info(item_id, body={"body": html_table})
    return item_id


def fix_image_src_by_uploads(body, uploads):
    soup = BeautifulSoup(body, "html.parser")
    base_url = "https://wanghao93.xyz"

    for img in soup.find_all("img"):
        src = img.get("src", "")
        for up in uploads:
            real_name = up.get("real_name")
            long_name = up.get("long_name")
            storage = up.get("storage", 1)
            prefix = long_name[:2]

            if real_name in src or long_name in src:
                new_src = f"{base_url}/app/download.php?f={prefix}/{long_name}&storage={storage}"
                img["src"] = new_src
                break

    return str(soup)