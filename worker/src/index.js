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

    // Write endpoint using Worker KV binding (bypasses REST API rate limits)
    if (path === 'sync' && request.method === 'POST') {
        return handleSync(event);
    }
    
    // Resolve slug to numeric series ID
    if (path.startsWith('series:id:')) {
        const slug = decodeURIComponent(path.slice(10));
        const allSeries = await MANHWA_KV.get('all_series', { type: 'json' });
        if (allSeries && allSeries.series) {
            const series = allSeries.series.find(s => s.slug === slug);
            if (series) {
                const data = await MANHWA_KV.get('series:' + series.id, { type: 'json' });
                if (data) {
                    return new Response(JSON.stringify(data), {
                        headers: {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*',
                            'Cache-Control': 'public, max-age=300'
                        }
                    });
                }
            }
        }
        return new Response(
            JSON.stringify({ error: 'Not found', slug }),
            { status: 404, headers: { 'Content-Type': 'application/json' } }
        );
    }
    
    const key = path;
    if (!key || key === 'index.html') {
        return fetch(request);
    }
    
    try {
        const value = await MANHWA_KV.get(key, { type: 'json' });
        if (value === null) {
            return new Response(
                JSON.stringify({ error: 'Not found', key }),
                { status: 404, headers: { 'Content-Type': 'application/json' } }
            );
        }
        return new Response(JSON.stringify(value), {
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'public, max-age=300'
            }
        });
    } catch (err) {
        return new Response(
            JSON.stringify({ error: 'Internal error', message: err.message }),
            { status: 500, headers: { 'Content-Type': 'application/json' } }
        );
    }
}

async function handleSync(event) {
    try {
        const body = await event.request.json();
        const chapters = body.chapters || [];
        const all_series = body.all_series || null;
        const batchSize = 100;
        
        let synced = 0;
        let errors = 0;
        const errorDetails = [];
        
        for (let i = 0; i < chapters.length; i += batchSize) {
            const batch = chapters.slice(i, i + batchSize);
            for (const ch of batch) {
                try {
                    await MANHWA_KV.put('chapter:' + ch.id, JSON.stringify(ch));
                    synced++;
                } catch(e) {
                    errors++;
                    if (errorDetails.length < 3) errorDetails.push(e.message || 'unknown');
                }
            }
            if (i + batchSize < chapters.length) {
                await new Promise(r => setTimeout(r, 100));
            }
        }
        
        if (all_series) {
            try {
                await MANHWA_KV.put('all_series', JSON.stringify(all_series));
            } catch(e) {
                errors++;
                errorDetails.push('all_series: ' + e.message);
            }
        }
        
        return new Response(JSON.stringify({
            success: errors === 0,
            synced,
            errors,
            total: chapters.length,
            batches: Math.ceil(chapters.length / batchSize),
            errorDetails
        }), {
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        });
    } catch (err) {
        return new Response(JSON.stringify({
            success: false,
            error: err.message
        }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' }
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
