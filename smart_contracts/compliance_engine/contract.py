from algopy import (
    ARC4Contract,
    Bytes,
    Global,
    String,
    Txn,
    UInt64,
    arc4,
    itxn,
    op,
)
from algopy.arc4 import abimethod, Address, DynamicArray, DynamicBytes


# ─── Constants ────────────────────────────────────────────────────────────────
STATUS_CREATED = UInt64(0)
STATUS_APPROVED = UInt64(1)
STATUS_CERTIFIED = UInt64(2)

ROLE_ADMIN = UInt64(0)
ROLE_VENDOR = UInt64(1)
ROLE_INSPECTOR = UInt64(2)


class ComplianceEngine(ARC4Contract):

    # ─── Existing State ────────────────────────────────────────────────────────
    # (Preserved exactly as original — no removal or renaming)

    # ─── NEW State (Feature 1 + 2 + 4) ────────────────────────────────────────
    # Box maps added via box_map declarations in __init__ equivalent:
    # batch_status:  Bytes → UInt64
    # batch_asset:   Bytes → UInt64   (ASA ID per batch)
    # vendor_role:   Address → UInt64 (role registry)
    # vendor_batches: Address → arc4.String  (pipe-delimited batch list)

    # ─────────────────────────────────────────────────────────────────────────
    # ORIGINAL METHODS — Preserved untouched
    # ─────────────────────────────────────────────────────────────────────────

    @abimethod()
    def create_batch(self, batch_id: UInt64) -> UInt64:
        return UInt64(0)  # STATUS_CREATED

    @abimethod()
    def approve_batch(self, batch_id: UInt64) -> UInt64:
        return UInt64(1)  # STATUS_APPROVED

    @abimethod()
    def get_batch_status(self, batch_id: UInt64) -> UInt64:
        return UInt64(1)

    # ─────────────────────────────────────────────────────────────────────────
    # NEW METHODS — Feature 1: Compliance Batch Lifecycle System
    # ─────────────────────────────────────────────────────────────────────────

    @abimethod()
    def assign_role(self, account: Address, role: UInt64) -> UInt64:
        """
        Assign a role (ROLE_VENDOR=1, ROLE_INSPECTOR=2) to an account.
        Only admin (creator) can call this.
        Emits: assign_role event log.
        """
        assert Txn.sender == Global.creator_address, "Only admin can assign roles"
        assert role == UInt64(1) or role == UInt64(2), "Invalid role"

        # Store role in box: key = b"role:" + account_bytes
        key = Bytes(b"role:") + account.bytes
        op.Box.put(key, op.itob(role))

        # Feature 3: Audit log
        log_event = String("assign_role|") + String(account.bytes.hex()) + String("|") + String(Txn.sender.bytes.hex())
        arc4.emit("assign_role", log_event)

        return role

    @abimethod()
    def create_batch_v2(self, batch_id: Bytes) -> UInt64:
        """
        Feature 1: Create a new compliance batch.
        Only ROLE_VENDOR can call.
        Stores batch state = CREATED.
        Feature 4: Appends batch_id to vendor registry.
        Feature 3: Emits audit log.
        """
        # Role check: sender must be ROLE_VENDOR
        role_key = Bytes(b"role:") + Txn.sender.bytes
        role_val, role_exists = op.Box.get(role_key)
        assert role_exists, "Sender has no assigned role"
        assert op.btoi(role_val) == UInt64(1), "Only ROLE_VENDOR can create batches"

        # State check: batch must not already exist
        state_key = Bytes(b"batch:") + batch_id
        _, already_exists = op.Box.get(state_key)
        assert not already_exists, "Batch already exists"

        # Store batch state = CREATED (0)
        op.Box.put(state_key, op.itob(UInt64(0)))

        # Feature 4: Append batch_id to vendor's list
        vendor_key = Bytes(b"vendor:") + Txn.sender.bytes
        existing, vend_exists = op.Box.get(vendor_key)
        if vend_exists:
            new_val = existing + Bytes(b"|") + batch_id
        else:
            new_val = batch_id
        op.Box.put(vendor_key, new_val)

        # Feature 3: Audit log
        log_event = String("create_batch|") + String(batch_id.hex()) + String("|") + String(Txn.sender.bytes.hex())
        arc4.emit("create_batch", log_event)

        return UInt64(0)  # STATUS_CREATED

    @abimethod()
    def approve_batch_v2(self, batch_id: Bytes) -> UInt64:
        """
        Feature 1: Approve a compliance batch.
        Only ROLE_INSPECTOR can call.
        Transitions CREATED → APPROVED.
        Feature 3: Emits audit log.
        """
        # Role check
        role_key = Bytes(b"role:") + Txn.sender.bytes
        role_val, role_exists = op.Box.get(role_key)
        assert role_exists, "Sender has no assigned role"
        assert op.btoi(role_val) == UInt64(2), "Only ROLE_INSPECTOR can approve batches"

        # State transition check
        state_key = Bytes(b"batch:") + batch_id
        state_val, state_exists = op.Box.get(state_key)
        assert state_exists, "Batch does not exist"
        assert op.btoi(state_val) == UInt64(0), "Batch must be in CREATED state"

        # Transition → APPROVED
        op.Box.put(state_key, op.itob(UInt64(1)))

        # Feature 3: Audit log
        log_event = String("approve_batch|") + String(batch_id.hex()) + String("|") + String(Txn.sender.bytes.hex())
        arc4.emit("approve_batch", log_event)

        return UInt64(1)  # STATUS_APPROVED

    @abimethod()
    def certify_batch(self, batch_id: Bytes) -> UInt64:
        """
        Feature 1: Certify a compliance batch.
        Admin (creator) OR ROLE_INSPECTOR can call.
        Transitions APPROVED → CERTIFIED.
        Feature 2: Mints certification NFT (ASA) via inner transaction.
        Feature 3: Emits audit log.
        """
        # Role check: admin OR inspector
        is_admin = Txn.sender == Global.creator_address
        if not is_admin:
            role_key = Bytes(b"role:") + Txn.sender.bytes
            role_val, role_exists = op.Box.get(role_key)
            assert role_exists, "Sender has no assigned role"
            assert op.btoi(role_val) == UInt64(2), "Only admin or ROLE_INSPECTOR can certify"

        # State transition check
        state_key = Bytes(b"batch:") + batch_id
        state_val, state_exists = op.Box.get(state_key)
        assert state_exists, "Batch does not exist"
        assert op.btoi(state_val) == UInt64(1), "Batch must be in APPROVED state"

        # Transition → CERTIFIED
        op.Box.put(state_key, op.itob(UInt64(2)))

        # ── Feature 2: Mint Certification NFT ─────────────────────────────────
        asset_name = Bytes(b"CERT-") + batch_id
        created_asset = itxn.AssetConfig(
            total=1,
            decimals=0,
            default_frozen=False,
            unit_name=b"CERT",
            asset_name=asset_name,
            manager=Global.current_application_address,
            reserve=Global.current_application_address,
            freeze=Global.zero_address,
            clawback=Global.zero_address,
            fee=0,
        ).submit()

        asa_id = created_asset.created_asset.id

        # Store ASA ID → batch mapping
        asset_key = Bytes(b"asset:") + batch_id
        op.Box.put(asset_key, op.itob(asa_id))
        # ──────────────────────────────────────────────────────────────────────

        # Feature 3: Audit log
        log_event = String("certify_batch|") + String(batch_id.hex()) + String("|") + String(Txn.sender.bytes.hex())
        arc4.emit("certify_batch", log_event)

        return UInt64(2)  # STATUS_CERTIFIED

    # ─────────────────────────────────────────────────────────────────────────
    # NEW METHODS — Feature 4: Verifiable Supply Chain Registry
    # ─────────────────────────────────────────────────────────────────────────

    @abimethod(readonly=True)
    def get_batch_status_v2(self, batch_id: Bytes) -> UInt64:
        """
        Feature 4: Get the current state of a batch by Bytes ID.
        Returns 0=CREATED, 1=APPROVED, 2=CERTIFIED, 99=NOT_FOUND.
        """
        state_key = Bytes(b"batch:") + batch_id
        state_val, state_exists = op.Box.get(state_key)
        if state_exists:
            return op.btoi(state_val)
        return UInt64(99)  # NOT_FOUND

    @abimethod(readonly=True)
    def get_batch_asset(self, batch_id: Bytes) -> UInt64:
        """
        Feature 2: Get ASA ID for a certified batch.
        Returns 0 if not certified.
        """
        asset_key = Bytes(b"asset:") + batch_id
        asset_val, asset_exists = op.Box.get(asset_key)
        if asset_exists:
            return op.btoi(asset_val)
        return UInt64(0)

    @abimethod(readonly=True)
    def get_vendor_batches(self, vendor: Address) -> arc4.String:
        """
        Feature 4: Return pipe-delimited list of batch IDs for a vendor.
        Returns empty string if vendor has no batches.
        """
        vendor_key = Bytes(b"vendor:") + vendor.bytes
        vendor_val, vend_exists = op.Box.get(vendor_key)
        if vend_exists:
            return arc4.String(vendor_val.decode())
        return arc4.String("")

    @abimethod(readonly=True)
    def get_role(self, account: Address) -> UInt64:
        """
        Helper: Return role of account.
        0=ADMIN (if creator), 1=VENDOR, 2=INSPECTOR, 99=NONE
        """
        if account.bytes == Global.creator_address.bytes:
            return UInt64(0)
        role_key = Bytes(b"role:") + account.bytes
        role_val, role_exists = op.Box.get(role_key)
        if role_exists:
            return op.btoi(role_val)
        return UInt64(99)  # NONE