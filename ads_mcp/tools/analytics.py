"""Advanced analytics tools: device, geo, hourly, quality score, auction insights."""

from typing import Optional
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils


@mcp.tool()
def get_device_performance(
    customer_id: str,
    date_range: str = "LAST_30_DAYS",
    campaign_resource: Optional[str] = None,
) -> list:
    """Get campaign performance broken down by device (MOBILE, DESKTOP, TABLET).

    Essential for deciding device bid adjustments.

    Args:
        customer_id: Google Ads customer ID (digits only)
        date_range: TODAY, YESTERDAY, LAST_7_DAYS, LAST_30_DAYS, THIS_MONTH (default: LAST_30_DAYS)
        campaign_resource: Optional — filter to a single campaign resource name
    """
    client = utils.get_googleads_client()
    svc = client.get_service("GoogleAdsService")

    where_clause = f"segments.date DURING {date_range} AND campaign.status != 'REMOVED'"
    if campaign_resource:
        where_clause += f" AND campaign.resource_name = '{campaign_resource}'"

    query = f"""
        SELECT
          campaign.name,
          campaign.resource_name,
          segments.device,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.ctr,
          metrics.average_cpc,
          metrics.conversions,
          metrics.cost_per_conversion
        FROM campaign
        WHERE {where_clause}
        ORDER BY metrics.cost_micros DESC
    """

    rows = []
    stream = svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            m = row.metrics
            rows.append({
                "campaign": row.campaign.name,
                "device": row.segments.device.name,
                "impressions": m.impressions,
                "clicks": m.clicks,
                "ctr_pct": round(m.ctr * 100, 2),
                "spend_rupees": round(m.cost_micros / 1_000_000, 2),
                "avg_cpc_rupees": round(m.average_cpc / 1_000_000, 2),
                "conversions": round(m.conversions, 2),
                "conversions": m.conversions,
                "cost_per_conversion_rupees": round(m.cost_per_conversion / 1_000_000, 2) if m.conversions > 0 else None,
            })
    return rows


@mcp.tool()
def get_geo_performance(
    customer_id: str,
    date_range: str = "LAST_30_DAYS",
    campaign_resource: Optional[str] = None,
    limit: int = 50,
) -> list:
    """Get performance broken down by geographic location.

    Shows which cities/countries are generating clicks and conversions.

    Args:
        customer_id: Google Ads customer ID (digits only)
        date_range: TODAY, YESTERDAY, LAST_7_DAYS, LAST_30_DAYS, THIS_MONTH (default: LAST_30_DAYS)
        campaign_resource: Optional — filter to a single campaign resource name
        limit: Max rows to return (default 50)
    """
    client = utils.get_googleads_client()
    svc = client.get_service("GoogleAdsService")

    where_clause = f"segments.date DURING {date_range}"
    if campaign_resource:
        where_clause += f" AND campaign.resource_name = '{campaign_resource}'"

    query = f"""
        SELECT
          campaign.name,
          geographic_view.resource_name,
          geographic_view.country_criterion_id,
          geographic_view.location_type,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.ctr,
          metrics.average_cpc
        FROM geographic_view
        WHERE {where_clause}
        ORDER BY metrics.cost_micros DESC
        LIMIT {limit}
    """

    rows = []
    stream = svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            m = row.metrics
            gv = row.geographic_view
            rows.append({
                "campaign": row.campaign.name,
                "location_type": gv.location_type.name,
                "country_criterion_id": gv.country_criterion_id,
                "impressions": m.impressions,
                "clicks": m.clicks,
                "ctr_pct": round(m.ctr * 100, 2),
                "spend_rupees": round(m.cost_micros / 1_000_000, 2),
                "avg_cpc_rupees": round(m.average_cpc / 1_000_000, 2),
                "conversions": round(m.conversions, 2),
                "conversions": m.conversions,
            })
    return rows


@mcp.tool()
def get_hourly_performance(
    customer_id: str,
    date_range: str = "LAST_30_DAYS",
    campaign_resource: Optional[str] = None,
) -> list:
    """Get performance segmented by hour of day AND day of week.

    Use this to optimize ad scheduling — identify peak hours and wasteful hours.

    Args:
        customer_id: Google Ads customer ID (digits only)
        date_range: LAST_7_DAYS, LAST_30_DAYS, THIS_MONTH (default: LAST_30_DAYS)
        campaign_resource: Optional — filter to a single campaign resource name
    """
    client = utils.get_googleads_client()
    svc = client.get_service("GoogleAdsService")

    where_clause = f"segments.date DURING {date_range} AND campaign.status != 'REMOVED'"
    if campaign_resource:
        where_clause += f" AND campaign.resource_name = '{campaign_resource}'"

    query = f"""
        SELECT
          campaign.name,
          segments.hour,
          segments.day_of_week,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.average_cpc
        FROM campaign
        WHERE {where_clause}
        ORDER BY segments.day_of_week, segments.hour
    """

    rows = []
    stream = svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            m = row.metrics
            rows.append({
                "campaign": row.campaign.name,
                "day_of_week": row.segments.day_of_week.name,
                "hour": row.segments.hour,
                "impressions": m.impressions,
                "clicks": m.clicks,
                "spend_rupees": round(m.cost_micros / 1_000_000, 2),
                "avg_cpc_rupees": round(m.average_cpc / 1_000_000, 2),
                "conversions": round(m.conversions, 2),
            })
    return rows


