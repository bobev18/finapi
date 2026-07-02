"""
Shared schemas package for the FinAPI monorepo.

All Pydantic models that are exchanged across service boundaries live here.
Each service's local schemas/market.py re-exports from this package so that:
  - Internal imports within a service remain unchanged.
  - Schema evolution only requires editing this single file.
  - Docker containers get this package via COPY shared/ /app/shared/.
"""
