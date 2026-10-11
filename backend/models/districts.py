"""District boundaries and administrative divisions."""

from geoalchemy2 import Geometry
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class District(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "districts"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    boundary: Mapped[object] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True),
        nullable=True,
    )
