Yes. If you're defining **data strategy / data architecture principles for smart contracts in banking and capital markets**, I would make **“No PII on-chain”** one of the foundational principles—but it should be part of a broader **On-chain Data Governance Policy**.

The key architectural idea is:

> **Blockchain should contain verifiable state, references, proofs and transaction facts—not the bank's sensitive business data.**

This aligns well with current institutional tokenisation work: BIS Project Agorá explicitly considers data privacy alongside settlement finality, AML/CFT and other regulatory requirements, while BIS research highlights privacy/security and interoperability as core principles for tokenised financial infrastructure. ([Bank for International Settlements][1])

## Smart Contract Data Strategy — Banking & Capital Markets

| #      | Principle                                                        | Strategy                                                                                                                                                                                                                                                                                        |
| ------ | ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1**  | **No PII on-chain**                                              | Never store name, address, SIN/SSN, DOB, account number, email, phone, KYC documents or client-identifiable data directly on blockchain.                                                                                                                                                        |
| **2**  | **No confidential business data on-chain**                       | Don't put trade strategy, order details beyond required settlement facts, client positions, proprietary pricing, credit models or internal risk data on-chain.                                                                                                                                  |
| **3**  | **Store proofs, not data**                                       | Store cryptographic hashes, commitments, attestations and references rather than the underlying sensitive data.                                                                                                                                                                                 |
| **4**  | **Off-chain source of truth for PII**                            | Keep PII/KYC/customer records in controlled systems such as KYC, CRM, client master and data platforms.                                                                                                                                                                                         |
| **5**  | **On-chain = authoritative transaction state**                   | Use the ledger for facts that participants need to independently verify: ownership, transfer, settlement status, timestamps, asset state and contractual state.                                                                                                                                 |
| **6**  | **Tokenize identity, don't expose identity**                     | Represent parties using wallet/address IDs, institutional identifiers or privacy-preserving credentials rather than human identity.                                                                                                                                                             |
| **7**  | **Use verifiable credentials**                                   | Smart contracts should verify claims such as `KYC_APPROVED`, `ACCREDITED_INVESTOR`, `ELIGIBLE_JURISDICTION` rather than receiving the underlying KYC data.                                                                                                                                      |
| **8**  | **Zero-knowledge proofs where appropriate**                      | Prove a condition without revealing the underlying information—for example, “investor satisfies eligibility requirement” without exposing income/net worth. BIS Project Mandala specifically explores ZKPs and MPC for privacy-preserving compliance. ([Bank for International Settlements][2]) |
| **9**  | **Data minimization**                                            | Put the absolute minimum information required for the smart contract to execute on-chain.                                                                                                                                                                                                       |
| **10** | **Purpose limitation**                                           | Every on-chain field should have a documented business/legal purpose. No “just in case” data.                                                                                                                                                                                                   |
| **11** | **Immutable data requires special controls**                     | Never put information on-chain that may need deletion, correction or rectification.                                                                                                                                                                                                             |
| **12** | **No secrets on-chain**                                          | Never store passwords, private keys, API keys, encryption keys, credentials or secrets in contract state.                                                                                                                                                                                       |
| **13** | **Encrypt where appropriate—but don't rely on encryption alone** | Encryption reduces exposure but does not make immutable storage of regulated data automatically acceptable.                                                                                                                                                                                     |
| **14** | **Hash carefully**                                               | A hash of PII is **not automatically anonymous**. If the underlying information can be obtained or guessed, the hash can remain sensitive/personal data.                                                                                                                                        |
| **15** | **Reference architecture**                                       | Use `On-chain ID → Off-chain Data Vault → Controlled API` rather than `On-chain ID → PII`.                                                                                                                                                                                                      |
| **16** | **Permissioned access**                                          | Sensitive financial workflows should use permissioned participants, channels or privacy-preserving mechanisms where appropriate.                                                                                                                                                                |
| **17** | **Segregate data domains**                                       | Separate client data, trading data, settlement data, risk data, regulatory data and reference data.                                                                                                                                                                                             |
| **18** | **Data classification before smart-contract design**             | Classify every proposed field: Public / Internal / Confidential / Restricted / PII / Financial Crime / Material Non-Public Information.                                                                                                                                                         |
| **19** | **Smart contract should consume validated data**                 | Don't allow arbitrary external data directly into contract execution. Use governed oracles/data services.                                                                                                                                                                                       |
| **20** | **Oracle governance**                                            | Define source, freshness, accuracy, quorum, fallback and dispute mechanisms for every external data feed.                                                                                                                                                                                       |
| **21** | **Compliance-by-design**                                         | Encode regulatory eligibility and transaction controls as deterministic rules where appropriate. BIS research specifically explores embedding compliance into programmable financial infrastructure. ([Bank for International Settlements][3])                                                  |
| **22** | **Human override / exception management**                        | Smart contracts shouldn't create an irreversible automated path for every exception. Banks need controlled pause, remediation and escalation mechanisms.                                                                                                                                        |
| **23** | **Legal state ≠ technical state**                                | Define when a blockchain state change becomes legally effective. Blockchain finality and legal finality aren't necessarily the same. ([Eidgenössische Finanzmarktaufsicht FINMA][4])                                                                                                            |
| **24** | **Auditability without excessive disclosure**                    | Auditors/regulators should be able to reconstruct transactions without exposing unnecessary client information.                                                                                                                                                                                 |
| **25** | **Data lineage**                                                 | Every on-chain value should be traceable to its authoritative off-chain source and transformation.                                                                                                                                                                                              |
| **26** | **Versioning**                                                   | Smart-contract data schemas must support controlled evolution without corrupting historical records.                                                                                                                                                                                            |
| **27** | **Retention policy**                                             | Define how long off-chain source data and on-chain references/commitments must be retained.                                                                                                                                                                                                     |
| **28** | **Cross-border data controls**                                   | Consider jurisdictional restrictions before data crosses nodes, jurisdictions or cloud environments.                                                                                                                                                                                            |
| **29** | **Interoperability**                                             | Define canonical identifiers and schemas so tokenised assets can interact with other ledgers and traditional financial infrastructure. BIS identifies interoperability as a core tokenisation principle. ([Bank for International Settlements][5])                                              |
| **30** | **Operational resilience**                                       | Smart contracts, blockchain nodes, oracles and key-management infrastructure become part of the bank's critical technology stack and require resilience controls.                                                                                                                               |

