# Faraz Pharmacy

Responsive pharmacy website for Faraz Pharmacy, in front of THQ Hospital, Barikot, Swat, Pakistan.

## Features

- Mobile-friendly pharmacy landing page
- Click-to-call and WhatsApp contact: +92 344 9006940
- Multi-item order enquiry form with quantities and review
- WhatsApp message preparation; customers must press Send in WhatsApp
- Location search and FAQs

## Run locally

Open `index.html` in a browser, or serve the folder with `python -m http.server 8000` and visit http://localhost:8000.

No build step or dependencies are required.

## Hosting

Deploy the repository root as a static website. For GitHub Pages, select the main branch and / (root) folder in repository Settings > Pages if supported by the account plan and visibility.

## Order behaviour

Requests require pharmacy confirmation of availability, pricing, prescription requirements and delivery. No payment is collected and no stock is reserved. Reviewed requests (name, WhatsApp number, items, collection preference and optional product photos) are sent to a separate authenticated backend, never to the public repository. Request records are stored in D1 and photos in private R2 storage. Owner access requires a GitHub token for iemfaraz with write access to faraz-pharmacy, exchanged for a 30-minute in-memory inbox session. The dashboard can search requests, view private photos, update status and save internal notes. WhatsApp conversations are not synchronised.

Uploads: up to 3 JPEG/PNG/WebP photos, 5 MB each. The browser re-encodes uploads to remove metadata. Use product packaging photos; do not upload identity documents, prescriptions, faces or medical history.

Backend: https://faraz-pharmacy-orders.faraznawaz2014.chatgpt.site. Public submission endpoint: POST /api/requests. Session: POST /api/session. Authenticated inbox/review: GET/PATCH /api/requests. Authenticated photos: GET /api/photo. API requests are rate limited and customer records are never committed to GitHub.

Opening hours are awaiting confirmation.
