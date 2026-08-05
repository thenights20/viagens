from pathlib import Path

path = Path("app_v03.py")
text = path.read_text(encoding="utf-8")

old = '''                        query = create_query(
                            flights=[
                                FlightQuery(date=dep.isoformat(), from_airport=origin, to_airport=destination, max_stops=params["max_stops"]),
                                FlightQuery(date=ret.isoformat(), from_airport=destination, to_airport=origin, max_stops=params["max_stops"]),
                            ],
                            seat=params["seat"], trip="round-trip",
                            passengers=Passengers(adults=params["adults"]), language="pt-BR",
                            currency=params["currency"], max_price=params["max_price"] or None,
                        )
'''

new = '''                        import inspect

                        def supported_kwargs(func, values):
                            allowed = inspect.signature(func).parameters
                            return {
                                key: value
                                for key, value in values.items()
                                if key in allowed and value is not None
                            }

                        outbound = FlightQuery(**supported_kwargs(FlightQuery, {
                            "date": dep.isoformat(),
                            "from_airport": origin,
                            "to_airport": destination,
                            "max_stops": params["max_stops"],
                        }))
                        inbound = FlightQuery(**supported_kwargs(FlightQuery, {
                            "date": ret.isoformat(),
                            "from_airport": destination,
                            "to_airport": origin,
                            "max_stops": params["max_stops"],
                        }))

                        query = create_query(**supported_kwargs(create_query, {
                            "flights": [outbound, inbound],
                            "seat": params["seat"],
                            "trip": "round-trip",
                            "passengers": Passengers(adults=params["adults"]),
                            "language": "pt-BR",
                            "currency": params["currency"],
                            "max_price": params["max_price"] or None,
                        }))
'''

if old not in text:
    raise SystemExit("Bloco esperado não encontrado em app_v03.py; patch não aplicado.")

text = text.replace(old, new)
text = text.replace('APP_VERSION = "0.3.0"', 'APP_VERSION = "0.3.1"')
path.write_text(text, encoding="utf-8")
print("Compatibilidade fast-flights aplicada à v0.3.1.")