---

# The architecture I would recommend

For a **banking/capital-markets smart-contract platform**, I'd use a model like this:

```text
                    ┌─────────────────────────┐
                    │       CLIENT / BANK     │
                    │                         │
                    │ KYC / PII / Accounts    │
                    │ Trading / Risk / CRM    │
                    └────────────┬────────────┘
                                 │
                          Controlled API
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   DATA / IDENTITY LAYER │
                    │                         │
                    │ Client ID               │
                    │ KYC Status              │
                    │ Eligibility              │
                    │ Credit / Risk attributes│
                    │ PII                     │
                    └────────────┬────────────┘
                                 │
                         Attestation /
                         ZKP / Proof
                                 │
                                 ▼
              ┌──────────────────────────────────┐
              │        SMART CONTRACT             │
              │                                   │
              │ Is KYC valid?                     │
              │ Is investor eligible?             │
              │ Is asset transferable?            │
              │ Is settlement condition satisfied?│
              │ Is payment received?              │
              └────────────────┬─────────────────┘
                               │
                               ▼
              ┌──────────────────────────────────┐
              │           BLOCKCHAIN              │
              │                                   │
              │ Asset ID                          │
              │ Wallet / participant ID           │
              │ Ownership state                   │
              │ Transaction state                 │
              │ Settlement state                  │
              │ Timestamp                         │
              │ Hash / commitment                 │
              │ Contract version                  │
              └──────────────────────────────────┘
```

