from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from app.database.database import Base, DATABASE_URL

# Import every SQLAlchemy model so Base.metadata is complete.
from app.models.asset_registry import AssetRegistry
from app.models.asset_transaction import AssetTransaction
from app.models.asset_passport import AssetPassport
from app.models.passport_lifecycle_history import PassportLifecycleHistory
from app.models.asset_evidence import AssetEvidence
from app.models.asset_evidence_review_history import AssetEvidenceReviewHistory
from app.models.audit_event import AuditEvent
from app.models.bank_account import BankAccount
from app.models.bond import Bond
from app.models.business import Business
from app.models.company import Company
from app.models.country import Country
from app.models.crypto_wallet import CryptoWallet
from app.models.diamond import Diamond
from app.models.farm import Farm
from app.models.gold import Gold
from app.models.government_verification import GovernmentVerification
from app.models.insurance import Insurance
from app.models.intellectual_property import IntellectualProperty
from app.models.invoice import Invoice
from app.models.land import Land
from app.models.ledger_entry import LedgerEntry
from app.models.payment import Payment
from app.models.payment_audit import PaymentAudit
from app.models.payment_reconciliation import PaymentReconciliation
from app.models.pricing import Pricing
from app.models.receipt import Receipt
from app.models.stock import Stock
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.webhook_event import WebhookEvent

# Alembic Config object.
config = context.config

# Configure logging from alembic.ini when available.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use SAL's actual SQLAlchemy metadata for autogeneration.
target_metadata = Base.metadata

# Use the same database URL as the application.
config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""
    url = DATABASE_URL

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a live database connection."""
    from sqlalchemy import engine_from_config

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
