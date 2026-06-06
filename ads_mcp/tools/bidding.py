"""Bidding strategy tools — switch between manual CPC, target CPA, maximize conversions, etc."""

from typing import Optional
from google.protobuf import field_mask_pb2
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils


@mcp.tool()
def set_target_cpa(
    customer_id: str,
    campaign_resource: str,
    target_cpa_rupees: float,
) -> dict:
    """Switch a campaign to Target CPA smart bidding strategy.

    Google will automatically set bids to get as many conversions as possible
    at or below the target CPA. Requires conversion tracking to be working.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Campaign resource name (e.g. 'customers/XXX/campaigns/YYY')
        target_cpa_rupees: Target cost-per-acquisition in Indian Rupees
    """
    client = utils.get_googleads_client()
    svc = client.get_service("CampaignService")

    op = client.get_type("CampaignOperation")
    c = op.update
    c.resource_name = campaign_resource
    c.target_cpa.target_cpa_micros = int(target_cpa_rupees * 1_000_000)
    op.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["target_cpa.target_cpa_micros"]))

    resp = svc.mutate_campaigns(customer_id=customer_id, operations=[op])
    return {
        "updated": resp.results[0].resource_name,
        "bidding_strategy": "TARGET_CPA",
        "target_cpa_rupees": target_cpa_rupees,
    }


@mcp.tool()
def set_maximize_conversions(
    customer_id: str,
    campaign_resource: str,
    target_cpa_rupees: Optional[float] = None,
) -> dict:
    """Switch a campaign to Maximize Conversions bidding.

    Google will automatically set bids to get the most conversions within budget.
    Optionally set a Target CPA constraint.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Campaign resource name
        target_cpa_rupees: Optional target CPA constraint in INR. If None, fully
                           maximizes conversions within budget.
    """
    client = utils.get_googleads_client()
    svc = client.get_service("CampaignService")

    op = client.get_type("CampaignOperation")
    c = op.update
    c.resource_name = campaign_resource

    if target_cpa_rupees is not None:
        c.maximize_conversions.target_cpa_micros = int(target_cpa_rupees * 1_000_000)
        paths = ["maximize_conversions.target_cpa_micros"]
    else:
        # Set empty maximize_conversions to trigger the strategy switch
        c.maximize_conversions.CopyFrom(client.get_type("MaximizeConversions"))
        paths = ["maximize_conversions"]

    op.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))
    resp = svc.mutate_campaigns(customer_id=customer_id, operations=[op])
    return {
        "updated": resp.results[0].resource_name,
        "bidding_strategy": "MAXIMIZE_CONVERSIONS",
        "target_cpa_rupees": target_cpa_rupees,
    }


@mcp.tool()
def set_maximize_conversion_value(
    customer_id: str,
    campaign_resource: str,
    target_roas: Optional[float] = None,
) -> dict:
    """Switch a campaign to Maximize Conversion Value bidding.

    Google maximizes total conversion value within budget. Optionally set a
    Target ROAS (return on ad spend) constraint.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Campaign resource name
        target_roas: Optional target ROAS as a decimal (e.g. 3.0 = 300% ROAS = ₹3 return per ₹1 spent)
    """
    client = utils.get_googleads_client()
    svc = client.get_service("CampaignService")

    op = client.get_type("CampaignOperation")
    c = op.update
    c.resource_name = campaign_resource

    if target_roas is not None:
        c.maximize_conversion_value.target_roas = target_roas
        paths = ["maximize_conversion_value.target_roas"]
    else:
        c.maximize_conversion_value.CopyFrom(client.get_type("MaximizeConversionValue"))
        paths = ["maximize_conversion_value"]

    op.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))
    resp = svc.mutate_campaigns(customer_id=customer_id, operations=[op])
    return {
        "updated": resp.results[0].resource_name,
        "bidding_strategy": "MAXIMIZE_CONVERSION_VALUE",
        "target_roas": target_roas,
    }


@mcp.tool()
def set_manual_cpc(
    customer_id: str,
    campaign_resource: str,
    enhanced_cpc: bool = True,
) -> dict:
    """Switch a campaign back to Manual CPC bidding.

    Gives full control over individual keyword bids.
    enhanced_cpc=True lets Google adjust bids up/down based on conversion likelihood.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Campaign resource name
        enhanced_cpc: Whether to enable Enhanced CPC (default True)
    """
    client = utils.get_googleads_client()
    svc = client.get_service("CampaignService")

    op = client.get_type("CampaignOperation")
    c = op.update
    c.resource_name = campaign_resource
    c.manual_cpc.enhanced_cpc_enabled = enhanced_cpc
    op.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["manual_cpc.enhanced_cpc_enabled"]))

    resp = svc.mutate_campaigns(customer_id=customer_id, operations=[op])
    return {
        "updated": resp.results[0].resource_name,
        "bidding_strategy": "MANUAL_CPC",
        "enhanced_cpc": enhanced_cpc,
    }