### The key rule

I'd make this an architectural **"red line"**:

> **PII → Off-chain**
> **Confidential data → Off-chain**
> **Secrets → Off-chain**
> **Business documents → Off-chain**
> **Large datasets → Off-chain**
> **Verifiable state → On-chain**
> **Proof/commitment → On-chain**
> **Asset ownership → On-chain**
> **Settlement state → On-chain**
> **Contract state → On-chain**

---

# Capital Markets-specific examples

### Securities settlement

**Don't put:**

```text
John Smith
SIN: xxx
TD Securities account: 123456
Address: ...
```

on-chain.

Instead:

```text
InvestorID = DID/InstitutionalID
SecurityID = ISIN
Quantity = 10,000
SettlementDate = 2026-09-01
SettlementStatus = SETTLED
```

with the investor identity resolved through a controlled off-chain identity service.

---

### Repo

Instead of putting the entire legal agreement on-chain:

```text
RepoAgreement.pdf
Client information
Collateral schedules
Bank account information
```

store:

```text
AgreementHash
RepoID
CollateralTokenID
Notional
Rate
Maturity
MarginRequirement
SettlementState
```

The legal agreement remains off-chain, while the smart contract enforces the relevant executable terms.

---

### Tokenized bond

On-chain:

```text
BondID
ISIN
IssuerID
FaceValue
Currency
Coupon
Maturity
Ownership
TransferRestrictions
SettlementStatus
```

Off-chain:

```text
Investor KYC
Investor name
Investor address
Tax information
Beneficial owner
Account details
Suitability documents
AML investigation
Client documentation
```

---

# An even more important principle

For institutional blockchain, I would distinguish **three categories of data**:

### 1. Data

Actual information:

> "Investor has $10M net worth."

Keep off-chain.

### 2. Assertion

A trusted party says:

> "Investor satisfies $5M minimum requirement."

Could be represented as an attestation.

### 3. Proof

Cryptographically demonstrate:

> "Investor satisfies the requirement."

without revealing the $10M figure.

**Smart contracts should increasingly operate on #2 and #3 rather than #1.**

That's where institutional blockchain becomes much more powerful. BIS's Project Mandala is exploring essentially this **programmable compliance + privacy-preserving proof** model. ([Bank for International Settlements][2])

---

## If you're defining a banking blockchain platform

I'd organize the overall **Data Strategy** into these 10 pillars:

1. **Data Classification**
2. **Data Residency**
3. **PII & Privacy**
4. **Identity & Credentials**
5. **On-chain vs Off-chain**
6. **Data Ownership & Governance**
7. **Oracle & External Data Governance**
8. **Data Lineage & Auditability**
9. **Interoperability & Canonical Data Models**
10. **Retention, Immutability & Regulatory Compliance**

And I'd make **"On-chain Data Policy" a mandatory architecture gate** before any smart contract reaches production.

This is particularly important in capital markets because tokenisation is moving beyond experiments toward **programmable settlement, tokenised deposits, securities and cross-border payments**; BIS's current Project Agorá work explicitly combines tokenisation with smart-contract-based workflows and compliance considerations. ([Bank for International Settlements][1])

[1]: https://www.bis.org/about/bisih/topics/fmis/agora.htm?utm_source=chatgpt.com "Project Agorá: exploring tokenisation of wholesale cross-border payments"
[2]: https://www.bis.org/about/bisih/topics/cbdc/mandala.htm?utm_source=chatgpt.com "Project Mandala: shaping the future of cross-border payments compliance"
[3]: https://www.bis.org/publ/work811.pdf?utm_source=chatgpt.com "Embedded supervision: how to build regulation into blockchain finance"
[4]: https://www.finma.ch/en/documentation/dossier/dossier-fintech/entwicklung-der-digitalisierung-im-finanzbereich---2024/?utm_source=chatgpt.com "Development of digitalisation in the financial sector (2024) | FINMA"
[5]: https://www.bis.org/publ/othp92.pdf?utm_source=chatgpt.com "Leveraging tokenisation for payments and financial transactions"


