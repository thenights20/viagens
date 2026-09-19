#!/usr/bin/env python3
"""Empty Leg Hunter: coleta ofertas reais de APIs configuradas e publica JSON para o painel."""
import json, os, urllib.request, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

OUT=Path("docs/data/empty-legs.json")

def get_json(url, headers=None):
    req=urllib.request.Request(url, headers=headers or {"User-Agent":"viagens-empty-leg-hunter/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def code(v):
    if isinstance(v, dict):
        return (v.get("iata") or v.get("icao") or v.get("code") or v.get("name") or "").upper()
    return str(v or "").upper()

def num(v):
    try: return float(str(v).replace(",",""))
    except: return None

def normalize(row, source):
    origin=code(row.get("origin") or row.get("from") or row.get("start_airport") or row.get("startAirport"))
    dest=code(row.get("destination") or row.get("to") or row.get("end_airport") or row.get("endAirport"))
    price=num(row.get("price") or row.get("seller_price") or row.get("sellerPrice") or row.get("total_price"))
    currency=row.get("currency") or row.get("sellerPriceCurrency") or row.get("price_currency") or ""
    aircraft=row.get("aircraft") or row.get("aircraft_type") or row.get("type") or ""
    if isinstance(aircraft,dict): aircraft=aircraft.get("name") or aircraft.get("type") or aircraft.get("model") or ""
    seats=row.get("seats") or row.get("passengers") or row.get("pax") or ""
    date=row.get("date") or row.get("departure") or row.get("departure_date") or row.get("startDate") or row.get("start_date") or ""
    url=row.get("url") or row.get("href") or row.get("booking_url") or ""
    if not origin or not dest: return None
    return {"origin":origin,"destination":dest,"date":date,"price":price,"currency":currency,
            "aircraft":str(aircraft),"seats":seats,"source":source,"url":url}

def rows_from(payload):
    if isinstance(payload,list): return payload
    if not isinstance(payload,dict): return []
    for k in ("results","data","empty_legs","items"):
        if isinstance(payload.get(k),list): return payload[k]
    return []

offers=[]; status={}

# Aviapages: endpoint oficial /v3/empty_legs/. Requer token da conta.
token=os.getenv("AVIAPAGES_API_KEY","").strip()
if token:
    try:
        p=get_json("https://api.aviapages.com/v3/empty_legs/",{"Authorization":f"Token {token}","User-Agent":"viagens-empty-leg-hunter/1.0"})
        for x in rows_from(p):
            n=normalize(x,"Aviapages")
            if n: offers.append(n)
        status["Aviapages"]={"ok":True,"items":len(rows_from(p))}
    except Exception as e: status["Aviapages"]={"ok":False,"error":str(e)[:180]}
else: status["Aviapages"]={"ok":False,"error":"API key não configurada"}

# Fontes extras compatíveis com JSON podem ser ligadas por Secrets sem alterar o código.
# Formato: URL retornando lista/results/data; token opcional em Authorization.
for i in range(1,4):
    url=os.getenv(f"EMPTY_LEG_SOURCE_{i}_URL","").strip()
    if not url: continue
    name=os.getenv(f"EMPTY_LEG_SOURCE_{i}_NAME",f"Fonte {i}")
    auth=os.getenv(f"EMPTY_LEG_SOURCE_{i}_AUTH","").strip()
    try:
        h={"User-Agent":"viagens-empty-leg-hunter/1.0"}
        if auth: h["Authorization"]=auth
        p=get_json(url,h); rr=rows_from(p)
        for x in rr:
            n=normalize(x,name)
            if n: offers.append(n)
        status[name]={"ok":True,"items":len(rr)}
    except Exception as e: status[name]={"ok":False,"error":str(e)[:180]}

# remove duplicados e ordena: preços conhecidos primeiro, menor preço primeiro
uniq={}
for x in offers:
    key=(x["source"],x["origin"],x["destination"],str(x["date"]),x["price"],x["currency"])
    uniq[key]=x
offers=list(uniq.values())
offers.sort(key=lambda x:(x["price"] is None, x["price"] if x["price"] is not None else 10**18, x["origin"], x["destination"]))

payload={"version":"1.0.0","generated_at":datetime.now(timezone.utc).isoformat(),
         "offer_count":len(offers),"offers":offers,"sources":status}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
print(f"Empty Leg Hunter: {len(offers)} ofertas")
