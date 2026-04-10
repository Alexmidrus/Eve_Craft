from __future__ import annotations


class EsiService:
    base_url = "https://esi.evetech.net/latest"

    def describe_status(self) -> str:
        return (
            "The ESI service is registered in the service layer. "
            f"Base endpoint: {self.base_url}. Live requests and token-aware clients will be added later."
        )
