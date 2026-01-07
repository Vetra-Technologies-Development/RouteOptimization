"""LoadBoard Network API router."""
import logging
from fastapi import APIRouter, HTTPException
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


@router.post(
    "/post_loads",
    response_class=PlainTextResponse,
    summary="Post Loads",
    description="LoadBoard Network Post Loads endpoint. Receives XML POST requests and saves loads to Supabase.\n\n**For Swagger UI:** Send JSON with `{\"xml\": \"<your-xml-here>\"}`\n**For raw XML requests:** Send XML directly with `Content-Type: application/xml`"
)
async def post_loads(
    xml_request: XMLRequest
):
    if not is_supabase_enabled():
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured. Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables and install the supabase package."
        )
    
    try:
        # Get XML from the request model
        xml_content = xml_request.xml
        
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
    description="LoadBoard Network Remove Loads endpoint. Receives XML POST requests and removes loads from Supabase.\n\n**For Swagger UI:** Send JSON with `{\"xml\": \"<your-xml-here>\"}`\n**For raw XML requests:** Send XML directly with `Content-Type: application/xml`"
)
async def remove_loads(
    xml_request: XMLRequest
):
    if not is_supabase_enabled():
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured. Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables and install the supabase package."
        )
    
    try:
        # Get XML from the request model
        xml_content = xml_request.xml
        
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

