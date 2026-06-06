"""Geo targeting tools — list, replace, remove, and exclude campaign locations.

Built on top of `add_geo_targets` / `suggest_geo_targets` in campaigns.py.
Focused on premium-market workflows: target rich countries, exclude low-ARPU geos.
"""

from typing import Optional
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils


# Curated list of premium B2B markets (rich economies where high-value services sell).
# Keys: country name, Values: Google Ads geo target constant ID.
# Use via `apply_premium_markets_preset` — safe default for high-ticket consulting/AI work.
PREMIUM_MARKETS = {
    # North America
    "United States": 2840,
    "Canada": 2124,
    # Western Europe
    "United Kingdom": 2826,
    "Germany": 2276,
    "France": 2250,
    "Switzerland": 2756,
    "Austria": 2040,
    "Netherlands": 2528,
    "Belgium": 2056,
    "Luxembourg": 2442,
    "Ireland": 2372,
    "Iceland": 2352,
    # Nordics
    "Sweden": 2752,
    "Norway": 2578,
    "Denmark": 2208,
    "Finland": 2246,
    # Asia-Pacific developed
    "Japan": 2392,
    "South Korea": 2410,
    "Singapore": 2702,
    "Hong Kong": 2344,
    "Taiwan": 2158,
    "Australia": 2036,
    "New Zealand": 2554,
    # High-income Gulf / Middle East
    "United Arab Emirates": 2784,
    "Saudi Arabia": 2682,
    "Qatar": 2634,
    "Kuwait": 2414,
    "Bahrain": 2048,
    "Oman": 2512,
    "Israel": 2376,
}

# Deliberately excluded: India, Pakistan, Bangladesh, Nepal, Sri Lanka, Philippines,
# Vietnam, Indonesia, Thailand, Egypt, Nigeria, Kenya, South Africa, Brazil, Mexico,
# Russia, China mainland, Turkey, Ukraine, and all other low-ARPU markets.
# If you want to add a market to the preset, edit this file — keep the bar high.

# Hard-banned markets. Always added as NEGATIVE location criteria on any campaign
# touched by `apply_premium_markets_preset`. These are geographies where returns
# on premium B2B services are structurally poor — confirmed by real campaign data
# and by the owner's explicit decision (2026-04-11). Do not remove these.
# Iran is NOT listed here because Google Ads has no geo target constant for Iran
# (US sanctions block the entire country at the platform level — already zero-risk).
BANNED_MARKETS = {
    "India": 2356,
    "Pakistan": 2586,
    "Bangladesh": 2050,
    "Palestine": 2275,
    # Iran has no Google Ads geo constant (US sanctions block the platform in-country),
    # so it's already unreachable via any campaign. Listed here for documentation.
    # If Google ever adds a constant for Iran, update this value to the real ID.
    "Iran": None,
}