@mcp.tool()
def set_target_impression_share(
    customer_id: str,
    campaign_resource: str,
    location: str = "ANYWHERE_ON_PAGE",
    percent: float = 80.0,
    max_cpc_rupees: Optional[float] = None,
) -> dict:
    """Switch a campaign to Target Impression Share bidding.

    Automatically sets bids to show your ad a target % of the time in a chosen location.
    Useful for brand visibility campaigns.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Campaign resource name
        location: Where to show — ANYWHERE_ON_PAGE, TOP_OF_PAGE, or ABSOLUTE_TOP_OF_PAGE
        percent: Target impression share percentage (0-100, default 80)
        max_cpc_rupees: Optional ceiling on max CPC in INR to control costs
    """
    client = utils.get_googleads_client()
    svc = client.get_service("CampaignService")

    op = client.get_type("CampaignOperation")
    c = op.update
    c.resource_name = campaign_resource
    tis = c.target_impression_share
    tis.location = client.enums.TargetImpressionShareLocationEnum[location]
    tis.location_fraction_micros = int(percent * 10_000)  # micros of fraction (80% = 800000)
    paths = [
        "target_impression_share.location",
        "target_impression_share.location_fraction_micros",
    ]
    if max_cpc_rupees:
        tis.cpc_bid_ceiling_micros = int(max_cpc_rupees * 1_000_000)
        paths.append("target_impression_share.cpc_bid_ceiling_micros")

    op.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))
    resp = svc.mutate_campaigns(customer_id=customer_id, operations=[op])
    return {
        "updated": resp.results[0].resource_name,
        "bidding_strategy": "TARGET_IMPRESSION_SHARE",
        "location": location,
        "target_percent": percent,
        "max_cpc_rupees": max_cpc_rupees,
    }


def _pct_to_bid_modifier(pct: float) -> float:
    """Convert a percentage bid adjustment to Google Ads bid_modifier multiplier.

    -90% → 0.1, -50% → 0.5, 0% → 1.0, +50% → 1.5, +900% → 10.0
    Google Ads valid range for device/location: 0.1 to 10.0 (i.e. -90% to +900%).
    -100% is only allowed on DESKTOP/TABLET for some campaign types and maps to 0.1
    as the safest floor.
    """
    if pct <= -100:
        return 0.1
    mult = 1.0 + (pct / 100.0)
    return max(0.1, min(10.0, mult))


@mcp.tool()
def set_device_bid_adjustment(
    customer_id: str,
    campaign_resource: str,
    device: str,
    bid_adjustment_pct: float,
) -> dict:
    """Set a device bid adjustment on a campaign (upsert — creates or updates).

    Use this to shift spend toward converting devices. For example, if mobile
    converts well and desktop wastes budget, set DESKTOP to -90%.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Campaign resource name (e.g. 'customers/XXX/campaigns/YYY')
        device: MOBILE, DESKTOP, TABLET, or CONNECTED_TV
        bid_adjustment_pct: Adjustment in percent. -90 = bid 90% less, +50 = bid 50% more.
                            Valid range: -90 to +900. (-100 is clamped to -90.)
    """
    client = utils.get_googleads_client()
    svc = client.get_service("CampaignCriterionService")
    ga_svc = client.get_service("GoogleAdsService")

    bid_modifier = _pct_to_bid_modifier(bid_adjustment_pct)
    device_enum = client.enums.DeviceEnum[device]

    query = f"""
        SELECT campaign_criterion.resource_name, campaign_criterion.device.type
        FROM campaign_criterion
        WHERE campaign.resource_name = '{campaign_resource}'
          AND campaign_criterion.type = 'DEVICE'
    """
    existing_resource = None
    stream = ga_svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            if row.campaign_criterion.device.type_ == device_enum:
                existing_resource = row.campaign_criterion.resource_name
                break

    from google.protobuf import field_mask_pb2
    op = client.get_type("CampaignCriterionOperation")
    if existing_resource:
        crit = op.update
        crit.resource_name = existing_resource
        crit.bid_modifier = bid_modifier
        op.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["bid_modifier"]))
        action = "updated"
    else:
        crit = op.create
        crit.campaign = campaign_resource
        crit.device.type_ = device_enum
        crit.bid_modifier = bid_modifier
        action = "created"

    resp = svc.mutate_campaign_criteria(customer_id=customer_id, operations=[op])
    return {
        action: resp.results[0].resource_name,
        "device": device,
        "bid_adjustment_pct": bid_adjustment_pct,
        "bid_modifier": round(bid_modifier, 3),
    }


