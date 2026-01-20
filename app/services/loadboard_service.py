"""LoadBoard Network service for processing load requests."""
import logging
from typing import Dict, Any, List, Tuple
from app.utils.parsers import parse_lbn_xml
from app.services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)


class LoadBoardService:
    """Service for processing LoadBoard Network requests."""
    
    def __init__(self, supabase_service: SupabaseService):
        """Initialize with Supabase service."""
        self.supabase_service = supabase_service
    
    def process_xml_request(self, xml_content: str) -> Tuple[str, int]:
        """
        Process LoadBoard Network XML request.
        
        Returns:
            Tuple of (response_message, success_count)
        """
        try:
            # Parse XML
            parsed_data = parse_lbn_xml(xml_content)
            
            account_data = parsed_data['account']
            operation = parsed_data['operation']
            loads = parsed_data['loads']
            
            if not loads:
                logger.warning("No loads found in request")
                return "Data format incorrect", 0
            
            success_count = 0
            
            if operation == 'post':
                # Process PostLoads
                for load_data in loads:
                    try:
                        if self.supabase_service.save_load(account_data, load_data):
                            success_count += 1
                    except Exception as e:
                        logger.error(f"Error processing load: {e}", exc_info=True)
                        continue
                
                logger.info(f"Successfully processed {success_count}/{len(loads)} loads")
                return "Successfully posted", success_count
            
            elif operation == 'remove':
                # Process RemoveLoads
                missing_ids: List[str] = []
                for load_data in loads:
                    try:
                        removed, message = self.supabase_service.remove_load(account_data, load_data)
                        if removed:
                            success_count += 1
                        else:
                            if "ID does not exist" in message:
                                missing_ids.append(message.replace("ID does not exist: ", ""))
                    except Exception as e:
                        logger.error(f"Error processing remove load: {e}", exc_info=True)
                        continue
                
                logger.info(f"Successfully removed {success_count}/{len(loads)} loads")
                if missing_ids and success_count == 0:
                    return f"ID does not exist: {', '.join(missing_ids)}", success_count
                if missing_ids:
                    return f"Removed {success_count}, missing: {', '.join(missing_ids)}", success_count
                return "Successfully removed", success_count
            
            else:
                return "Data format incorrect", 0
                
        except ValueError as e:
            logger.error(f"XML parsing error: {e}")
            return f"Data invalid: {str(e)}", 0
        except Exception as e:
            logger.error(f"Error processing LoadBoard Network request: {e}", exc_info=True)
            return f"Error: {str(e)}", 0

