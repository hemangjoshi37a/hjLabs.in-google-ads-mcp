# Copyright 2025 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tools for linking assets to campaigns, ad groups, and customers."""

from typing import Dict, Any, List, Optional
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils


@mcp.tool()
def link_asset_to_campaign(
    customer_id: str,
    campaign_resource: str,
    asset_resource_name: str,
    field_type: str,
    login_customer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Links an asset to a campaign.

    After creating an asset (sitelink, callout, etc.), use this to attach it
    to a specific campaign.

    Args:
        customer_id: The Google Ads customer ID (numbers only, no hyphens).
        campaign_resource: The campaign resource name (e.g. 'customers/XXX/campaigns/YYY').
        asset_resource_name: The resource name of the asset to link.
        field_type: The field type for the asset. One of: SITELINK, CALLOUT,
            STRUCTURED_SNIPPET, CALL, PROMOTION, PRICE, LEAD_FORM,
            BUSINESS_NAME, LOGO, LANDSCAPE_LOGO, AD_IMAGE.
            For image extensions on Search campaigns, use AD_IMAGE.
        login_customer_id: The Manager Account ID for accessing client accounts via a manager. Optional.

    Returns:
        Dictionary with the created campaign asset resource name.
    """
    client = utils.get_googleads_client(login_customer_id=login_customer_id)
    svc = client.get_service("CampaignAssetService")

    op = client.get_type("CampaignAssetOperation")
    ca = op.create
    ca.campaign = campaign_resource
    ca.asset = asset_resource_name
    ca.field_type = client.enums.AssetFieldTypeEnum[field_type]

    response = svc.mutate_campaign_assets(
        customer_id=customer_id, operations=[op]
    )

    return {
        "campaign_asset_resource_name": response.results[0].resource_name,
        "message": f"Asset linked to campaign as {field_type}.",
    }


@mcp.tool()
def link_asset_to_ad_group(
    customer_id: str,
    ad_group_resource: str,
    asset_resource_name: str,
    field_type: str,
    login_customer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Links an asset to an ad group.

    After creating an asset, use this to attach it to a specific ad group.

    Args:
        customer_id: The Google Ads customer ID (numbers only, no hyphens).
        ad_group_resource: The ad group resource name (e.g. 'customers/XXX/adGroups/YYY').
        asset_resource_name: The resource name of the asset to link.
        field_type: The field type for the asset. One of: SITELINK, CALLOUT,
            STRUCTURED_SNIPPET, CALL, PROMOTION, PRICE, AD_IMAGE.
            For image extensions on Search ad groups, use AD_IMAGE.
        login_customer_id: The Manager Account ID for accessing client accounts via a manager. Optional.

    Returns:
        Dictionary with the created ad group asset resource name.
    """
    client = utils.get_googleads_client(login_customer_id=login_customer_id)
    svc = client.get_service("AdGroupAssetService")

    op = client.get_type("AdGroupAssetOperation")
    aga = op.create
    aga.ad_group = ad_group_resource
    aga.asset = asset_resource_name
    aga.field_type = client.enums.AssetFieldTypeEnum[field_type]

    response = svc.mutate_ad_group_assets(
        customer_id=customer_id, operations=[op]
    )

    return {
        "ad_group_asset_resource_name": response.results[0].resource_name,
        "message": f"Asset linked to ad group as {field_type}.",
    }


@mcp.tool()
def link_assets_to_customer(
    customer_id: str,
    asset_resource_names: List[str],
    field_type: str,
    login_customer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Links assets to the customer (account level) — applies to all campaigns.

    Account-level assets apply to all campaigns automatically.

    Args:
        customer_id: The Google Ads customer ID (numbers only, no hyphens).
        asset_resource_names: List of asset resource names to link.
        field_type: The field type for the assets. One of: SITELINK, CALLOUT,
            STRUCTURED_SNIPPET, CALL, PROMOTION, PRICE.
        login_customer_id: The Manager Account ID for accessing client accounts via a manager. Optional.

    Returns:
        Dictionary with count of linked assets.
    """
    client = utils.get_googleads_client(login_customer_id=login_customer_id)
    svc = client.get_service("CustomerAssetService")

    ops = []
    for asset_rn in asset_resource_names:
        op = client.get_type("CustomerAssetOperation")
        ca = op.create
        ca.asset = asset_rn
        ca.field_type = client.enums.AssetFieldTypeEnum[field_type]
        ops.append(op)

    response = svc.mutate_customer_assets(
        customer_id=customer_id, operations=ops
    )

    return {
        "assets_linked": len(response.results),
        "message": f"Linked {len(response.results)} asset(s) to account as {field_type}.",
    }


@mcp.tool()
def remove_campaign_asset(
    customer_id: str,
    campaign_asset_resource_name: str,
    login_customer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Removes an asset link from a campaign.

    Use this to unlink an asset from a campaign without deleting the asset itself.

    Args:
        customer_id: The Google Ads customer ID (numbers only, no hyphens).
        campaign_asset_resource_name: The campaign asset resource name to remove
            (e.g. 'customers/XXX/campaignAssets/YYY~ZZZ~SITELINK').
        login_customer_id: The Manager Account ID for accessing client accounts via a manager. Optional.

    Returns:
        Dictionary confirming the removal.
    """
    client = utils.get_googleads_client(login_customer_id=login_customer_id)
    svc = client.get_service("CampaignAssetService")

    op = client.get_type("CampaignAssetOperation")
    op.remove = campaign_asset_resource_name

    svc.mutate_campaign_assets(customer_id=customer_id, operations=[op])

    return {
        "removed": campaign_asset_resource_name,
        "message": "Campaign asset link removed successfully.",
    }


@mcp.tool()
def link_image_assets_to_campaign(
    customer_id: str,
    campaign_resource: str,
    asset_resource_names: List[str],
    login_customer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Links image assets to a campaign as AD_IMAGE extensions.

    Use this after creating image assets with create_image_asset to attach
    them to a Search or other campaign as image extensions.

    Args:
        customer_id: The Google Ads customer ID (numbers only, no hyphens).
        campaign_resource: The campaign resource name (e.g. 'customers/XXX/campaigns/YYY').
        asset_resource_names: List of image asset resource names to link.
        login_customer_id: The Manager Account ID for accessing client accounts via a manager. Optional.

    Returns:
        Dictionary with count of linked image assets.
    """
    client = utils.get_googleads_client(login_customer_id=login_customer_id)
    svc = client.get_service("CampaignAssetService")

    ops = []
    for asset_rn in asset_resource_names:
        op = client.get_type("CampaignAssetOperation")
        ca = op.create
        ca.campaign = campaign_resource
        ca.asset = asset_rn
        ca.field_type = client.enums.AssetFieldTypeEnum.AD_IMAGE
        ops.append(op)

    response = svc.mutate_campaign_assets(
        customer_id=customer_id, operations=ops
    )

    return {
        "assets_linked": len(response.results),
        "results": [r.resource_name for r in response.results],
        "message": f"Linked {len(response.results)} image asset(s) to campaign.",
    }


@mcp.tool()
def link_image_assets_to_ad_group(
    customer_id: str,
    ad_group_resource: str,
    asset_resource_names: List[str],
    login_customer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Links image assets to an ad group as AD_IMAGE extensions.

    Use this to attach image assets to a specific ad group for image extensions.

    Args:
        customer_id: The Google Ads customer ID (numbers only, no hyphens).
        ad_group_resource: The ad group resource name (e.g. 'customers/XXX/adGroups/YYY').
        asset_resource_names: List of image asset resource names to link.
        login_customer_id: The Manager Account ID for accessing client accounts via a manager. Optional.

    Returns:
        Dictionary with count of linked image assets.
    """
    client = utils.get_googleads_client(login_customer_id=login_customer_id)
    svc = client.get_service("AdGroupAssetService")

    ops = []
    for asset_rn in asset_resource_names:
        op = client.get_type("AdGroupAssetOperation")
        aga = op.create
        aga.ad_group = ad_group_resource
        aga.asset = asset_rn
        aga.field_type = client.enums.AssetFieldTypeEnum.AD_IMAGE
        ops.append(op)

    response = svc.mutate_ad_group_assets(
        customer_id=customer_id, operations=ops
    )

    return {
        "assets_linked": len(response.results),
        "results": [r.resource_name for r in response.results],
        "message": f"Linked {len(response.results)} image asset(s) to ad group.",
    }


@mcp.tool()
def list_campaign_image_assets(
    customer_id: str,
    campaign_id: str,
    login_customer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Lists all image assets linked to a campaign.

    Args:
        customer_id: The Google Ads customer ID (numbers only, no hyphens).
        campaign_id: Campaign ID (numeric only).
        login_customer_id: The Manager Account ID for accessing client accounts via a manager. Optional.

    Returns:
        Dictionary with list of linked image assets.
    """
    client = utils.get_googleads_client(login_customer_id=login_customer_id)
    ga_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            campaign_asset.asset,
            campaign_asset.field_type,
            campaign_asset.status,
            asset.id,
            asset.name,
            asset.type,
            asset.image_asset.file_size,
            asset.image_asset.full_size.width_pixels,
            asset.image_asset.full_size.height_pixels
        FROM campaign_asset
        WHERE campaign.id = {campaign_id}
            AND asset.type = 'IMAGE'
    """

    response = ga_service.search(customer_id=customer_id, query=query)

    assets = []
    for row in response:
        assets.append({
            "asset_resource": row.campaign_asset.asset,
            "asset_id": row.asset.id,
            "name": row.asset.name,
            "field_type": row.campaign_asset.field_type.name,
            "status": row.campaign_asset.status.name,
            "width": row.asset.image_asset.full_size.width_pixels,
            "height": row.asset.image_asset.full_size.height_pixels,
            "file_size": row.asset.image_asset.file_size,
        })

    return {
        "campaign_id": campaign_id,
        "image_assets": assets,
        "count": len(assets),
    }


@mcp.tool()
def remove_ad_group_asset(
    customer_id: str,
    ad_group_asset_resource_name: str,
    login_customer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Removes an asset link from an ad group.

    Use this to unlink an asset from an ad group without deleting the asset itself.

    Args:
        customer_id: The Google Ads customer ID (numbers only, no hyphens).
        ad_group_asset_resource_name: The ad group asset resource name to remove
            (e.g. 'customers/XXX/adGroupAssets/YYY~ZZZ~AD_IMAGE').
        login_customer_id: The Manager Account ID for accessing client accounts via a manager. Optional.

    Returns:
        Dictionary confirming the removal.
    """
    client = utils.get_googleads_client(login_customer_id=login_customer_id)
    svc = client.get_service("AdGroupAssetService")

    op = client.get_type("AdGroupAssetOperation")
    op.remove = ad_group_asset_resource_name

    svc.mutate_ad_group_assets(customer_id=customer_id, operations=[op])

    return {
        "removed": ad_group_asset_resource_name,
        "message": "Ad group asset link removed successfully.",
    }
