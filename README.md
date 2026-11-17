# TOP-X Showroom

Flask + MySQL second-hand vehicle dealership with **Discord login**, an admin CRUD panel and a full **sales log**.

## Quick start
```
cp .env.example .env      # fill in Discord + DB details (Windows: just run start.bat)
make db                  # once: creates the database
make start               # runs http://localhost:5000
make admin ID=<your_discord_id>   # optional extra admins
```

## Setup (details)
1. `pip install -r requirements.txt`
2. Database: new install `mysql -u root -p < schema.sql`  
   (existing database from the previous version: run `migrate_existing_db.sql` once instead)
3. Create a Discord app at https://discord.com/developers/applications  
   - OAuth2 > Redirects: add `http://localhost:5000/auth/discord/callback` (use your real domain when live)  
   - copy the Client ID and Client Secret
4. Environment variables:

| Variable | Meaning |
|---|---|
| `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET` | from the Discord developer portal |
| `DISCORD_REDIRECT_URI` | must match the redirect above (default `http://localhost:5000/auth/discord/callback`) |
| `ADMIN_DISCORD_IDS` | comma-separated Discord user IDs that are admins, e.g. `1234567890,9876543210` |
| `SECRET_KEY` | long random string |
| `DB_HOST`, `DB_USER`, `DB_PASS`, `DB_NAME` | MySQL connection |

   More admins later: `flask --app app make-admin <discord_id>`  
   (Discord > Settings > Advanced > Developer Mode, then right-click a user > Copy User ID)
5. Run `python app.py`, open http://localhost:5000

## How it works
- **Login:** the whole site is locked until the visitor logs in with Discord. Every login is stored in `users` (+ `login_log`).
- **Admin > Vehicles > Add vehicle:** vehicle name, model type (Sedan / SUV / Bike / Sports / Supercar / Luxury / Other), plate number, upgraded or non-upgraded, car seller (old owner), dealer who bought it, purchase amount, listing price.
- **Catalog (all logged-in users) shows:** name, model, plate, upgrade, old owner, price. Dealer and purchase amount are private (admin only).
- **Mark sold:** asks for customer name, dealer who sold the car and sold amount, then in one DB transaction sets the vehicle to *Sold* and writes a full `sales_log` row (car details + old owner + buying dealer + purchase amount + customer + selling dealer + sold amount + profit + who logged it).
- **Sales log tab:** search, edit, delete, totals, CSV export. "Relist" puts a sold car back in stock.