----------------------

For a **banking and capital-markets smart-contract / blockchain platform**, I would structure **Risk, Security and Compliance Strategy** as a set of mandatory architectural controls rather than generic cybersecurity principles.

A useful top-level model is:

> **Govern → Identify → Prevent → Detect → Respond → Recover → Prove**

## 1. Risk Strategy

| #       | Principle                          | Strategy                                                                                                                    |
| ------- | ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **R1**  | **Risk classification**            | Classify every blockchain use case by financial, operational, regulatory, market, liquidity and systemic risk.              |
| **R2**  | **Risk appetite**                  | Define explicit limits for transaction value, asset types, counterparties, automation level and operational exposure.       |
| **R3**  | **Three lines of defense**         | Separate business ownership, technology/risk oversight and independent audit.                                               |
| **R4**  | **Smart-contract risk assessment** | Mandatory risk assessment before contract deployment and after material changes.                                            |
| **R5**  | **Code immutability risk**         | Never assume deployed code is perfect; use controlled upgrade mechanisms, versioning and emergency controls.                |
| **R6**  | **Oracle risk**                    | Assess accuracy, manipulation, availability, latency and concentration risk for every oracle.                               |
| **R7**  | **Counterparty risk**              | Maintain institutional counterparty identity, eligibility and exposure limits off-chain.                                    |
| **R8**  | **Settlement risk**                | Define atomic settlement, failure states, rollback/compensation and reconciliation procedures.                              |
| **R9**  | **Liquidity risk**                 | Monitor liquidity of tokenized assets and ensure redemption mechanisms exist.                                               |
| **R10** | **Model risk**                     | Treat pricing, valuation, collateral and risk models feeding smart contracts as governed models.                            |
| **R11** | **Operational risk**               | Assess node failures, key loss, contract bugs, oracle outages, network congestion and operator errors.                      |
| **R12** | **Concentration risk**             | Avoid dependence on a single blockchain, validator, oracle, custodian or technology provider.                               |
| **R13** | **Third-party risk**               | Apply vendor due diligence to blockchain networks, custodians, node providers, oracle providers and smart-contract vendors. |
| **R14** | **Scenario testing**               | Test extreme events: market crash, chain halt, oracle manipulation, compromised key, validator failure and cyberattack.     |
| **R15** | **Kill switch**                    | High-value financial contracts need governed pause/emergency mechanisms.                                                    |
| **R16** | **Risk monitoring**                | Continuously monitor transaction anomalies, exposure, contract behavior, liquidity and network health.                      |
| **R17** | **Reconciliation risk**            | Reconcile blockchain state against books & records, custody and core banking systems.                                       |
| **R18** | **Exit strategy**                  | Every blockchain application must have a controlled migration/decommissioning strategy.                                     |

---

# 2. Security Strategy

