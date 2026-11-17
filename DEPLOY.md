# Deploy TOP-X Showroom on Vercel (free)

GitHub -> Vercel, with TiDB Cloud (free MySQL) and Cloudinary (free image storage).

## 1. Database - TiDB Cloud Starter
1. Sign up at https://tidbcloud.com and create a free **Starter** cluster (MySQL-compatible).
2. Click **Connect**, generate a password, and note: Host, Port (4000), User (looks like `abc123.root`), Password. Default database is `test`.
3. Open **SQL Editor**, paste the whole of `schema_cloud.sql`, run it.

## 2. Images - Cloudinary
1. Sign up at https://cloudinary.com (free plan).
2. Dashboard > **API Keys** > copy the **API environment variable**: `cloudinary://KEY:SECRET@CLOUDNAME`.

## 3. Discord
Developer Portal > your app > OAuth2: **Reset Secret** (new secret), copy Client ID and Secret. Redirect is added in step 5.

## 4. GitHub + Vercel
1. Push this folder to a new GitHub repo (`.gitignore` already excludes `.env`).
2. vercel.com > **Add New > Project** > import the repo. Leave all build settings as detected.
3. Before clicking Deploy, add Environment Variables:

| Name | Value |
|---|---|
| SECRET_KEY | any long random string |
| DB_HOST | TiDB host |
| DB_PORT | 4000 |
| DB_USER | TiDB user (e.g. abc123.root) |
| DB_PASS | TiDB password |
| DB_NAME | test |
| DB_SSL | 1 |
| DISCORD_CLIENT_ID | from Discord |
| DISCORD_CLIENT_SECRET | from Discord |
| DISCORD_REDIRECT_URI | https://YOURPROJECT.vercel.app/auth/discord/callback |
| ADMIN_DISCORD_IDS | your Discord user ID |
| CLOUDINARY_URL | cloudinary://KEY:SECRET@CLOUDNAME |

4. Click **Deploy**. Note the real URL Vercel gives you. If it differs from YOURPROJECT above, fix `DISCORD_REDIRECT_URI` and **Redeploy**.

## 5. Final step
Discord Developer Portal > OAuth2 > Redirects > add `https://YOURPROJECT.vercel.app/auth/discord/callback` > Save.
Open your site, log in with Discord - IDs listed in `ADMIN_DISCORD_IDS` are admins.

## Notes
- Image uploads are limited to 4 MB (Vercel's request limit).
- Static files live in `public/` (Vercel serves that folder from its CDN).
- Running on your own PC still works: copy `.env.example` to `.env`, leave `CLOUDINARY_URL` empty, `make start`.
