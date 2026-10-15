import { NextRequest, NextResponse } from "next/server";

// In-memory cache for recent queries to respect Nominatim rate limits (1 req/sec) and provide instant response
const cache = new Map<string, { data: unknown; expiresAt: number }>();
const CACHE_TTL_MS = 1000 * 60 * 10; // 10 minutes cache

function getCached(key: string) {
  const item = cache.get(key);
  if (!item) return null;
  if (Date.now() > item.expiresAt) {
    cache.delete(key);
    return null;
  }
  return item.data;
}

function setCached(key: string, data: unknown) {
  if (cache.size > 200) {
    const firstKey = cache.keys().next().value;
    if (firstKey) cache.delete(firstKey);
  }
  cache.set(key, { data, expiresAt: Date.now() + CACHE_TTL_MS });
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const q = searchParams.get("q");
  const lat = searchParams.get("lat");
  const lon = searchParams.get("lon");

  try {
    // 1. Search Autocomplete
    if (q && q.trim().length >= 3) {
      const cacheKey = `search:${q.trim().toLowerCase()}`;
      const cached = getCached(cacheKey);
      if (cached) {
        return NextResponse.json(cached);
      }

      const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(
        q.trim()
      )}&format=json&addressdetails=1&limit=6&countrycodes=in`;

      const response = await fetch(url, {
        headers: {
          "Accept-Language": "en",
          "User-Agent": "RouteX-Logistics-Platform/1.0 (contact: support@routex.nerlink.in)",
        },
      });

      if (!response.ok) {
        return NextResponse.json({ error: "Geocoding service unavailable" }, { status: response.status });
      }

      const data = await response.json();
      setCached(cacheKey, data);
      return NextResponse.json(data);
    }

    // 2. Reverse Geocoding
    if (lat && lon) {
      const parsedLat = parseFloat(lat);
      const parsedLon = parseFloat(lon);
      if (isNaN(parsedLat) || isNaN(parsedLon)) {
        return NextResponse.json({ error: "Invalid coordinates" }, { status: 400 });
      }

      const cacheKey = `reverse:${parsedLat.toFixed(4)},${parsedLon.toFixed(4)}`;
      const cached = getCached(cacheKey);
      if (cached) {
        return NextResponse.json(cached);
      }

      const url = `https://nominatim.openstreetmap.org/reverse?lat=${parsedLat}&lon=${parsedLon}&format=json&addressdetails=1`;

      const response = await fetch(url, {
        headers: {
          "Accept-Language": "en",
          "User-Agent": "RouteX-Logistics-Platform/1.0 (contact: support@routex.nerlink.in)",
        },
      });

      if (!response.ok) {
        return NextResponse.json({ error: "Reverse geocoding service unavailable" }, { status: response.status });
      }

      const data = await response.json();
      setCached(cacheKey, data);
      return NextResponse.json(data);
    }

    return NextResponse.json({ error: "Missing 'q' or 'lat' and 'lon' query parameters" }, { status: 400 });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Geocoding proxy error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
