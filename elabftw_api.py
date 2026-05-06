import base64
import io
import re
from typing import Any, Dict, List, Optional

import qrcode


def normalize_text(value: Any) -> str:
    """Convert a value to a clean string."""
    if value is None:
        return ""
    return str(value).strip()


def generate_qr_code_data_url(url: str) -> str:
    """Generate a QR code as a base64 data URL."""
    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def extract_extra_fields(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract user-defined eLabFTW extra fields.

    eLabFTW stores custom metadata in different structures depending on the
    server version and template configuration. This function tries to support
    common layouts, including grouped metadata such as SSL_Metadata.
    """
    extra_info = {}

    metadata = record.get("metadata")
    if not metadata:
        return extra_info

    if isinstance(metadata, str):
        import json
        try:
            metadata = json.loads(metadata)
        except Exception:
            return extra_info

    extra_fields = metadata.get("extra_fields", {})

    if not isinstance(extra_fields, dict):
        return extra_info

    for key, value in extra_fields.items():
        if isinstance(value, dict):
            if "value" in value:
                extra_info[key] = value.get("value", "")
            elif "extra_fields" in value:
                nested = value.get("extra_fields", {})
                if isinstance(nested, dict):
                    for nested_key, nested_value in nested.items():
                        if isinstance(nested_value, dict):
                            extra_info[nested_key] = nested_value.get("value", "")
                        else:
                            extra_info[nested_key] = nested_value
            else:
                for nested_key, nested_value in value.items():
                    if isinstance(nested_value, dict) and "value" in nested_value:
                        extra_info[nested_key] = nested_value.get("value", "")
        else:
            extra_info[key] = value

    return extra_info


def find_sample_id(record: Dict[str, Any]) -> str:
    """
    Try to find a Sample ID from extra fields, custom_id, title, or body.
    """
    extra_info = extract_extra_fields(record)

    possible_keys = [
        "Sample-ID",
        "Sample ID",
        "SampleId",
        "Sample",
        "sample_id",
    ]

    for key in possible_keys:
        value = normalize_text(extra_info.get(key))
        if value:
            return value

    custom_id = normalize_text(record.get("custom_id"))
    if custom_id:
        return custom_id

    title = normalize_text(record.get("title"))
    body = normalize_text(record.get("body"))
    text = f"{title} {body}"

    patterns = [
        r"\bMB\d?-\d{3,5}\b",
        r"\bMB-\d{3,5}\b",
        r"\bMB\d-\d{3,5}\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)

    return ""


def record_matches_sample_id(
    sample_id: str,
    record: Dict[str, Any],
    full_text: bool = False,
) -> bool:
    """Check whether an eLabFTW record matches the requested Sample ID."""
    if not sample_id:
        return True

    sample_id_lower = sample_id.lower()

    extracted_sample_id = find_sample_id(record)
    if sample_id_lower in extracted_sample_id.lower():
        return True

    title = normalize_text(record.get("title"))
    custom_id = normalize_text(record.get("custom_id"))

    if sample_id_lower in title.lower():
        return True

    if sample_id_lower in custom_id.lower():
        return True

    if full_text:
        body = normalize_text(record.get("body"))
        metadata = normalize_text(record.get("metadata"))
        combined = f"{title} {custom_id} {body} {metadata}".lower()
        return sample_id_lower in combined

    return False


def generate_summary_rows_by_sample_id_full_text(
    sample_id: str,
    data: List[Dict[str, Any]],
    base_url: str,
    full_text: bool = False,
) -> List[Dict[str, Any]]:
    """
    Convert matching eLabFTW records into rows used by the HTML templates.
    """
    rows = []

    for record in data:
        if not record_matches_sample_id(sample_id, record, full_text=full_text):
            continue

        record_id = record.get("id")
        link = f"{base_url}{record_id}"

        extra_info = extract_extra_fields(record)
        extracted_sample_id = find_sample_id(record)

        row = {
            "id": record_id,
            "sample_id": extracted_sample_id or sample_id,
            "title": record.get("title", ""),
            "fullname": record.get("fullname", ""),
            "created_at": record.get("created_at", ""),
            "modified_at": record.get("modified_at", ""),
            "body": record.get("body", ""),
            "link": link,
            "qr_code": generate_qr_code_data_url(link),
            "extra_info": extra_info,
            "match_source": "full_text" if full_text else "metadata_or_title",
        }

        rows.append(row)

    return rows


def save_summary_as_item(items_api, sample_id: str, summary_rows: List[Dict[str, Any]]) -> Optional[int]:
    """
    Save the current search result as a new eLabFTW item.

    The exact fields accepted by eLabFTW may depend on the server setup.
    """
    body_lines = [
        f"<h2>Sample history summary for {sample_id}</h2>",
        "<table border='1' cellpadding='5' cellspacing='0'>",
        "<tr><th>ID</th><th>Created At</th><th>Created By</th><th>Title</th><th>Link</th></tr>",
    ]

    for row in summary_rows:
        body_lines.append(
            "<tr>"
            f"<td>{row.get('id')}</td>"
            f"<td>{row.get('created_at')}</td>"
            f"<td>{row.get('fullname')}</td>"
            f"<td>{row.get('title')}</td>"
            f"<td><a href='{row.get('link')}'>Open</a></td>"
            "</tr>"
        )

    body_lines.append("</table>")
    body_html = "\n".join(body_lines)

    response = items_api.post_item_with_http_info(
        body={
            "category_id": 1,
            "tags": ["sample-tracking", sample_id],
        }
    )

    location = response[2].get("Location")
    if not location:
        return None

    new_item_id = int(location.split("/").pop())

    items_api.patch_item_with_http_info(
        new_item_id,
        body={
            "title": f"Sample history summary: {sample_id}",
            "body": body_html,
        },
    )

    return new_item_id


def infer_action(row: Dict[str, Any]) -> str:
    """Infer the experimental action from extra fields or the title."""
    extra = row.get("extra_info") or {}
    title = normalize_text(row.get("title"))
    lower = title.lower()

    preferred_keys = [
        "Experiment Performed",
        "Experiment",
        "Measurement",
        "Method",
        "Technique",
        "Action",
        "Process",
        "Characterization",
    ]

    for key in preferred_keys:
        value = normalize_text(extra.get(key))
        if value:
            return value

    rules = [
        ("xps", "XPS"),
        ("xas", "XAS"),
        ("xrd", "XRD"),
        ("raman", "Raman"),
        ("sem", "SEM"),
        ("tem", "TEM"),
        ("transport", "Transport"),
        ("hall", "Hall measurement"),
        ("sinter", "Sintering"),
        ("furnace", "Furnace treatment"),
        ("anneal", "Annealing"),
        ("synthesis", "Synthesis"),
        ("pechini", "Pechini synthesis"),
        ("growth", "Growth"),
    ]

    for keyword, action in rules:
        if keyword in lower:
            return action

    return "Record"


def get_extra_value(row: Dict[str, Any], keys: List[str]) -> str:
    """Return the first non-empty value from a list of possible extra-field keys."""
    extra = row.get("extra_info") or {}

    for key in keys:
        value = normalize_text(extra.get(key))
        if value:
            return value

    return ""


def collect_extra_field_names(rows: List[Dict[str, Any]]) -> List[str]:
    """
    Collect all custom extra-field names appearing in all matching records.

    This is important because different eLabFTW entries may use different
    templates or custom metadata fields.
    """
    field_names = set()

    for row in rows:
        extra = row.get("extra_info") or {}
        for key in extra.keys():
            field_names.add(key)

    priority = [
        "Sample Type",
        "Experiment Performed",
        "Sample Composition",
        "CRC-Project",
        "Project",
        "Instrument",
        "Location",
        "Temperature",
        "Pressure",
    ]

    priority_existing = [key for key in priority if key in field_names]
    remaining = sorted(field_names - set(priority_existing), key=str.lower)

    return priority_existing + remaining


def build_timeline_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build chronological rows for the sample history timeline."""
    timeline = []

    for row in rows:
        timeline.append(
            {
                "id": row.get("id"),
                "sample_id": row.get("sample_id", ""),
                "title": row.get("title", ""),
                "person": row.get("fullname", "Unknown"),
                "created_at": row.get("created_at", ""),
                "action": infer_action(row),
                "composition": get_extra_value(row, ["Sample Composition", "Composition"]),
                "sample_type": get_extra_value(row, ["Sample Type", "Type"]),
                "project": get_extra_value(row, ["CRC-Project", "Project"]),
                "link": row.get("link", ""),
            }
        )

    return sorted(timeline, key=lambda r: r.get("created_at", ""))


def build_transfer_graph(
    rows: List[Dict[str, Any]],
    query: str,
    graph_center: str = "sample",
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build graph data for visualizing sample provenance and contributor records.
    """
    nodes = []
    edges = []
    node_ids = set()
    edge_ids = set()

    def add_node(node_id: str, label: str, group: str, size: int = 8, link: Optional[str] = None):
        if not label:
            return

        if node_id not in node_ids:
            node = {
                "id": node_id,
                "label": label,
                "group": group,
                "size": size,
            }

            if link:
                node["link"] = link

            nodes.append(node)
            node_ids.add(node_id)

    def add_edge(source: str, target: str, label: str = ""):
        if not source or not target:
            return

        edge_id = f"{source}::{target}::{label}"
        if edge_id not in edge_ids:
            edges.append(
                {
                    "from": source,
                    "to": target,
                    "label": label,
                }
            )
            edge_ids.add(edge_id)

    center_id = f"center::{query}"
    center_group = "sample" if graph_center == "sample" else "person"
    add_node(center_id, query, center_group, size=30)

    previous_event_id = None

    for i, row in enumerate(sorted(rows, key=lambda r: r.get("created_at", ""))):
        row_id = row.get("id", i)
        sample_id = normalize_text(row.get("sample_id")) or query
        person = normalize_text(row.get("fullname")) or "Unknown"
        created_at = normalize_text(row.get("created_at"))
        action = infer_action(row)
        link = row.get("link", "")

        sample_node = f"sample::{sample_id}"
        person_node = f"person::{person}"
        action_node = f"action::{action}"
        event_node = f"event::{row_id}"

        event_label = f"{created_at}\n{action}"

        add_node(sample_node, sample_id, "sample", size=20)
        add_node(person_node, person, "person", size=18)
        add_node(action_node, action, "action", size=13)
        add_node(event_node, event_label, "event", size=9, link=link)

        if graph_center == "sample":
            add_edge(center_id, person_node, "handled by")
            add_edge(person_node, event_node, "performed")
            add_edge(event_node, action_node, "type")
            add_edge(event_node, sample_node, "record of")
        else:
            add_edge(center_id, sample_node, "worked on")
            add_edge(sample_node, event_node, "has event")
            add_edge(event_node, action_node, "type")
            add_edge(person_node, event_node, "performed")

        if previous_event_id:
            add_edge(previous_event_id, event_node, "next")

        previous_event_id = event_node

        composition = get_extra_value(row, ["Sample Composition", "Composition"])
        sample_type = get_extra_value(row, ["Sample Type", "Type"])
        project = get_extra_value(row, ["CRC-Project", "Project"])
        instrument = get_extra_value(row, ["Instrument", "Device", "Equipment"])
        location = get_extra_value(row, ["Location", "Lab", "Facility", "Institute"])

        if composition:
            comp_node = f"composition::{composition}"
            add_node(comp_node, composition, "composition", size=10)
            add_edge(sample_node, comp_node, "composition")

        if sample_type:
            type_node = f"type::{sample_type}"
            add_node(type_node, sample_type, "sample_type", size=10)
            add_edge(sample_node, type_node, "type")

        if project:
            project_node = f"project::{project}"
            add_node(project_node, project, "project", size=12)
            add_edge(sample_node, project_node, "project")

        if instrument:
            instrument_node = f"instrument::{instrument}"
            add_node(instrument_node, instrument, "instrument", size=10)
            add_edge(event_node, instrument_node, "instrument")

        if location:
            location_node = f"location::{location}"
            add_node(location_node, location, "location", size=10)
            add_edge(event_node, location_node, "location")

    return {
        "nodes": nodes,
        "edges": edges,
    }
