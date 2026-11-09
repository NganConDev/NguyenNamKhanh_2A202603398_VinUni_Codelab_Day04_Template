import json
import os
from typing import List, Dict, Any
from datetime import datetime

RAW_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "raw-data")

# ---------------------------------------------------------------------------
# Tool #1: search_product_catalog
# TODO: Hoàn thiện hàm này — đọc file product_catalog.json, lọc theo category và max_price.
# ---------------------------------------------------------------------------

def search_product_catalog(category: str, max_price: int = 999999999999) -> List[Dict[str, Any]]:
    """
    Tra cứu sản phẩm/dịch vụ Vingroup theo danh mục và giá tối đa.
    
    Args:
        category: Loại sản phẩm ('xe_dien' hoặc 'du_lich').
        max_price: Giá tối đa (VNĐ). Mặc định không giới hạn.
    
    Returns:
        Danh sách sản phẩm phù hợp điều kiện.
    """
    catalog_file = os.path.join(RAW_DATA_DIR, "product_catalog.json")
    if not os.path.exists(catalog_file):
        return []

    try:
        with open(catalog_file, "r", encoding="utf-8") as f:
            catalog = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    category = (category or "").strip().lower()
    if not category:
        return []

    try:
        limit = int(max_price)
    except (TypeError, ValueError):
        limit = 999999999999

    return [
        product for product in catalog
        if str(product.get("category", "")).lower() == category
        and int(product.get("price_vnd", 0)) <= limit
    ]


# ---------------------------------------------------------------------------
# Tool #2: submit_support_ticket
# TODO: Hoàn thiện hàm này — tạo ticket mới và lưu vào support_tickets.json.
# ---------------------------------------------------------------------------

def submit_support_ticket(
    customer_name: str,
    issue_description: str,
    priority: str = "medium"
) -> Dict[str, Any]:
    """
    Ghi nhận yêu cầu hỗ trợ của khách hàng vào hệ thống ticket.
    
    Args:
        customer_name: Tên khách hàng.
        issue_description: Mô tả vấn đề cần hỗ trợ.
        priority: Mức độ ưu tiên ('low', 'medium', 'high'). Mặc định 'medium'.
    
    Returns:
        Thông tin ticket vừa tạo bao gồm ticket_id, status.
    """
    tickets_file = os.path.join(RAW_DATA_DIR, "support_tickets.json")

    if not customer_name or not issue_description:
        raise ValueError("customer_name và issue_description không được để trống.")

    priority = (priority or "medium").strip().lower()
    if priority not in {"low", "medium", "high"}:
        priority = "medium"

    existing_tickets: List[Dict[str, Any]] = []
    if os.path.exists(tickets_file):
        try:
            with open(tickets_file, "r", encoding="utf-8") as f:
                existing_tickets = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing_tickets = []

    if not isinstance(existing_tickets, list):
        existing_tickets = []

    today = datetime.now().strftime("%Y%m%d")
    seq = 1
    for ticket in existing_tickets:
        ticket_id = str(ticket.get("ticket_id", ""))
        if ticket_id.startswith(f"TK-{today}-"):
            seq += 1

    ticket_id = f"TK-{today}-{seq:03d}"
    created_at = datetime.now().isoformat()
    new_ticket = {
        "ticket_id": ticket_id,
        "customer_name": customer_name,
        "issue_description": issue_description,
        "priority": priority,
        "status": "open",
        "created_at": created_at,
        "category": "general"
    }

    existing_tickets.append(new_ticket)

    with open(tickets_file, "w", encoding="utf-8") as f:
        json.dump(existing_tickets, f, ensure_ascii=False, indent=2)

    return new_ticket


# ---------------------------------------------------------------------------
# TOOL_DEFINITIONS — JSON Schemas mô tả cho LLM
# TODO: Định nghĩa JSON Schema cho từng tool (name, description, parameters).
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_product_catalog",
            "description": "Tra cứu sản phẩm/dịch vụ Vingroup theo danh mục và giá tối đa.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["xe_dien", "du_lich"],
                        "description": "Loại sản phẩm cần tìm: xe_dien hoặc du_lich."
                    },
                    "max_price": {
                        "type": "integer",
                        "description": "Giá tối đa theo VNĐ để lọc sản phẩm."
                    }
                },
                "required": ["category"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_support_ticket",
            "description": "Ghi nhận yêu cầu hỗ trợ của khách hàng và tạo ticket mới trong hệ thống.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Tên khách hàng cần tạo ticket."
                    },
                    "issue_description": {
                        "type": "string",
                        "description": "Mô tả chi tiết vấn đề cần hỗ trợ."
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Mức độ ưu tiên của ticket."
                    }
                },
                "required": ["customer_name", "issue_description"],
                "additionalProperties": False
            }
        }
    }
]


# ---------------------------------------------------------------------------
# TOOL_MAP — Ánh xạ tên tool → hàm thực thi
# ---------------------------------------------------------------------------

TOOL_MAP = {
    "search_product_catalog": search_product_catalog,
    "submit_support_ticket": submit_support_ticket
}