@mcp.tool()
def get_quality_scores(
    customer_id: str,
    campaign_resource: Optional[str] = None,
) -> list:
    """Get Quality Score details for all active keywords.

    Returns quality score (1-10), expected CTR, ad relevance, and landing page
    experience for each keyword. Low QS keywords increase CPC significantly.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Optional — filter to one campaign's keywords
    """
    client = utils.get_googleads_client()
    svc = client.get_service("GoogleAdsService")

    where_clause = (
        "ad_group_criterion.type = 'KEYWORD'"
        " AND ad_group_criterion.status != 'REMOVED'"
        " AND ad_group.status != 'REMOVED'"
        " AND campaign.status != 'REMOVED'"
    )
    if campaign_resource:
        where_clause += f" AND campaign.resource_name = '{campaign_resource}'"

    query = f"""
        SELECT
          campaign.name,
          ad_group.name,
          ad_group_criterion.criterion_id,
          ad_group_criterion.keyword.text,
          ad_group_criterion.keyword.match_type,
          ad_group_criterion.status,
          ad_group_criterion.quality_info.quality_score,
          ad_group_criterion.quality_info.creative_quality_score,
          ad_group_criterion.quality_info.post_click_quality_score,
          ad_group_criterion.quality_info.search_predicted_ctr,
          ad_group_criterion.cpc_bid_micros
        FROM ad_group_criterion
        WHERE {where_clause}
        ORDER BY ad_group_criterion.quality_info.quality_score ASC
    """

    rows = []
    stream = svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            crit = row.ad_group_criterion
            qi = crit.quality_info
            rows.append({
                "campaign": row.campaign.name,
                "ad_group": row.ad_group.name,
                "keyword": crit.keyword.text,
                "match_type": crit.keyword.match_type.name,
                "status": crit.status.name,
                "quality_score": qi.quality_score if qi.quality_score else "—",
                "expected_ctr": qi.search_predicted_ctr.name if qi.search_predicted_ctr else "—",
                "ad_relevance": qi.creative_quality_score.name if qi.creative_quality_score else "—",
                "landing_page_experience": qi.post_click_quality_score.name if qi.post_click_quality_score else "—",
                "cpc_bid_rupees": round(crit.cpc_bid_micros / 1_000_000, 2),
            })
    return rows


@mcp.tool()
def get_auction_insights(
    customer_id: str,
    campaign_resource: Optional[str] = None,
    date_range: str = "LAST_30_DAYS",
) -> list:
    """Get Auction Insights — see competitor impression share and overlap rates.

    Shows which domains are competing in the same auctions and how you compare.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Optional — filter to a specific campaign
        date_range: LAST_7_DAYS, LAST_30_DAYS, THIS_MONTH (default: LAST_30_DAYS)
    """
    client = utils.get_googleads_client()
    svc = client.get_service("GoogleAdsService")

    where_clause = f"segments.date DURING {date_range}"
    if campaign_resource:
        where_clause += f" AND campaign.resource_name = '{campaign_resource}'"

    query = f"""
        SELECT
          auction_insight_summary.domain,
          auction_insight_summary.impression_share,
          auction_insight_summary.overlap_rate,
          auction_insight_summary.outranking_share,
          auction_insight_summary.position_above_rate,
          auction_insight_summary.top_of_page_rate,
          auction_insight_summary.abs_top_of_page_rate,
          campaign.name
        FROM auction_insight_summary
        WHERE {where_clause}
        ORDER BY auction_insight_summary.impression_share DESC
    """

    rows = []
    stream = svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            ai = row.auction_insight_summary
            rows.append({
                "domain": ai.domain,
                "campaign": row.campaign.name,
                "impression_share_pct": round(ai.impression_share * 100, 1),
                "overlap_rate_pct": round(ai.overlap_rate * 100, 1),
                "outranking_share_pct": round(ai.outranking_share * 100, 1),
                "position_above_rate_pct": round(ai.position_above_rate * 100, 1),
                "top_of_page_rate_pct": round(ai.top_of_page_rate * 100, 1),
                "abs_top_of_page_rate_pct": round(ai.abs_top_of_page_rate * 100, 1),
            })
    return rows


