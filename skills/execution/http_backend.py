"""HTTP execution: delegate to a remote skill service. For distributed skills."""
import httpx
from typing import Any, Dict


class HTTPBackend:
    """Call a remote skill service over HTTP.

    The remote service is expected to expose:
        POST /execute  body: ``{"code": str, "context": dict}``
                       reply: arbitrary JSON dict (the same shape as other backends)
        GET  /health   reply: any 2xx (used by :meth:`is_available`).

    Args:
        base_url: Remote service root (no trailing slash).
        timeout:  Per-request timeout in seconds.
    """

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def execute(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/execute",
                    json={"code": code, "context": context},
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPError as e:
            return {"success": False, "error": f"HTTP error: {e}"}

    def cleanup(self) -> None:
        pass

    def is_available(self) -> bool:
        try:
            with httpx.Client(timeout=3.0) as client:
                client.get(f"{self.base_url}/health")
            return True
        except httpx.HTTPError:
            return False


__all__ = ["HTTPBackend"]
