"""Supabase service for database operations."""
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class SupabaseService:
    """Service for Supabase database operations."""
    
    def __init__(self, client):
        """Initialize with Supabase client."""
        self.client = client
    
    def save_load(self, account_data: Dict, load_data: Dict) -> bool:
        """Save or update a load in Supabase."""
        if not self.client:
            logger.error("Supabase client not initialized")
            return False
        
        try:
            # Create unique identifier: user_id + tracking_number
            user_id = account_data.get('userID') or account_data.get('userid')
            tracking_number = load_data.get('tracking_number')
            
            if not user_id or not tracking_number:
                logger.error("Missing user_id or tracking_number")
                return False
            
            unique_id = f"{user_id}_{tracking_number}"
            
            # Prepare load record for Supabase - include all fields from XML
            load_record = {
                'unique_id': unique_id,
                'user_id': user_id,
                'user_name': account_data.get('username'),
                'tracking_number': tracking_number,
                'company_name': account_data.get('companyname'),
                'contact_name': account_data.get('contactname'),
                'contact_phone': account_data.get('contactphone'),
                'contact_fax': account_data.get('contactfax'),
                'contact_email': account_data.get('contactemail'),
                'mc_number': account_data.get('mcnumber'),
                'dot_number': account_data.get('dotnumber'),
                # Origin fields
                'origin_city': load_data.get('origin_city'),
                'origin_state': load_data.get('origin_state'),
                'origin_postcode': load_data.get('origin_postcode'),
                'origin_county': load_data.get('origin_county'),
                'origin_country': load_data.get('origin_country'),
                'origin_latitude': load_data.get('origin_latitude'),
                'origin_longitude': load_data.get('origin_longitude'),
                'origin_pickup_date': load_data.get('origin_pickup_date').isoformat() if load_data.get('origin_pickup_date') else None,
                'origin_pickup_date_end': load_data.get('origin_pickup_date_end').isoformat() if load_data.get('origin_pickup_date_end') else None,
                # Destination fields
                'destination_city': load_data.get('destination_city'),
                'destination_state': load_data.get('destination_state'),
                'destination_postcode': load_data.get('destination_postcode'),
                'destination_county': load_data.get('destination_county'),
                'destination_country': load_data.get('destination_country'),
                'destination_latitude': load_data.get('destination_latitude'),
                'destination_longitude': load_data.get('destination_longitude'),
                'destination_delivery_date': load_data.get('destination_delivery_date').isoformat() if load_data.get('destination_delivery_date') else None,
                'destination_delivery_date_end': load_data.get('destination_delivery_date_end').isoformat() if load_data.get('destination_delivery_date_end') else None,
                # Equipment and load size
                'equipment': str(load_data.get('equipment', [])),
                'full_load': load_data.get('full_load', False),
                'length': load_data.get('length'),
                'width': load_data.get('width'),
                'height': load_data.get('height'),
                'weight': load_data.get('weight'),
                # Other fields
                'load_count': load_data.get('load_count', 1),
                'stops': load_data.get('stops', 0),
                'distance': load_data.get('distance'),
                'rate': load_data.get('rate'),
                'comment': load_data.get('comment'),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Remove None values for optional fields, but keep required fields
            # Required fields: unique_id, tracking_number, user_id
            required_fields = {'unique_id', 'tracking_number', 'user_id'}
            load_record = {k: v for k, v in load_record.items() if v is not None or k in required_fields}
            
            # Upsert (insert or update) the load
            result = self.client.table('loadboard_loads').upsert(load_record, on_conflict='unique_id').execute()
            logger.info(f"Saved load {unique_id} to Supabase")
            return True
            
        except Exception as e:
            logger.error(f"Error saving load to Supabase: {e}", exc_info=True)
            return False
    
    def remove_load(self, account_data: Dict, load_data: Dict) -> Tuple[bool, str]:
        """Remove a load from Supabase."""
        if not self.client:
            logger.error("Supabase client not initialized")
            return False, "Supabase not configured"
        
        try:
            # Create unique identifier: user_id + tracking_number
            user_id = account_data.get('userID') or account_data.get('userid')
            tracking_number = load_data.get('tracking_number')
            
            if not user_id or not tracking_number:
                logger.error("Missing user_id or tracking_number")
                return False, "Missing user_id or tracking_number"
            
            unique_id = f"{user_id}_{tracking_number}"
            
            # Check if load exists
            existing = self.client.table('loadboard_loads').select('unique_id').eq('unique_id', unique_id).limit(1).execute()
            if not existing.data:
                logger.warning(f"Load {unique_id} does not exist")
                return False, f"ID does not exist: {unique_id}"

            # Remove load from Supabase
            self.client.table('loadboard_loads').delete().eq('unique_id', unique_id).execute()
            logger.info(f"Removed load {unique_id} from Supabase")
            return True, "Removed"
            
        except Exception as e:
            logger.error(f"Error removing load from Supabase: {e}", exc_info=True)
            return False, f"Error: {str(e)}"

