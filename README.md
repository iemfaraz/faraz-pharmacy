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

Requests require pharmacy confirmation of availability, pricing, prescription requirements and delivery. No payment is collected, no stock is reserved, and no customer records are stored by this static website. Item details are passed to WhatsApp only when the customer selects Continue to WhatsApp.

Opening hours are awaiting confirmation.