@mcp.tool()
def set_location_bid_adjustment(
    customer_id: str,
    campaign_resource: str,
    geo_target_constant_id: str,
    bid_adjustment_pct: float,
) -> dict:
    """Set a location bid adjustment on a campaign (upsert — creates or updates).

    Use this to bid more aggressively in high-converting cities or reduce bids
    in wasteful geographies. The location must already be in campaign targeting.

    Common geo_target_constant IDs:
      2356 = India, 1007751 = Ahmedabad, 1007767 = Mumbai, 1007754 = Bangalore,
      1007764 = Delhi, 2840 = United States, 2826 = United Kingdom

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Campaign resource name
        geo_target_constant_id: Numeric geo target constant ID (digits only)
        bid_adjustment_pct: Adjustment in percent. Valid range -90 to +900.
    """
    client = utils.get_googleads_client()
    svc = client.get_service("CampaignCriterionService")
    ga_svc = client.get_service("GoogleAdsService")

    bid_modifier = _pct_to_bid_modifier(bid_adjustment_pct)
    geo_resource = f"geoTargetConstants/{geo_target_constant_id}"

    query = f"""
        SELECT campaign_criterion.resource_name,
               campaign_criterion.location.geo_target_constant
        FROM campaign_criterion
        WHERE campaign.resource_name = '{campaign_resource}'
          AND campaign_criterion.type = 'LOCATION'
    """
    existing_resource = None
    stream = ga_svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            if row.campaign_criterion.location.geo_target_constant == geo_resource:
                existing_resource = row.campaign_criterion.resource_name
                break

    from google.protobuf import field_mask_pb2
    op = client.get_type("CampaignCriterionOperation")
    if existing_resource:
        crit = op.update
        crit.resource_name = existing_resource
        crit.bid_modifier = bid_modifier
        op.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["bid_modifier"]))
        action = "updated"
    else:
        crit = op.create
        crit.campaign = campaign_resource
        crit.location.geo_target_constant = geo_resource
        crit.bid_modifier = bid_modifier
        action = "created"

    resp = svc.mutate_campaign_criteria(customer_id=customer_id, operations=[op])
    return {
        action: resp.results[0].resource_name,
        "geo_target_constant_id": geo_target_constant_id,
        "bid_adjustment_pct": bid_adjustment_pct,
        "bid_modifier": round(bid_modifier, 3),
    }


@mcp.tool()
def list_device_bid_adjustments(
    customer_id: str,
    campaign_resource: str,
) -> list:
    """List current device bid adjustments on a campaign.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Campaign resource name
    """
    client = utils.get_googleads_client()
    ga_svc = client.get_service("GoogleAdsService")
    query = f"""
        SELECT campaign_criterion.resource_name,
               campaign_criterion.device.type,
               campaign_criterion.bid_modifier,
               campaign_criterion.negative
        FROM campaign_criterion
        WHERE campaign.resource_name = '{campaign_resource}'
          AND campaign_criterion.type = 'DEVICE'
    """
    rows = []
    stream = ga_svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            cc = row.campaign_criterion
            mult = cc.bid_modifier if cc.bid_modifier else 1.0
            rows.append({
                "resource_name": cc.resource_name,
                "device": cc.device.type_.name,
                "bid_modifier": round(mult, 3),
                "bid_adjustment_pct": round((mult - 1.0) * 100, 1),
                "negative": cc.negative,
            })
    return rows


@mcp.tool()
def update_keyword_bids_bulk(
    customer_id: str,
    keyword_bids: list,
) -> dict:
    """Update CPC bids for multiple keywords in a single API call.

    More efficient than calling update_keyword_bid one at a time.

    Args:
        customer_id: Google Ads customer ID (digits only)
        keyword_bids: List of dicts with keys:
                      - ad_group_criterion_resource: resource name of the keyword
                        (e.g. 'customers/XXX/adGroupCriteria/YYY~ZZZ')
                      - cpc_bid_rupees: new bid in INR
                      Example: [
                        {"ad_group_criterion_resource": "customers/4170793536/adGroupCriteria/12345~67890", "cpc_bid_rupees": 120.0},
                        {"ad_group_criterion_resource": "customers/4170793536/adGroupCriteria/12345~67891", "cpc_bid_rupees": 80.0}
                      ]
    """
    client = utils.get_googleads_client()
    svc = client.get_service("AdGroupCriterionService")

    ops = []
    for item in keyword_bids:
        op = client.get_type("AdGroupCriterionOperation")
        crit = op.update
        crit.resource_name = item["ad_group_criterion_resource"]
        crit.cpc_bid_micros = int(item["cpc_bid_rupees"] * 1_000_000)
        op.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["cpc_bid_micros"]))
        ops.append(op)

    resp = svc.mutate_ad_group_criteria(customer_id=customer_id, operations=ops)
    return {
        "updated_count": len(resp.results),
        "updated_keywords": [r.resource_name for r in resp.results],
    }
