"""Keyword planning and research tools using the Google Ads Keyword Planner API."""

from typing import Optional, List
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils


@mcp.tool()
def get_keyword_ideas(
    customer_id: str,
    keywords: List[str],
    geo_target_ids: Optional[List[int]] = None,
    language_id: int = 1000,
    include_adult_keywords: bool = False,
    page_size: int = 50,
) -> list:
    """Generate keyword ideas using the Google Ads Keyword Planner.

    Given seed keywords, returns related keyword ideas with avg monthly searches,
    competition level, and suggested bid ranges. Ideal for discovering new keywords
    and understanding search volume before adding to campaigns.

    Args:
        customer_id: Google Ads customer ID (digits only)
        keywords: List of seed keywords, e.g. ['machine learning consulting', 'AI services india']
        geo_target_ids: List of geo target constant IDs. Default: [2356] (India).
                        Use suggest_geo_targets to find IDs for other countries.
        language_id: Language constant ID. 1000=English (default), 1023=Hindi
        include_adult_keywords: Whether to include adult keywords (default False)
        page_size: Number of ideas to return (default 50, max 1000)
    """
    if geo_target_ids is None:
        geo_target_ids = [2356]  # India

    client = utils.get_googleads_client()
    svc = client.get_service("KeywordPlanIdeaService")

    req = client.get_type("GenerateKeywordIdeasRequest")
    req.customer_id = customer_id
    req.language = f"languageConstants/{language_id}"
    req.geo_target_constants.extend([
        f"geoTargetConstants/{geo_id}" for geo_id in geo_target_ids
    ])
    req.include_adult_keywords = include_adult_keywords
    req.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS
    req.page_size = min(page_size, 1000)

    req.keyword_seed.keywords.extend(keywords)

    ideas = []
    response = svc.generate_keyword_ideas(request=req)
    for idea in response:
        kwm = idea.keyword_idea_metrics
        ideas.append({
            "keyword": idea.text,
            "avg_monthly_searches": kwm.avg_monthly_searches,
            "competition": kwm.competition.name,
            "competition_index": kwm.competition_index,
            "low_top_of_page_bid_rupees": round(kwm.low_top_of_page_bid_micros / 1_000_000, 2) if kwm.low_top_of_page_bid_micros else None,
            "high_top_of_page_bid_rupees": round(kwm.high_top_of_page_bid_micros / 1_000_000, 2) if kwm.high_top_of_page_bid_micros else None,
        })

    # Sort by monthly searches descending
    ideas.sort(key=lambda x: x["avg_monthly_searches"] or 0, reverse=True)
    return ideas


@mcp.tool()
def get_keyword_forecast(
    customer_id: str,
    keywords: List[str],
    daily_budget_rupees: float,
    bid_rupees: float,
    geo_target_ids: Optional[List[int]] = None,
    language_id: int = 1000,
) -> dict:
    """Forecast clicks, impressions, and spend for a set of keywords with a given budget and bid.

    Useful for estimating campaign performance before going live.

    Args:
        customer_id: Google Ads customer ID (digits only)
        keywords: List of keywords to forecast (use exact match for most accuracy)
        daily_budget_rupees: Daily budget in INR to simulate
        bid_rupees: Max CPC bid in INR to simulate
        geo_target_ids: List of geo target constant IDs. Default: [2356] (India).
        language_id: Language constant ID. 1000=English (default).
    """
    if geo_target_ids is None:
        geo_target_ids = [2356]

    client = utils.get_googleads_client()

    # Build a KeywordPlan with the provided keywords
    plan_svc = client.get_service("KeywordPlanService")
    plan_op = client.get_type("KeywordPlanOperation")
    plan = plan_op.create
    plan.name = f"Forecast Plan - {','.join(keywords[:3])}"
    plan.forecast_period.date_interval = client.enums.KeywordPlanForecastIntervalEnum.NEXT_MONTH
    plan_resp = plan_svc.mutate_keyword_plans(customer_id=customer_id, operations=[plan_op])
    plan_resource = plan_resp.results[0].resource_name

    try:
        # Add a campaign to the plan
        camp_svc = client.get_service("KeywordPlanCampaignService")
        camp_op = client.get_type("KeywordPlanCampaignOperation")
        kp_camp = camp_op.create
        kp_camp.name = "Forecast Campaign"
        kp_camp.keyword_plan = plan_resource
        kp_camp.cpc_bid_micros = int(bid_rupees * 1_000_000)
        kp_camp.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS
        kp_camp.geo_targets.extend([
            client.get_type("KeywordPlanGeoTarget").__class__(
                **{"geo_target_constant": f"geoTargetConstants/{gid}"}
            )
            for gid in geo_target_ids
        ])
        kp_camp.language_constants.append(f"languageConstants/{language_id}")
        camp_resp = camp_svc.mutate_keyword_plan_campaigns(customer_id=customer_id, operations=[camp_op])
        kp_camp_resource = camp_resp.results[0].resource_name

        # Add an ad group
        ag_svc = client.get_service("KeywordPlanAdGroupService")
        ag_op = client.get_type("KeywordPlanAdGroupOperation")
        kp_ag = ag_op.create
        kp_ag.name = "Forecast Ad Group"
        kp_ag.keyword_plan_campaign = kp_camp_resource
        kp_ag.cpc_bid_micros = int(bid_rupees * 1_000_000)
        ag_resp = ag_svc.mutate_keyword_plan_ad_groups(customer_id=customer_id, operations=[ag_op])
        kp_ag_resource = ag_resp.results[0].resource_name

        # Add keywords
        kw_svc = client.get_service("KeywordPlanAdGroupKeywordService")
        kw_ops = []
        for kw in keywords:
            kw_op = client.get_type("KeywordPlanAdGroupKeywordOperation")
            k = kw_op.create
            k.text = kw
            k.match_type = client.enums.KeywordMatchTypeEnum.BROAD
            k.keyword_plan_ad_group = kp_ag_resource
            k.cpc_bid_micros = int(bid_rupees * 1_000_000)
            kw_ops.append(kw_op)
        kw_svc.mutate_keyword_plan_ad_group_keywords(customer_id=customer_id, operations=kw_ops)

        # Generate forecast
        forecast_svc = client.get_service("KeywordPlanIdeaService")
        forecast = plan_svc.generate_forecast_metrics(keyword_plan=plan_resource)
        fc = forecast.campaign_forecasts[0].keyword_forecasts if forecast.campaign_forecasts else []

        result = {
            "daily_budget_rupees": daily_budget_rupees,
            "bid_rupees": bid_rupees,
            "keyword_forecasts": [],
        }
        for kf in fc:
            m = kf.keyword_forecast
            result["keyword_forecasts"].append({
                "impressions": round(m.impressions, 0),
                "clicks": round(m.clicks, 0),
                "spend_rupees": round(m.cost_micros / 1_000_000, 2) if m.cost_micros else 0,
                "ctr_pct": round(m.ctr * 100, 2) if m.ctr else 0,
                "average_cpc_rupees": round(m.average_cpc / 1_000_000, 2) if m.average_cpc else 0,
            })
        return result

    finally:
        # Clean up the temporary plan
        try:
            rm_op = client.get_type("KeywordPlanOperation")
            rm_op.remove = plan_resource
            plan_svc.mutate_keyword_plans(customer_id=customer_id, operations=[rm_op])
        except Exception:
            pass
