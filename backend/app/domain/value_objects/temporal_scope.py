from datetime import date

from pydantic import BaseModel, Field, model_validator


class TemporalScope(BaseModel):
    """
    Describes the time period to which a fact applies.

    A fact may refer to:
    - a single date,
    - a start/end period,
    - a fiscal year,
    - a quarter,
    - or an explicitly stated period label.
    """

    start_date: date | None = Field(
        default=None,
        description="Beginning of the period covered by the fact.",
    )

    end_date: date | None = Field(
        default=None,
        description="End of the period covered by the fact.",
    )

    period_label: str | None = Field(
        default=None,
        description="Original period wording such as FY2021, Q3 2024, or December 2021.",
    )

    granularity: str | None = Field(
        default=None,
        description="Temporal granularity such as day, month, quarter, fiscal_year, or year.",
    )

    @model_validator(mode="after")
    def validate_date_range(self) -> "TemporalScope":
        """Ensure the temporal range is logically ordered."""
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date cannot be later than end_date")

        return self

    def is_same_period(self, other: "TemporalScope") -> bool:
        """
        Determine whether two temporal scopes represent the same period.
        """
        if (
            self.start_date is not None
            and self.end_date is not None
            and other.start_date is not None
            and other.end_date is not None
        ):
            return (
                self.start_date == other.start_date
                and self.end_date == other.end_date
            )

        if self.period_label and other.period_label:
            return self.period_label.strip().lower() == other.period_label.strip().lower()

        return False

    def overlaps(self, other: "TemporalScope") -> bool:
        """
        Determine whether two explicitly dated periods overlap.
        """
        if (
            self.start_date is None
            or self.end_date is None
            or other.start_date is None
            or other.end_date is None
        ):
            return False

        return self.start_date <= other.end_date and other.start_date <= self.end_date