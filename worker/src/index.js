addEventListener('fetch', event => {
    event.respondWith(handleRequest(event));
});

async function handleRequest(event) {
    const request = event.request;
    const url = new URL(request.url);
    const path = url.pathname.slice(1);
    
    if (path === 'proxy/image') {
        return proxyImage(url.searchParams.get('url'));
    }

    // NEW: Write endpoint using Worker KV binding (bypasses REST API rate limits)
    if (path === 'sync' && request.method === 'POST') {
        return handleSync(request);
    }
    
    const key = path;
    if (!key || key === 'index.html') {
        return fetch(request);
    }
    
    try {
        const value = await MANHWA_KV.get(key, { type: "json" });
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
                "Cache-Control": "public, max-age=300"
            }
        });
    } catch (err) {
        return new Response(
            JSON.stringify({ error: "Internal error", message: err.message }),
            { status: 500, headers: { "Content-Type": "application/json" } }
        );
    }
}

// Worker KV binding sync endpoint — bypasses REST API rate limits
async function handleSync(request) {
    try {
        const body = await request.json();
        const chapters = body.chapters || [];
        const all_series = body.all_series || null;
        const batch_size = body.batch_size || 100;
        
        let synced = 0;
        let errors = 0;
        
        // Write chapters in batches of 100 (each batch = 1 KV operation)
        for (let i = 0; i < chapters.length; i += batch_size) {
            const batch = chapters.slice(i, i + batch_size);
            await Promise.all(batch.map(ch => 
                MANHWA_KV.put(`chapter:${ch.id}`, JSON.stringify(ch))
                    .then(() => synced++)
                    .catch(e => { errors++; console.error(e); })
            ));
        }
        
        // Write all_series metadata
        if (all_series) {
            await MANHWA_KV.put('all_series', JSON.stringify(all_series));
        }
        
        return new Response(JSON.stringify({
            success: true,
            synced,
            errors,
            total: chapters.length,
            batches: Math.ceil(chapters.length / batch_size)
        }), {
            headers: {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        });
    } catch (err) {
        return new Response(JSON.stringify({
            success: false,
            error: err.message
        }), {
            status: 500,
            headers: { "Content-Type": "application/json" }
        });
    }
}

async function proxyImage(imageUrl) {
    if (!imageUrl) {
        return new Response('Missing url parameter', { status: 400 });
    }
    
    const allowedDomains = ['mangadex.org', 'cdn.asurascans.com', 'cdn.mangadex.org'];
    const urlObj = new URL(imageUrl);
    if (!allowedDomains.includes(urlObj.hostname)) {
        return new Response('Domain not allowed', { status: 403 });
    }
    
    try {
        const response = await fetch(imageUrl, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://mangadex.org/',
                'Accept': 'image/*,*/*;q=0.8'
            }
        });
        
        if (!response.ok) {
            return new Response('Image fetch failed', { status: response.status });
        }
        
        const headers = new Headers(response.headers);
        headers.set('Access-Control-Allow-Origin', '*');
        headers.set('Cache-Control', 'public, max-age=86400');
        headers.set('Content-Type', response.headers.get('Content-Type') || 'image/jpeg');
        
        return new Response(response.body, {
            status: 200,
            headers
        });
    } catch (err) {
        return new Response('Proxy error: ' + err.message, { status: 500 });
    }
}
