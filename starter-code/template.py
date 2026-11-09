"""
Lab #4: System Prompt Engineering & Tool Calling Engine
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.

Kiến trúc:
  - ChatbotBaseline: LLM thuần, không dùng tool → quan sát hallucination.
  - ToolCallingAgent: Agent dùng System Prompt + 2 Tool Schemas.
"""

import json
import re
from typing import Dict, Any, List
from tools import TOOL_DEFINITIONS, TOOL_MAP, search_product_catalog, submit_support_ticket

# ═══════════════════════════════════════════════════════════════════════════
# TODO 1: Thiết kế SYSTEM PROMPT cấp sản xuất
# Yêu cầu: Phải chứa Persona, Core Rules, Operational Boundaries, Output Contract.
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = f"""
Bạn là VinAssistant, trợ lý chăm sóc khách hàng chính thức của Tập đoàn Vingroup.

PERSONA
- Tên: VinAssistant
- Vai trò: tư vấn sản phẩm, dịch vụ Vingroup, hỗ trợ khách hàng và xử lý ticket hỗ trợ.
- Giọng điệu: rõ ràng, thân thiện, chuyên nghiệp, ngắn gọn nhưng đầy đủ.

AVAILABLE TOOLS
- search_product_catalog(category: str, max_price: int)
- submit_support_ticket(customer_name: str, issue_description: str, priority: str)

CORE RULES
1. Không bịa dữ liệu hoặc suy đoán thông tin chưa có trong hệ thống.
2. Nếu người dùng hỏi về sản phẩm, giá, hoặc danh mục, phải ưu tiên gọi tool phù hợp.
3. Nếu người dùng mô tả sự cố hoặc yêu cầu được hỗ trợ, phải tạo ticket bằng tool submit_support_ticket.
4. Luôn dựa trên dữ liệu thực có trong catalog hoặc ticket system.
5. Nếu không có dữ liệu phù hợp, trả lời rõ ràng rằng không tìm thấy kết quả.

OPERATIONAL BOUNDARIES
- Chỉ trả lời về các sản phẩm/dịch vụ của Vingroup như VinFast, Vinpearl, VinWonders, v.v.
- Không trả lời các câu hỏi ngoài phạm vi Vingroup.
- Nếu câu hỏi không liên quan đến Vingroup, hãy lịch sự từ chối và hướng dẫn về nội dung phù hợp.

OUTPUT CONTRACT
- Thought: xác định mục tiêu và tool cần dùng.
- Action: gọi tool hoặc trả lời trực tiếp.
- Observation: dữ liệu trả về từ tool.
- Final Answer: kết luận cuối cùng cho người dùng.
"""


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ChatbotBaseline
# ═══════════════════════════════════════════════════════════════════════════

class ChatbotBaseline:
    """Baseline LLM Chatbot — Không sử dụng Tool Calling hay ReAct Loop."""

    def query(self, user_input: str) -> Dict[str, Any]:
        # TODO 2: Trả về câu trả lời tĩnh (mock) hoặc gọi Gemini API 1 lượt (không dùng tool)
        # Mục tiêu: Quan sát hiện tượng bịa thông tin (hallucination)
        text = (user_input or "").strip()
        lower = text.lower()

        if "bảo hành" in lower and "pin" in lower:
            answer = "VinFast áp dụng chính sách bảo hành pin lên đến 10 năm cho xe điện." \
                     " Đây là thông tin chính sách chung của VinFast."
        elif "vinfast" in lower or "xe điện" in lower:
            answer = "VinFast cung cấp các dòng xe điện như VF 3, VF 5, VF 8 và VF 9, cùng nhiều chương trình ưu đãi và dịch vụ hậu mãi."
        elif "vinpearl" in lower or "du lịch" in lower:
            answer = "Vinpearl có nhiều sản phẩm du lịch như resort, kỳ nghỉ, trải nghiệm nghỉ dưỡng và lễ hội tại các điểm đến nổi tiếng."
        else:
            answer = f"Tôi là chatbot cơ bản, có thể hỗ trợ thông tin chung về Vingroup. Bạn có thể hỏi về xe điện VinFast, du lịch Vinpearl hoặc chính sách hỗ trợ khách hàng."

        return {
            "answer": answer,
            "tool_calls": [],
            "status": "success",
            "mode": "mock_baseline"
        }


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ToolCallingAgent
# ═══════════════════════════════════════════════════════════════════════════

