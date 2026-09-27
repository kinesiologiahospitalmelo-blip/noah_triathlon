"""
noah_fuel_images.py — Fotos reales para las 5 comidas de NOAH Nutrition
=========================================================================
Cadena de resolución, en este orden:
  1) Asset propio: /static/comidas/<foto_key>.jpg (si Erre sube/genera sus
     propias fotos, van acá y tienen prioridad siempre).
  2) Unsplash API (requiere UNSPLASH_ACCESS_KEY en variables de entorno --
     gratis, 50 requests/hora en el plan demo, alcanza de sobra para esto
     porque se cachea en memoria por búsqueda).
  3) Si no hay API key ni asset propio: no inventa una URL. Devuelve
     disponible=False y el frontend cae al emoji -- nunca una imagen rota.

NO se guarda la key ni la URL de Unsplash en el frontend: todo pasa por
este endpoint del backend, como corresponde.
"""
import os, time

_CACHE = {}  # {query: (url, timestamp)}
_CACHE_TTL_S = 60 * 60 * 24 * 7  # 1 semana -- la foto de "oatmeal breakfast" no cambia de un día a otro

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'comidas')


def _asset_propio(foto_key: str):
    for ext in ('.jpg', '.jpeg', '.png', '.webp'):
        ruta = os.path.join(STATIC_DIR, f'{foto_key}{ext}')
        if os.path.isfile(ruta):
            return f'/static/comidas/{foto_key}{ext}'
    return None


def _unsplash(query: str):
    import requests
    key = os.environ.get('UNSPLASH_ACCESS_KEY')
    if not key:
        return None
    try:
        r = requests.get('https://api.unsplash.com/search/photos',
            params={'query': query, 'per_page': 1, 'orientation': 'squarish'},
            headers={'Authorization': f'Client-ID {key}'}, timeout=8)
        if r.status_code != 200:
            return None
        results = r.json().get('results') or []
        if not results:
            return None
        # 'small' alcanza para una card de 52-80px sin pesar de más
        return results[0]['urls']['small']
    except Exception:
        return None


def resolver_foto(foto_key: str, busqueda: str) -> dict:
    """foto_key: identificador estable (breakfast, lunch, pre_workout...) para buscar asset propio.
    busqueda: texto libre en inglés para Unsplash (ej. 'oatmeal banana breakfast bowl food photography')."""
    ahora = time.time()
    cache_hit = _CACHE.get(foto_key)
    if cache_hit and (ahora - cache_hit[1]) < _CACHE_TTL_S:
        return {'disponible': True, 'url': cache_hit[0], 'fuente': cache_hit[2]}

    propio = _asset_propio(foto_key)
    if propio:
        _CACHE[foto_key] = (propio, ahora, 'propio')
        return {'disponible': True, 'url': propio, 'fuente': 'propio'}

    url = _unsplash(busqueda)
    if url:
        _CACHE[foto_key] = (url, ahora, 'unsplash')
        return {'disponible': True, 'url': url, 'fuente': 'unsplash'}

    return {'disponible': False, 'url': None, 'fuente': None}
