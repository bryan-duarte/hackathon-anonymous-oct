from frontier.contracts.deployer import Deployment, DeployRequest


class DeployerService:
    """Publishes the generated replacement service. Secret handles become platform secrets."""

    async def deploy(self, request: DeployRequest) -> Deployment:
        raise NotImplementedError("deployer.deploy")
