export default {
    async fetch(request, env) {
        const url = new URL(request.url);
        const key = url.pathname.slice(1); // Remove leading /

        if (!key) {
            return new Response(
                JSON.stringify({ error: "Key required. Use /series:123 or /chapter:456" }),
                { status: 400, headers: { "Content-Type": "application/json" } }
            );
        }

        try {
            const value = await env.MANHWA_KV.get(key, { type: "json" });

            if (value === null) {
                return new Response(
                    JSON.stringify({ error: "Not found", key }),
                    { status: 404, headers: { "Content-Type": "application/json" } }
                );
            }

            return new Response(JSON.stringify(value), {
                headers: {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "public, max-age=300", // 5 min edge cache
                },
            });
        } catch (err) {
            return new Response(
                JSON.stringify({ error: "Internal error", message: err.message }),
                { status: 500, headers: { "Content-Type": "application/json" } }
            );
        }
    },
};
