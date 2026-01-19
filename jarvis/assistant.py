import ast
import datetime
import math
import operator
import os
import platform
import random
import statistics
from typing import Any, Dict, Iterable, List, Optional


class _SafeEvaluator(ast.NodeVisitor):
    """Safely evaluate arithmetic expressions for Jarvis."""

    _operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
    }

    def visit(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        if isinstance(node, ast.Num):  # type: ignore[attr-defined]
            return node.n
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Unsupported constant.")
        if isinstance(node, ast.BinOp):
            left = self.visit(node.left)
            right = self.visit(node.right)
            op_type = type(node.op)
            if op_type not in self._operators:
                raise ValueError("Operator not allowed.")
            result = self._operators[op_type](left, right)
            if isinstance(node.op, ast.Pow) and abs(result) > 1e12:
                raise ValueError("Exponent too large.")
            return result
        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in self._operators:
                raise ValueError("Operator not allowed.")
            return self._operators[op_type](self.visit(node.operand))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func_name = node.func.id
            allowed_funcs = {
                "sqrt": math.sqrt,
                "log": math.log,
                "log10": math.log10,
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "abs": abs,
                "round": round,
                "mean": statistics.mean,
            }
            if func_name not in allowed_funcs:
                raise ValueError("Function not permitted.")
            args = [self.visit(arg) for arg in node.args]
            return allowed_funcs[func_name](*args)
        if isinstance(node, ast.List):
            return [self.visit(child) for child in node.elts]
        raise ValueError("Unsupported expression.")

    @classmethod
    def evaluate(cls, expr: str) -> float:
        tree = ast.parse(expr, mode="eval")
        value = cls().visit(tree)
        if isinstance(value, list):
            raise ValueError("List literals are not supported at top level.")
        return float(value)


class JarvisAssistant:
    """Conversational assistant with optional LLM backing."""

    def __init__(self) -> None:
        self.identity = (
            "You are Jarvis, a tactical operations assistant. "
            "Respond with clarity, calm confidence, and concise detail. "
            "Offer actionable next steps whenever possible."
        )
        self._client = self._bootstrap_client()
        self._intent_aliases = {
            "diagnostics": {"diagnostic", "diagnostics", "system status"},
            "time": {"time", "timezone", "date"},
            "plan": {"plan", "schedule", "roadmap"},
            "motivation": {"motivate", "motivation", "quote"},
            "calculation": {"calculate", "compute", "math"},
            "summary": {"summarize", "summary", "recap"},
            "general": set(),
        }

    def _bootstrap_client(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        try:
            from openai import OpenAI

            return OpenAI(api_key=api_key)
        except Exception:
            return None

    def _detect_intent(self, message: str) -> str:
        lowered = message.lower()
        for intent, aliases in self._intent_aliases.items():
            if any(alias in lowered for alias in aliases):
                return intent
        if "weather" in lowered:
            return "weather"
        if "remind" in lowered or "reminder" in lowered:
            return "reminder"
        return "general"

    def handle(self, message: str, history: Optional[Iterable[Dict[str, str]]] = None) -> Dict[str, Any]:
        history_list = list(history or [])
        intent = self._detect_intent(message)
        for handler in (
            self._handle_diagnostics,
            self._handle_time,
            self._handle_calculation,
            self._handle_motivation,
            self._handle_summary,
            self._handle_learning_plan,
        ):
            result = handler(message, history_list, intent)
            if result:
                result["intent"] = result.get("intent", intent)
                return result

        llm_result = self._call_model(message, history_list, intent)
        llm_result["intent"] = llm_result.get("intent", intent)
        return llm_result

    # Handlers
    def _handle_diagnostics(
        self,
        message: str,
        history: List[Dict[str, str]],
        intent: str,
    ) -> Optional[Dict[str, Any]]:
        if intent != "diagnostics":
            return None
        now = datetime.datetime.utcnow()
        platform_info = platform.platform()
        python_version = platform.python_version()
        actions = [
            f"Timestamp: {now:%Y-%m-%d %H:%M:%S} UTC",
            f"Runtime: Python {python_version}",
            f"Platform: {platform_info}",
            "Self-check: Core systems nominal. Latency < 200ms.",
        ]
        return {
            "reply": (
                "System diagnostic complete. All monitored subsystems report nominal performance. "
                "No anomalies detected within the last cycle. Ready for further directives."
            ),
            "actions": actions,
            "intent": "diagnostics",
        }

    def _handle_time(
        self,
        message: str,
        history: List[Dict[str, str]],
        intent: str,
    ) -> Optional[Dict[str, Any]]:
        if intent != "time":
            return None
        now = datetime.datetime.now(datetime.timezone.utc)
        local = datetime.datetime.now()
        return {
            "reply": (
                f"It's currently {local:%I:%M %p} local time ({now:%H:%M} UTC) "
                f"on {now:%A, %B %d, %Y}."
            ),
            "actions": [
                f"Local time check: {local:%I:%M:%S %p}",
                f"UTC time check: {now:%H:%M:%S}",
                "Reminder: Synchronize mission-critical events with UTC baseline.",
            ],
            "intent": "time",
        }

    def _handle_calculation(
        self,
        message: str,
        history: List[Dict[str, str]],
        intent: str,
    ) -> Optional[Dict[str, Any]]:
        if intent != "calculation":
            if not any(token in message.lower() for token in ("calculate", "compute", "evaluate")):
                return None
        expression = (
            message.lower()
            .replace("calculate", "")
            .replace("compute", "")
            .replace("evaluate", "")
            .strip()
        )
        if not expression:
            return {
                "reply": (
                    "Provide the equation you'd like me to solve. Example: 'Calculate (42 * 7) / 3.'"
                ),
                "actions": ["Awaiting target expression.", "Accepts + - * / ^, sin/cos/tan, sqrt."],
                "intent": "calculation",
            }
        try:
            result = _SafeEvaluator.evaluate(expression)
        except Exception as exc:  # noqa: BLE001
            return {
                "reply": (
                    "That expression triggered a safety guard. Confirm the syntax and try again."
                ),
                "actions": [f"Parser exception: {exc}"],
                "intent": "calculation",
            }
        return {
            "reply": f"Computation complete. The result is {result:.4f}.",
            "actions": [
                f"Input expression: {expression}",
                f"Evaluated result: {result:.4f}",
                "Precision limited to four decimal places.",
            ],
            "intent": "calculation",
        }

    def _handle_motivation(
        self,
        message: str,
        history: List[Dict[str, str]],
        intent: str,
    ) -> Optional[Dict[str, Any]]:
        if intent != "motivation":
            return None
        quotes = [
            "The future is built by those who show up fully prepared. You already did the hardest part by starting.",
            "Every system has latency. Progress happens when you keep the pipeline moving anyway.",
            "Precision and consistency beat bursts of inspiration. Stay on the loop.",
            "Discipline is the difference between intention and execution. You've got this.",
        ]
        selection = random.choice(quotes)
        return {
            "reply": f"Motivation delivered: {selection}",
            "actions": [
                "Recommendation: schedule a 25-minute focus block.",
                "Hydration reminder: take a sip of water.",
            ],
            "intent": "motivation",
        }

    def _handle_summary(
        self,
        message: str,
        history: List[Dict[str, str]],
        intent: str,
    ) -> Optional[Dict[str, Any]]:
        if intent != "summary":
            return None
        if not history:
            return {
                "reply": "There is no conversation history to summarize yet.",
                "actions": ["Summary aborted: no prior transmissions detected."],
                "intent": "summary",
            }
        snippets = []
        for item in history[-8:]:
            role = "You" if item["role"] == "user" else "Jarvis"
            snippets.append(f"{role}: {item['content']}")
        summary = " | ".join(snippets)
        return {
            "reply": (
                "Summary compiled from recent exchanges:\n"
                f"{summary}\n"
                "Let me know if you'd like a strategic next step."
            ),
            "actions": ["Summary window: last 8 exchanges.", "Context ready for follow-up."],
            "intent": "summary",
        }

    def _handle_learning_plan(
        self,
        message: str,
        history: List[Dict[str, str]],
        intent: str,
    ) -> Optional[Dict[str, Any]]:
        lowered = message.lower()
        if "plan" not in lowered or "python" not in lowered:
            return None
        actions = [
            "Phase 1 (Week 1): Master syntax fundamentals and control flow.",
            "Phase 2 (Week 2): Dive into functions, modules, and error handling.",
            "Phase 3 (Week 3): Build projects with file I/O and data structures.",
            "Phase 4 (Week 4): Explore APIs, automation, and deployment.",
        ]
        return {
            "reply": (
                "Python mastery protocol initiated. I recommend a four-week sprint:\n"
                "Week 1: Syntax, data types, control flow, daily coding drills.\n"
                "Week 2: Functions, modules, testing fundamentals, mini-project.\n"
                "Week 3: Data structures, file I/O, build a CLI utility.\n"
                "Week 4: API integration, automation scripts, deploy a portfolio project.\n"
                "Signal when you want detailed drills or resources for any phase."
            ),
            "actions": actions,
            "intent": "plan",
        }

    # Model invocation and fallbacks
    def _call_model(
        self,
        message: str,
        history: List[Dict[str, str]],
        intent: str,
    ) -> Dict[str, Any]:
        if not self._client:
            return self._offline_response(message, history, intent)

        try:
            conversation = [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": self.identity
                            + " Provide structured, tactical responses. Include next steps when useful.",
                        }
                    ],
                }
            ]
            for item in history[-8:]:
                conversation.append(
                    {
                        "role": item["role"],
                        "content": [{"type": "text", "text": item["content"]}],
                    }
                )

            conversation.append({"role": "user", "content": [{"type": "text", "text": message}]})

            response = self._client.responses.create(
                model=os.getenv("JARVIS_MODEL", "gpt-4o-mini"),
                input=conversation,
                reasoning={"effort": "medium"},
                temperature=0.7,
            )

            reply_text = getattr(response, "output_text", None)
            if not reply_text:
                reply_text = "Model response did not contain textual output."

            actions = []
            if hasattr(response, "metadata") and isinstance(response.metadata, dict):
                suggestions = response.metadata.get("suggestions")
                if isinstance(suggestions, list):
                    actions.extend(str(item) for item in suggestions)

            if not actions:
                actions = [f"Intent classified as {intent}.", "LLM response delivered."]

            return {
                "reply": reply_text.strip(),
                "actions": actions,
                "intent": intent,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "reply": (
                    "LLM channel encountered interference. Switching to offline reasoning protocols. "
                    "Issue the command again once the uplink stabilizes if you need deeper synthesis."
                ),
                "actions": [f"Model exception: {exc}"],
                "intent": "general",
            }

    def _offline_response(
        self,
        message: str,
        history: List[Dict[str, str]],
        intent: str,
    ) -> Dict[str, Any]:
        lowered = message.lower()
        if "weather" in lowered:
            return {
                "reply": (
                    "Weather intel requires an external API uplink. Configure an API key and I'll patch in."
                ),
                "actions": ["Missing dependency: WEATHER_API_KEY."],
                "intent": "weather",
            }
        fillers = [
            "Channel secured. I'm ready to iterate on that with you.",
            "Operational control confirmed. Let's break this down.",
            "Interpreting your directive. I can propose a course of action or build artifacts on request.",
        ]
        last_user = next((item["content"] for item in reversed(history) if item["role"] == "user"), "")
        if last_user and last_user != message:
            context_hint = f"Previously you mentioned: {last_user}"
        else:
            context_hint = "No additional context detected."
        return {
            "reply": f"{random.choice(fillers)}\nContext snapshot: {context_hint}",
            "actions": [
                "Offline mode active: OPENAI_API_KEY not detected.",
                "Enable an LLM provider for richer responses.",
            ],
            "intent": intent,
            "speak": False,
        }
