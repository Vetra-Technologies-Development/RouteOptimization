"""Supabase service for database operations."""
import logging
from typing import Optional, Dict, Any
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
            
            # Prepare load record for Supabase
            load_record = {
                'unique_id': unique_id,
                'user_id': user_id,
                'user_name': account_data.get('username'),
                'tracking_number': tracking_number,
                'company_name': account_data.get('companyname'),
                'contact_name': account_data.get('contactname'),
                'contact_phone': account_data.get('contactphone'),
                'contact_email': account_data.get('contactemail'),
                'mc_number': account_data.get('mcnumber'),
                'dot_number': account_data.get('dotnumber'),
                'origin_city': load_data.get('origin_city'),
                'origin_state': load_data.get('origin_state'),
                'origin_postcode': load_data.get('origin_postcode'),
                'origin_latitude': load_data.get('origin_latitude'),
                'origin_longitude': load_data.get('origin_longitude'),
                'origin_pickup_date': load_data.get('origin_pickup_date').isoformat() if load_data.get('origin_pickup_date') else None,
                'destination_city': load_data.get('destination_city'),
                'destination_state': load_data.get('destination_state'),
                'destination_postcode': load_data.get('destination_postcode'),
                'destination_latitude': load_data.get('destination_latitude'),
                'destination_longitude': load_data.get('destination_longitude'),
                'destination_delivery_date': load_data.get('destination_delivery_date').isoformat() if load_data.get('destination_delivery_date') else None,
                'equipment': str(load_data.get('equipment', [])),
                'full_load': load_data.get('full_load', False),
                'length': load_data.get('length'),
                'width': load_data.get('width'),
                'height': load_data.get('height'),
                'weight': load_data.get('weight'),
                'load_count': load_data.get('load_count', 1),
                'stops': load_data.get('stops', 0),
                'distance': load_data.get('distance'),
                'rate': load_data.get('rate'),
                'comment': load_data.get('comment'),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Upsert (insert or update) the load
            result = self.client.table('loads').upsert(load_record, on_conflict='unique_id').execute()
            logger.info(f"Saved load {unique_id} to Supabase")
            return True
            
        except Exception as e:
            logger.error(f"Error saving load to Supabase: {e}", exc_info=True)
            return False
    
    def remove_load(self, account_data: Dict, load_data: Dict) -> bool:
        """Remove a load from Supabase."""
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
            
            # Remove load from Supabase
            result = self.client.table('loads').delete().eq('unique_id', unique_id).execute()
            logger.info(f"Removed load {unique_id} from Supabase")
            return True
            
        except Exception as e:
            logger.error(f"Error removing load from Supabase: {e}", exc_info=True)
            return False

