"""Billing, balance, and account spend tools for the Google Ads MCP server."""

from typing import Optional
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils


@mcp.tool()
def get_billing_info(
    customer_id: str,
) -> dict:
    """Get billing setup and account budget information including approved spending limits.

    Returns billing status, payment method name, account budget name, approved
    spending limit, and how much has been served so far.

    Args:
        customer_id: Google Ads customer ID (digits only, e.g. '4170793536')
    """
    client = utils.get_googleads_client()
    svc = client.get_service("GoogleAdsService")

    # --- Billing setup ---
    billing_query = """
        SELECT
          billing_setup.id,
          billing_setup.status,
          billing_setup.start_date_time,
          billing_setup.payments_account_info.payments_account_name,
          billing_setup.payments_account_info.payments_profile_name
        FROM billing_setup
        WHERE billing_setup.status = 'APPROVED'
    """
    billing_results = []
    try:
        stream = svc.search_stream(customer_id=customer_id, query=billing_query)
        for batch in stream:
            for row in batch.results:
                bs = row.billing_setup
                billing_results.append({
                    "billing_setup_id": bs.id,
                    "status": bs.status.name,
                    "start_date_time": bs.start_date_time,
                    "payments_account_name": bs.payments_account_info.payments_account_name,
                    "payments_profile_name": bs.payments_account_info.payments_profile_name,
                })
    except Exception as e:
        billing_results = [{"error": str(e)}]

    # --- Account budgets ---
    budget_query = """
        SELECT
          account_budget.id,
          account_budget.name,
          account_budget.status,
          account_budget.approved_spending_limit_micros,
          account_budget.approved_spending_limit_type,
          account_budget.amount_served_micros,
          account_budget.total_adjustments_micros,
          account_budget.approved_start_date_time,
          account_budget.approved_end_date_time,
          account_budget.purchase_order_number
        FROM account_budget
        WHERE account_budget.status = 'APPROVED'
    """
    budget_results = []
    try:
        stream = svc.search_stream(customer_id=customer_id, query=budget_query)
        for batch in stream:
            for row in batch.results:
                ab = row.account_budget
                approved_limit = ab.approved_spending_limit_micros
                served = ab.amount_served_micros
                adjustments = ab.total_adjustments_micros
                remaining = approved_limit - served + adjustments if approved_limit else None
                budget_results.append({
                    "budget_id": ab.id,
                    "name": ab.name,
                    "status": ab.status.name,
                    "approved_spending_limit_type": ab.approved_spending_limit_type.name,
                    "approved_spending_limit_rupees": round(approved_limit / 1_000_000, 2) if approved_limit else "UNLIMITED",
                    "amount_served_rupees": round(served / 1_000_000, 2),
                    "total_adjustments_rupees": round(adjustments / 1_000_000, 2),
                    "estimated_remaining_rupees": round(remaining / 1_000_000, 2) if remaining is not None else "UNLIMITED",
                    "approved_start_date_time": ab.approved_start_date_time,
                    "approved_end_date_time": ab.approved_end_date_time or "No end date",
                    "purchase_order_number": ab.purchase_order_number or "N/A",
                })
    except Exception as e:
        budget_results = [{"error": str(e)}]

    return {
        "billing_setups": billing_results,
        "account_budgets": budget_results,
    }


@mcp.tool()
def get_account_spend_summary(
    customer_id: str,
    date_range: str = "LAST_30_DAYS",
) -> dict:
    """Get a spend summary across all campaigns for a given date range.

    Shows total spend, clicks, impressions, and conversions by campaign.

    Args:
        customer_id: Google Ads customer ID (digits only)
        date_range: One of TODAY, YESTERDAY, LAST_7_DAYS, LAST_30_DAYS,
                    THIS_MONTH, LAST_MONTH (default: LAST_30_DAYS)
    """
    client = utils.get_googleads_client()
    svc = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          metrics.cost_micros,
          metrics.impressions,
          metrics.clicks,
          metrics.conversions,
          metrics.ctr,
          metrics.average_cpc,
          metrics.conversion_rate,
          metrics.cost_per_conversion
        FROM campaign
        WHERE segments.date DURING {date_range}
          AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
    """

    campaigns = []
    total_spend = 0
    total_clicks = 0
    total_impressions = 0
    total_conversions = 0.0

    stream = svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            c = row.campaign
            m = row.metrics
            spend = m.cost_micros / 1_000_000
            total_spend += spend
            total_clicks += m.clicks
            total_impressions += m.impressions
            total_conversions += m.conversions
            campaigns.append({
                "campaign_id": c.id,
                "campaign_name": c.name,
                "status": c.status.name,
                "spend_rupees": round(spend, 2),
                "impressions": m.impressions,
                "clicks": m.clicks,
                "ctr_pct": round(m.ctr * 100, 2),
                "avg_cpc_rupees": round(m.average_cpc / 1_000_000, 2),
                "conversions": round(m.conversions, 2),
                "conversion_rate_pct": round(m.conversion_rate * 100, 2),
                "cost_per_conversion_rupees": round(m.cost_per_conversion / 1_000_000, 2) if m.conversions > 0 else "N/A",
            })

    return {
        "date_range": date_range,
        "summary": {
            "total_spend_rupees": round(total_spend, 2),
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "overall_ctr_pct": round((total_clicks / total_impressions * 100) if total_impressions else 0, 2),
            "total_conversions": round(total_conversions, 2),
            "cost_per_conversion_rupees": round(total_spend / total_conversions, 2) if total_conversions else "N/A",
        },
        "by_campaign": campaigns,
    }


@mcp.tool()
def get_daily_spend_trend(
    customer_id: str,
    days: int = 30,
) -> list:
    """Get day-by-day spend, clicks, and conversions for the last N days.

    Useful for spotting spend spikes, identifying best/worst days, and
    understanding burn rate against budget.

    Args:
        customer_id: Google Ads customer ID (digits only)
        days: Number of recent days to retrieve (default 30, max 90)
    """
    days = min(days, 90)
    client = utils.get_googleads_client()
    svc = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
          segments.date,
          metrics.cost_micros,
          metrics.impressions,
          metrics.clicks,
          metrics.conversions,
          metrics.ctr,
          metrics.average_cpc
        FROM customer
        WHERE segments.date DURING LAST_{days}_DAYS
        ORDER BY segments.date DESC
    """

    # LAST_N_DAYS is not valid GAQL — use date arithmetic
    query = """
        SELECT
          segments.date,
          metrics.cost_micros,
          metrics.impressions,
          metrics.clicks,
          metrics.conversions,
          metrics.average_cpc
        FROM customer
        ORDER BY segments.date DESC
        LIMIT 90
    """

    # Build date range manually
    import datetime
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)

    query = f"""
        SELECT
          segments.date,
          metrics.cost_micros,
          metrics.impressions,
          metrics.clicks,
          metrics.conversions,
          metrics.average_cpc
        FROM customer
        WHERE segments.date BETWEEN '{start.strftime('%Y-%m-%d')}' AND '{end.strftime('%Y-%m-%d')}'
        ORDER BY segments.date DESC
    """

    rows = []
    stream = svc.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            m = row.metrics
            rows.append({
                "date": row.segments.date,
                "spend_rupees": round(m.cost_micros / 1_000_000, 2),
                "impressions": m.impressions,
                "clicks": m.clicks,
                "avg_cpc_rupees": round(m.average_cpc / 1_000_000, 2),
                "conversions": round(m.conversions, 2),
            })

    return rows
