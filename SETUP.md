# StarTalk Discord Notifier: Setup Guide

This posts to Discord whenever there's a new **YouTube video**, **YouTube Short**, **Patreon post**, or **podcast episode**, and pings the matching role. It runs free on GitHub, checking roughly every 10 minutes.

Allow about 45 minutes. Collect everything in a private note as you go. You'll paste it all into GitHub in Part 7.

> Webhook URLs and tokens work like passwords. Don't post them in Discord or anywhere public.

---

## Part 1: Add a Podcast role (Discord)

You have roles for Videos, Shorts, and Patreon, but not the podcast yet.

1. Click **StarTalk** (top left) → **Server Settings** → **Roles** → **Create Role**.
2. Name it **Podcast**. Leave both switches on the Display tab off.
3. Open the **Permissions** tab, scroll to the bottom, and click **Clear permissions**.
4. Click **Save Changes**.
5. In the left sidebar, go to **Onboarding** → **Questions**, open your notification question, and click **+ Add an Answer**:
   - Emoji 🎙️, title **Podcast**, description *Get pinged when a new episode is out*, role **Podcast**.
6. Click **Save Changes**.

## Part 2: Create webhooks (Discord)

A webhook is a posting address for one channel. Make one in each channel where alerts should appear. If videos and Shorts go to the same channel, one webhook covers both.

