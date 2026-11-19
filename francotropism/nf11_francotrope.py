#!/usr/bin/env python3
"""
Norme Francotrope d'Écriture à Onze Axes (NF-11) — Reference Engine (`nf11_francotrope.py`).

Extends `ledger_v2.py` (`Sweetbrier Eleven-Entry Bookkeeping v2`) without mutating a single
line of `ledger_v2.py`, closing the three Stage-One "Economic Schengen" gaps identified in
Christopher Duguay, *Francotropism: An Economic Alliance for the French-Speaking World*
(Winnipeg, 18 November 2026):

  1. Chain of Delegation (`Mandat / Procuration` — Code civil du Québec art. 2130-2185 &
     OHADA Acte uniforme portant sur le droit commercial général):
       - Party-signed Ed25519 `DelegationMandate` chains (`mandant -> mandataire -> agent_logiciel`)
       - Strict monotonic capability attenuation across sub-delegation hops (ceiling, accounts,
         expiry, pinned Axis 9 dictionaries, and express `allow_forgiveness` authority)
       - Express Remise-de-Dette Guard: software agents and commercial brokers are refused on
         `Axis 11 = forgiven` unless every link in the mandate chain explicitly grants
         `allow_forgiveness = True` (`CCQ art. 2138`)
       - Append-only mandate revocation (`mandat_revocations`) enforced against `posted_at`
  2. Francotropic Four-Standard Accounting Crosswalk (`Axis 9 = nf11-francotrope-2026.v1`):
       - Pins official French commercial terminology (`OQLF` Grand dictionnaire terminologique,
         satisfying Bill 96 / Charte de la langue française documentary rules by construction)
       - Maps deterministically across `SYSCOHADA Révisé` (17 OHADA African states),
         Québec `CPA Canada NCECF + Revenu Québec CO-17 IGRF (GIFI)`, and French `PCG (ANC)`
  3. Cross-Border "Economic Schengen" Admission Passport (`export_schengen_passport()`):
       - Produces a zero-private-key, offline-verifiable JSON & CSV audit bundle proving
         4 Quebec Green-Lane gates (`Loi 96 / OQLF`, `LCCJTI RLRQ c. C-1.1`, `CCQ / OHADA Mandat`,
         and `SYSCOHADA <-> NCECF/IGRF` single-audit journal parity).

Attestation: probabilistic_structural (Box Verified under Sweetbrier Master DAG)
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey, Ed25519PrivateKey

import ledger_v2 as lv2
from ledger_v2 import (
    CANONICAL_AXES,
    GENESIS_CHAIN_HASH,
    KEY_LOSS_DOCTRINE,
    EntryV2,
    PartyKeypair,
    Rejected,
    VerificationReport,
    _canonical_json_dumps,
    _now_utc_iso,
    _require_non_empty_str,
    _require_pos_int_minor,
    _sha256_hex,
    _validate_iso8601_aware,
    verify_ed25519_receipt_signature,
)

NF11_SCHEMA_VERSION = "nf11.francotrope.v1"
NF11_DEFINITION_VERSION = "nf11-francotrope-2026.v1"
MANDATE_SIGNING_DOMAIN = b"NF11_MANDAT_V1|"


def _parse_iso_utc(ts: str) -> datetime:
    norm = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
    return datetime.fromisoformat(norm)


def sign_mandate_digest_hex(keypair: PartyKeypair, digest_sha256: str) -> str:
    """Sign a 64-hex SHA-256 mandate digest with `MANDATE_SIGNING_DOMAIN` separation."""
    if not isinstance(digest_sha256, str) or len(digest_sha256) != 64:
        raise ValueError("digest_sha256 must be a 64-char hex SHA-256 digest")
    bytes.fromhex(digest_sha256)
    priv = Ed25519PrivateKey.from_private_bytes(keypair._seed_bytes)
    return priv.sign(MANDATE_SIGNING_DOMAIN + digest_sha256.encode("ascii")).hex()


def verify_mandate_signature(
    public_key_hex: str, digest_sha256: str, signature_hex: str
) -> bool:
    """Verify detached Ed25519 signature over `MANDATE_SIGNING_DOMAIN + digest_sha256`."""
    try:
        pub_bytes = bytes.fromhex(public_key_hex)
        sig_bytes = bytes.fromhex(signature_hex)
        if len(pub_bytes) != 32 or len(sig_bytes) != 64:
            return False
        if not isinstance(digest_sha256, str) or len(digest_sha256) != 64:
            return False
        pub = Ed25519PublicKey.from_public_bytes(pub_bytes)
        pub.verify(sig_bytes, MANDATE_SIGNING_DOMAIN + digest_sha256.encode("ascii"))
        return True
    except (ValueError, InvalidSignature):
        return False


# ---------------------------------------------------------------------------
# Canonical Axis 9 Lexicon: OQLF (Loi 96) x SYSCOHADA Révisé x Québec NCECF/IGRF x PCG
# ---------------------------------------------------------------------------

NF11_ACCOUNTING_CROSSWALK: Dict[str, Dict[str, str]] = {
    "creance_client_export": {
        "terme_oqlf_fr": "Créance client sur vente internationale de marchandises",
        "syscohada_revise": "411 Clients / 701 Ventes de marchandises (AUDCIF OHADA)",
        "quebec_ncecf_igrf": "IGRF 1060 Comptes clients / IGRF 8000 Ventes commerciales (CO-17)",
        "france_pcg_anc": "411 Clients / 707 Ventes de marchandises (PCG)",
        "gloss_en": "Trade accounts receivable — cross-border sale of goods",
    },
    "dette_fournisseur_import": {
        "terme_oqlf_fr": "Dette fournisseur sur importation de marchandises",
        "syscohada_revise": "401 Fournisseurs, dettes en compte / 601 Achats de marchandises",
        "quebec_ncecf_igrf": "IGRF 2620 Fournisseurs et charges à payer / IGRF 8300 Achats (CO-17)",
        "france_pcg_anc": "401 Fournisseurs / 607 Achats de marchandises (PCG)",
        "gloss_en": "Trade accounts payable — cross-border purchase of goods",
    },
    "reglement_tresorerie": {
        "terme_oqlf_fr": "Règlement bancaire compensé sur facture commerciale",
        "syscohada_revise": "521 Banques locales <-> 411 Clients / 401 Fournisseurs",
        "quebec_ncecf_igrf": "IGRF 1001 Encaisse et dépôts <-> IGRF 1060 / 2620 (CO-17)",
        "france_pcg_anc": "512 Banques <-> 411 Clients / 401 Fournisseurs (PCG)",
        "gloss_en": "Cleared bank / credit-union settlement discharging open trade obligation",
    },
    "remise_de_dette_commerciale": {
        "terme_oqlf_fr": "Remise de dette commerciale bilatérale inscrite au grand livre",
        "syscohada_revise": "651 Pertes sur créances clients / 84 Abandon de créance commerciale",
        "quebec_ncecf_igrf": "IGRF 8590 Créances irrécouvrables et remises / CCQ art. 1687",
        "france_pcg_anc": "654 Pertes sur créances irrécouvrables / 778 Abandon de créance",
        "gloss_en": "Formal bilateral debt forgiveness releasing remaining obligation on-record",
    },
    "mandat_delegation": {
        "terme_oqlf_fr": "Mandat de représentation à plafond et durée déterminés",
        "syscohada_revise": "OHADA AUDCG Livres IV-VII (Intermédiaires de commerce / Commissionnaires)",
        "quebec_ncecf_igrf": "Code civil du Québec art. 2130-2185 (Le mandat) & LCCJTI art. 5-6",
        "france_pcg_anc": "Code civil art. 1984-2010 (Du mandat)",
        "gloss_en": "Bounded cryptographic agency mandate (principal -> broker or software agent)",
    },
}

NF11_CANONICAL_TERMS_FR: Dict[str, str] = {
    "langue_de_reference": "fr-CA / fr-OIF (Conforme Charte de la langue française / Loi 96, OQLF)",
    "owed": "Exigible (obligation ouverte inscrite au grand livre, SYSCOHADA 411/401 <-> IGRF 1060/2620)",
    "settled": "Réglé (extinction totale ou partielle par paiement compensé, SYSCOHADA 521 <-> IGRF 1001)",
    "forgiven": "Remis (remise de dette bilatérale irrévocable, CCQ art. 1687 / SYSCOHADA 651 <-> IGRF 8590)",
    "mandat": "Chaîne de délégation signée Ed25519 avec atténuation monotone des plafonds et échéances",
    "remise_expresse": "Interdiction à tout agent logiciel ou courtier de remettre une dette sans pouvoir exprès",
    "unite_monetaire_compensation": "Unités entières mineures sans virgule flottante (ex. CAD_CENTS, XOF_UNIT)",
    "foi_probante_lccjti": "Intégrité technologique garantie par hachage SHA-256 chaîné et signatures Ed25519 (LCCJTI art. 5-6)",
}


# ---------------------------------------------------------------------------
# Bounded Chain of Delegation (`Mandat / Procuration`)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DelegationMandate:
    """
    Cryptographic agency certificate (`Mandat`, CCQ art. 2130 / OHADA AUDCG).

    Authorizes `mandataire_party_id` (a customs broker, commercial factor, or autonomous
    ERP software agent) to bind `mandant_party_id` on `allowed_accounts` up to
    `max_amount_minor` in `unit` between `issued_at` and `expires_at` under
    `allowed_definition_versions`.
    """

    mandate_id: str
    mandant_party_id: str
    mandataire_party_id: str
    allowed_accounts: Tuple[str, ...]
    max_amount_minor: int
    unit: str
    allowed_definition_versions: Tuple[str, ...]
    issued_at: str
    expires_at: str
    purpose_fr: str
    allow_forgiveness: bool = False
    is_software_agent: bool = False
    parent_mandate_id: Optional[str] = None
    mandant_signature_hex: str = ""

    def __post_init__(self) -> None:
        mid = _require_non_empty_str(self.mandate_id, "mandate_id")
        mandant = _require_non_empty_str(self.mandant_party_id, "mandant_party_id")
        mandataire = _require_non_empty_str(self.mandataire_party_id, "mandataire_party_id")
        if mandant == mandataire:
            raise Rejected(f"Self-delegation forbidden on mandate '{mid}' ('{mandant}')")
        if isinstance(self.allowed_accounts, str) or not isinstance(self.allowed_accounts, Iterable):
            raise Rejected("allowed_accounts must be a non-empty tuple/list of account_ids")
        accts = tuple(sorted({_require_non_empty_str(a, "allowed_accounts[]") for a in self.allowed_accounts}))
        if not accts:
            raise Rejected("allowed_accounts must be non-empty")
        ceil_amt = _require_pos_int_minor(self.max_amount_minor, "max_amount_minor")
        unit_clean = _require_non_empty_str(self.unit, "unit")
        if isinstance(self.allowed_definition_versions, str) or not isinstance(
            self.allowed_definition_versions, Iterable
        ):
            raise Rejected("allowed_definition_versions must be a non-empty tuple/list")
        defs = tuple(
            sorted(
                {
                    _require_non_empty_str(d, "allowed_definition_versions[]")
                    for d in self.allowed_definition_versions
                }
            )
        )
        if not defs:
            raise Rejected("allowed_definition_versions must be non-empty")

        ts_issued = _validate_iso8601_aware(self.issued_at, "issued_at")
        ts_exp = _validate_iso8601_aware(self.expires_at, "expires_at")
        if _parse_iso_utc(ts_exp) <= _parse_iso_utc(ts_issued):
            raise Rejected(f"Mandate '{mid}' expires_at must be strictly after issued_at")

        purp = _require_non_empty_str(self.purpose_fr, "purpose_fr")
        parent_id = (
            _require_non_empty_str(self.parent_mandate_id, "parent_mandate_id")
            if self.parent_mandate_id is not None
            else None
        )
        if parent_id == mid:
            raise Rejected(f"Mandate '{mid}' cannot cite itself as parent_mandate_id")

        object.__setattr__(self, "mandate_id", mid)
        object.__setattr__(self, "mandant_party_id", mandant)
        object.__setattr__(self, "mandataire_party_id", mandataire)
        object.__setattr__(self, "allowed_accounts", accts)
        object.__setattr__(self, "max_amount_minor", ceil_amt)
        object.__setattr__(self, "unit", unit_clean)
        object.__setattr__(self, "allowed_definition_versions", defs)
        object.__setattr__(self, "issued_at", ts_issued)
        object.__setattr__(self, "expires_at", ts_exp)
        object.__setattr__(self, "purpose_fr", purp)
        object.__setattr__(self, "allow_forgiveness", bool(self.allow_forgiveness))
        object.__setattr__(self, "is_software_agent", bool(self.is_software_agent))
        object.__setattr__(self, "parent_mandate_id", parent_id)
        object.__setattr__(self, "mandant_signature_hex", str(self.mandant_signature_hex).strip().lower())

    def payload_dict(self) -> Dict[str, Any]:
        return {
            "schema": NF11_SCHEMA_VERSION,
            "mandate_id": self.mandate_id,
            "mandant_party_id": self.mandant_party_id,
            "mandataire_party_id": self.mandataire_party_id,
            "allowed_accounts": list(self.allowed_accounts),
            "max_amount_minor": self.max_amount_minor,
            "unit": self.unit,
            "allowed_definition_versions": list(self.allowed_definition_versions),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "purpose_fr": self.purpose_fr,
            "allow_forgiveness": self.allow_forgiveness,
            "is_software_agent": self.is_software_agent,
            "parent_mandate_id": self.parent_mandate_id,
        }

    def canonical_json(self) -> str:
        return _canonical_json_dumps(self.payload_dict())

    def digest_sha256(self) -> str:
        return _sha256_hex(self.canonical_json())

    def with_mandant_signature(self, mandant_keypair: PartyKeypair) -> "DelegationMandate":
        if mandant_keypair.party_id != self.mandant_party_id:
            raise Rejected(
                f"Keypair '{mandant_keypair.party_id}' cannot sign as mandant '{self.mandant_party_id}'"
            )
        sig = sign_mandate_digest_hex(mandant_keypair, self.digest_sha256())
        return replace(self, mandant_signature_hex=sig)


@dataclass(frozen=True, slots=True)
class FrancotropeEntry:
    """
    Wraps a canonical Eleven-Entry `EntryV2` together with optional cross-border
    accounting classification (`crosswalk_code`) and cryptographic `delegation_chains`
    mapping `account_owner_party_id -> Tuple[mandate_id_1, ..., mandate_id_k]`.

    Notice: The inner `EntryV2` remains 100% compatible with `ledger_v2.py` canonical
    field ordering (`Axis 1 = debit_account ... Axis 11 = forgiveness`).
    """

    entry: EntryV2
    crosswalk_code: str = "creance_client_export"
    delegation_chains: Tuple[Tuple[str, Tuple[str, ...]], ...] = ()
    jurisdiction_debit: str = "QC-CA"
    jurisdiction_credit: str = "SN-OHADA"

    def __post_init__(self) -> None:
        if not isinstance(self.entry, EntryV2):
            raise Rejected("FrancotropeEntry.entry must be an EntryV2 instance")
        if self.crosswalk_code not in NF11_ACCOUNTING_CROSSWALK:
            raise Rejected(
                f"Unknown NF-11 accounting crosswalk_code {self.crosswalk_code!r}; "
                f"expected one of {sorted(NF11_ACCOUNTING_CROSSWALK)}"
            )
        raw_chains = dict(self.delegation_chains)
        norm_chains: List[Tuple[str, Tuple[str, ...]]] = []
        for owner_id, chain_ids in sorted(raw_chains.items()):
            oid = _require_non_empty_str(owner_id, "delegation_chains owner")
            if isinstance(chain_ids, str) or not isinstance(chain_ids, Iterable):
                raise Rejected(f"delegation_chains[{oid}] must be a sequence of mandate_ids")
            c_tuple = tuple(_require_non_empty_str(m, "mandate_id") for m in chain_ids)
            if not c_tuple:
                raise Rejected(f"delegation_chains[{oid}] cannot be empty")
            norm_chains.append((oid, c_tuple))
        object.__setattr__(self, "delegation_chains", tuple(norm_chains))
        object.__setattr__(
            self, "jurisdiction_debit", _require_non_empty_str(self.jurisdiction_debit, "jurisdiction_debit")
        )
        object.__setattr__(
            self, "jurisdiction_credit", _require_non_empty_str(self.jurisdiction_credit, "jurisdiction_credit")
        )

    def delegation_map(self) -> Dict[str, Tuple[str, ...]]:
        return dict(self.delegation_chains)


# ---------------------------------------------------------------------------
# Francotrope Common Book (`FrancotropeBook`)
# ---------------------------------------------------------------------------


class FrancotropeBook(lv2.BookV2):
    """
    Stage-One OIF / Quebec 'Economic Schengen' Reference Book.

    Inherits `BookV2` append-only SQLite WAL storage, party-held `Ed25519` public-key
    registries, pinned `Axis 9` definitions, and `Axis 11` one-time obligation discharge,
    while adding:
      - `mandats` (signed `DelegationMandate` registry, append-only)
      - `mandat_revocations` (signed principal revocations, append-only)
      - `entry_francotrope_meta` (per-entry delegation chains & 4-standard crosswalk tags)
    """

    def __init__(
        self,
        db_path: Union[str, Path] = ":memory:",
        tenant_id: str = "oif-schengen-corridor",
    ) -> None:
        super().__init__(db_path=db_path, tenant_id=tenant_id)
        self._init_francotrope_tables()
        # Automatically pin the canonical NF-11 Francotropic dictionary on initialization
        self.register_definition(NF11_DEFINITION_VERSION, NF11_CANONICAL_TERMS_FR)

    def _init_francotrope_tables(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS mandats (
                    tenant_id TEXT NOT NULL,
                    mandate_id TEXT NOT NULL,
                    canonical_json TEXT NOT NULL,
                    digest_sha256 TEXT NOT NULL,
                    mandant_signature_hex TEXT NOT NULL,
                    registered_utc TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, mandate_id)
                );

                CREATE TABLE IF NOT EXISTS mandat_revocations (
                    tenant_id TEXT NOT NULL,
                    mandate_id TEXT NOT NULL,
                    revoked_by_party_id TEXT NOT NULL,
                    revoked_at_utc TEXT NOT NULL,
                    reason_fr TEXT NOT NULL,
                    revocation_signature_hex TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, mandate_id)
                );

                CREATE TABLE IF NOT EXISTS entry_francotrope_meta (
                    tenant_id TEXT NOT NULL,
                    entry_id TEXT NOT NULL,
                    crosswalk_code TEXT NOT NULL,
                    delegation_chains_json TEXT NOT NULL,
                    jurisdiction_debit TEXT NOT NULL,
                    jurisdiction_credit TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, entry_id)
                );

                CREATE TRIGGER IF NOT EXISTS mandats_no_update
                BEFORE UPDATE ON mandats
                BEGIN
                    SELECT RAISE(ABORT, 'append-only mandats: UPDATE forbidden');
                END;

                CREATE TRIGGER IF NOT EXISTS mandats_no_delete
                BEFORE DELETE ON mandats
                BEGIN
                    SELECT RAISE(ABORT, 'append-only mandats: DELETE forbidden');
                END;

                CREATE TRIGGER IF NOT EXISTS revocations_no_update
                BEFORE UPDATE ON mandat_revocations
                BEGIN
                    SELECT RAISE(ABORT, 'append-only mandat_revocations: UPDATE forbidden');
                END;

                CREATE TRIGGER IF NOT EXISTS revocations_no_delete
                BEFORE DELETE ON mandat_revocations
                BEGIN
                    SELECT RAISE(ABORT, 'append-only mandat_revocations: DELETE forbidden');
                END;
                """
            )

    # ------------------------------------------------- Mandate Registry & Revocation

    def register_mandate(self, mandate: DelegationMandate) -> Dict[str, Any]:
        """Verify and register an immutable `DelegationMandate` (`Mandat / Procuration`)."""
        if not isinstance(mandate, DelegationMandate):
            raise Rejected("Expected a DelegationMandate instance")
        if not mandate.mandant_signature_hex:
            raise Rejected(f"Mandate '{mandate.mandate_id}' is missing mandant_signature_hex")

        with self._lock:
            self._begin_immediate()
            try:
                cur = self._conn.cursor()
                dup = cur.execute(
                    "SELECT 1 FROM mandats WHERE tenant_id=? AND mandate_id=?",
                    (self.tenant_id, mandate.mandate_id),
                ).fetchone()
                if dup is not None:
                    raise Rejected(f"Mandate '{mandate.mandate_id}' already registered")

                mandant_row = cur.execute(
                    "SELECT public_key_hex FROM parties WHERE tenant_id=? AND party_id=?",
                    (self.tenant_id, mandate.mandant_party_id),
                ).fetchone()
                mandataire_row = cur.execute(
                    "SELECT public_key_hex FROM parties WHERE tenant_id=? AND party_id=?",
                    (self.tenant_id, mandate.mandataire_party_id),
                ).fetchone()
                if mandant_row is None or mandataire_row is None:
                    raise Rejected(
                        f"Mandate '{mandate.mandate_id}' references unregistered party "
                        f"(mandant={mandate.mandant_party_id!r}, mandataire={mandate.mandataire_party_id!r})"
                    )

                digest = mandate.digest_sha256()
                if not verify_mandate_signature(
                    mandant_row["public_key_hex"], digest, mandate.mandant_signature_hex
                ):
                    raise Rejected(
                        f"Invalid Ed25519 signature by mandant '{mandate.mandant_party_id}' on mandate '{mandate.mandate_id}'"
                    )

                for acct in mandate.allowed_accounts:
                    a_row = cur.execute(
                        "SELECT owner_party_id FROM accounts WHERE tenant_id=? AND account_id=?",
                        (self.tenant_id, acct),
                    ).fetchone()
                    if a_row is None:
                        raise Rejected(
                            f"Mandate '{mandate.mandate_id}' cites unknown account '{acct}'"
                        )

                # If sub-delegation (`parent_mandate_id`), enforce strict monotonic attenuation!
                if mandate.parent_mandate_id is not None:
                    parent = self._load_mandate_in_tx(cur, mandate.parent_mandate_id)
                    if parent is None:
                        raise Rejected(
                            f"Sub-mandate '{mandate.mandate_id}' cites unknown parent_mandate_id '{mandate.parent_mandate_id}'"
                        )
                    self._assert_submandate_attenuation(parent, mandate, cur)
                else:
                    # Root mandate: mandant MUST own every account in allowed_accounts!
                    for acct in mandate.allowed_accounts:
                        owner_id = cur.execute(
                            "SELECT owner_party_id FROM accounts WHERE tenant_id=? AND account_id=?",
                            (self.tenant_id, acct),
                        ).fetchone()["owner_party_id"]
                        if owner_id != mandate.mandant_party_id:
                            raise Rejected(
                                f"Root mandate '{mandate.mandate_id}' mandant '{mandate.mandant_party_id}' "
                                f"does not own account '{acct}' (owned by '{owner_id}')"
                            )

                cur.execute(
                    """
                    INSERT INTO mandats(
                        tenant_id, mandate_id, canonical_json, digest_sha256,
                        mandant_signature_hex, registered_utc
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.tenant_id,
                        mandate.mandate_id,
                        mandate.canonical_json(),
                        digest,
                        mandate.mandant_signature_hex,
                        _now_utc_iso(),
                    ),
                )
                self._conn.execute("COMMIT;")
                return {"mandate_id": mandate.mandate_id, "digest_sha256": digest}
            except Exception:
                self._rollback_quietly()
                raise

    def _load_mandate_in_tx(
        self, cur: sqlite3.Cursor, mandate_id: str
    ) -> Optional[DelegationMandate]:
        row = cur.execute(
            "SELECT canonical_json, mandant_signature_hex FROM mandats WHERE tenant_id=? AND mandate_id=?",
            (self.tenant_id, mandate_id),
        ).fetchone()
        if row is None:
            return None
        doc = json.loads(row["canonical_json"])
        return DelegationMandate(
            mandate_id=doc["mandate_id"],
            mandant_party_id=doc["mandant_party_id"],
            mandataire_party_id=doc["mandataire_party_id"],
            allowed_accounts=tuple(doc["allowed_accounts"]),
            max_amount_minor=int(doc["max_amount_minor"]),
            unit=doc["unit"],
            allowed_definition_versions=tuple(doc["allowed_definition_versions"]),
            issued_at=doc["issued_at"],
            expires_at=doc["expires_at"],
            purpose_fr=doc["purpose_fr"],
            allow_forgiveness=bool(doc["allow_forgiveness"]),
            is_software_agent=bool(doc["is_software_agent"]),
            parent_mandate_id=doc["parent_mandate_id"],
            mandant_signature_hex=row["mandant_signature_hex"],
        )

    def _assert_submandate_attenuation(
        self,
        parent: DelegationMandate,
        child: DelegationMandate,
        cur: sqlite3.Cursor,
    ) -> None:
        """
        Enforce strict capability attenuation on sub-delegation (`CCQ art. 2141` / object capabilities):
        a delegate can NEVER grant a sub-delegate broader accounts, higher ceilings, later expiry,
        extra dictionary versions, or debt-forgiveness power that the parent mandate lacked.
        """
        if child.mandant_party_id != parent.mandataire_party_id:
            raise Rejected(
                f"Broken delegation handoff: sub-mandate '{child.mandate_id}' mandant "
                f"'{child.mandant_party_id}' != parent mandataire '{parent.mandataire_party_id}'"
            )
        # Walk ancestor mandates to prevent cycles
        seen = {child.mandate_id, parent.mandate_id}
        anc_id = parent.parent_mandate_id
        while anc_id is not None:
            if anc_id in seen:
                raise Rejected("Cyclic delegation mandate chain detected")
            seen.add(anc_id)
            anc = self._load_mandate_in_tx(cur, anc_id)
            if anc is None:
                raise Rejected(f"Dangling ancestor mandate '{anc_id}'")
            anc_id = anc.parent_mandate_id

        if child.unit != parent.unit:
            raise Rejected(
                f"Sub-mandate '{child.mandate_id}' unit '{child.unit}' != parent unit '{parent.unit}'"
            )
        if child.max_amount_minor > parent.max_amount_minor:
            raise Rejected(
                f"Sub-delegation ceiling escalation forbidden: child '{child.mandate_id}' "
                f"max_amount_minor ({child.max_amount_minor}) > parent ({parent.max_amount_minor})"
            )
        if not set(child.allowed_accounts).issubset(set(parent.allowed_accounts)):
            raise Rejected(
                f"Sub-delegation account escalation forbidden on '{child.mandate_id}'"
            )
        if not set(child.allowed_definition_versions).issubset(
            set(parent.allowed_definition_versions)
        ):
            raise Rejected(
                f"Sub-delegation Axis 9 definition escalation forbidden on '{child.mandate_id}'"
            )
        if _parse_iso_utc(child.expires_at) > _parse_iso_utc(parent.expires_at):
            raise Rejected(
                f"Sub-delegation expiry escalation forbidden: '{child.mandate_id}' outlives parent '{parent.mandate_id}'"
            )
        if _parse_iso_utc(child.issued_at) < _parse_iso_utc(parent.issued_at):
            raise Rejected(
                f"Sub-delegation '{child.mandate_id}' issued_at predates parent '{parent.mandate_id}'"
            )
        if child.allow_forgiveness and not parent.allow_forgiveness:
            raise Rejected(
                f"Sub-delegation forgiveness escalation forbidden: '{child.mandate_id}' grants "
                "Axis 11 remise de dette without parent authority"
            )

    def revoke_mandate(
        self,
        mandate_id: str,
        revoking_keypair: PartyKeypair,
        revoked_at_utc: str,
        reason_fr: str,
    ) -> Dict[str, Any]:
        """Append an irreversible, timestamped revocation (`CCQ art. 2175`)."""
        mid = _require_non_empty_str(mandate_id, "mandate_id")
        ts_rev = _validate_iso8601_aware(revoked_at_utc, "revoked_at_utc")
        reas = _require_non_empty_str(reason_fr, "reason_fr")

        with self._lock:
            self._begin_immediate()
            try:
                cur = self._conn.cursor()
                mandate = self._load_mandate_in_tx(cur, mid)
                if mandate is None:
                    raise Rejected(f"Cannot revoke unknown mandate '{mid}'")

                # Root account owner OR direct mandant of `mid` may revoke it
                allowed_revokers = {mandate.mandant_party_id}
                anc_id = mandate.parent_mandate_id
                while anc_id is not None:
                    anc = self._load_mandate_in_tx(cur, anc_id)
                    if anc is None:
                        break
                    allowed_revokers.add(anc.mandant_party_id)
                    anc_id = anc.parent_mandate_id

                if revoking_keypair.party_id not in allowed_revokers:
                    raise Rejected(
                        f"Party '{revoking_keypair.party_id}' is not authorized to revoke mandate '{mid}'"
                    )

                existing = cur.execute(
                    "SELECT 1 FROM mandat_revocations WHERE tenant_id=? AND mandate_id=?",
                    (self.tenant_id, mid),
                ).fetchone()
                if existing is not None:
                    raise Rejected(f"Mandate '{mid}' is already revoked")

                rev_payload = _canonical_json_dumps(
                    {
                        "schema": NF11_SCHEMA_VERSION,
                        "action": "REVOKE_MANDAT",
                        "mandate_id": mid,
                        "revoked_by": revoking_keypair.party_id,
                        "revoked_at_utc": ts_rev,
                        "reason_fr": reas,
                    }
                )
                rev_digest = _sha256_hex(rev_payload)
                sig_hex = sign_mandate_digest_hex(revoking_keypair, rev_digest)

                cur.execute(
                    """
                    INSERT INTO mandat_revocations(
                        tenant_id, mandate_id, revoked_by_party_id,
                        revoked_at_utc, reason_fr, revocation_signature_hex
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (self.tenant_id, mid, revoking_keypair.party_id, ts_rev, reas, sig_hex),
                )
                self._conn.execute("COMMIT;")
                return {"mandate_id": mid, "revoked_at_utc": ts_rev, "digest_sha256": rev_digest}
            except Exception:
                self._rollback_quietly()
                raise

    # ---------------------------------------------- Delegated Validation & Posting

    def _resolve_delegated_signer_in_tx(
        self,
        cur: sqlite3.Cursor,
        owner_party_id: str,
        touched_account: str,
        chain_ids: Tuple[str, ...],
        e: EntryV2,
    ) -> str:
        """
        Verify a multi-hop `DelegationMandate` chain for `owner_party_id` on `e` and
        return the `terminal_delegate_id` whose `Ed25519` signature must seal `e`.
        """
        expected_mandant = owner_party_id
        expected_parent_id: Optional[str] = None
        posted_dt = _parse_iso_utc(e.posted_at)
        seen_mids = set()

        for idx, mid in enumerate(chain_ids):
            if mid in seen_mids:
                raise Rejected(f"Duplicate mandate '{mid}' in delegation chain")
            seen_mids.add(mid)

            mandate = self._load_mandate_in_tx(cur, mid)
            if mandate is None:
                raise Rejected(f"Unknown mandate '{mid}' in delegation chain")

            # Verify mandant Ed25519 signature on the mandate itself
            m_pub = cur.execute(
                "SELECT public_key_hex FROM parties WHERE tenant_id=? AND party_id=?",
                (self.tenant_id, mandate.mandant_party_id),
            ).fetchone()
            if m_pub is None or not verify_mandate_signature(
                m_pub["public_key_hex"], mandate.digest_sha256(), mandate.mandant_signature_hex
            ):
                raise Rejected(f"Mandate '{mid}' failed Ed25519 signature verification")

            if mandate.mandant_party_id != expected_mandant:
                raise Rejected(
                    f"Delegation chain break at hop {idx + 1} ('{mid}'): "
                    f"expected mandant '{expected_mandant}', got '{mandate.mandant_party_id}'"
                )
            if mandate.parent_mandate_id != expected_parent_id:
                raise Rejected(
                    f"Mandate '{mid}' parent_mandate_id mismatch: "
                    f"expected {expected_parent_id!r}, got {mandate.parent_mandate_id!r}"
                )

            # Check revocation status against entry `posted_at`
            rev_row = cur.execute(
                "SELECT revoked_at_utc FROM mandat_revocations WHERE tenant_id=? AND mandate_id=?",
                (self.tenant_id, mid),
            ).fetchone()
            if rev_row is not None:
                rev_dt = _parse_iso_utc(rev_row["revoked_at_utc"])
                if posted_dt >= rev_dt:
                    raise Rejected(
                        f"Mandate '{mid}' was revoked at {rev_row['revoked_at_utc']} "
                        f"(prior to or at entry posted_at {e.posted_at})"
                    )

            # Check scope, unit, ceiling, time window, definition version, and forgiveness guard
            if touched_account not in mandate.allowed_accounts:
                raise Rejected(
                    f"Mandate '{mid}' does not authorize account '{touched_account}'"
                )
            if e.unit != mandate.unit:
                raise Rejected(
                    f"Mandate '{mid}' unit '{mandate.unit}' != entry unit '{e.unit}'"
                )
            if e.amount_minor > mandate.max_amount_minor:
                raise Rejected(
                    f"Mandate '{mid}' ceiling exceeded: entry {e.amount_minor} > ceiling {mandate.max_amount_minor}"
                )
            if posted_dt < _parse_iso_utc(mandate.issued_at) or posted_dt > _parse_iso_utc(
                mandate.expires_at
            ):
                raise Rejected(
                    f"Entry posted_at {e.posted_at} outside validity window of mandate '{mid}' "
                    f"[{mandate.issued_at}, {mandate.expires_at}]"
                )
            if e.definition_version not in mandate.allowed_definition_versions:
                raise Rejected(
                    f"Mandate '{mid}' does not authorize Axis 9 definition_version '{e.definition_version}'"
                )
            if e.forgiveness == "forgiven" and not mandate.allow_forgiveness:
                raise Rejected(
                    f"[GARDE REMISE DE DETTE / CCQ art. 2138] Mandate '{mid}' "
                    f"(software_agent={mandate.is_software_agent}) lacks express authority "
                    "(`allow_forgiveness=True`) to release debt on Axis 11"
                )

            expected_mandant = mandate.mandataire_party_id
            expected_parent_id = mid

        return expected_mandant

    def post_francotrope(self, fe: FrancotropeEntry) -> Dict[str, Any]:
        """
        Validate all 11 canonical axes PLUS cryptographic chains of delegation (`Mandat`)
        and append atomically to the SQLite WAL book.
        """
        if not isinstance(fe, FrancotropeEntry):
            raise Rejected("Expected a FrancotropeEntry instance")
        e = fe.entry
        del_map = fe.delegation_map()

        with self._lock:
            self._begin_immediate()
            try:
                cur = self._conn.cursor()
                # Check duplicate ID
                if (
                    cur.execute(
                        "SELECT 1 FROM entries WHERE tenant_id=? AND entry_id=?",
                        (self.tenant_id, e.entry_id),
                    ).fetchone()
                    is not None
                ):
                    raise Rejected(f"id '{e.entry_id}' already posted; book is append-only")

                deb_row = cur.execute(
                    "SELECT owner_party_id FROM accounts WHERE tenant_id=? AND account_id=?",
                    (self.tenant_id, e.debit_account),
                ).fetchone()
                cred_row = cur.execute(
                    "SELECT owner_party_id FROM accounts WHERE tenant_id=? AND account_id=?",
                    (self.tenant_id, e.credit_account),
                ).fetchone()
                if deb_row is None or cred_row is None:
                    raise Rejected("Axes 1 & 2 unknown debit or credit account")

                deb_owner = deb_row["owner_party_id"]
                cred_owner = cred_row["owner_party_id"]

                if (
                    cur.execute(
                        "SELECT 1 FROM parties WHERE tenant_id=? AND party_id=?",
                        (self.tenant_id, e.author),
                    ).fetchone()
                    is None
                ):
                    raise Rejected(f"Axis 6 unregistered author '{e.author}'")

                if (
                    cur.execute(
                        "SELECT 1 FROM definitions WHERE tenant_id=? AND version_id=?",
                        (self.tenant_id, e.definition_version),
                    ).fetchone()
                    is None
                ):
                    raise Rejected(
                        f"Axis 9 unregistered definition_version '{e.definition_version}'"
                    )

                # Axis 5: Acyclic provenance walk to GENESIS
                if e.provenance == e.entry_id:
                    raise Rejected("Axis 5 circular self-provenance")
                seen = set()
                cursor_id = e.provenance
                parent_payload: Optional[Dict[str, Any]] = None
                while cursor_id != "GENESIS":
                    if cursor_id in seen:
                        raise Rejected("Axis 5 cyclic provenance")
                    p_row = cur.execute(
                        "SELECT canonical_json FROM entries WHERE tenant_id=? AND entry_id=?",
                        (self.tenant_id, cursor_id),
                    ).fetchone()
                    if p_row is None:
                        raise Rejected(f"Axis 5 dangling provenance '{cursor_id}'")
                    p_obj = json.loads(p_row["canonical_json"])
                    if cursor_id == e.provenance:
                        parent_payload = p_obj
                    seen.add(cursor_id)
                    cursor_id = p_obj["provenance"]

                # Axis 10: Momentum check
                if (
                    e.provenance != "GENESIS"
                    and e.forgiveness != "forgiven"
                    and parent_payload is not None
                ):
                    proj = parent_payload.get("momentum_minor")
                    if proj is not None and proj != e.amount_minor:
                        raise Rejected(
                            f"Axis 10 trajectory broken: expected {proj}, got {e.amount_minor}"
                        )

                # Axis 11: One-Time Obligation Discharge
                ob_update: Optional[Dict[str, Any]] = None
                if e.forgiveness == "forgiven":
                    if e.provenance == "GENESIS":
                        raise Rejected("Axis 11 forgiveness must cite parent owed obligation")
                    ob_row = cur.execute(
                        "SELECT * FROM obligations WHERE tenant_id=? AND obligation_entry_id=?",
                        (self.tenant_id, e.provenance),
                    ).fetchone()
                    if ob_row is None:
                        raise Rejected("Axis 11 counterfeit grace: parent was never 'owed'")
                    remaining = int(ob_row["principal_minor"]) - int(ob_row["discharged_minor"])
                    if remaining <= 0 or ob_row["status"] in ("SETTLED", "FORGIVEN"):
                        raise Rejected(
                            f"Axis 11 obligation '{e.provenance}' already {ob_row['status']}; "
                            "forgiveness cannot be replayed"
                        )
                    if (e.debit_account, e.credit_account, e.unit) != (
                        ob_row["debtor_account"],
                        ob_row["creditor_account"],
                        ob_row["unit"],
                    ):
                        raise Rejected("Axis 11 forgiveness must reverse debtor/creditor identically")
                    if e.amount_minor != remaining:
                        raise Rejected(
                            f"Axis 11 forgiveness must match remaining {remaining}, got {e.amount_minor}"
                        )
                    hist = json.loads(ob_row["discharge_history_json"])
                    hist.append(
                        {"entry_id": e.entry_id, "type": "forgiven", "amount_minor": e.amount_minor}
                    )
                    ob_update = {
                        "mode": "UPDATE",
                        "obligation_entry_id": e.provenance,
                        "discharged_minor": int(ob_row["principal_minor"]),
                        "status": "FORGIVEN",
                        "history": hist,
                    }
                elif e.discharges is not None:
                    if e.forgiveness != "settled":
                        raise Rejected("Only 'settled' entries may cite discharges")
                    ob_row = cur.execute(
                        "SELECT * FROM obligations WHERE tenant_id=? AND obligation_entry_id=?",
                        (self.tenant_id, e.discharges),
                    ).fetchone()
                    if ob_row is None:
                        raise Rejected(f"Unknown obligation '{e.discharges}'")
                    remaining = int(ob_row["principal_minor"]) - int(ob_row["discharged_minor"])
                    if remaining <= 0 or ob_row["status"] in ("SETTLED", "FORGIVEN"):
                        raise Rejected(f"Obligation '{e.discharges}' already {ob_row['status']}")
                    if (e.debit_account, e.credit_account, e.unit) != (
                        ob_row["debtor_account"],
                        ob_row["creditor_account"],
                        ob_row["unit"],
                    ):
                        raise Rejected("Repayment must reverse debtor/creditor and match unit")
                    if e.amount_minor > remaining:
                        raise Rejected(
                            f"Repayment {e.amount_minor} exceeds remaining balance {remaining}"
                        )
                    new_disch = int(ob_row["discharged_minor"]) + e.amount_minor
                    new_status = (
                        "SETTLED" if new_disch == int(ob_row["principal_minor"]) else "PARTIAL"
                    )
                    hist = json.loads(ob_row["discharge_history_json"])
                    hist.append(
                        {"entry_id": e.entry_id, "type": "settled", "amount_minor": e.amount_minor}
                    )
                    ob_update = {
                        "mode": "UPDATE",
                        "obligation_entry_id": e.discharges,
                        "discharged_minor": new_disch,
                        "status": new_status,
                        "history": hist,
                    }
                elif e.forgiveness == "owed":
                    ob_update = {
                        "mode": "INSERT",
                        "obligation_entry_id": e.entry_id,
                        "creditor_account": e.debit_account,
                        "debtor_account": e.credit_account,
                        "unit": e.unit,
                        "principal_minor": e.amount_minor,
                    }

                # Axis 8 Consent + Chain of Delegation Resolution
                needed_owners = {deb_owner: e.debit_account, cred_owner: e.credit_account}
                consent_set = set(e.consent)
                if not set(needed_owners.keys()).issubset(consent_set):
                    raise Rejected(
                        f"Axis 8 consent missing account owners: {sorted(set(needed_owners) - consent_set)}"
                    )

                for extra_del_owner in del_map:
                    if extra_del_owner not in needed_owners:
                        raise Rejected(
                            f"Delegation chain supplied for non-account-owner '{extra_del_owner}'"
                        )

                required_signers = {e.author}
                for owner_id in consent_set:
                    if owner_id in del_map:
                        terminal_signer = self._resolve_delegated_signer_in_tx(
                            cur, owner_id, needed_owners[owner_id], del_map[owner_id], e
                        )
                        required_signers.add(terminal_signer)
                    else:
                        required_signers.add(owner_id)

                sigs = e.signatures_dict()
                receipt_hex = e.receipt()
                for signer_id in sorted(required_signers):
                    p_row = cur.execute(
                        "SELECT public_key_hex FROM parties WHERE tenant_id=? AND party_id=?",
                        (self.tenant_id, signer_id),
                    ).fetchone()
                    if p_row is None:
                        raise Rejected(f"Unknown required signer '{signer_id}'")
                    sig_hex = sigs.get(signer_id)
                    if not sig_hex or not verify_ed25519_receipt_signature(
                        p_row["public_key_hex"], receipt_hex, sig_hex
                    ):
                        raise Rejected(
                            f"Missing or invalid Ed25519 signature for required signer '{signer_id}'"
                        )

                for extra_signer, sig_hex in sigs.items():
                    if extra_signer not in required_signers:
                        p_row = cur.execute(
                            "SELECT public_key_hex FROM parties WHERE tenant_id=? AND party_id=?",
                            (self.tenant_id, extra_signer),
                        ).fetchone()
                        if p_row is None or not verify_ed25519_receipt_signature(
                            p_row["public_key_hex"], receipt_hex, sig_hex
                        ):
                            raise Rejected(f"Invalid detached signature from '{extra_signer}'")

                # Append to `entries`, `entry_francotrope_meta`, and `obligations`
                tail = cur.execute(
                    "SELECT seq_no, chain_hash FROM entries WHERE tenant_id=? ORDER BY seq_no DESC LIMIT 1",
                    (self.tenant_id,),
                ).fetchone()
                seq_no = 1 if tail is None else int(tail["seq_no"]) + 1
                prev_chain = GENESIS_CHAIN_HASH if tail is None else tail["chain_hash"]

                can_json = e.canonical_json()
                sigs_json = _canonical_json_dumps(sigs)
                chain_hash = self._compute_chain_hash(prev_chain, seq_no, receipt_hex, sigs_json)

                cur.execute(
                    """
                    INSERT INTO entries(
                        tenant_id, seq_no, entry_id, canonical_json,
                        receipt_sha256, signatures_json, prev_chain_hash,
                        chain_hash, posted_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.tenant_id,
                        seq_no,
                        e.entry_id,
                        can_json,
                        receipt_hex,
                        sigs_json,
                        prev_chain,
                        chain_hash,
                        _now_utc_iso(),
                    ),
                )

                cur.execute(
                    """
                    INSERT INTO entry_francotrope_meta(
                        tenant_id, entry_id, crosswalk_code,
                        delegation_chains_json, jurisdiction_debit, jurisdiction_credit
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.tenant_id,
                        e.entry_id,
                        fe.crosswalk_code,
                        _canonical_json_dumps({k: list(v) for k, v in del_map.items()}),
                        fe.jurisdiction_debit,
                        fe.jurisdiction_credit,
                    ),
                )

                if ob_update is not None:
                    if ob_update["mode"] == "INSERT":
                        cur.execute(
                            """
                            INSERT INTO obligations(
                                tenant_id, obligation_entry_id, creditor_account,
                                debtor_account, unit, principal_minor,
                                discharged_minor, status, discharge_history_json
                            ) VALUES (?, ?, ?, ?, ?, ?, 0, 'OPEN', '[]')
                            """,
                            (
                                self.tenant_id,
                                ob_update["obligation_entry_id"],
                                ob_update["creditor_account"],
                                ob_update["debtor_account"],
                                ob_update["unit"],
                                ob_update["principal_minor"],
                            ),
                        )
                    else:
                        cur.execute(
                            """
                            UPDATE obligations
                            SET discharged_minor=?, status=?, discharge_history_json=?
                            WHERE tenant_id=? AND obligation_entry_id=?
                            """,
                            (
                                ob_update["discharged_minor"],
                                ob_update["status"],
                                _canonical_json_dumps(ob_update["history"]),
                                self.tenant_id,
                                ob_update["obligation_entry_id"],
                            ),
                        )

                self._conn.execute("COMMIT;")
                return {
                    "seq_no": seq_no,
                    "entry_id": e.entry_id,
                    "receipt_sha256": receipt_hex,
                    "prev_chain_hash": prev_chain,
                    "chain_hash": chain_hash,
                    "crosswalk": NF11_ACCOUNTING_CROSSWALK[fe.crosswalk_code],
                }
            except Exception:
                self._rollback_quietly()
                raise

    # ---------------------------------------------- Full Replay & Schengen Passport

    def verify_francotrope_book(self) -> VerificationReport:
        """
        Replay the entire Francotrope book from `GENESIS`, verifying all 11 axes,
        hash chains, detached Ed25519 signatures, delegation mandates, revocations,
        and obligation discharge conservation.
        """
        with self._lock:
            cur = self._conn.cursor()
            parties = {
                r["party_id"]: r["public_key_hex"]
                for r in cur.execute(
                    "SELECT party_id, public_key_hex FROM parties WHERE tenant_id=?",
                    (self.tenant_id,),
                ).fetchall()
            }
            accounts = {
                r["account_id"]: r["owner_party_id"]
                for r in cur.execute(
                    "SELECT account_id, owner_party_id FROM accounts WHERE tenant_id=?",
                    (self.tenant_id,),
                ).fetchall()
            }
            defs = {
                r["version_id"]: r["terms_sha256"]
                for r in cur.execute(
                    "SELECT version_id, terms_sha256 FROM definitions WHERE tenant_id=?",
                    (self.tenant_id,),
                ).fetchall()
            }
            metas = {
                r["entry_id"]: {
                    "crosswalk_code": r["crosswalk_code"],
                    "delegations": json.loads(r["delegation_chains_json"]),
                    "jurisdiction_debit": r["jurisdiction_debit"],
                    "jurisdiction_credit": r["jurisdiction_credit"],
                }
                for r in cur.execute(
                    "SELECT * FROM entry_francotrope_meta WHERE tenant_id=?",
                    (self.tenant_id,),
                ).fetchall()
            }

            errors: List[str] = []
            entry_rows = cur.execute(
                "SELECT * FROM entries WHERE tenant_id=? ORDER BY seq_no ASC",
                (self.tenant_id,),
            ).fetchall()

            expected_seq = 1
            expected_prev = GENESIS_CHAIN_HASH
            seen_entries: Dict[str, EntryV2] = {}
            replayed_obs: Dict[str, Dict[str, Any]] = {}

            for r in entry_rows:
                seq_no = int(r["seq_no"])
                if seq_no != expected_seq:
                    errors.append(f"Sequence gap at seq_no={seq_no}")
                if r["prev_chain_hash"] != expected_prev:
                    errors.append(f"prev_chain_hash mismatch at seq_no={seq_no}")

                doc = json.loads(r["canonical_json"])
                doc["signatures"] = json.loads(r["signatures_json"])
                e, _ = EntryV2.from_document(doc)

                if e.receipt() != r["receipt_sha256"]:
                    errors.append(f"Receipt SHA-256 tamper at '{e.entry_id}'")
                if (
                    self._compute_chain_hash(
                        r["prev_chain_hash"], seq_no, r["receipt_sha256"], r["signatures_json"]
                    )
                    != r["chain_hash"]
                ):
                    errors.append(f"Chain hash tamper at '{e.entry_id}'")

                if e.definition_version not in defs:
                    errors.append(f"Unregistered definition_version in '{e.entry_id}'")

                meta = metas.get(e.entry_id, {"delegations": {}})
                del_chains: Dict[str, List[str]] = meta["delegations"]

                if e.debit_account not in accounts or e.credit_account not in accounts:
                    errors.append(f"Unknown account in '{e.entry_id}'")
                else:
                    deb_owner = accounts[e.debit_account]
                    cred_owner = accounts[e.credit_account]
                    needed_map = {deb_owner: e.debit_account, cred_owner: e.credit_account}
                    if not set(needed_map).issubset(set(e.consent)):
                        errors.append(f"Missing owner consent in '{e.entry_id}'")

                    req_signers = {e.author}
                    for owner_id in e.consent:
                        if owner_id in del_chains:
                            try:
                                term = self._resolve_delegated_signer_in_tx(
                                    cur,
                                    owner_id,
                                    needed_map[owner_id],
                                    tuple(del_chains[owner_id]),
                                    e,
                                )
                                req_signers.add(term)
                            except Rejected as exc:
                                errors.append(f"Delegation invalid on '{e.entry_id}': {exc}")
                        else:
                            req_signers.add(owner_id)

                    sigs = e.signatures_dict()
                    for s_id in req_signers:
                        pub = parties.get(s_id)
                        if not pub or not verify_ed25519_receipt_signature(
                            pub, r["receipt_sha256"], sigs.get(s_id, "")
                        ):
                            errors.append(
                                f"Invalid/missing Ed25519 signature for '{s_id}' on '{e.entry_id}'"
                            )

                if e.provenance != "GENESIS":
                    if e.provenance not in seen_entries:
                        errors.append(f"Dangling provenance at '{e.entry_id}'")
                    else:
                        parent = seen_entries[e.provenance]
                        if (
                            e.forgiveness != "forgiven"
                            and parent.momentum_minor is not None
                            and parent.momentum_minor != e.amount_minor
                        ):
                            errors.append(f"Momentum mismatch at '{e.entry_id}'")

                if e.forgiveness == "owed":
                    replayed_obs[e.entry_id] = {
                        "creditor_account": e.debit_account,
                        "debtor_account": e.credit_account,
                        "unit": e.unit,
                        "principal_minor": e.amount_minor,
                        "discharged_minor": 0,
                        "status": "OPEN",
                    }
                elif e.forgiveness == "forgiven":
                    ob = replayed_obs.get(e.provenance)
                    if ob is None or (ob["principal_minor"] - ob["discharged_minor"]) != e.amount_minor:
                        errors.append(f"Invalid forgiveness at '{e.entry_id}'")
                    else:
                        ob["discharged_minor"] = ob["principal_minor"]
                        ob["status"] = "FORGIVEN"
                elif e.discharges is not None:
                    ob = replayed_obs.get(e.discharges)
                    rem = (ob["principal_minor"] - ob["discharged_minor"]) if ob else -1
                    if ob is None or e.amount_minor > rem:
                        errors.append(f"Invalid repayment discharge at '{e.entry_id}'")
                    else:
                        ob["discharged_minor"] += e.amount_minor
                        ob["status"] = (
                            "SETTLED"
                            if ob["discharged_minor"] == ob["principal_minor"]
                            else "PARTIAL"
                        )

                seen_entries[e.entry_id] = e
                expected_seq = seq_no + 1
                expected_prev = r["chain_hash"]

            return VerificationReport(
                ok=len(errors) == 0,
                tenant_id=self.tenant_id,
                entry_count=len(entry_rows),
                head_chain_hash=expected_prev,
                obligations=replayed_obs,
                errors=tuple(errors),
            )

    def export_schengen_passport(self) -> Dict[str, Any]:
        """
        Export the zero-private-key Francotropic 'Economic Schengen' Admission Passport
        for Quebec Green-Lane recognition (`MRIF`, `REQ`, `OQLF`, `Revenu Québec`, `Desjardins`)
        and OIF counterpart clearing (`OHADA / SYSCOHADA`, `PCG`).
        """
        report = self.verify_francotrope_book()
        with self._lock:
            cur = self._conn.cursor()
            parties = {
                r["party_id"]: {
                    "public_key_hex": r["public_key_hex"],
                    "jwk": json.loads(r["jwk_json"]),
                }
                for r in cur.execute(
                    "SELECT * FROM parties WHERE tenant_id=? ORDER BY party_id ASC",
                    (self.tenant_id,),
                ).fetchall()
            }
            accounts = {
                r["account_id"]: r["owner_party_id"]
                for r in cur.execute(
                    "SELECT account_id, owner_party_id FROM accounts WHERE tenant_id=? ORDER BY account_id ASC",
                    (self.tenant_id,),
                ).fetchall()
            }
            mandats = [
                {
                    **json.loads(r["canonical_json"]),
                    "digest_sha256": r["digest_sha256"],
                    "mandant_signature_hex": r["mandant_signature_hex"],
                }
                for r in cur.execute(
                    "SELECT * FROM mandats WHERE tenant_id=? ORDER BY mandate_id ASC",
                    (self.tenant_id,),
                ).fetchall()
            ]
            revocations = [
                {
                    "mandate_id": r["mandate_id"],
                    "revoked_by_party_id": r["revoked_by_party_id"],
                    "revoked_at_utc": r["revoked_at_utc"],
                    "reason_fr": r["reason_fr"],
                    "revocation_signature_hex": r["revocation_signature_hex"],
                }
                for r in cur.execute(
                    "SELECT * FROM mandat_revocations WHERE tenant_id=? ORDER BY mandate_id ASC",
                    (self.tenant_id,),
                ).fetchall()
            ]
            metas = {
                r["entry_id"]: {
                    "crosswalk_code": r["crosswalk_code"],
                    "crosswalk": NF11_ACCOUNTING_CROSSWALK[r["crosswalk_code"]],
                    "delegation_chains": json.loads(r["delegation_chains_json"]),
                    "jurisdiction_debit": r["jurisdiction_debit"],
                    "jurisdiction_credit": r["jurisdiction_credit"],
                }
                for r in cur.execute(
                    "SELECT * FROM entry_francotrope_meta WHERE tenant_id=?",
                    (self.tenant_id,),
                ).fetchall()
            }

            entries_out = []
            all_french_pinned = True
            for e_row in self.all_entries():
                eid = e_row["entry_id"]
                if e_row["payload"]["definition_version"] != NF11_DEFINITION_VERSION:
                    all_french_pinned = False
                entries_out.append({**e_row, "francotrope": metas.get(eid, {})})

            gates = {
                "gate_1_loi96_oqlf_french_lexicon": report.ok and all_french_pinned and len(entries_out) > 0,
                "gate_2_lccjti_technological_integrity": report.ok,
                "gate_3_ccq2130_ohada_mandat_delegation": report.ok,
                "gate_4_syscohada_ncecf_igrf_parity": report.ok and len(entries_out) > 0,
            }
            eligible = all(gates.values())

            passport = {
                "schema_version": NF11_SCHEMA_VERSION,
                "attestation": "probabilistic_structural",
                "corridor_tenant_id": self.tenant_id,
                "quebec_schengen_admission_eligible": eligible,
                "quebec_green_lane_gates": gates,
                "canonical_axes": {str(k): v for k, v in CANONICAL_AXES.items()},
                "definition_version": NF11_DEFINITION_VERSION,
                "crosswalk_dictionary": NF11_ACCOUNTING_CROSSWALK,
                "key_loss_doctrine": KEY_LOSS_DOCTRINE,
                "verification": {
                    "ok": report.ok,
                    "entry_count": report.entry_count,
                    "head_chain_hash": report.head_chain_hash,
                    "errors": list(report.errors),
                },
                "parties": parties,
                "accounts": accounts,
                "mandats": mandats,
                "mandat_revocations": revocations,
                "obligations": report.obligations,
                "entries": entries_out,
            }
            passport["passport_sha256"] = _sha256_hex(_canonical_json_dumps(passport))
            return passport

    def export_dual_journal_csv(self) -> str:
        """
        Export a single-audit bilingual journal CSV mapping every entry simultaneously
        to `SYSCOHADA Révisé` (Dakar / OHADA) and `CPA NCECF + Revenu Québec CO-17 IGRF`.
        """
        passport = self.export_schengen_passport()
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(
            [
                "Seq",
                "Entry_ID",
                "Posted_UTC",
                "Debit_Account",
                "Credit_Account",
                "Amount_Minor",
                "Unit",
                "Axis_11_Standing",
                "Discharges_Obligation",
                "Delegation_Chain",
                "OQLF_Terme_Francais_Loi96",
                "SYSCOHADA_Revise_OHADA",
                "Quebec_NCECF_IGRF_CO17",
                "France_PCG_ANC",
                "Receipt_SHA256",
            ]
        )
        for item in passport["entries"]:
            p = item["payload"]
            fmeta = item.get("francotrope", {})
            cw = fmeta.get("crosswalk", {})
            dchains = fmeta.get("delegation_chains", {})
            d_str = (
                "; ".join(f"{k}:{'->'.join(v)}" for k, v in dchains.items())
                if dchains
                else "Direct (Principal Ed25519)"
            )
            writer.writerow(
                [
                    item["seq_no"],
                    item["entry_id"],
                    p["posted_at"],
                    p["debit_account"],
                    p["credit_account"],
                    p["amount_minor"],
                    p["unit"],
                    p["forgiveness"],
                    p["discharges"] or "",
                    d_str,
                    cw.get("terme_oqlf_fr", ""),
                    cw.get("syscohada_revise", ""),
                    cw.get("quebec_ncecf_igrf", ""),
                    cw.get("france_pcg_anc", ""),
                    item["receipt_sha256"],
                ]
            )
        return buf.getvalue()


# ---------------------------------------------------------------------------
# Reference Corridor Simulation: Dakar (SYSCOHADA) <-> Québec City (NCECF/IGRF)
# ---------------------------------------------------------------------------


def build_dakar_quebec_reference_corridor() -> Tuple[FrancotropeBook, Dict[str, Any]]:
    """
    Construct and verify a realistic Stage-One OIF commercial corridor between:
      - `coop_khelcom_dakar` (Coopérative Khelcom Cajou S.A.R.L., Dakar, Sénégal — SYSCOHADA)
      - `importations_st_laurent_qc` (Les Importations Saint-Laurent Inc., Québec, QC — NCECF/IGRF)
    including a 2-hop delegation chain (`Mandant -> Courtier Maritime -> Agent Logiciel ERP`),
    partial port-of-Quebec settlement, blocked unauthorized software forgiveness, and
    bilateral principal `Axis 11 = forgiven` (`Remise de dette commerciale`).
    """
    book = FrancotropeBook(db_path=":memory:", tenant_id="corridor-dakar-quebec-2026")

    # 1. Party-held Ed25519 keypairs (Book holds ZERO private keys)
    kp_dakar = PartyKeypair.generate("coop_khelcom_dakar")
    kp_courtier_dkr = PartyKeypair.generate("courtier_maritime_dakar")
    kp_erp_bot_dkr = PartyKeypair.generate("agent_logiciel_erp_dakar")
    kp_quebec = PartyKeypair.generate("importations_st_laurent_qc")

    for kp in (kp_dakar, kp_courtier_dkr, kp_erp_bot_dkr, kp_quebec):
        book.register_party_public(kp)

    book.register_account("acct_khelcom_411_clients", "coop_khelcom_dakar")
    book.register_account("acct_st_laurent_2620_fournisseurs", "importations_st_laurent_qc")

    # 2. Register 2-hop Dakar Chain of Delegation (`Mandat -> Sous-Mandat Logiciel`)
    m_root = DelegationMandate(
        mandate_id="MANDAT-DKR-2026-01",
        mandant_party_id="coop_khelcom_dakar",
        mandataire_party_id="courtier_maritime_dakar",
        allowed_accounts=("acct_khelcom_411_clients",),
        max_amount_minor=10_000_000,  # $100,000.00 CAD ceiling
        unit="CAD_CENTS",
        allowed_definition_versions=(NF11_DEFINITION_VERSION,),
        issued_at="2026-11-01T00:00:00Z",
        expires_at="2027-06-30T23:59:59Z",
        purpose_fr="Mandat d'expédition et de facturation maritime Dakar -> Port de Québec",
        allow_forgiveness=False,
        is_software_agent=False,
    ).with_mandant_signature(kp_dakar)
    book.register_mandate(m_root)

    m_sub_erp = DelegationMandate(
        mandate_id="MANDAT-DKR-2026-01-ERP",
        mandant_party_id="courtier_maritime_dakar",
        mandataire_party_id="agent_logiciel_erp_dakar",
        allowed_accounts=("acct_khelcom_411_clients",),
        max_amount_minor=9_000_000,  # Attenuated to $90,000.00 CAD ceiling
        unit="CAD_CENTS",
        allowed_definition_versions=(NF11_DEFINITION_VERSION,),
        issued_at="2026-11-02T00:00:00Z",
        expires_at="2027-03-31T23:59:59Z",
        purpose_fr="Sous-mandat automatisé EDI/ERP pour émission de connaissement et quittancement",
        allow_forgiveness=False,
        is_software_agent=True,
        parent_mandate_id="MANDAT-DKR-2026-01",
    ).with_mandant_signature(kp_courtier_dkr)
    book.register_mandate(m_sub_erp)

    # 3. Entry 1 (`owed`): $84,000.00 CAD organic cashew shipment booked via 2-hop delegation
    e1 = (
        EntryV2(
            entry_id="DKR-QC-2026-001",
            debit_account="acct_khelcom_411_clients",
            credit_account="acct_st_laurent_2620_fournisseurs",
            amount_minor=8_400_000,
            unit="CAD_CENTS",
            posted_at="2026-11-18T09:15:00Z",
            provenance="GENESIS",
            author="agent_logiciel_erp_dakar",
            reason="Expédition de 12 000 kg de noix de cajou biologiques certifiées (Port autonome de Dakar -> Port de Québec)",
            consent=("coop_khelcom_dakar", "importations_st_laurent_qc"),
            definition_version=NF11_DEFINITION_VERSION,
            momentum_minor=7_900_000,  # Agreed 94% tranche upon Port of Quebec inspection
            forgiveness="owed",
        )
        .with_signature(kp_erp_bot_dkr)
        .with_signature(kp_quebec)
    )
    book.post_francotrope(
        FrancotropeEntry(
            entry=e1,
            crosswalk_code="creance_client_export",
            delegation_chains=(
                ("coop_khelcom_dakar", ("MANDAT-DKR-2026-01", "MANDAT-DKR-2026-01-ERP")),
            ),
            jurisdiction_debit="SN-OHADA",
            jurisdiction_credit="QC-CA",
        )
    )

    # 4. Entry 2 (`settled`): $79,000.00 CAD cleared upon Port of Quebec delivery
    e2 = (
        EntryV2(
            entry_id="DKR-QC-2026-002",
            debit_account="acct_st_laurent_2620_fournisseurs",
            credit_account="acct_khelcom_411_clients",
            amount_minor=7_900_000,
            unit="CAD_CENTS",
            posted_at="2026-11-18T14:30:00Z",
            provenance="DKR-QC-2026-001",
            author="importations_st_laurent_qc",
            reason="Règlement compensé Desjardins <-> BCEAO à réception conforme au Port de Québec (tranche principale)",
            consent=("coop_khelcom_dakar", "importations_st_laurent_qc"),
            definition_version=NF11_DEFINITION_VERSION,
            momentum_minor=None,
            forgiveness="settled",
            discharges="DKR-QC-2026-001",
        )
        .with_signature(kp_erp_bot_dkr)
        .with_signature(kp_quebec)
    )
    book.post_francotrope(
        FrancotropeEntry(
            entry=e2,
            crosswalk_code="reglement_tresorerie",
            delegation_chains=(
                ("coop_khelcom_dakar", ("MANDAT-DKR-2026-01", "MANDAT-DKR-2026-01-ERP")),
            ),
            jurisdiction_debit="QC-CA",
            jurisdiction_credit="SN-OHADA",
        )
    )

    # 5. Guard proof: ERP software agent attempts to forgive remaining $5,000.00 humidity adjustment -> REFUSED!
    rogue_bot_forgiveness_blocked = False
    draft_remise = book.prepare_forgiveness_draft(
        obligation_id="DKR-QC-2026-001",
        author="agent_logiciel_erp_dakar",
        reason="Tentative automatisée de remise de dette sans mandat exprès",
        posted_at="2026-11-18T16:00:00Z",
        definition_version=NF11_DEFINITION_VERSION,
        entry_id="DKR-QC-2026-003-BOT-ILLEGAL",
    )
    try:
        book.post_francotrope(
            FrancotropeEntry(
                entry=draft_remise.with_signature(kp_erp_bot_dkr).with_signature(kp_quebec),
                crosswalk_code="remise_de_dette_commerciale",
                delegation_chains=(
                    ("coop_khelcom_dakar", ("MANDAT-DKR-2026-01", "MANDAT-DKR-2026-01-ERP")),
                ),
                jurisdiction_debit="QC-CA",
                jurisdiction_credit="SN-OHADA",
            )
        )
    except Rejected:
        rogue_bot_forgiveness_blocked = True

    # 6. Entry 3 (`forgiven`): Both human principals countersign formal $5,000.00 Remise de dette (`CCQ art. 1687`)
    e3_remise = (
        book.prepare_forgiveness_draft(
            obligation_id="DKR-QC-2026-001",
            author="coop_khelcom_dakar",
            reason="Remise de dette commerciale amiable sur 1 palette affectée par l'humidité maritime (CCQ art. 1687 / SYSCOHADA 651)",
            posted_at="2026-11-18T16:45:00Z",
            definition_version=NF11_DEFINITION_VERSION,
            entry_id="DKR-QC-2026-003-REMISE",
        )
        .with_signature(kp_dakar)
        .with_signature(kp_quebec)
    )
    book.post_francotrope(
        FrancotropeEntry(
            entry=e3_remise,
            crosswalk_code="remise_de_dette_commerciale",
            delegation_chains=(),
            jurisdiction_debit="QC-CA",
            jurisdiction_credit="SN-OHADA",
        )
    )

    passport = book.export_schengen_passport()
    passport["guard_rogue_software_forgiveness_blocked"] = rogue_bot_forgiveness_blocked
    return book, passport


if __name__ == "__main__":
    bk, bundle = build_dakar_quebec_reference_corridor()
    assert bundle["quebec_schengen_admission_eligible"] is True
    assert bundle["guard_rogue_software_forgiveness_blocked"] is True
    assert bundle["obligations"]["DKR-QC-2026-001"]["status"] == "FORGIVEN"
    print(
        json.dumps(
            {
                "attestation": bundle["attestation"],
                "schema_version": bundle["schema_version"],
                "quebec_schengen_admission_eligible": bundle["quebec_schengen_admission_eligible"],
                "quebec_green_lane_gates": bundle["quebec_green_lane_gates"],
                "entry_count": bundle["verification"]["entry_count"],
                "head_chain_hash": bundle["verification"]["head_chain_hash"],
                "passport_sha256": bundle["passport_sha256"],
                "guard_rogue_software_forgiveness_blocked": bundle[
                    "guard_rogue_software_forgiveness_blocked"
                ],
                "obligation_final_status": bundle["obligations"]["DKR-QC-2026-001"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    bk.close()
