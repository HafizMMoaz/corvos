SELECT '--- USERS ---';
SELECT id || ' | ' || email || ' | active=' || is_active || ' | super=' || is_superuser FROM "user" ORDER BY id;
SELECT '--- CONNECTIONS ---';
SELECT id || ' | provider=' || COALESCE(provider, '?') || ' | user=' || COALESCE(user_id::text, 'global') || ' | enabled=' || enabled FROM connections ORDER BY id;
SELECT '--- MODELS (first 20) ---';
SELECT connection_id || ' | ' || model_id || ' | enabled=' || enabled FROM models ORDER BY connection_id, model_id LIMIT 20;
SELECT '--- WORKSPACES ---';
SELECT id || ' | ' || COALESCE(name, '?') FROM workspaces ORDER BY id LIMIT 5;
