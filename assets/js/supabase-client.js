// assets/js/supabase-client.js - Client Supabase pour le frontend
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';

const supabaseUrl = 'https://votre-projet.supabase.co';
const supabaseAnonKey = 'votre-clé-anon';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);