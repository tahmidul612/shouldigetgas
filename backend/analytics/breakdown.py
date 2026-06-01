"""
Module D — Cost Breakdown Estimation.

Per-region breakdown of gas price into crude, refining, taxes, and distribution.
Percentages sum to 100; stored as integers for the frontend.
"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from config import US_TAX_CPG, CA_TAX_RATES, is_canadian


# Nominal refining + distribution margins (approximate, vary by region/season)
_US_REFINING_CPG = {
    "ca": 60, "wa": 55, "or": 52,          # West Coast — premium for CARB/RBOB
    "hi": 50,
    "ny": 45, "ct": 44, "nj": 44, "ma": 44,
    "il": 48,                               # Chicago reformulated
}
_US_REFINING_DEFAULT_CPG = 38   # ¢/gal
_US_DIST_DEFAULT_CPG     = 30   # ¢/gal

_CA_REFINING_CPL = 12   # ¢/L
_CA_DIST_CPL     = 7    # ¢/L


def us_breakdown(region_id: str, price_per_gal: float) -> dict:
    """
    Decompose a US gas price ($/gal) into % breakdown.
    Uses published EIA/API estimates for crude share, region-specific taxes.
    """
    price_cents = price_per_gal * 100  # convert to ¢/gal

    tax_cpg     = US_TAX_CPG.get(region_id, 45)   # ¢/gal
    refin_cpg   = _US_REFINING_CPG.get(region_id, _US_REFINING_DEFAULT_CPG)
    dist_cpg    = _US_DIST_DEFAULT_CPG

    overhead    = tax_cpg + refin_cpg + dist_cpg
    crude_cents = max(price_cents - overhead, price_cents * 0.45)  # crude ≥ 45% of price

    total = crude_cents + refin_cpg + tax_cpg + dist_cpg
    # Normalise so percentages sum to 100
    def pct(v): return max(1, round(v / total * 100))

    crude_pct   = pct(crude_cents)
    refin_pct   = pct(refin_cpg)
    tax_pct     = pct(tax_cpg)
    dist_pct    = pct(dist_cpg)

    # Adjust rounding: force sum to exactly 100
    diff = 100 - (crude_pct + refin_pct + tax_pct + dist_pct)
    crude_pct += diff   # absorb rounding in largest component

    return {"crude": crude_pct, "refining": refin_pct, "taxes": tax_pct, "dist": dist_pct}


def ca_breakdown(region_id: str, price_per_litre: float) -> dict:
    """
    Decompose a Canadian gas price ($/L CAD) into % breakdown.
    Uses known federal + provincial tax schedules.
    """
    price_cents = price_per_litre * 100  # $/L → ¢/L

    rates = CA_TAX_RATES.get(region_id, CA_TAX_RATES["on"])

    fed_excise  = rates["federal_excise"]     # ¢/L
    carbon      = rates["carbon_levy"]        # ¢/L
    prov_fuel   = rates["prov_fuel"]          # ¢/L
    sales_pct   = rates["sales_tax_pct"] / 100.0

    # Specific taxes (applied to base price before sales tax)
    specific_tax = fed_excise + carbon + prov_fuel

    # Estimate base price (crude + refining + dist) as what's left after specific taxes
    pre_sales    = price_cents / (1 + sales_pct)
    base_price   = pre_sales - specific_tax
    sales_tax_amt = price_cents - pre_sales

    total_tax   = specific_tax + sales_tax_amt
    refin_cpl   = _CA_REFINING_CPL
    dist_cpl    = _CA_DIST_CPL
    crude_cpl   = max(base_price - refin_cpl - dist_cpl, price_cents * 0.40)

    total = crude_cpl + refin_cpl + total_tax + dist_cpl
    def pct(v): return max(1, round(v / total * 100))

    crude_pct = pct(crude_cpl)
    refin_pct = pct(refin_cpl)
    tax_pct   = pct(total_tax)
    dist_pct  = pct(dist_cpl)

    diff = 100 - (crude_pct + refin_pct + tax_pct + dist_pct)
    crude_pct += diff

    return {"crude": crude_pct, "refining": refin_pct, "taxes": tax_pct, "dist": dist_pct}


def get_breakdown(region_id: str, price: float) -> dict:
    """Return breakdown dict for any region. Price in native unit ($/gal or $/L)."""
    if is_canadian(region_id):
        return ca_breakdown(region_id, price)
    return us_breakdown(region_id, price)
