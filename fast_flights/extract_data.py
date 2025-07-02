import json
import re


def get_js_callback_data(js_string):
    """Extract data field from AF_initDataCallback JavaScript"""
    pattern = r"data:\s*(\[.*?\]),\s*sideChannel"
    match = re.search(pattern, js_string, re.DOTALL)

    if match:
        data_str = re.sub(r"\s+", " ", match.group(1).strip())
        # Remove trailing commas that are valid in JS but not JSON
        data_str = re.sub(r",(\s*[\]}])", r"\1", data_str)
        try:
            return json.loads(data_str)
        except Exception:
            return None
    return None
