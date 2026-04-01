"""Tools for listing and applying Google Ads automated recommendations."""

from typing import Optional, List
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils


@mcp.tool()
def list_recommendations(
    customer_id: str,
    campaign_resource: Optional[str] = None,
) -> list:
    """List pending automated recommendations from Google Ads.

    Google constantly analyses your account and suggests improvements.
    This tool surfaces those recommendations so you can review and apply them.

    Types include: KEYWORD, BID, BUDGET, AD, TARGET_CPA_OPT_IN,
    MAXIMIZE_CONVERSIONS_OPT_IN, ENHANCED_CPC_OPT_IN, SITELINK, CALLOUT, etc.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Optional — filter to a single campaign
    """
    client = utils.get_googleads_client()
    svc = client.get_service("GoogleAdsService")

    where_clause = "recommendation.type != 'UNSPECIFIED'"
    if campaign_resource:
        where_clause += f" AND recommendation.campaign = '{campaign_resource}'"

    query = f"""
        SELECT
          recommendation.resource_name,
          recommendation.type,
          recommendation.campaign,
          recommendation.ad_group,
          recommendation.dismissed,
          recommendation.impact.base_metrics.impressions,
          recommendation.impact.potential_metrics.impressions,
          recommendation.impact.base_metrics.clicks,
          recommendation.impact.potential_metrics.clicks,
          recommendation.impact.base_metrics.cost_micros,
          recommendation.impact.potential_metrics.cost_micros,
          recommendation.impact.base_metrics.conversions,
          recommendation.impact.potential_metrics.conversions
        FROM recommendation
        WHERE {where_clause}
    """

    rows = []
    stream = svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            rec = row.recommendation
            base = rec.impact.base_metrics
            potential = rec.impact.potential_metrics

            def _delta(a, b):
                return round(b - a, 2) if b and a else None

            rows.append({
                "resource_name": rec.resource_name,
                "type": rec.type_.name,
                "campaign": rec.campaign,
                "ad_group": rec.ad_group or None,
                "dismissed": rec.dismissed,
                "impact": {
                    "impressions_delta": _delta(base.impressions, potential.impressions),
                    "clicks_delta": _delta(base.clicks, potential.clicks),
                    "conversions_delta": _delta(base.conversions, potential.conversions),
                    "spend_delta_rupees": _delta(
                        base.cost_micros / 1_000_000 if base.cost_micros else 0,
                        potential.cost_micros / 1_000_000 if potential.cost_micros else 0,
                    ),
                },
            })
    return rows


@mcp.tool()
def apply_recommendation(
    customer_id: str,
    recommendation_resource_name: str,
) -> dict:
    """Apply a specific Google Ads recommendation.

    Use list_recommendations first to get the resource_name, then pass it here.
    Once applied, the recommendation is removed from the pending list.

    Args:
        customer_id: Google Ads customer ID (digits only)
        recommendation_resource_name: Resource name from list_recommendations
                                      (e.g. 'customers/XXX/recommendations/YYY')
    """
    client = utils.get_googleads_client()
    svc = client.get_service("RecommendationService")

    apply_op = client.get_type("ApplyRecommendationOperation")
    apply_op.resource_name = recommendation_resource_name

    response = svc.apply_recommendation(
        customer_id=customer_id,
        operations=[apply_op],
    )

    return {
        "applied": recommendation_resource_name,
        "result": response.results[0].resource_name if response.results else "Applied",
        "message": "Recommendation applied successfully.",
    }


@mcp.tool()
def dismiss_recommendation(
    customer_id: str,
    recommendation_resource_names: List[str],
) -> dict:
    """Dismiss one or more recommendations so they stop appearing.

    Use this when a recommendation is not relevant to your strategy.

    Args:
        customer_id: Google Ads customer ID (digits only)
        recommendation_resource_names: List of resource names to dismiss
    """
    client = utils.get_googleads_client()
    svc = client.get_service("RecommendationService")

    req = client.get_type("DismissRecommendationRequest")
    req.customer_id = customer_id
    for rn in recommendation_resource_names:
        op = client.get_type("DismissRecommendationRequest").Operations()
        op.resource_name = rn
        req.operations.append(op)

    svc.dismiss_recommendation(request=req)

    return {
        "dismissed_count": len(recommendation_resource_names),
        "resource_names": recommendation_resource_names,
        "message": f"Dismissed {len(recommendation_resource_names)} recommendation(s).",
    }
