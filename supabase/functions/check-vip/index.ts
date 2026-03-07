import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

serve(async (req) => {
  const { code, userId } = await req.json()
  const clientIp = req.headers.get('x-forwarded-for') || ''

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_ANON_KEY')!
  )

  const { data, error } = await supabase
    .from('vip_users')
    .select('*')
    .eq('vip_code', code)
    .eq('user_id', userId)
    .single()

  if (error || !data) {
    return new Response(JSON.stringify({ valid: false }), { status: 401 })
  }

  // Vérifier l'IP (si enregistrée)
  if (data.ip_address && data.ip_address !== clientIp) {
    return new Response(JSON.stringify({ valid: false, reason: 'IP mismatch' }), { status: 403 })
  }

  const now = new Date()
  const expires = new Date(data.expires_at)
  const valid = data.is_active && expires > now

  return new Response(JSON.stringify({ valid, expires_at: data.expires_at }), {
    headers: { 'Content-Type': 'application/json' }
  })
})