class ToolCallingAgent:
    """Agent với System Prompt Engineering & Tool Calling."""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace: List[Dict[str, Any]] = []

    def _parse_price(self, text: str):
        lower = text.lower()
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(triệu|tr|m|vnđ|vnd)', lower)
        if match:
            value = float(match.group(1).replace(',', '.'))
            unit = match.group(2)
            if unit in {"triệu", "tr", "m"}:
                return int(value * 1_000_000)
            return int(value)
        return None

    def _detect_catalog_intent(self, text: str):
        lower = text.lower()
        category = None
        if any(k in lower for k in ["du lịch", "vinpearl", "resort", "kỳ nghỉ", "tour", "du_lich"]):
            category = "du_lich"
        elif any(k in lower for k in ["xe điện", "vinfast", "vf ", "vf3", "vf5", "vf8", "vf9", "xe_dien", "ô tô điện", "ôto điện"]):
            category = "xe_dien"

        if category is None:
            return None

        max_price = self._parse_price(text)
        if max_price is None:
            max_price = 999999999999
        return {"tool": "search_product_catalog", "category": category, "max_price": max_price}

    def _detect_ticket_intent(self, text: str):
        lower = text.lower()
        if not any(k in lower for k in ["bị lỗi", "hệ thống", "hỗ trợ", "yêu cầu hỗ trợ", "cần xử lý", "gấp", "nghiêm trọng", "sửa chữa", "lỗi", "trợ giúp"]):
            return None

        name = "Khách hàng"
        match = re.search(
            r"(?:tôi|mình|em)\s+tên\s+([A-ZÀ-ỸĂÂĐÊÔƠƯ][A-Za-zÀ-ỹĂÂÊÔƠƯăâđêôơư]*(?:\s+[A-ZÀ-ỸĂÂĐÊÔƠƯ][A-Za-zÀ-ỹĂÂÊÔƠƯăâđêôơư]*)*)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            name = match.group(1).strip()
        else:
            match = re.search(
                r"khách hàng\s+([A-ZÀ-ỸĂÂĐÊÔƠƯ][A-Za-zÀ-ỹĂÂÊÔƠƯăâđêôơư]*(?:\s+[A-ZÀ-ỸĂÂĐÊÔƠƯ][A-Za-zÀ-ỹĂÂÊÔƠƯăâđêôơư]*)*)",
                text,
                flags=re.IGNORECASE,
            )
            if match:
                name = match.group(1).strip()

        issue_description = text.strip()
        if len(issue_description) > 200:
            issue_description = issue_description[:200]

        priority = "high" if any(k in lower for k in ["gấp", "khẩn cấp", "nghiêm trọng", "nguy hiểm", "quan trọng", "cần xử lý gấp"]) else "medium"
        return {"tool": "submit_support_ticket", "customer_name": name, "issue_description": issue_description, "priority": priority}

    def _detect_faq_intent(self, text: str):
        lower = text.lower()
        if "bảo hành" in lower and "pin" in lower and ("vinfast" in lower or "xe điện" in lower):
            return {"tool": "faq", "answer": "Chính sách bảo hành pin xe điện VinFast lên đến 10 năm, tùy dòng xe và điều kiện bảo hành cụ thể."}
        return None

    def run(self, user_input: str) -> Dict[str, Any]:
        """Điểm vào chính — chạy Agent Loop."""
        self.trace = []
        self.trace.append({"step": "init", "user_input": user_input})

        text = (user_input or "").strip()
        if not text:
            return {
                "answer": "Tôi cần thông tin cụ thể để hỗ trợ bạn.",
                "trace": self.trace,
                "iterations": 1,
                "status": "completed"
            }

        if self._detect_ticket_intent(text):
            intent = self._detect_ticket_intent(text)
            ticket = submit_support_ticket(
                customer_name=intent["customer_name"],
                issue_description=intent["issue_description"],
                priority=intent["priority"]
            )
            self.trace.append({"step": "tool_call", "tool": "submit_support_ticket", "params": intent, "result": ticket})
            answer = f"Đã tiếp nhận yêu cầu hỗ trợ cho {ticket['customer_name']} với mã ticket {ticket['ticket_id']}. Trạng thái hiện tại: {ticket['status']}."
            return {
                "answer": answer,
                "trace": self.trace,
                "iterations": 1,
                "status": "completed"
            }

        faq = self._detect_faq_intent(text)
        if faq:
            self.trace.append({"step": "faq", "answer": faq["answer"]})
            return {
                "answer": faq["answer"],
                "trace": self.trace,
                "iterations": 1,
                "status": "completed"
            }

        catalog_intent = self._detect_catalog_intent(text)
        if catalog_intent:
            results = search_product_catalog(category=catalog_intent["category"], max_price=catalog_intent["max_price"])
            self.trace.append({"step": "tool_call", "tool": "search_product_catalog", "params": catalog_intent, "result": results})
            if not results:
                answer = "Rất tiếc, không tìm thấy sản phẩm phù hợp với tiêu chí của bạn. Bạn có thể tăng ngân sách hoặc thay đổi danh mục tìm kiếm."
            else:
                names = ", ".join(item["name"] for item in results[:5])
                answer = f"Tôi tìm thấy các sản phẩm phù hợp: {names}."
            return {
                "answer": answer,
                "trace": self.trace,
                "iterations": 1,
                "status": "completed"
            }

        self.trace.append({"step": "fallback", "reason": "No tool intent matched"})
        return {
            "answer": "Tôi có thể hỗ trợ về sản phẩm và dịch vụ Vingroup. Nếu bạn cần tìm xe điện, du lịch Vinpearl, hoặc tạo ticket hỗ trợ, hãy mô tả rõ hơn.",
            "trace": self.trace,
            "iterations": 1,
            "status": "completed"
        }


# ═══════════════════════════════════════════════════════════════════
# MAIN — Chạy thử nhanh
# ═══════════════════════════════════════════════════════════════════

def main():
    user_query = "Tôi muốn xem xe điện VinFast giá dưới 600 triệu."

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING TOOL CALLING AGENT ===")
    agent = ToolCallingAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result["answer"])
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
