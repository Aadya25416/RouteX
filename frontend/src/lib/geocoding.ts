export interface GeocodeSuggestion {
  id: string;
  name: string;
  secondaryText: string;
  displayName: string;
  lat: number;
  lon: number;
}

export interface NominatimAddress {
  road?: string;
  suburb?: string;
  hamlet?: string;
  village?: string;
  town?: string;
  city?: string;
  county?: string;
  state_district?: string;
  state?: string;
  country?: string;
  postcode?: string;
  [key: string]: string | undefined;
}

export interface NominatimItem {
  place_id?: number | string;
  osm_id?: number | string;
  name?: string;
  display_name?: string;
  lat: string | number;
  lon: string | number;
  address?: NominatimAddress;
}

/**
 * Format address into a prominent place name and secondary location string
 */
export function parseNominatimResult(item: NominatimItem): GeocodeSuggestion {
  const addr = item.address || {};
  const lat = typeof item.lat === "number" ? item.lat : parseFloat(item.lat);
  const lon = typeof item.lon === "number" ? item.lon : parseFloat(item.lon);

  // Primary place name: Specific town, village, landmark, road or name
  let name = item.name;
  if (!name || name.trim().length === 0) {
    name = addr.road || addr.village || addr.town || addr.city || addr.suburb || "Location";
  }

  // Secondary text: District, State, Country
  const secondaryParts: string[] = [];
  const locality = addr.county || addr.state_district || (addr.city !== name ? addr.city : undefined);
  if (locality) secondaryParts.push(locality);
  if (addr.state) secondaryParts.push(addr.state);
  if (addr.country && addr.country !== "India") secondaryParts.push(addr.country);

  const secondaryText = secondaryParts.join(", ") || (item.display_name?.split(",").slice(1, 4).join(", ") || "India");

  const displayName = `${name}, ${secondaryText}`;

  return {
    id: String(item.place_id || item.osm_id || `${lat},${lon}`),
    name,
    secondaryText,
    displayName,
    lat,
    lon,
  };
}

/**
 * Format reverse geocoding result into human-readable label
 * e.g. "Near Bomdila, West Kameng, Arunachal Pradesh"
 */
export function formatReverseGeocodeAddress(
  item: NominatimItem | null,
  lat: number,
  lon: number
): string {
  if (!item || !item.address) {
    return `Selected location (${lat.toFixed(4)}, ${lon.toFixed(4)})`;
  }

  const addr = item.address;
  const place = addr.road || addr.hamlet || addr.village || addr.town || addr.city || addr.suburb || item.name;
  const district = addr.state_district || addr.county || (addr.city !== place ? addr.city : undefined);
  const state = addr.state;

  const parts: string[] = [];
  if (place) {
    if (place.startsWith("NH") || place.startsWith("SH") || place.includes("Highway")) {
      parts.push(place);
    } else {
      parts.push(`Near ${place}`);
    }
  }

  if (district && !parts.some((p) => p.includes(district))) {
    parts.push(district);
  }

  if (state && !parts.some((p) => p.includes(state))) {
    parts.push(state);
  }

  if (parts.length > 0) {
    return parts.join(", ");
  }

  if (item.display_name) {
    return item.display_name.split(",").slice(0, 3).join(", ");
  }

  return `Selected location (${lat.toFixed(4)}, ${lon.toFixed(4)})`;
}

/**
 * Search locations with Next.js API proxy and client-side fallback
 */
export async function searchLocations(
  query: string,
  signal?: AbortSignal
): Promise<GeocodeSuggestion[]> {
  const trimmed = query.trim();
  if (trimmed.length < 3) return [];

  // 1. Try local Next.js API proxy
  try {
    const res = await fetch(`/api/geocode?q=${encodeURIComponent(trimmed)}`, { signal });
    if (res.ok) {
      const items: NominatimItem[] = await res.json();
      if (Array.isArray(items)) {
        return items.map(parseNominatimResult);
      }
    }
  } catch (err: unknown) {
    if (signal?.aborted) throw err;
    console.warn("Local geocode proxy failed, falling back to direct Nominatim:", err);
  }

  // 2. Direct fallback to OpenStreetMap Nominatim
  const directUrl = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(
    trimmed
  )}&format=json&addressdetails=1&limit=6&countrycodes=in`;

  const fallbackRes = await fetch(directUrl, { signal });
  if (!fallbackRes.ok) {
    throw new Error("Unable to search locations at this time");
  }

  const fallbackItems: NominatimItem[] = await fallbackRes.json();
  return Array.isArray(fallbackItems) ? fallbackItems.map(parseNominatimResult) : [];
}

/**
 * Reverse geocode coordinates to human-readable address
 */
export async function reverseGeocodeCoordinates(
  lat: number,
  lon: number,
  signal?: AbortSignal
): Promise<string> {
  // 1. Try local Next.js API proxy
  try {
    const res = await fetch(`/api/geocode?lat=${lat}&lon=${lon}`, { signal });
    if (res.ok) {
      const data: NominatimItem = await res.json();
      return formatReverseGeocodeAddress(data, lat, lon);
    }
  } catch (err: unknown) {
    if (signal?.aborted) throw err;
    console.warn("Local reverse geocode proxy failed, falling back to direct:", err);
  }

  // 2. Fallback to direct Nominatim
  try {
    const directUrl = `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json&addressdetails=1`;
    const fallbackRes = await fetch(directUrl, { signal });
    if (fallbackRes.ok) {
      const data: NominatimItem = await fallbackRes.json();
      return formatReverseGeocodeAddress(data, lat, lon);
    }
  } catch (err: unknown) {
    if (signal?.aborted) throw err;
  }

  // 3. Fallback when geocoding is unavailable
  return `Selected location (${lat.toFixed(4)}, ${lon.toFixed(4)})`;
}
