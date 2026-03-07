"""Business logic for TMF633 ServiceSpecCharacteristic and CharacteristicValueSpecification."""

import uuid

from fastapi import HTTPException, status

from src.catalog.models.orm import (
    CharacteristicValueSpecificationOrm,
    ServiceSpecCharacteristicOrm,
)
from src.catalog.models.schemas import (
    CharacteristicValueSpecCreate,
    CharacteristicValueSpecResponse,
    ServiceSpecCharacteristicCreate,
    ServiceSpecCharacteristicPatch,
    ServiceSpecCharacteristicResponse,
)
from src.catalog.repositories.characteristic_repo import (
    CharacteristicSpecRepository,
    CharacteristicValueSpecRepository,
)
from src.catalog.repositories.service_spec_repo import ServiceSpecificationRepository
from src.shared.events.bus import EventBus
from src.shared.events.schemas import EventPayload, TMFEvent


def _char_to_response(orm: ServiceSpecCharacteristicOrm) -> ServiceSpecCharacteristicResponse:
    """Map a ServiceSpecCharacteristicOrm to the response schema."""
    return ServiceSpecCharacteristicResponse.model_validate(orm)


def _vs_to_response(
    orm: CharacteristicValueSpecificationOrm,
) -> CharacteristicValueSpecResponse:
    """Map a CharacteristicValueSpecificationOrm to the response schema."""
    return CharacteristicValueSpecResponse.model_validate(orm)


