-- Scripts SQL pour Supabase (à exécuter dans l'éditeur SQL)

-- Table des événements
CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    page TEXT,
    user_id TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Table des compteurs
CREATE TABLE counters (
    id INTEGER PRIMARY KEY DEFAULT 1,
    total_users INTEGER NOT NULL DEFAULT 1000,
    total_shares INTEGER NOT NULL DEFAULT 10000,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Fonctions RPC sécurisées (utilisables avec la clé anon)
CREATE OR REPLACE FUNCTION increment_shares()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    new_count INTEGER;
BEGIN
    UPDATE counters SET total_shares = total_shares + 1, updated_at = NOW() WHERE id = 1 RETURNING total_shares INTO new_count;
    RETURN new_count;
END;
$$;

CREATE OR REPLACE FUNCTION increment_users()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    new_count INTEGER;
BEGIN
    UPDATE counters SET total_users = total_users + 1, updated_at = NOW() WHERE id = 1 RETURNING total_users INTO new_count;
    RETURN new_count;
END;
$$;

-- Table des bookmakers
CREATE TABLE bookmakers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    logo TEXT,
    url TEXT
);

-- Table des bonus
CREATE TABLE bonus (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    image TEXT,
    link TEXT,
    start_date DATE,
    end_date DATE,
    active BOOLEAN DEFAULT TRUE
);

-- Politiques RLS (à configurer selon vos besoins)
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE counters ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookmakers ENABLE ROW LEVEL SECURITY;
ALTER TABLE bonus ENABLE ROW LEVEL SECURITY;

-- Permettre l'insertion anonyme dans events (nécessaire pour le frontend)
CREATE POLICY "Allow anonymous insert" ON events FOR INSERT WITH CHECK (true);
-- Permettre la sélection anonyme des compteurs
CREATE POLICY "Allow anonymous select" ON counters FOR SELECT USING (true);
-- Permettre la sélection anonyme des bookmakers et bonus
CREATE POLICY "Allow anonymous select" ON bookmakers FOR SELECT USING (true);
CREATE POLICY "Allow anonymous select" ON bonus FOR SELECT USING (true);

-- Insertion initiale du compteur
INSERT INTO counters (id, total_users, total_shares) VALUES (1, 1000, 10000) ON CONFLICT (id) DO NOTHING;