def _list_location_criteria(customer_id: str, campaign_resource: str) -> list:
    """Internal helper: list all LOCATION criteria on a campaign with resource names."""
    client = utils.get_googleads_client()
    ga_svc = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
          campaign_criterion.resource_name,
          campaign_criterion.location.geo_target_constant,
          campaign_criterion.negative,
          campaign_criterion.bid_modifier,
          campaign_criterion.status
        FROM campaign_criterion
        WHERE campaign.resource_name = '{campaign_resource}'
          AND campaign_criterion.type = 'LOCATION'
    """
    rows = []
    stream = ga_svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            cc = row.campaign_criterion
            gtc = cc.location.geo_target_constant
            geo_id = gtc.split("/")[-1] if gtc else None
            rows.append({
                "resource_name": cc.resource_name,
                "geo_target_constant": gtc,
                "geo_id": geo_id,
                "negative": cc.negative,
                "bid_modifier": round(cc.bid_modifier, 3) if cc.bid_modifier else 1.0,
                "status": cc.status.name,
            })
    return rows


@mcp.tool()
def list_campaign_location_targets(
    customer_id: str,
    campaign_resource: str,
) -> list:
    """List all location criteria (positive + negative) on a campaign.

    Shows geo target constant IDs, whether each is a positive or negative target,
    and any bid adjustments. Use before making bulk geo changes to understand
    current state.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Campaign resource name (e.g. 'customers/XXX/campaigns/YYY')
    """
    return _list_location_criteria(customer_id, campaign_resource)


@mcp.tool()
def remove_campaign_location_targets(
    customer_id: str,
    campaign_resource: str,
    geo_ids_to_remove: Optional[list] = None,
    remove_all: bool = False,
) -> dict:
    """Remove specific location targets from a campaign, or remove all of them.

    Pass either `geo_ids_to_remove` with specific criterion constant IDs, OR
    `remove_all=True` to wipe all location criteria.

    WARNING: If you remove all locations without adding new ones, the campaign
    will default to targeting everyone in all countries — always follow up with
    `add_geo_targets` or use `set_campaign_location_targeting` for atomic replace.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Campaign resource name
        geo_ids_to_remove: List of geo target constant IDs to remove, e.g. [2356, 2586]
        remove_all: If True, removes all location criteria (ignores geo_ids_to_remove)
    """
    client = utils.get_googleads_client()
    svc = client.get_service("CampaignCriterionService")

    existing = _list_location_criteria(customer_id, campaign_resource)
    to_remove = []
    if remove_all:
        to_remove = [loc["resource_name"] for loc in existing]
    elif geo_ids_to_remove:
        wanted = {str(gid) for gid in geo_ids_to_remove}
        to_remove = [loc["resource_name"] for loc in existing if loc["geo_id"] in wanted]
    else:
        return {"removed_count": 0, "reason": "No geo_ids_to_remove and remove_all=False"}

    if not to_remove:
        return {"removed_count": 0, "reason": "No matching location criteria found"}

    ops = []
    for rn in to_remove:
        op = client.get_type("CampaignCriterionOperation")
        op.remove = rn
        ops.append(op)
    svc.mutate_campaign_criteria(customer_id=customer_id, operations=ops)
    return {"removed_count": len(ops), "removed_resources": to_remove}


@mcp.tool()
def set_campaign_location_targeting(
    customer_id: str,
    campaign_resource: str,
    geo_target_ids: list,
) -> dict:
    """Atomically replace ALL positive location targets on a campaign with a new list.

    Removes every existing positive location criterion, then adds the new geo IDs.
    Negative location criteria are preserved. Use this to pivot a campaign's geo
    focus in one shot — e.g. from "Global" to "US + UK + Gulf only".

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Campaign resource name
        geo_target_ids: List of geo target constant IDs to target (integers or strings).
                        e.g. [2840, 2826, 2784, 2682] for US, UK, UAE, Saudi Arabia
    """
    client = utils.get_googleads_client()
    svc = client.get_service("CampaignCriterionService")

    existing = _list_location_criteria(customer_id, campaign_resource)
    positive_existing = [loc for loc in existing if not loc["negative"]]

    remove_ops = []
    for loc in positive_existing:
        op = client.get_type("CampaignCriterionOperation")
        op.remove = loc["resource_name"]
        remove_ops.append(op)

    create_ops = []
    for geo_id in geo_target_ids:
        op = client.get_type("CampaignCriterionOperation")
        cr = op.create
        cr.campaign = campaign_resource
        cr.location.geo_target_constant = f"geoTargetConstants/{geo_id}"
        create_ops.append(op)

    # Remove first, then create. Google Ads allows same-request mixed ops but
    # ordering matters for idempotency: do removes before creates.
    if remove_ops:
        svc.mutate_campaign_criteria(customer_id=customer_id, operations=remove_ops)
    if create_ops:
        svc.mutate_campaign_criteria(customer_id=customer_id, operations=create_ops)

    return {
        "removed_count": len(remove_ops),
        "added_count": len(create_ops),
        "new_geo_target_ids": [int(g) for g in geo_target_ids],
    }


@mcp.tool()
def exclude_campaign_locations(
    customer_id: str,
    campaign_resource: str,
    geo_target_ids: list,
) -> dict:
    """Add NEGATIVE location criteria to a campaign (exclude these geos).

    Use when you want to keep broad targeting (e.g. "Worldwide") but cut specific
    countries or regions. Alternative to `set_campaign_location_targeting` which
    replaces the positive list instead.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Campaign resource name
        geo_target_ids: List of geo target constant IDs to exclude, e.g. [2356, 2586, 2050]
                        for India, Pakistan, Cambodia
    """
    client = utils.get_googleads_client()
    svc = client.get_service("CampaignCriterionService")
    ops = []
    for geo_id in geo_target_ids:
        op = client.get_type("CampaignCriterionOperation")
        cr = op.create
        cr.campaign = campaign_resource
        cr.location.geo_target_constant = f"geoTargetConstants/{geo_id}"
        cr.negative = True
        ops.append(op)
    svc.mutate_campaign_criteria(customer_id=customer_id, operations=ops)
    return {"excluded_count": len(ops), "geo_target_ids": geo_target_ids}


@mcp.tool()
def apply_premium_markets_preset(
    customer_id: str,
    campaign_resource: str,
    include_gulf: bool = True,
    include_apac: bool = True,
    extra_geo_ids: Optional[list] = None,
) -> dict:
    """Atomically set campaign targeting to the curated premium/rich-country preset.

    Premium markets = high-income economies where B2B buyers pay full rate for
    specialist work. The preset deliberately excludes India and all other low-ARPU
    geographies. See PREMIUM_MARKETS in geo_targeting.py for the full list.

    Default includes: US, Canada, UK, Germany, France, Switzerland, Austria,
    Netherlands, Belgium, Luxembourg, Ireland, Iceland, Sweden, Norway, Denmark,
    Finland, Australia, New Zealand, Japan, South Korea, Singapore, Hong Kong,
    Taiwan, UAE, Saudi Arabia, Qatar, Kuwait, Bahrain, Oman, Israel.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Campaign resource name
        include_gulf: Include UAE/Saudi/Qatar/Kuwait/Bahrain/Oman/Israel (default True)
        include_apac: Include Japan/Korea/Singapore/HK/Taiwan/Australia/NZ (default True)
        extra_geo_ids: Optional additional geo IDs to include beyond the preset
    """
    gulf = {"United Arab Emirates", "Saudi Arabia", "Qatar", "Kuwait",
            "Bahrain", "Oman", "Israel"}
    apac = {"Japan", "South Korea", "Singapore", "Hong Kong", "Taiwan",
            "Australia", "New Zealand"}

    selected = {}
    for name, gid in PREMIUM_MARKETS.items():
        if name in gulf and not include_gulf:
            continue
        if name in apac and not include_apac:
            continue
        selected[name] = gid

    geo_ids = list(selected.values())
    if extra_geo_ids:
        geo_ids.extend(int(g) for g in extra_geo_ids)

    result = set_campaign_location_targeting(customer_id, campaign_resource, geo_ids)
    result["preset"] = "PREMIUM_MARKETS"
    result["countries_targeted"] = list(selected.keys())

    # Always apply BANNED_MARKETS as negative location criteria. Idempotent-ish:
    # if an exclusion already exists Google Ads will error on the duplicate, so we
    # catch per-country and keep going. Iran (None) is skipped.
    banned_ids = [gid for gid in BANNED_MARKETS.values() if gid is not None]
    client = utils.get_googleads_client()
    svc = client.get_service("CampaignCriterionService")
    existing = _list_location_criteria(customer_id, campaign_resource)
    existing_negative_ids = {loc["geo_id"] for loc in existing if loc["negative"]}

    to_ban = [gid for gid in banned_ids if str(gid) not in existing_negative_ids]
    if to_ban:
        ban_ops = []
        for geo_id in to_ban:
            op = client.get_type("CampaignCriterionOperation")
            cr = op.create
            cr.campaign = campaign_resource
            cr.location.geo_target_constant = f"geoTargetConstants/{geo_id}"
            cr.negative = True
            ban_ops.append(op)
        svc.mutate_campaign_criteria(customer_id=customer_id, operations=ban_ops)
        result["banned_countries_added"] = [
            name for name, gid in BANNED_MARKETS.items()
            if gid in to_ban
        ]
    else:
        result["banned_countries_added"] = []
    result["banned_countries_already_blocked"] = [
        name for name, gid in BANNED_MARKETS.items()
        if gid is not None and str(gid) in existing_negative_ids
    ]
    result["iran_note"] = "Iran has no Google Ads geo constant (sanctions) — platform-level block"
    return result