@mcp.tool()
def get_user_location_performance(
    customer_id: str,
    date_range: str = "LAST_30_DAYS",
    campaign_resource: Optional[str] = None,
    targeting_status: str = "ALL",
    limit: int = 50,
) -> list:
    """Get performance by the ACTUAL physical location of the user who clicked.

    This is different from `get_geo_performance` which shows targeted-location data.
    `user_location_view` reveals where clickers were physically located — critical
    when you want to know if your "Global" campaign is actually reaching the markets
    you expect. Exposes country_criterion_id which you decode via well-known IDs
    (2840=US, 2356=India, 2784=UAE, 2682=Saudi, 2276=Germany, 2826=UK, etc.).

    Args:
        customer_id: Google Ads customer ID (digits only)
        date_range: LAST_7_DAYS, LAST_30_DAYS, LAST_90_DAYS, THIS_MONTH, LAST_MONTH,
                    TODAY, YESTERDAY, or a literal range 'YYYY-MM-DD TO YYYY-MM-DD'
        campaign_resource: Optional — filter to one campaign
        targeting_status: ALL, TARGETING_LOCATION, or NOT_TARGETING_LOCATION.
                          TARGETING_LOCATION shows only clicks from within your
                          targeted geos; NOT_TARGETING_LOCATION shows spillover from
                          "people searching for" your targeted places but located elsewhere.
        limit: Max rows to return (default 50)
    """
    client = utils.get_googleads_client()
    svc = client.get_service("GoogleAdsService")

    if " TO " in date_range:
        start, end = date_range.split(" TO ")
        date_clause = f"segments.date BETWEEN '{start.strip()}' AND '{end.strip()}'"
    else:
        date_clause = f"segments.date DURING {date_range}"

    where_clause = date_clause
    if campaign_resource:
        where_clause += f" AND campaign.resource_name = '{campaign_resource}'"
    if targeting_status == "TARGETING_LOCATION":
        where_clause += " AND user_location_view.targeting_location = TRUE"
    elif targeting_status == "NOT_TARGETING_LOCATION":
        where_clause += " AND user_location_view.targeting_location = FALSE"

    query = f"""
        SELECT
          campaign.name,
          campaign.resource_name,
          user_location_view.country_criterion_id,
          user_location_view.targeting_location,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.ctr,
          metrics.average_cpc
        FROM user_location_view
        WHERE {where_clause}
        ORDER BY metrics.cost_micros DESC
        LIMIT {limit}
    """

    rows = []
    stream = svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            m = row.metrics
            ulv = row.user_location_view
            rows.append({
                "campaign": row.campaign.name,
                "country_criterion_id": ulv.country_criterion_id,
                "targeting_location": ulv.targeting_location,
                "impressions": m.impressions,
                "clicks": m.clicks,
                "ctr_pct": round(m.ctr * 100, 2),
                "spend_rupees": round(m.cost_micros / 1_000_000, 2),
                "avg_cpc_rupees": round(m.average_cpc / 1_000_000, 2),
                "conversions": round(m.conversions, 2),
            })
    return rows


@mcp.tool()
def get_landing_page_performance(
    customer_id: str,
    date_range: str = "LAST_30_DAYS",
    campaign_resource: Optional[str] = None,
    limit: int = 30,
) -> list:
    """Get performance broken down by landing page URL.

    Shows which pages drive conversions and which pages burn clicks. Essential
    for landing-page-level optimization — pages with low conversion rate often
    have a relevance or trust-signal problem.

    Args:
        customer_id: Google Ads customer ID (digits only)
        date_range: LAST_7_DAYS, LAST_30_DAYS, LAST_90_DAYS, etc.
        campaign_resource: Optional — filter to one campaign
        limit: Max rows to return (default 30)
    """
    client = utils.get_googleads_client()
    svc = client.get_service("GoogleAdsService")

    where_clause = f"segments.date DURING {date_range}"
    if campaign_resource:
        where_clause += f" AND campaign.resource_name = '{campaign_resource}'"

    query = f"""
        SELECT
          campaign.name,
          campaign.resource_name,
          landing_page_view.unexpanded_final_url,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.ctr,
          metrics.average_cpc
        FROM landing_page_view
        WHERE {where_clause}
        ORDER BY metrics.cost_micros DESC
        LIMIT {limit}
    """

    rows = []
    stream = svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            m = row.metrics
            conv = m.conversions
            clicks = m.clicks
            conv_rate = round((conv / clicks * 100), 2) if clicks > 0 else 0.0
            rows.append({
                "campaign": row.campaign.name,
                "landing_url": row.landing_page_view.unexpanded_final_url,
                "impressions": m.impressions,
                "clicks": clicks,
                "ctr_pct": round(m.ctr * 100, 2),
                "spend_rupees": round(m.cost_micros / 1_000_000, 2),
                "avg_cpc_rupees": round(m.average_cpc / 1_000_000, 2),
                "conversions": round(conv, 2),
                "conversion_rate_pct": conv_rate,
            })
    return rows


