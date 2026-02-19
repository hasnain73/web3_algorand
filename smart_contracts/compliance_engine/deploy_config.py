import logging

import algokit_utils

logger = logging.getLogger(__name__)


# define deployment behaviour based on supplied app spec
def deploy() -> None:
    from smart_contracts.artifacts.compliance_engine.compliance_engine_client import (
        ComplianceEngineFactory,
    )

    import algokit_utils

    algorand = algokit_utils.AlgorandClient.from_environment()
    deployer_ = algorand.account.from_environment("DEPLOYER")

    factory = algorand.client.get_typed_app_factory(
        ComplianceEngineFactory, default_sender=deployer_.address
    )

    app_client, result = factory.deploy(
        on_update=algokit_utils.OnUpdate.AppendApp,
        on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
    )

    print(f"App deployed successfully with ID: {app_client.app_id}")

    # ── NEW: Fund app account to cover minimum balance for box storage ────────
    # Each box requires ~0.0025 ALGO per box + 0.0004 ALGO per byte stored.
    # Pre-fund with 1 ALGO to support initial batch/role/vendor boxes.
    fund_amount = algokit_utils.AlgoAmount(algo=1)
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=deployer_.address,
            receiver=app_client.app_address,
            amount=fund_amount,
        )
    )
    print(f"Funded app address {app_client.app_address} with {fund_amount} for box storage")
    # ─────────────────────────────────────────────────────────────────────────