| #       | Principle                         | Strategy                                                                                                           |
| ------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **S1**  | **Zero Trust**                    | Never trust a wallet, node, API or participant merely because it is inside the network.                            |
| **S2**  | **Strong identity**               | Institutional participants require authenticated, governed identities.                                             |
| **S3**  | **Least privilege**               | Wallets, smart contracts, APIs and administrators receive minimum required permissions.                            |
| **S4**  | **Privileged access management**  | Administrative blockchain operations require PAM, MFA, approvals and session monitoring.                           |
| **S5**  | **HSM/MPC key management**        | Institutional private keys should be protected using HSM, MPC or equivalent institutional-grade controls.          |
| **S6**  | **Key rotation**                  | Establish controlled key rotation, revocation and emergency recovery.                                              |
| **S7**  | **Multi-signature authorization** | High-value transactions require multiple independent approvals.                                                    |
| **S8**  | **Transaction limits**            | Enforce value, velocity and counterparty limits at wallet and smart-contract level.                                |
| **S9**  | **Smart-contract security**       | Static analysis, formal verification where appropriate, fuzzing, penetration testing and independent audits.       |
| **S10** | **Secure SDLC**                   | Smart contracts follow the same—or stronger—security lifecycle as bank-critical software.                          |
| **S11** | **Dependency security**           | Govern libraries, contract dependencies, bridges, SDKs and third-party packages.                                   |
| **S12** | **Network segmentation**          | Separate blockchain nodes, APIs, signing infrastructure and enterprise systems.                                    |
| **S13** | **Node security**                 | Harden nodes, minimize exposed interfaces and continuously patch/monitor infrastructure.                           |
| **S14** | **Bridge security**               | Treat blockchain bridges as high-risk infrastructure with independent controls and limits.                         |
| **S15** | **Runtime monitoring**            | Detect abnormal contract calls, wallet behavior, transaction patterns and privilege changes.                       |
| **S16** | **Threat intelligence**           | Continuously monitor exploits, compromised addresses, malicious contracts and emerging blockchain threats.         |
| **S17** | **Anti-MEV controls**             | Assess front-running, sandwiching, transaction ordering and information leakage where applicable.                  |
| **S18** | **DDoS resilience**               | Protect APIs, nodes, RPC endpoints and transaction submission infrastructure.                                      |
| **S19** | **Backup & recovery**             | Back up configuration, keys according to security policy, contract metadata and operational state.                 |
| **S20** | **Incident response**             | Maintain blockchain-specific playbooks for key compromise, contract exploit, oracle manipulation and chain outage. |

---

# 3. Compliance Strategy

This is where a **banking blockchain platform** differs substantially from a normal Web3 platform.

| #       | Principle                        | Strategy                                                                                                                                    |
| ------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **C1**  | **KYC/AML by design**            | Every participant must satisfy appropriate KYC/AML requirements before accessing regulated workflows.                                       |
| **C2**  | **Permissioned participation**   | Restrict regulated activities to approved institutional participants where required.                                                        |
| **C3**  | **Identity verification**        | Map blockchain identities/wallets to verified legal entities without putting PII on-chain.                                                  |
| **C4**  | **Sanctions screening**          | Screen participants and transactions against applicable sanctions requirements.                                                             |
| **C5**  | **Transaction monitoring**       | Detect suspicious patterns, structuring, unusual transfers and other AML indicators.                                                        |
| **C6**  | **Travel Rule**                  | Where applicable, capture and transmit required originator/beneficiary information without exposing it publicly on-chain.                   |
| **C7**  | **Regulatory reporting**         | Maintain auditable data required for regulatory reporting.                                                                                  |
| **C8**  | **Books & records**              | Preserve records needed to reconstruct transactions, decisions and approvals.                                                               |
| **C9**  | **Auditability**                 | Ensure regulators and internal audit can independently verify transaction history and control effectiveness.                                |
| **C10** | **Data privacy**                 | No PII or unnecessary confidential information on-chain.                                                                                    |
| **C11** | **Data residency**               | Control where nodes, databases, backups and off-chain identity systems store regulated information.                                         |
| **C12** | **Retention**                    | Define regulatory retention periods for blockchain transactions and associated off-chain records.                                           |
| **C13** | **Legal enforceability**         | Establish the legal relationship between smart-contract state and contractual/legal obligations.                                            |
| **C14** | **Regulatory perimeter**         | Determine whether the token, activity, participant or platform falls under securities, derivatives, payments, banking or other regulations. |
| **C15** | **Asset eligibility**            | Define which assets may be tokenized and under what regulatory framework.                                                                   |
| **C16** | **Transfer restrictions**        | Smart contracts should enforce jurisdiction, investor-type and holding restrictions where appropriate.                                      |
| **C17** | **Market conduct**               | Detect manipulation, insider trading, front-running and other prohibited behavior.                                                          |
| **C18** | **Consumer/investor protection** | Apply suitability, disclosure and eligibility requirements where applicable.                                                                |
| **C19** | **Third-party compliance**       | Ensure external blockchain/oracle/custody providers satisfy bank regulatory requirements.                                                   |
| **C20** | **Regulatory change management** | Regulatory changes must trigger impact assessment and potentially smart-contract/platform changes.                                          |

