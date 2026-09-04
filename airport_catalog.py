AIRPORTS_BY_REGION = {
    "BR-AC — Acre": ["RBR", "CZS"],
    "BR-AL — Alagoas": ["MCZ"],
    "BR-AP — Amapá": ["MCP"],
    "BR-AM — Amazonas": ["MAO", "TBT", "TEF", "TFF", "PIN"],
    "BR-BA — Bahia": ["SSA", "IOS", "BPS", "VDC", "BRA", "LEC"],
    "BR-CE — Ceará": ["FOR", "JDO", "JJD"],
    "BR-DF — Distrito Federal": ["BSB"],
    "BR-ES — Espírito Santo": ["VIX"],
    "BR-GO — Goiás": ["GYN", "CLV", "RVD"],
    "BR-MA — Maranhão": ["SLZ", "IMP"],
    "BR-MT — Mato Grosso": ["CGB", "ROO", "OPS", "AFL"],
    "BR-MS — Mato Grosso do Sul": ["CGR", "DOU", "CMG", "TJL", "BYO"],
    "BR-MG — Minas Gerais": ["CNF", "PLU", "UDI", "MOC", "IZA", "VAG", "IPN"],
    "BR-PA — Pará": ["BEL", "STM", "MAB", "ATM", "CKS"],
    "BR-PB — Paraíba": ["JPA", "CPV"],
    "BR-PR — Paraná": ["CWB", "IGU", "LDB", "MGF", "CAC"],
    "BR-PE — Pernambuco": ["REC", "PNZ", "FEN"],
    "BR-PI — Piauí": ["THE", "PHB"],
    "BR-RJ — Rio de Janeiro": ["GIG", "SDU", "CFB"],
    "BR-RN — Rio Grande do Norte": ["NAT"],
    "BR-RS — Rio Grande do Sul": ["POA", "CXJ", "PFB", "PET", "URG", "RIA", "BGX"],
    "BR-RO — Rondônia": ["PVH", "JPR", "BVH"],
    "BR-RR — Roraima": ["BVB"],
    "BR-SC — Santa Catarina": ["FLN", "NVT", "JOI", "XAP", "JJG"],
    "BR-SP — São Paulo": ["GRU", "CGH", "VCP", "RAO", "SJP", "PPB", "ARU", "BAU", "JTC", "MII"],
    "BR-SE — Sergipe": ["AJU"],
    "BR-TO — Tocantins": ["PMW", "AUX"],
    "US-FL — Flórida": ["MIA", "FLL", "MCO", "TPA", "PBI", "RSW", "JAX"],
    "US-NY — Nova York": ["JFK", "LGA", "BUF", "ROC", "SYR", "ALB"],
    "US-NJ — Nova Jersey": ["EWR", "ACY"],
    "US-CA — Califórnia": ["LAX", "SFO", "SAN", "SJC", "OAK", "SMF"],
    "US-TX — Texas": ["DFW", "IAH", "AUS", "SAT", "HOU"],
    "US-GA — Geórgia": ["ATL", "SAV"],
    "US-IL — Illinois": ["ORD", "MDW"],
    "US-MA — Massachusetts": ["BOS"],
    "US-DC — Washington DC": ["DCA", "IAD", "BWI"],
    "US-NV — Nevada": ["LAS", "RNO"],
    "US-WA — Washington": ["SEA", "GEG"],
    "US-CO — Colorado": ["DEN"],
    "US-AZ — Arizona": ["PHX", "TUS"],
    "US-HI — Havaí": ["HNL", "OGG", "KOA", "LIH"],
}


def airports_for_regions(regions):
    result = []
    for region in regions:
        for code in AIRPORTS_BY_REGION.get(region, []):
            if code not in result:
                result.append(code)
    return result
