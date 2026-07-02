# Product Context: FinAPI

FinAPI is a secure, resilient, multi-service backend system designed to normalize and deliver financial market data to clients.

## Problem Statement
Clients need standard, structured, and normalized market data (e.g., stock snapshots, crypto snapshots). However, direct integration with public market APIs (like Yahoo Finance) poses several challenges:
- High latency and potential rate limiting due to repetitive requests.
- Fluctuating API contracts and raw/unstructured formats.
- Security concerns regarding exposing API credentials or downstream services directly to clients.
- Lack of fail-safe mechanisms (timeouts, retries) on client-side requests.

## Product Goal
Provide a secure, local API gateway (Service A) that exposes clean, normalized endpoints to authenticated clients while offloading upstream data fetching, normalization, and caching to an isolated internal service (Service B).

## Target Audience / Clients
- internal developers or authorized third-party applications needing clean financial snapshots.

## Key Features & Requirements
1. **Normalized Market Snapshot**: Fetches stock/crypto ticker details and formats them into a stable internal schema.
2. **Robust Authentication**: Protects public-facing endpoints using API Key Bearer authentication (`Authorization: Bearer <key>`).
3. **Internal Boundary Security**: Secures inter-service communications using a separate internal API key.
4. **Performance & Caching**: Employs SQLite storage to cache market data with a short TTL (Time to Live) to prevent upstream rate-limiting and minimize response times.
5. **Resilience**: Applies timeout and retry policies for external network calls to handle transient failures gracefully.
