import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { Mistral } from 'https://esm.sh/@mistralai/mistralai@0.1.3'

const MISTRAL_API_KEY = Deno.env.get('MISTRAL_API_KEY')
const SUPABASE_URL = Deno.env.get('SUPABASE_URL')
const SUPABASE_SERVICE_KEY = Deno.env.get('SUPABASE_SERVICE_KEY')

const supabase = createClient(SUPABASE_URL!, SUPABASE_SERVICE_KEY!)
const mistral = new Mistral({ apiKey: MISTRAL_API_KEY })

const SYSTEM_PROMPT = `Tu es un assistant expert en paris sportifs pour Mr XPRONOS. Ta mission est d'aider les utilisateurs à s'inscrire sur les bookmakers, à comprendre les promotions, à obtenir les pronostics du jour et à maximiser leurs gains. Tu es convaincant, professionnel, clair et orienté conversion. Tu encourages l'utilisation des liens partenaires (comme 1xBet, 1win, Betwinner, etc.) lorsque c'est pertinent. Tu parles français.`

serve(async (req) => {
  // CORS
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST', 'Access-Control-Allow-Headers': 'Content-Type' } })
  }

  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 })
  }

  try {
    const { question, user_id } = await req.json()
    if (!question) throw new Error('Question manquante')

    // 1. Recherche full-text dans la FAQ
    const { data: faq, error } = await supabase
      .from('faq')
      .select('id, question, reponse, usage_count')
      .textSearch('question', question, { config: 'french' })
      .limit(1)

    if (error) throw error

    if (faq && faq.length > 0 && faq[0].reponse) {
      // Mise à jour du compteur
      await supabase
        .from('faq')
        .update({ usage_count: faq[0].usage_count + 1 })
        .eq('id', faq[0].id)

      // Enregistrer la conversation
      await supabase
        .from('conversations')
        .insert({ user_id, question, reponse: faq[0].reponse, from_cache: true })

      return new Response(JSON.stringify({ answer: faq[0].reponse, from_cache: true }), {
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
      })
    }

    // 2. Appel à Mistral
    const chatResponse = await mistral.chat.complete({
      model: 'mistral-large-latest',
      messages: [
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content: question }
      ],
      temperature: 0.7,
      max_tokens: 500
    })

    const answer = chatResponse.choices[0].message.content

    // 3. Sauvegarder dans la FAQ
    await supabase
      .from('faq')
      .insert({ question, reponse: answer, usage_count: 1 })

    // 4. Enregistrer la conversation
    await supabase
      .from('conversations')
      .insert({ user_id, question, reponse: answer, from_cache: false })

    return new Response(JSON.stringify({ answer, from_cache: false }), {
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    })

  } catch (err) {
    console.error(err)
    return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' } })
  }
})