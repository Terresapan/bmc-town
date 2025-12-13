import json
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field


class BusinessExpertExtract(BaseModel):
    """A class representing raw business expert data extracted from external sources.

    This class follows the structure of the business_experts.json file and contains
    basic information about business experts before enrichment.

    Args:
        id (str): Unique identifier for the business expert.
        urls (List[str]): List of URLs with information about the business expert.
    """

    id: str = Field(description="Unique identifier for the business expert")
    urls: List[str] = Field(
        description="List of URLs with information about the business expert"
    )

    @classmethod
    def from_json(cls, metadata_file: Path) -> list["BusinessExpertExtract"]:
        with open(metadata_file, "r") as f:
            experts_data = json.load(f)

        return [cls(**expert) for expert in experts_data]


class BusinessExpert(BaseModel):
    """A class representing a business canvas expert agent with specialized knowledge.

    Args:
        id (str): Unique identifier for the business expert.
        name (str): Name of the business expert.
        domain (str): Business Model Canvas component they specialize in.
        perspective (str): Description of the expert's approach and expertise.
        style (str): Description of the expert's communication style.
    """

    id: str = Field(description="Unique identifier for the business expert")
    name: str = Field(description="Name of the business expert")
    domain: str = Field(description="Business Model Canvas component they specialize in")
    perspective: str = Field(
        description="Description of the expert's approach and expertise"
    )
    style: str = Field(description="Description of the expert's communication style")

    def __str__(self) -> str:
        return f"BusinessExpert(id={self.id}, name={self.name}, domain={self.domain}, perspective={self.perspective}, style={self.style})"
