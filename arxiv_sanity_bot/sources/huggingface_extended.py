"""HuggingFace extended API client for AI Daily Digest."""

from typing import Any, Literal

import requests
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from arxiv_sanity_bot.logger import get_logger
from arxiv_sanity_bot.config import HF_N_RETRIES, HF_WAIT_TIME

logger = get_logger(__name__)

HF_API_BASE = "https://huggingface.co/api"


class HFModel(BaseModel):
    """Model for a HuggingFace model, dataset, or space."""

    name: str = Field(..., description="Full name (e.g., 'microsoft/DialoGPT-medium')")
    description: str = Field("", description="Description or summary")
    downloads: int = Field(0, description="Download count")
    likes: int = Field(0, description="Number of likes")
    url: str = Field(..., description="HuggingFace URL")
    type: Literal["model", "dataset", "space"] = Field(..., description="Resource type")
    tags: list[str] = Field(default_factory=list, description="Tags/categories")


class HuggingFaceAPIError(Exception):
    """Exception raised for HuggingFace API errors."""

    pass


class HuggingFaceExtendedClient:
    """Extended client for fetching trending HuggingFace content."""

    def __init__(
        self,
        num_retries: int = HF_N_RETRIES,
        wait_time: int = HF_WAIT_TIME,
    ):
        """
        Initialize the HuggingFace extended client.

        Args:
            num_retries: Number of retry attempts
            wait_time: Maximum wait time between retries
        """
        self.num_retries = num_retries
        self.wait_time = wait_time

    def fetch_trending_models(
        self,
        limit: int = 10,
        sort_by: Literal["downloads", "likes"] = "downloads",
    ) -> list[HFModel]:
        """
        Fetch trending models from HuggingFace.

        Args:
            limit: Maximum number of models to return
            sort_by: Sort by 'downloads' or 'likes'

        Returns:
            List of HFModel objects
        """
        try:
            models = self._fetch_models_with_retry(limit, sort_by)
            return models
        except Exception as e:
            logger.error(
                f"Failed to fetch HuggingFace models: {e}",
                exc_info=True,
                extra={"sort_by": sort_by},
            )
            return []

    def fetch_trending_datasets(
        self,
        limit: int = 10,
        sort_by: Literal["downloads", "likes"] = "downloads",
    ) -> list[HFModel]:
        """
        Fetch trending datasets from HuggingFace.

        Args:
            limit: Maximum number of datasets to return
            sort_by: Sort by 'downloads' or 'likes'

        Returns:
            List of HFModel objects
        """
        try:
            datasets = self._fetch_datasets_with_retry(limit, sort_by)
            return datasets
        except Exception as e:
            logger.error(
                f"Failed to fetch HuggingFace datasets: {e}",
                exc_info=True,
                extra={"sort_by": sort_by},
            )
            return []

    def fetch_trending_spaces(
        self,
        limit: int = 10,
        sort_by: Literal["likes"] = "likes",
    ) -> list[HFModel]:
        """
        Fetch trending spaces from HuggingFace.

        Args:
            limit: Maximum number of spaces to return
            sort_by: Sort by 'likes' (spaces don't have download counts)

        Returns:
            List of HFModel objects
        """
        try:
            spaces = self._fetch_spaces_with_retry(limit, sort_by)
            return spaces
        except Exception as e:
            logger.error(
                f"Failed to fetch HuggingFace spaces: {e}",
                exc_info=True,
                extra={"sort_by": sort_by},
            )
            return []

    def fetch_all_trending(
        self,
        models_limit: int = 5,
        datasets_limit: int = 5,
        spaces_limit: int = 5,
    ) -> dict[str, list[HFModel]]:
        """
        Fetch trending models, datasets, and spaces.

        Args:
            models_limit: Maximum number of models
            datasets_limit: Maximum number of datasets
            spaces_limit: Maximum number of spaces

        Returns:
            Dictionary with 'models', 'datasets', and 'spaces' keys
        """
        return {
            "models": self.fetch_trending_models(models_limit),
            "datasets": self.fetch_trending_datasets(datasets_limit),
            "spaces": self.fetch_trending_spaces(spaces_limit),
        }

    @retry(
        retry=retry_if_exception_type((requests.RequestException, HuggingFaceAPIError)),
        stop=stop_after_attempt(HF_N_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=HF_WAIT_TIME),
        reraise=True,
    )
    def _fetch_models_with_retry(
        self,
        limit: int,
        sort_by: Literal["downloads", "likes"],
    ) -> list[HFModel]:
        """Fetch models with retry logic."""
        url = f"{HF_API_BASE}/models"
        params: dict[str, str | int] = {
            "limit": limit,
            "sort": "downloads" if sort_by == "downloads" else "likes",
            "direction": -1,
            "full": "true",
        }

        logger.debug("Fetching HuggingFace models", extra={"params": params})

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        models = [self._parse_model_item(item) for item in data if item]

        logger.info(f"Fetched {len(models)} models from HuggingFace")
        return models

    @retry(
        retry=retry_if_exception_type((requests.RequestException, HuggingFaceAPIError)),
        stop=stop_after_attempt(HF_N_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=HF_WAIT_TIME),
        reraise=True,
    )
    def _fetch_datasets_with_retry(
        self,
        limit: int,
        sort_by: Literal["downloads", "likes"],
    ) -> list[HFModel]:
        """Fetch datasets with retry logic."""
        url = f"{HF_API_BASE}/datasets"
        params: dict[str, str | int] = {
            "limit": limit,
            "sort": "downloads" if sort_by == "downloads" else "likes",
            "direction": -1,
            "full": "true",
        }

        logger.debug("Fetching HuggingFace datasets", extra={"params": params})

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        datasets = [self._parse_dataset_item(item) for item in data if item]

        logger.info(f"Fetched {len(datasets)} datasets from HuggingFace")
        return datasets

    @retry(
        retry=retry_if_exception_type((requests.RequestException, HuggingFaceAPIError)),
        stop=stop_after_attempt(HF_N_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=HF_WAIT_TIME),
        reraise=True,
    )
    def _fetch_spaces_with_retry(
        self,
        limit: int,
        sort_by: Literal["likes"],
    ) -> list[HFModel]:
        """Fetch spaces with retry logic."""
        url = f"{HF_API_BASE}/spaces"
        params: dict[str, str | int] = {
            "limit": limit,
            "sort": "likes",
            "direction": -1,
            "full": "true",
        }

        logger.debug("Fetching HuggingFace spaces", extra={"params": params})

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        spaces = [self._parse_space_item(item) for item in data if item]

        logger.info(f"Fetched {len(spaces)} spaces from HuggingFace")
        return spaces

    def _parse_model_item(self, item: dict[str, Any]) -> HFModel:
        """Parse a model item from API response."""
        model_id = item.get("modelId", "")
        return HFModel(
            name=model_id,
            description=item.get("description") or item.get("summary", ""),
            downloads=item.get("downloads", 0),
            likes=item.get("likes", 0),
            url=f"https://huggingface.co/{model_id}",
            type="model",
            tags=item.get("tags", []),
        )

    def _parse_dataset_item(self, item: dict[str, Any]) -> HFModel:
        """Parse a dataset item from API response."""
        dataset_id = item.get("id", "")
        return HFModel(
            name=dataset_id,
            description=item.get("description") or item.get("summary", ""),
            downloads=item.get("downloads", 0),
            likes=item.get("likes", 0),
            url=f"https://huggingface.co/datasets/{dataset_id}",
            type="dataset",
            tags=item.get("tags", []),
        )

    def _parse_space_item(self, item: dict[str, Any]) -> HFModel:
        """Parse a space item from API response."""
        space_id = item.get("id", "")
        return HFModel(
            name=space_id,
            description=item.get("description") or item.get("summary", ""),
            downloads=0,  # Spaces don't have downloads
            likes=item.get("likes", 0),
            url=f"https://huggingface.co/spaces/{space_id}",
            type="space",
            tags=item.get("tags", []),
        )


def fetch_huggingface_trending(
    models_limit: int = 5,
    datasets_limit: int = 5,
    spaces_limit: int = 5,
) -> dict[str, list[HFModel]]:
    """
    Convenience function to fetch trending HuggingFace content.

    Args:
        models_limit: Maximum number of models
        datasets_limit: Maximum number of datasets
        spaces_limit: Maximum number of spaces

    Returns:
        Dictionary with 'models', 'datasets', and 'spaces' keys
    """
    client = HuggingFaceExtendedClient()
    return client.fetch_all_trending(models_limit, datasets_limit, spaces_limit)
