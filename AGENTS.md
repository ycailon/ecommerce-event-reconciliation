# Engineering Notes for Coding Agents

- Maintain this file when behavior, interfaces or assumptions change.
- Never claim this demo implements actual Shopify, Cloud Run, or BigQuery production integration. Local code and optional warehouse design examples are separate.
- Do not add customer data, access tokens, secrets, or scraped private information.
- Keep input validation explicit and tests offline, repeatable and dependency-light.
- Preserve operational `order_paid` vs consented `checkout_completed` separation.
- For changes, describe assumptions, security effects, acceptance tests, and any unverified behavior.
- SQL preference: lowercase clauses, leading commas on subsequent selected columns, clear CTE boundaries.
- Before checkpoint: run `PYTHONPATH=src python -m unittest discover -s tests -v` and update README as needed.

## Initial checkpoint
- Python stdlib implementation; verified offline synthetic fixtures.
- BigQuery/dbt files are illustrative and not deployment validated.
