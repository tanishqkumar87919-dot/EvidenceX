/**
 * EvidenceX Frontend Supabase Client
 * 
 * SECURITY RULE:
 * This client runs in the browser/client-side and MUST ONLY use:
 * - NEXT_PUBLIC_SUPABASE_URL
 * - NEXT_PUBLIC_SUPABASE_ANON_KEY
 * 
 * NEVER import or reference SUPABASE_SERVICE_ROLE_KEY in frontend code!
 */

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

// Runtime security validation
if (typeof window !== 'undefined') {
  // Enforce frontend safety check
  const forbiddenVars = ['SUPABASE_SERVICE_ROLE_KEY', 'DATABASE_URL', 'SEARCH_API_KEY'];
  for (const varName of forbiddenVars) {
    if ((process.env as Record<string, string | undefined>)[varName]) {
      console.error(`[CRITICAL SECURITY WARNING] Backend secret "${varName}" was detected in client-side bundle!`);
    }
  }
}

export const isSupabaseConfigured = (): boolean => {
  return Boolean(supabaseUrl && supabaseAnonKey && !supabaseUrl.includes('your-project-id'));
};

export interface SupabaseClientConfig {
  url: string;
  anonKey: string;
  configured: boolean;
}

export const getSupabaseFrontendConfig = (): SupabaseClientConfig => ({
  url: supabaseUrl,
  anonKey: supabaseAnonKey,
  configured: isSupabaseConfigured(),
});
