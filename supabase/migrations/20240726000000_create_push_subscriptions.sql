-- Migration: Create Push Subscriptions Table
CREATE TABLE public.push_subscriptions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS
ALTER TABLE public.push_subscriptions ENABLE ROW LEVEL SECURITY;

-- Grant access to roles
GRANT ALL ON TABLE public.push_subscriptions TO postgres, anon, authenticated, service_role;

-- Add RLS Policies
CREATE POLICY "Allow public full access to push_subscriptions" ON public.push_subscriptions
    FOR ALL TO public
    USING (true)
    WITH CHECK (true);