---

# 4. The most important architecture principle

I'd combine **Data + Risk + Security + Compliance** into a single control framework:

```text
                    ┌─────────────────────────┐
                    │     GOVERNANCE LAYER     │
                    │                         │
                    │ Risk Appetite            │
                    │ Regulatory Policy       │
                    │ Data Classification      │
                    │ Legal Framework          │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
       ┌────────────┐     ┌────────────┐     ┌────────────┐
       │    DATA    │     │   RISK     │     │ COMPLIANCE │
       │            │     │            │     │            │
       │ No PII     │     │ Exposure   │     │ KYC / AML  │
       │ Privacy    │     │ Limits     │     │ Sanctions  │
       │ Lineage    │     │ Scenarios  │     │ Reporting  │
       │ Residency  │     │ Liquidity  │     │ Records    │
       └─────┬──────┘     └─────┬──────┘     └─────┬──────┘
             │                  │                  │
             └──────────────────┼──────────────────┘
                                ▼
                    ┌─────────────────────────┐
                    │   SMART CONTRACT LAYER  │
                    │                         │
                    │ Policy Enforcement      │
                    │ Eligibility             │
                    │ Transfer Rules          │
                    │ Settlement              │
                    │ Limits                  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │     BLOCKCHAIN / DLT     │
                    │                         │
                    │ State                   │
                    │ Ownership               │
                    │ Settlement              │
                    │ Proofs / Attestations   │
                    └─────────────────────────┘
```

## 5. I would add one more concept: **Policy-as-Code**

For an institutional platform, this is particularly powerful.

Instead of embedding everything directly into the smart contract:

```text
IF investor.country == Canada
AND investor.kyc == TRUE
AND investor.type == Institutional
AND asset.jurisdiction == Canada
AND sanctions == CLEAR
AND holding_limit < limit
THEN transfer()
```

use a governed policy layer:

```text
Identity ────────┐
KYC/AML ─────────┤
Sanctions ───────┤
Investor Rules ──┼──> Policy Engine ──> Smart Contract
Jurisdiction ────┤
Risk Limits ─────┤
Asset Rules ─────┘
```

The smart contract receives a **signed authorization/attestation**, rather than directly owning all compliance logic.

That gives the bank the ability to change a regulatory policy **without necessarily redeploying the entire asset contract**.

---

# 6. Five controls I would make mandatory

For a **CIBC-like Capital Markets blockchain platform**, I'd make these non-negotiable:

### 🔴 1. No PII / secrets on-chain

Immutable infrastructure should never become the bank's PII database.

### 🔴 2. Institutional identity + permissioning

Every regulated participant must have a verified identity and appropriate authorization.

### 🔴 3. Multi-party key governance

No individual should be capable of unilaterally moving institutional assets or changing critical contract configuration.

### 🔴 4. Smart-contract emergency controls

`Pause → Investigate → Contain → Remediate → Resume`

with strict governance and full audit trail.

### 🔴 5. Compliance before execution

The architecture should make it **technically difficult or impossible** for an invalid participant/transaction to reach settlement.

---

## A useful way to position the overall strategy

For an institutional blockchain platform, I would summarize the architecture in **four statements**:

> **Data:** *Put data off-chain; put verifiable state on-chain.*

> **Risk:** *Automate execution, not accountability.*

> **Security:** *Treat keys and smart contracts as critical financial infrastructure.*

> **Compliance:** *Make regulatory eligibility a prerequisite for transaction execution.*

That gives you a strong foundation for a **Banking & Capital Markets Smart Contract Platform Architecture / Data Strategy** rather than a generic blockchain security model.