1. Hover over the channel (e.g. **#new-videos**) and click its **⚙️ gear**.
2. In the left sidebar, click **Integrations** → **Webhooks** → **New Webhook**.
3. Click the new webhook to open it.
4. Change its name to **StarTalk** and click the avatar circle to upload your logo. This is the name and picture the alerts will show.
5. Click **Copy Webhook URL** and paste it in your note, labeled with the channel.
6. Click **Save Changes**.

Repeat for each alert channel (e.g. one for Patreon, one for the podcast).

## Part 3: Copy the role IDs (Discord)

1. Click the **gear** next to your name (bottom left) → **Advanced** → turn on **Developer Mode**.
2. Go to **Server Settings → Roles**.
3. Right-click each of these roles and choose **Copy Role ID**, pasting each into your note:
   **YouTube Videos**, **YouTube Shorts**, **Patreon**, **Podcast**.

## Part 4: Get the YouTube channel ID

1. Open the StarTalk channel page on YouTube.
2. Click the **"more"** link under the channel description to open the About panel.
3. Scroll down and click **Share channel** → **Copy channel ID**.
4. Paste it in your note. It starts with **UC** and is about 24 characters long.

## Part 5: Get a Patreon token

Do this logged in as the **StarTalk creator account** on Patreon.

1. Go to **https://www.patreon.com/portal/registration/register-clients**.
2. Click **Create Client** and fill in:
   - **App Name:** StarTalk Discord
   - **Description:** Posts new Patreon posts to Discord
   - **App Category:** pick the closest option
   - **Redirect URIs:** `https://localhost`
   - **Client API Version:** 2
3. Click **Create Client**.
4. Expand the new client and copy the **Creator's Access Token** into your note.

> Patreon creator tokens can expire. If Patreon alerts stop and the log says the token was rejected, come back here, copy a fresh token, and update the `PATREON_TOKEN` secret (Part 7).

## Part 6: Podcast source (pick ONE)

**Option A: Spotify (alert links go to Spotify)**

1. Go to **https://developer.spotify.com/dashboard** and log in with any Spotify account.
2. Click **Create app** and fill in:
   - **App name:** StarTalk Discord
   - **App description:** Podcast alerts
   - **Redirect URI:** `http://127.0.0.1:8888/callback`, then click **Add**
   - Under "Which API/SDKs are you planning to use?", tick **Web API**
3. Agree to the terms and click **Save**.
4. Click **Settings**. Copy the **Client ID**, then click **View client secret** and copy that too.
5. In the Spotify app, open the StarTalk podcast → **⋯** → **Share** → **Copy link to show**. The link looks like `https://open.spotify.com/show/`**`abc123XYZexample`**`?si=...`. The bold part is the **show ID**. Save just that part.

**Option B: RSS feed (simpler; links go to the podcast host's page)**

Every podcast has an RSS feed. Your podcast host (or whoever manages the podcast) can give you the URL. Save it in your note. Use this if Spotify's developer site gives you trouble.

## Part 7: Put it on GitHub

1. Create a free account at **https://github.com** if you don't have one.
2. Click **+** (top right) → **New repository**.
   - **Name:** `startalk-notifier`
   - **Public** is recommended: it gets unlimited free running time. Your secrets stay hidden either way; only the code and a list of already-announced video IDs are visible. (If you choose **Private**, see the note at the end.)
   - Click **Create repository**.
3. Click **uploading an existing file**, drag in `notifier.py`, `requirements.txt`, and `SETUP.md`, then click **Commit changes**.
4. Add the workflow file. It's in a hidden folder that Mac's Finder won't show, so create it by hand:
   - Click **Add file** → **Create new file**.
   - In the name box, type exactly: `.github/workflows/notify.yml` (the slashes create the folders).
   - Open `notify.yml` from the download in TextEdit, copy everything, and paste it into the big box.
   - Click **Commit changes**.
5. Add your secrets: click **Settings** (repo tab bar) → **Secrets and variables** → **Actions** → **New repository secret**. Add each one below by pasting the name exactly, then the value, then **Add secret**:

| Name | Value |
|---|---|
| `YOUTUBE_CHANNEL_ID` | The UC… ID from Part 4 |
| `WEBHOOK_VIDEOS` | Webhook URL for the videos channel |
| `ROLE_VIDEOS` | YouTube Videos role ID |
| `WEBHOOK_SHORTS` | Webhook URL for the Shorts channel (can be the same as videos) |
| `ROLE_SHORTS` | YouTube Shorts role ID |
| `PATREON_TOKEN` | Creator's Access Token from Part 5 |
| `WEBHOOK_PATREON` | Webhook URL for the Patreon channel |
| `ROLE_PATREON` | Patreon role ID |
| `WEBHOOK_PODCAST` | Webhook URL for the podcast channel |
| `ROLE_PODCAST` | Podcast role ID |
| `SPOTIFY_CLIENT_ID` | *(Option A)* Client ID |
| `SPOTIFY_CLIENT_SECRET` | *(Option A)* Client secret |
| `SPOTIFY_SHOW_ID` | *(Option A)* Show ID |
| `PODCAST_RSS_URL` | *(Option B only)* RSS feed URL |

## Part 8: Start it and test

1. Click the **Actions** tab. If GitHub asks, click the green button to enable workflows.
2. Click **StarTalk notifier** on the left → **Run workflow** (right side) → leave mode as **normal** → **Run workflow**.
   - This first run **records what already exists without posting anything**, so there's no flood of old uploads.
   - After a minute, refresh. A green ✓ means it worked.
3. Run it again, this time choosing mode **test**. It posts the latest video, Short, Patreon post, and episode, marked **[TEST]**. The role tags show, but **nobody actually gets pinged**. Check that each one landed in the right channel, then delete the test messages.
4. That's it. From now on it runs every ~10 minutes by itself.

## Part 9: Turn off Sapphire's YouTube alert

Otherwise every upload gets announced twice. In the Sapphire dashboard → **Social Notifications** → click the **trash icon** next to @StarTalk → **Save changes**.

---

## If something goes wrong

- In the **Actions** tab, a **red ✗** means a run failed. Click it, then click **notify**, and read the log. The error is usually spelled out. One broken source doesn't stop the others.
- **"Patreon token was rejected"**: make a fresh token (Part 5) and update the `PATREON_TOKEN` secret.
- **"Discord webhook error 404"**: the webhook was deleted. Make a new one (Part 2) and update its secret.
- **Alerts post but nobody gets a notification**: in Server Settings → Roles, open that role and turn on **Allow anyone to @mention this role**.
- **"couldn't tell if … is a Short yet"**: harmless. It retries on the next run.
- **It stopped running entirely**: GitHub pauses scheduled jobs in repos with no activity for 60 days and emails you first. Re-enable it in the Actions tab. Regular uploads normally keep it active.
- **Change the message text**: edit the `MESSAGES` section near the top of `notifier.py` on GitHub (pencil icon → edit → Commit changes).

**Private repo note:** private repos get 2,000 free minutes a month, and checking every 10 minutes uses more than that. In `.github/workflows/notify.yml`, change `*/10 * * * *` to `*/30 * * * *` (every 30 minutes).
