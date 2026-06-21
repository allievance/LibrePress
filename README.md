# LibrePress

A lightweight, end-to-end publishing system for producing and distributing small-run books without inventory risk.

## Overview

LibrePress is a self-hosted publishing storefront built for solo operators. It replaces the fragmented toolchain of traditional small-press publishing — CMS platforms, manual order handling, separate fulfillment workflows — with a single, integrated system.

Books are designed, typeset, and listed once. Orders are fulfilled automatically through Lulu's print-on-demand API. No inventory. No warehouse. No overhead.

## Stack

- **Backend:** Python / Flask
- **Database:** SQLite via SQLAlchemy
- **Templates:** Jinja2
- **Payments:** Stripe Checkout
- **Fulfillment:** Lulu Print API
- **Deployment:** Railway

## Features

- Dynamic book catalog served from SQLite database
- Product pages with cover image, description, and print specifications
- Session-based cart with add/remove functionality
- Shipping address collection before checkout
- Stripe Checkout integration for payment processing
- Automated Lulu print job creation on successful payment
- Stripe webhook for production-grade order fulfillment
- Responsive storefront optimized for mobile and desktop

## Project Structure
