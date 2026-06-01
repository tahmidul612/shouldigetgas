# Should I Get Gas? ⛽

Should I Get Gas helps you answer one simple question: **should you fill up now, or wait a bit?**  
It gives timing advice, not just station listings.

<div align="center">
  <img alt="Live" src="https://img.shields.io/badge/Live-Vercel-000000?style=for-the-badge&logo=vercel" />
  <img alt="Frontend" src="https://img.shields.io/badge/Frontend-React%2018-61DAFB?style=for-the-badge&logo=react&logoColor=000" />
  <img alt="Backend" src="https://img.shields.io/badge/Backend-Python-3776AB?style=for-the-badge&logo=python&logoColor=fff" />
  <img alt="Regions" src="https://img.shields.io/badge/Regions-62-3b82f6?style=for-the-badge" />
  <img alt="No Build Step" src="https://img.shields.io/badge/Frontend-Zero%20Build-111827?style=for-the-badge" />
</div>

## Try it live

👉 **https://shouldigetgas.vercel.app/**

## Why this exists

Most gas apps help with **where** to buy.  
This project focuses on **when** to buy — especially if waiting 1–3 days might save money.

## How it works (plain language)

1. Detect your approximate region (or let you choose one).
2. Load fresh regional price data from the backend-generated snapshot.
3. Show a simple verdict: **Fill up**, **Top off**, or **Wait** — plus a short explanation.

## ⚠️ Important disclaimer

This project was entirely **vibe-coded with Claude**, uses **Claude Haiku** internally for parts of data processing, and the output may not be **100% accurate**.  
Use it as a helpful signal — not financial or safety-critical advice.

## For developers and contributors

- Developer guide: [`docs/development.md`](docs/development.md)
- Contributing guide: [`docs/contributing.md`](docs/contributing.md)
- Research + product evolution: [`docs/research-and-vision.md`](docs/research-and-vision.md)
- Deployment guide: [`docs/deployment.md`](docs/deployment.md)

## Acknowledgements

- U.S. EIA open data
- NRCAN and Ontario public fuel datasets
- News providers and open-source libraries used in the pipeline
- Everyone who tests, reports issues, and contributes improvements
