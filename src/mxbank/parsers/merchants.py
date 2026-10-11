"""Comercios conocidos: se conserva solo el nombre normalizado, sin sucursal ni ciudad.

Los bancos pegan sucursal y ciudad al comercio (``<COMERCIO><SUCURSAL> <CIUDAD>``); eso es
un cuasi-identificador (revela dónde vive o se mueve el titular), ver docs/04 §7.
"""

from __future__ import annotations

# prefijo normalizado tal como aparece en el estado de cuenta -> nombre canónico
MERCHANTS: dict[str, str] = {
    "OXXO": "OXXO",
    "7 ELEVEN": "7-ELEVEN",
    "7-ELEVEN": "7-ELEVEN",
    "SEVEN ELEVEN": "7-ELEVEN",
    "WALMART": "WALMART",
    "WAL MART": "WALMART",
    "WAL-MART": "WALMART",
    "BODEGA AURRERA": "BODEGA AURRERA",
    "SAMS CLUB": "SAMS CLUB",
    "SAMS": "SAMS CLUB",
    "COSTCO": "COSTCO",
    "SORIANA": "SORIANA",
    "CHEDRAUI": "CHEDRAUI",
    "LA COMER": "LA COMER",
    "FARMACIAS GUADALAJARA": "FARMACIAS GUADALAJARA",
    "FARM GUADALAJARA": "FARMACIAS GUADALAJARA",
    "FARMACIA DEL AHORRO": "FARMACIAS DEL AHORRO",
    "FARMACIAS DEL AHORRO": "FARMACIAS DEL AHORRO",
    "FARMACIAS SIMILARES": "FARMACIAS SIMILARES",
    "LIVERPOOL": "LIVERPOOL",
    "COPPEL": "COPPEL",
    "ELEKTRA": "ELEKTRA",
    "HOME DEPOT": "HOME DEPOT",
    "STARBUCKS": "STARBUCKS",
    "PEMEX": "PEMEX",
    "AMAZON": "AMAZON",
    "AMZN": "AMAZON",
    "MERCADOPAGO": "MERCADO PAGO",
    "MERCADO PAGO": "MERCADO PAGO",
    "MERPAGO": "MERCADO PAGO",
    "MERCADOLIBRE": "MERCADO LIBRE",
    "MERCADO LIBRE": "MERCADO LIBRE",
    "UBER EATS": "UBER EATS",
    "UBER": "UBER",
    "DIDI": "DIDI",
    "RAPPI": "RAPPI",
    "NETFLIX": "NETFLIX",
    "SPOTIFY": "SPOTIFY",
    "GOOGLE": "GOOGLE",
    "APPLE": "APPLE",
    "TELCEL": "TELCEL",
    "TELMEX": "TELMEX",
    "CFE": "CFE",
}

_ORDERED = sorted(MERCHANTS.items(), key=lambda kv: len(kv[0]), reverse=True)


def match_merchant(ntext: str) -> str | None:
    """Comercio canónico si el texto normalizado empieza con un prefijo conocido.

    Los prefijos cortos (<= 4 letras) exigen separador después para evitar falsos positivos.
    """
    for prefix, canonical in _ORDERED:
        if ntext.startswith(prefix):
            rest = ntext[len(prefix):]
            if len(prefix) > 4 or not rest or not rest[0].isalpha() or prefix == "OXXO":
                return canonical
    return None
