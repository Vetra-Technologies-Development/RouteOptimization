-- LoadBoard Network Loads Table Schema
-- Create this table in your Supabase database

CREATE TABLE IF NOT EXISTS loadboard_loads (
    -- Primary key
    unique_id TEXT PRIMARY KEY,
    
    -- Account information
    user_id TEXT,
    user_name TEXT,
    company_name TEXT,
    contact_name TEXT,
    contact_phone TEXT,
    contact_fax TEXT,
    contact_email TEXT,
    mc_number TEXT,
    dot_number TEXT,
    
    -- Load identification
    tracking_number TEXT NOT NULL,
    
    -- Origin information
    origin_city TEXT,
    origin_state TEXT,
    origin_postcode TEXT,
    origin_county TEXT,
    origin_country TEXT,
    origin_latitude DOUBLE PRECISION,
    origin_longitude DOUBLE PRECISION,
    origin_pickup_date TIMESTAMPTZ,
    origin_pickup_date_end TIMESTAMPTZ,
    
    -- Destination information
    destination_city TEXT,
    destination_state TEXT,
    destination_postcode TEXT,
    destination_county TEXT,
    destination_country TEXT,
    destination_latitude DOUBLE PRECISION,
    destination_longitude DOUBLE PRECISION,
    destination_delivery_date TIMESTAMPTZ,
    destination_delivery_date_end TIMESTAMPTZ,
    
    -- Equipment and load details
    equipment TEXT, -- JSON string of equipment types
    full_load BOOLEAN DEFAULT FALSE,
    length DOUBLE PRECISION,
    width DOUBLE PRECISION,
    height DOUBLE PRECISION,
    weight DOUBLE PRECISION,
    
    -- Load metadata
    load_count INTEGER DEFAULT 1,
    stops INTEGER DEFAULT 0,
    distance DOUBLE PRECISION,
    rate TEXT,
    comment TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index on user_id for faster queries
CREATE INDEX IF NOT EXISTS idx_loadboard_loads_user_id ON loadboard_loads(user_id);

-- Create index on tracking_number for faster lookups
CREATE INDEX IF NOT EXISTS idx_loadboard_loads_tracking_number ON loadboard_loads(tracking_number);

-- Create index on origin/destination for location-based queries
CREATE INDEX IF NOT EXISTS idx_loadboard_loads_origin ON loadboard_loads(origin_city, origin_state);
CREATE INDEX IF NOT EXISTS idx_loadboard_loads_destination ON loadboard_loads(destination_city, destination_state);

-- Create index on dates for time-based queries
CREATE INDEX IF NOT EXISTS idx_loadboard_loads_origin_date ON loadboard_loads(origin_pickup_date);
CREATE INDEX IF NOT EXISTS idx_loadboard_loads_destination_date ON loadboard_loads(destination_delivery_date);

-- Enable Row Level Security (RLS) if needed
-- ALTER TABLE loadboard_loads ENABLE ROW LEVEL SECURITY;

-- Example RLS policy (adjust based on your needs):
-- CREATE POLICY "Users can view their own loads" ON loadboard_loads
--     FOR SELECT USING (auth.uid()::text = user_id);

-- CREATE POLICY "Users can insert their own loads" ON loadboard_loads
--     FOR INSERT WITH CHECK (auth.uid()::text = user_id);

-- CREATE POLICY "Users can update their own loads" ON loadboard_loads
--     FOR UPDATE USING (auth.uid()::text = user_id);

-- CREATE POLICY "Users can delete their own loads" ON loadboard_loads
--     FOR DELETE USING (auth.uid()::text = user_id);

