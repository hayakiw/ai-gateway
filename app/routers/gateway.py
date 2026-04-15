"""Gateway router — PII masking proxy endpoints."""

import asyncio
import json
import logging
from functools import partial

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.masking_logger import log_masked_request, log_masked_response
from app.schemas import PromptRequest, PromptResponse
from app.services.llm_client import LlmClient
from app.services.pii_detector import PiiDetector
from app.stores.mapping_store import MappingStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gateway")


@router.post("/generate", response_model=PromptResponse)
async def generate(request: Request, body: PromptRequest):
    """
    Main gateway endpoint (non-streaming).

    Flow:
    1. Detect and mask PII in the user's prompt
    2. Store the mapping table in Redis
    3. Send the masked prompt to the LLM
    4. Unmask the LLM response (if requested)
    5. Return the final response
    """
    detector: PiiDetector = request.app.state.pii_detector
    store: MappingStore = request.app.state.mapping_store
    llm: LlmClient = request.app.state.llm_client

    # Step 1: Detect PII and mask (run in executor to avoid blocking event loop)
    loop = asyncio.get_running_loop()
    masking_result = await loop.run_in_executor(
        None, partial(detector.mask, body.prompt, language=body.language)
    )
    logger.info(
        "PII detected: %d entities masked", len(masking_result.mapping)
    )

    # Step 2: Store mapping in Redis
    request_id = await store.save(masking_result.mapping)

    # Log masked request
    log_masked_request(
        request_id=request_id,
        masked_prompt=masking_result.masked_text,
        pii_count=len(masking_result.mapping),
        pii_placeholders=list(masking_result.mapping.keys()),
        endpoint="/gateway/generate",
    )

    # Step 3: Send masked prompt to LLM
    try:
        llm_response_raw = await llm.generate(masking_result.masked_text)
    except Exception as e:
        logger.error("LLM API call failed: %s", e)
        await store.delete(request_id)
        raise HTTPException(
            status_code=502, detail=f"LLM API call failed: {e}"
        )

    # Step 4: Unmask LLM response
    if body.unmask_response and masking_result.mapping:
        llm_response = detector.unmask(llm_response_raw, masking_result.mapping)
    else:
        llm_response = llm_response_raw

    # Log masked response
    log_masked_response(
        request_id=request_id,
        masked_response=llm_response_raw,
        endpoint="/gateway/generate",
    )

    # Cleanup mapping from Redis
    await store.delete(request_id)

    return PromptResponse(
        request_id=request_id,
        original_prompt=body.prompt,
        masked_prompt=masking_result.masked_text,
        llm_response_raw=llm_response_raw,
        llm_response=llm_response,
        pii_detected=masking_result.mapping,
    )


@router.post("/stream")
async def stream_generate(request: Request, body: PromptRequest):
    """
    Streaming gateway endpoint (Server-Sent Events).

    Returns SSE events:
      - event: meta    — PII masking info (sent first)
      - event: chunk   — each unmasked text chunk
      - event: done    — stream complete
      - event: error   — on failure
    """

    async def event_stream():
        detector: PiiDetector = request.app.state.pii_detector
        store: MappingStore = request.app.state.mapping_store
        llm: LlmClient = request.app.state.llm_client

        # Step 1: Detect PII and mask
        loop = asyncio.get_running_loop()
        masking_result = await loop.run_in_executor(
            None,
            partial(detector.mask, body.prompt, language=body.language),
        )

        request_id = await store.save(masking_result.mapping)

        # Log masked request
        log_masked_request(
            request_id=request_id,
            masked_prompt=masking_result.masked_text,
            pii_count=len(masking_result.mapping),
            pii_placeholders=list(masking_result.mapping.keys()),
            endpoint="/gateway/stream",
        )

        # Send meta event with masking info
        meta = json.dumps(
            {
                "request_id": request_id,
                "masked_prompt": masking_result.masked_text,
                "pii_detected": masking_result.mapping,
            },
            ensure_ascii=False,
        )
        yield f"event: meta\ndata: {meta}\n\n"

        # Step 2: Stream from LLM with real-time unmasking
        raw_chunks: list[str] = []
        try:
            if body.unmask_response and masking_result.mapping:
                unmasker = detector.create_stream_unmasker(
                    masking_result.mapping
                )
                async for chunk in llm.stream_generate(
                    masking_result.masked_text
                ):
                    raw_chunks.append(chunk)
                    text = unmasker.feed(chunk)
                    if text:
                        data = json.dumps(
                            {"text": text}, ensure_ascii=False
                        )
                        yield f"event: chunk\ndata: {data}\n\n"

                # Flush remaining buffer
                remaining = unmasker.flush()
                if remaining:
                    data = json.dumps(
                        {"text": remaining}, ensure_ascii=False
                    )
                    yield f"event: chunk\ndata: {data}\n\n"
            else:
                async for chunk in llm.stream_generate(
                    masking_result.masked_text
                ):
                    raw_chunks.append(chunk)
                    data = json.dumps({"text": chunk}, ensure_ascii=False)
                    yield f"event: chunk\ndata: {data}\n\n"

        except Exception as e:
            logger.error("LLM streaming failed: %s", e)
            yield f"event: error\ndata: {{\"error\": \"LLM streaming failed\"}}\n\n"
            return
        finally:
            # Log masked response
            if raw_chunks:
                log_masked_response(
                    request_id=request_id,
                    masked_response="".join(raw_chunks),
                    endpoint="/gateway/stream",
                )
            await store.delete(request_id)

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
