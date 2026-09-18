# Void Shop v3

Flask Blox Fruits shop with phone OTP demo, persistent database support, orders, receipt storage in the database, favorites, editable settings/products, and admin order management.

## Run locally

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
set SECRET_KEY=dev-secret
set ADMIN_USERNAME=admin
set ADMIN_PASSWORD=change-me
python app.py
```

Open http://127.0.0.1:5000

The demo OTP is printed in the terminal. Real SMS needs an SMS provider integration.

## Render

Create a Web Service from this repository.

Build command:
`pip install -r requirements.txt`

Start command:
`gunicorn app:app`

Set `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SECRET_KEY`, and a PostgreSQL `DATABASE_URL` in Environment Variables.

Important: the database stores receipt bytes, so receipts persist with the PostgreSQL database. Choose a PostgreSQL provider whose storage/retention terms meet your needs; free tiers can change or expire.
