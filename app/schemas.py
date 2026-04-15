"""Request/Response schemas."""

from pydantic import BaseModel


class PromptRequest(BaseModel):
    prompt: str
    language: str = "ja"
    unmask_response: bool = True  # whether to unmask the LLM response


class PromptResponse(BaseModel):
    request_id: str
    original_prompt: str
    masked_prompt: str
    llm_response_raw: str  # LLM response (masked)
    llm_response: str  # Final response (unmasked if requested)
    pii_detected: dict[str, str]  # mapping of placeholders to original values


class HealthResponse(BaseModel):
    status: str
    redis: str
