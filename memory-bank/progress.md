# Progress: FinAPI

## Project Roadmap

- [x] Initial Repository & Planning
  - [x] Initialize Git locally
  - [x] Set Git configurations (`user.name`, `user.email`)
  - [x] Create GitHub remote repository
  - [x] Push initial plan and `.gitignore` to GitHub
  - [x] Setup Memory Bank
- [ ] Base Configuration & Scaffolding
  - [ ] Create `service_a` and `service_b` directories
  - [ ] Set up environment files (`.env`, `.env.example`)
  - [ ] Configure `uv` virtual environments and dependencies
- [ ] Service B: Market Data Service
  - [ ] Test & implement `yfinance` integration
  - [ ] Test & implement response normalization (DTOs)
  - [ ] Test & implement SQLite cache & TTL checks
  - [ ] Write resilience wrapper (timeouts, retries)
- [ ] Service A: API Gateway
  - [ ] Test & implement API Key Bearer authentication
  - [ ] Test & implement HTTP client to fetch from Service B
  - [ ] Expose normalized public endpoint
- [ ] Containerization & Integration
  - [ ] Create individual Dockerfiles
  - [ ] Orchestrate via `docker-compose.yml`
  - [ ] Conduct end-to-end local validation
- [ ] Finalization
  - [ ] Write setup instructions in README
  - [ ] Commit all changes and push to GitHub
