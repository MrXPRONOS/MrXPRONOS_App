// supabase/functions/ask-assistant/index.ts
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { Mistral } from 'https://esm.sh/@mistralai/mistralai'

// ========== CONFIGURATION ==========
const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
const MISTRAL_API_KEY = Deno.env.get('MISTRAL_API_KEY')!

// Seuil de similarité pour la FAQ (85%)
const SIMILARITY_THRESHOLD = 0.85

// ========== PERSONNALITÉ DE L'ASSISTANT ==========
const BASE_SYSTEM_PROMPT = `
Tu es un assistant expert en paris sportifs pour le site Mr XPRONOS. 
Ta mission :
- Aider les utilisateurs à s'inscrire sur les bookmakers partenaires
- Expliquer les bonus et promotions
- Fournir les pronostics du jour
- Donner des conseils sur les paris (gestion de bankroll, types de paris, double chance, etc.)
- Encourager l'utilisation des liens d'affiliation quand c'est pertinent

Ton ton est professionnel, chaleureux et convaincant. 
Tu réponds toujours en français, de façon claire et précise.
`

// ========== CLIENTS ==========
const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
const mistral = new Mistral({ apiKey: MISTRAL_API_KEY })

// ========== FONCTIONS UTILITAIRES ==========

/** Génère l'embedding d'un texte via Mistral Embed */
async function generateEmbedding(text: string): Promise<number[]> {
  const response = await mistral.embeddings.create({
    model: 'mistral-embed',
    inputs: [text]
  })
  return response.data[0].embedding
}

/** Recherche une question similaire dans la FAQ */
async function findSimilarQuestion(embedding: number[]) {
  const { data, error } = await supabase.rpc('match_faq', {
    query_embedding: embedding,
    match_threshold: SIMILARITY_THRESHOLD,
    match_count: 1
  })
  if (error) throw error
  return data?.[0]
}

/** Incrémente le compteur d'utilisation d'une question FAQ */
async function incrementUsage(faqId: number, currentCount: number) {
  await supabase
    .from('faq')
    .update({ usage_count: currentCount + 1 })
    .eq('id', faqId)
}

/** Récupère les bookmakers et les pronostics du jour pour le contexte */
async function getContextData() {
  // Bookmakers
  const { data: bookmakers, error: bError } = await supabase
    .from('bookmakers')
    .select('name, bonus, affiliate_link')
  if (bError) throw bError

  // Pronostics du jour (format YYYY-MM-DD)
  const today = new Date().toISOString().split('T')[0]
  const { data: pronostics, error: pError } = await supabase
    .from('pronostics')
    .select('match, prediction, odds, competition')
    .eq('date', today)
  if (pError) throw pError

  return { bookmakers, pronostics }
}

/** Construit le prompt système dynamique */
function buildSystemPrompt(bookmakers: any[], pronostics: any[]): string {
  let prompt = BASE_SYSTEM_PROMPT

  if (bookmakers.length > 0) {
    prompt += '\n\n📌 **Nos bookmakers partenaires :**\n'
    bookmakers.forEach(b => {
      prompt += `- ${b.name} : ${b.bonus || 'Bonus exclusif'} – lien : ${b.affiliate_link}\n`
    })
  }

  if (pronostics.length > 0) {
    prompt += '\n\n⚽ **Pronostics du jour :**\n'
    pronostics.forEach(p => {
      prompt += `- ${p.match} : ${p.prediction} (cote ${p.odds}) – ${p.competition}\n`
    })
  } else {
    prompt += '\n\n⚠️ Aucun pronostic disponible aujourd’hui, mais tu peux demander des conseils généraux.\n'
  }

  prompt += '\nRéponds de manière naturelle, comme un expert qui conseille un ami.'
  return prompt
}

// ========== GESTIONNAIRE PRINCIPAL ==========
serve(async (req) => {
  try {
    // Vérification de la méthode
    if (req.method !== 'POST') {
      return new Response('Méthode non autorisée', { status: 405 })
    }

    // Extraction de la question
    const { question } = await req.json()
    if (!question || typeof question !== 'string') {
      return new Response('Question manquante ou invalide', { status: 400 })
    }

    // Étape 1 : Générer l'embedding de la question
    const embedding = await generateEmbedding(question)

    // Étape 2 : Chercher une question similaire
    const similar = await findSimilarQuestion(embedding)
    if (similar) {
      // Incrémenter le compteur en arrière-plan (ne pas attendre)
      incrementUsage(similar.id, similar.usage_count).catch(console.error)
      return new Response(JSON.stringify({ answer: similar.answer }), {
        headers: { 'Content-Type': 'application/json' }
      })
    }

    // Étape 3 : Récupérer le contexte (bookmakers, pronostics)
    const { bookmakers, pronostics } = await getContextData()
    const systemPrompt = buildSystemPrompt(bookmakers, pronostics)

    // Étape 4 : Appeler Mistral (chat)
    const chatResponse = await mistral.chat.complete({
      model: 'mistral-small',
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: question }
      ]
    })
    const answer = chatResponse.choices[0].message.content

    // Étape 5 : Sauvegarder la nouvelle question/réponse dans la FAQ (ne pas attendre)
    supabase
      .from('faq')
      .insert({
        question,
        embedding,
        answer,
        usage_count: 1
      })
      .then()
      .catch(console.error)

    // Étape 6 : Retourner la réponse
    return new Response(JSON.stringify({ answer }), {
      headers: { 'Content-Type': 'application/json' }
    })

  } catch (error) {
    console.error('Erreur dans ask-assistant:', error)
    return new Response(
      JSON.stringify({ error: 'Une erreur interne est survenue.' }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    )
  }
})