class CharacteristicSpecService:
    """Service layer for TMF633 ServiceSpecCharacteristic standalone management."""

    def __init__(
        self,
        repo: CharacteristicSpecRepository,
        spec_repo: ServiceSpecificationRepository,
    ) -> None:
        self._repo = repo
        self._spec_repo = spec_repo

    async def _assert_spec_exists(self, spec_id: str) -> None:
        """Raise 404 if the parent ServiceSpecification does not exist."""
        spec = await self._spec_repo.get_by_id(spec_id)
        if spec is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceSpecification '{spec_id}' not found.",
            )

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_characteristics(
        self,
        spec_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ServiceSpecCharacteristicResponse], int]:
        """Return paginated characteristics for a specification.

        Args:
            spec_id: Parent specification UUID.
            offset: Number to skip.
            limit: Max to return.

        Returns:
            Tuple of (response items, total count).
        """
        await self._assert_spec_exists(spec_id)
        items, total = await self._repo.get_all_by_spec_id(spec_id, offset, limit)
        return [_char_to_response(i) for i in items], total

    async def get_characteristic(
        self, spec_id: str, char_id: str
    ) -> ServiceSpecCharacteristicResponse:
        """Retrieve a single characteristic or raise 404.

        Args:
            spec_id: Parent specification UUID.
            char_id: Characteristic UUID.

        Returns:
            The characteristic response.
        """
        await self._assert_spec_exists(spec_id)
        orm = await self._repo.get_by_id(spec_id, char_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceSpecCharacteristic '{char_id}' not found.",
            )
        return _char_to_response(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_characteristic(
        self, spec_id: str, data: ServiceSpecCharacteristicCreate
    ) -> ServiceSpecCharacteristicResponse:
        """Create a new ServiceSpecCharacteristic.

        Args:
            spec_id: Parent specification UUID.
            data: Validated create payload.

        Returns:
            The created characteristic response.
        """
        await self._assert_spec_exists(spec_id)
        orm = await self._repo.create(spec_id, data)
        response = _char_to_response(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="ServiceSpecCharacteristicCreateEvent",
                domain="serviceCatalog",
                title="ServiceSpecCharacteristic Created",
                description=(
                    f"ServiceSpecCharacteristic '{orm.id}' created "
                    f"under ServiceSpecification '{spec_id}'."
                ),
                event=EventPayload(resource=response),
            )
        )
        return response

    async def patch_characteristic(
        self, spec_id: str, char_id: str, data: ServiceSpecCharacteristicPatch
    ) -> ServiceSpecCharacteristicResponse:
        """Partial update of a ServiceSpecCharacteristic.

        Args:
            spec_id: Parent specification UUID.
            char_id: Characteristic UUID.
            data: Partial patch payload.

        Returns:
            The updated characteristic response.
        """
        await self._assert_spec_exists(spec_id)
        orm = await self._repo.patch(spec_id, char_id, data)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceSpecCharacteristic '{char_id}' not found.",
            )
        return _char_to_response(orm)

    async def delete_characteristic(self, spec_id: str, char_id: str) -> None:
        """Delete a ServiceSpecCharacteristic.

        Args:
            spec_id: Parent specification UUID.
            char_id: Characteristic UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        await self._assert_spec_exists(spec_id)
        deleted = await self._repo.delete(spec_id, char_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceSpecCharacteristic '{char_id}' not found.",
            )


class CharacteristicValueSpecService:
    """Service layer for TMF633 CharacteristicValueSpecification management."""

    def __init__(
        self,
        repo: CharacteristicValueSpecRepository,
        char_repo: CharacteristicSpecRepository,
        spec_repo: ServiceSpecificationRepository,
    ) -> None:
        self._repo = repo
        self._char_repo = char_repo
        self._spec_repo = spec_repo

    async def _assert_parents_exist(self, spec_id: str, char_id: str) -> None:
        """Raise 404 if spec or characteristic do not exist."""
        spec = await self._spec_repo.get_by_id(spec_id)
        if spec is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceSpecification '{spec_id}' not found.",
            )
        char = await self._char_repo.get_by_id(spec_id, char_id)
        if char is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceSpecCharacteristic '{char_id}' not found.",
            )

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_value_specs(
        self,
        spec_id: str,
        char_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[CharacteristicValueSpecResponse], int]:
        """Return paginated value specifications for a characteristic.

        Args:
            spec_id: Parent specification UUID.
            char_id: Parent characteristic UUID.
            offset: Number to skip.
            limit: Max to return.

        Returns:
            Tuple of (response items, total count).
        """
        await self._assert_parents_exist(spec_id, char_id)
        items, total = await self._repo.get_all_by_char_id(char_id, offset, limit)
        return [_vs_to_response(i) for i in items], total

    async def get_value_spec(
        self, spec_id: str, char_id: str, vs_id: str
    ) -> CharacteristicValueSpecResponse:
        """Retrieve a single CharacteristicValueSpecification or raise 404.

        Args:
            spec_id: Parent specification UUID.
            char_id: Parent characteristic UUID.
            vs_id: Value specification UUID.

        Returns:
            The value specification response.
        """
        await self._assert_parents_exist(spec_id, char_id)
        orm = await self._repo.get_by_id(char_id, vs_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CharacteristicValueSpecification '{vs_id}' not found.",
            )
        return _vs_to_response(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_value_spec(
        self, spec_id: str, char_id: str, data: CharacteristicValueSpecCreate
    ) -> CharacteristicValueSpecResponse:
        """Create a new CharacteristicValueSpecification.

        Args:
            spec_id: Parent specification UUID.
            char_id: Parent characteristic UUID.
            data: Validated create payload.

        Returns:
            The created value specification response.
        """
        await self._assert_parents_exist(spec_id, char_id)
        orm = await self._repo.create(char_id, data)
        return _vs_to_response(orm)

    async def delete_value_spec(
        self, spec_id: str, char_id: str, vs_id: str
    ) -> None:
        """Delete a CharacteristicValueSpecification.

        Args:
            spec_id: Parent specification UUID.
            char_id: Parent characteristic UUID.
            vs_id: Value specification UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        await self._assert_parents_exist(spec_id, char_id)
        deleted = await self._repo.delete(char_id, vs_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CharacteristicValueSpecification '{vs_id}' not found.",
            )
