from typing import TYPE_CHECKING

from frontier.contracts.deployer import Deployment, DeployRequest

if TYPE_CHECKING:
    from frontier.modules.deployer import DeployerService


class DeployerClient:
    def __init__(self, service: "DeployerService") -> None:
        self._service = service

    async def deploy(self, request: DeployRequest) -> Deployment:
        return await self._service.deploy(request)
