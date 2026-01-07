"""LoadBoard Network API router."""
import logging
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.dependencies import get_loadboard_service, is_supabase_enabled

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/loadboard", tags=["LoadBoard Network"])


class XMLRequest(BaseModel):
    """XML request body model."""
    xml: str = Field(
        ...,
        description="XML content in LoadBoard Network format",
        example="""<LBNLoadPostings>
  <PostingAccount>
    <AccountID>12345</AccountID>
    <AccountName>Test Account</AccountName>
  </PostingAccount>
  <PostLoads>
    <Load>
      <TrackingNumber>TRACK001</TrackingNumber>
      <OriginCity>New York</OriginCity>
      <OriginState>NY</OriginState>
      <DestinationCity>Los Angeles</DestinationCity>
      <DestinationState>CA</DestinationState>
    </Load>
  </PostLoads>
</LBNLoadPostings>"""
    )


async def extract_xml_content(request: Request) -> str:
    """Extract XML content from request, handling both JSON and raw XML."""
    content_type = request.headers.get("content-type", "").lower()
    
    # Read body once and cache it
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")
    
    if "application/xml" in content_type or "text/xml" in content_type:
        # Raw XML request
        return body_str
    elif "application/json" in content_type:
        # JSON request with XML string
        try:
            data = json.loads(body_str)
            if isinstance(data, dict) and "xml" in data:
                return data["xml"]
            else:
                raise HTTPException(
                    status_code=400,
                    detail="JSON request must contain 'xml' field with XML content"
                )
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid JSON: {str(e)}. Note: Newlines in XML must be escaped as \\n in JSON strings."
            )
    else:
        # Try to parse as JSON first, then fall back to raw body
        try:
            data = json.loads(body_str)
            if isinstance(data, dict) and "xml" in data:
                return data["xml"]
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        
        # Fall back to raw body (treat as XML)
        return body_str


@router.post(
    "/post_loads",
    response_class=PlainTextResponse,
    summary="Post Loads",
    description="LoadBoard Network Post Loads endpoint. Receives XML POST requests and saves loads to Supabase.\n\n**For Swagger UI:** Send JSON with `{\"xml\": \"<your-xml-here>\"}` (XML must be escaped with \\n for newlines)\n**For raw XML requests:** Send XML directly with `Content-Type: application/xml`\n**For curl with JSON:** Escape newlines as \\n in the JSON string"
)
async def post_loads(
    request: Request
):
    if not is_supabase_enabled():
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured. Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables and install the supabase package."
        )
    
    try:
        # Extract XML content from request (handles both JSON and raw XML)
        xml_content = await extract_xml_content(request)
        
        logger.info(f"Received LoadBoard Network post request: {len(xml_content)} bytes")
        
        # Process request
        loadboard_service = get_loadboard_service()
        response_message, success_count = loadboard_service.process_xml_request(xml_content)
        
        if success_count == 0 and "Error" not in response_message:
            return PlainTextResponse(response_message, status_code=200)
        
        return PlainTextResponse(response_message, status_code=200)
    
    except Exception as e:
        logger.error(f"Error processing LoadBoard Network request: {e}", exc_info=True)
        return PlainTextResponse(f"Error: {str(e)}", status_code=200)


@router.post(
    "/remove_loads",
    response_class=PlainTextResponse,
    summary="Remove Loads",
    description="LoadBoard Network Remove Loads endpoint. Receives XML POST requests and removes loads from Supabase.\n\n**For Swagger UI:** Send JSON with `{\"xml\": \"<your-xml-here>\"}` (XML must be escaped with \\n for newlines)\n**For raw XML requests:** Send XML directly with `Content-Type: application/xml`\n**For curl with JSON:** Escape newlines as \\n in the JSON string"
)
async def remove_loads(
    request: Request
):
    if not is_supabase_enabled():
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured. Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables and install the supabase package."
        )
    
    try:
        # Extract XML content from request (handles both JSON and raw XML)
        xml_content = await extract_xml_content(request)
        
        logger.info(f"Received LoadBoard Network remove request: {len(xml_content)} bytes")
        
        # Process request
        loadboard_service = get_loadboard_service()
        response_message, success_count = loadboard_service.process_xml_request(xml_content)
        
        if success_count == 0 and "Error" not in response_message:
            return PlainTextResponse(response_message, status_code=200)
        
        return PlainTextResponse(response_message, status_code=200)
    
    except Exception as e:
        logger.error(f"Error processing LoadBoard Network request: {e}", exc_info=True)
        return PlainTextResponse(f"Error: {str(e)}", status_code=200)