@mcp.tool()
def get_audience_insights(
    customer_id: str,
    campaign_resource: Optional[str] = None,
    date_range: str = "LAST_30_DAYS",
) -> list:
    """Get ad-group-level demographic and audience performance.

    Returns age, gender, parental-status, household-income, and audience
    performance segments. Use to find where the money sits — e.g. which income
    bracket actually converts on your campaign.

    Args:
        customer_id: Google Ads customer ID (digits only)
        campaign_resource: Optional — filter to one campaign
        date_range: LAST_7_DAYS, LAST_30_DAYS, LAST_90_DAYS, etc.
    """
    client = utils.get_googleads_client()
    svc = client.get_service("GoogleAdsService")

    where_clause = f"segments.date DURING {date_range}"
    if campaign_resource:
        where_clause += f" AND campaign.resource_name = '{campaign_resource}'"

    resources_to_query = [
        ("age_range_view", "age_range_view.resource_name", "age"),
        ("gender_view", "gender_view.resource_name", "gender"),
        ("parental_status_view", "parental_status_view.resource_name", "parental"),
    ]

    all_rows = []
    for resource, id_field, segment_type in resources_to_query:
        query = f"""
            SELECT
              campaign.name,
              ad_group.name,
              {id_field},
              ad_group_criterion.age_range.type,
              ad_group_criterion.gender.type,
              ad_group_criterion.parental_status.type,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions,
              metrics.ctr
            FROM {resource}
            WHERE {where_clause}
            ORDER BY metrics.cost_micros DESC
        """
        try:
            stream = svc.search_stream(customer_id=customer_id, query=query)
            for batch in stream:
                for row in batch.results:
                    m = row.metrics
                    crit = row.ad_group_criterion
                    if segment_type == "age":
                        label = crit.age_range.type_.name
                    elif segment_type == "gender":
                        label = crit.gender.type_.name
                    else:
                        label = crit.parental_status.type_.name
                    all_rows.append({
                        "segment_type": segment_type,
                        "segment_value": label,
                        "campaign": row.campaign.name,
                        "ad_group": row.ad_group.name,
                        "impressions": m.impressions,
                        "clicks": m.clicks,
                        "ctr_pct": round(m.ctr * 100, 2),
                        "spend_rupees": round(m.cost_micros / 1_000_000, 2),
                        "conversions": round(m.conversions, 2),
                    })
        except Exception as e:
            all_rows.append({"error": f"{segment_type}: {str(e)[:200]}"})
    return all_rows


@mcp.tool()
def get_search_impression_share(
    customer_id: str,
    date_range: str = "LAST_30_DAYS",
) -> list:
    """Get impression share metrics showing how often ads appear vs. how often they could.

    Low impression share means budget or bid constraints are limiting reach.
    Key metrics: search_impression_share, search_budget_lost_impression_share,
    search_rank_lost_impression_share.

    Args:
        customer_id: Google Ads customer ID (digits only)
        date_range: LAST_7_DAYS, LAST_30_DAYS, THIS_MONTH (default: LAST_30_DAYS)
    """
    client = utils.get_googleads_client()
    svc = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
          campaign.name,
          campaign.status,
          metrics.search_impression_share,
          metrics.search_budget_lost_impression_share,
          metrics.search_rank_lost_impression_share,
          metrics.search_top_impression_share,
          metrics.search_absolute_top_impression_share,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros
        FROM campaign
        WHERE segments.date DURING {date_range}
          AND campaign.status != 'REMOVED'
          AND campaign.advertising_channel_type = 'SEARCH'
        ORDER BY metrics.search_impression_share ASC
    """

    rows = []
    stream = svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            m = row.metrics
            rows.append({
                "campaign": row.campaign.name,
                "status": row.campaign.status.name,
                "impression_share_pct": round(m.search_impression_share * 100, 1) if m.search_impression_share else None,
                "lost_to_budget_pct": round(m.search_budget_lost_impression_share * 100, 1) if m.search_budget_lost_impression_share else None,
                "lost_to_rank_pct": round(m.search_rank_lost_impression_share * 100, 1) if m.search_rank_lost_impression_share else None,
                "top_impression_share_pct": round(m.search_top_impression_share * 100, 1) if m.search_top_impression_share else None,
                "abs_top_impression_share_pct": round(m.search_absolute_top_impression_share * 100, 1) if m.search_absolute_top_impression_share else None,
                "impressions": m.impressions,
                "clicks": m.clicks,
                "spend_rupees": round(m.cost_micros / 1_000_000, 2),
            })
    return rows
