"""Business logic for TMF638 ServiceCharacteristic and CharacteristicValue management."""

import uuid

from fastapi import HTTPException, status

from src.inventory.models.orm import CharacteristicValueOrm, ServiceCharacteristicOrm
from src.inventory.models.schemas import (
    CharacteristicValueCreate,
    CharacteristicValueResponse,
    ServiceCharacteristicCreate,
    ServiceCharacteristicPatch,
    ServiceCharacteristicResponse,
)
from src.inventory.repositories.characteristic_repo import (
    CharacteristicValueRepository,
    ServiceCharacteristicRepository,
)
from src.inventory.repositories.service_repo import ServiceRepository
from src.shared.events.bus import EventBus
from src.shared.events.schemas import EventPayload, TMFEvent


def _char_to_response(orm: ServiceCharacteristicOrm) -> ServiceCharacteristicResponse:
    """Map a ServiceCharacteristicOrm to the response schema."""
    return ServiceCharacteristicResponse.model_validate(orm)


def _val_to_response(orm: CharacteristicValueOrm) -> CharacteristicValueResponse:
    """Map a CharacteristicValueOrm to the response schema."""
    return CharacteristicValueResponse.model_validate(orm)


class ServiceCharacteristicService:
    """Service layer for TMF638 ServiceCharacteristic standalone management."""

    def __init__(
        self,
        repo: ServiceCharacteristicRepository,
        service_repo: ServiceRepository,
    ) -> None:
        self._repo = repo
        self._service_repo = service_repo

    async def _assert_service_exists(self, service_id: str) -> None:
        """Raise 404 if the parent Service does not exist."""
        svc = await self._service_repo.get_by_id(service_id)
        if svc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_id}' not found.",
            )

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_characteristics(
        self,
        service_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ServiceCharacteristicResponse], int]:
        """Return paginated characteristics for a service instance.

        Args:
            service_id: Parent service UUID.
            offset: Number to skip.
            limit: Max to return.

        Returns:
            Tuple of (response items, total count).
        """
        await self._assert_service_exists(service_id)
        items, total = await self._repo.get_all_by_service_id(service_id, offset, limit)
        return [_char_to_response(i) for i in items], total

    async def get_characteristic(
        self, service_id: str, char_id: str
    ) -> ServiceCharacteristicResponse:
        """Retrieve a single service characteristic or raise 404.

        Args:
            service_id: Parent service UUID.
            char_id: Characteristic UUID.

        Returns:
            The characteristic response.
        """
        await self._assert_service_exists(service_id)
        orm = await self._repo.get_by_id(service_id, char_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCharacteristic '{char_id}' not found.",
            )
        return _char_to_response(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_characteristic(
        self, service_id: str, data: ServiceCharacteristicCreate
    ) -> ServiceCharacteristicResponse:
        """Create a new ServiceCharacteristic under the given service.

        Args:
            service_id: Parent service UUID.
            data: Validated create payload.

        Returns:
            The created characteristic response.
        """
        await self._assert_service_exists(service_id)
        orm = await self._repo.create(service_id, data)
        response = _char_to_response(orm)

        EventBus.publish(
            TMFEvent(
                event_id=str(uuid.uuid4()),
                event_type="ServiceCharacteristicCreateEvent",
                domain="serviceInventory",
                title="ServiceCharacteristic Created",
                description=(
                    f"ServiceCharacteristic '{orm.id}' created "
                    f"under Service '{service_id}'."
                ),
                event=EventPayload(resource=response),
            )
        )
        return response

    async def patch_characteristic(
        self, service_id: str, char_id: str, data: ServiceCharacteristicPatch
    ) -> ServiceCharacteristicResponse:
        """Partial update of a ServiceCharacteristic.

        Args:
            service_id: Parent service UUID.
            char_id: Characteristic UUID.
            data: Partial patch payload.

        Returns:
            The updated characteristic response.
        """
        await self._assert_service_exists(service_id)
        orm = await self._repo.patch(service_id, char_id, data)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCharacteristic '{char_id}' not found.",
            )
        return _char_to_response(orm)

    async def delete_characteristic(self, service_id: str, char_id: str) -> None:
        """Delete a ServiceCharacteristic and all its values.

        Args:
            service_id: Parent service UUID.
            char_id: Characteristic UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        await self._assert_service_exists(service_id)
        deleted = await self._repo.delete(service_id, char_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCharacteristic '{char_id}' not found.",
            )


class CharacteristicValueService:
    """Service layer for TMF638 CharacteristicValue management."""

    def __init__(
        self,
        repo: CharacteristicValueRepository,
        char_repo: ServiceCharacteristicRepository,
        service_repo: ServiceRepository,
    ) -> None:
        self._repo = repo
        self._char_repo = char_repo
        self._service_repo = service_repo

    async def _assert_parents_exist(self, service_id: str, char_id: str) -> None:
        """Raise 404 if service or characteristic do not exist."""
        svc = await self._service_repo.get_by_id(service_id)
        if svc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_id}' not found.",
            )
        char = await self._char_repo.get_by_id(service_id, char_id)
        if char is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ServiceCharacteristic '{char_id}' not found.",
            )

    # ── Query ─────────────────────────────────────────────────────────────────

    async def list_values(
        self,
        service_id: str,
        char_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[CharacteristicValueResponse], int]:
        """Return paginated values for a service characteristic.

        Args:
            service_id: Parent service UUID.
            char_id: Parent characteristic UUID.
            offset: Number to skip.
            limit: Max to return.

        Returns:
            Tuple of (response items, total count).
        """
        await self._assert_parents_exist(service_id, char_id)
        items, total = await self._repo.get_all_by_char_id(char_id, offset, limit)
        return [_val_to_response(i) for i in items], total

    async def get_value(
        self, service_id: str, char_id: str, val_id: str
    ) -> CharacteristicValueResponse:
        """Retrieve a single CharacteristicValue or raise 404.

        Args:
            service_id: Parent service UUID.
            char_id: Parent characteristic UUID.
            val_id: CharacteristicValue UUID.

        Returns:
            The value response.
        """
        await self._assert_parents_exist(service_id, char_id)
        orm = await self._repo.get_by_id(char_id, val_id)
        if orm is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CharacteristicValue '{val_id}' not found.",
            )
        return _val_to_response(orm)

    # ── Mutation ──────────────────────────────────────────────────────────────

    async def create_value(
        self, service_id: str, char_id: str, data: CharacteristicValueCreate
    ) -> CharacteristicValueResponse:
        """Create a new CharacteristicValue.

        Args:
            service_id: Parent service UUID.
            char_id: Parent characteristic UUID.
            data: Validated create payload.

        Returns:
            The created value response.
        """
        await self._assert_parents_exist(service_id, char_id)
        orm = await self._repo.create(char_id, data)
        return _val_to_response(orm)

    async def delete_value(
        self, service_id: str, char_id: str, val_id: str
    ) -> None:
        """Delete a CharacteristicValue.

        Args:
            service_id: Parent service UUID.
            char_id: Parent characteristic UUID.
            val_id: CharacteristicValue UUID.

        Raises:
            :class:`fastapi.HTTPException` (404) if not found.
        """
        await self._assert_parents_exist(service_id, char_id)
        deleted = await self._repo.delete(char_id, val_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"CharacteristicValue '{val_id}' not found.",
            )
