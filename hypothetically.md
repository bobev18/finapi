# Hypothetical Concept: Merging & Enriching Market Data

This document records notes on the hypothetical concept of querying both yfinance and EODHD to merge and enrich market data snapshots.

## Key Concepts

### 1. Data Enrichment
* **Idea**: Combine fields from both sources to create a single, fully populated `MarketSnapshot`.
* **Value**: yfinance provides rich corporate metadata (e.g., `longName`, `marketCap`) which is missing from EODHD's lightweight real-time price snapshot endpoint. Conversely, EODHD provides highly reliable real-time and delayed pricing data under formal APIs.
* **Trade-off / Risk**: 
  > [!WARNING]
  > **Stronger Dependency**: Merging data creates a hard dependency on *both* third-party services. If either service goes down or experiences issues, the enrichment step will fail or return incomplete snapshots unless complex fallback/partial-fill logic is written.

### 2. High Availability & Failover
* **Idea**: Fall back to the secondary provider if the primary provider is offline or rate-limited.
* **Value**: Mitigates yfinance scraping blocks and improves API uptime.

### 3. Cross-Validation
* **Idea**: Query both providers and check for price differences to spot delays or discrepancies.
* **Value**: Adds a verification layer to identify data anomalies.
