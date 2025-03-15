# Dogecoin News Bot

A Telegram bot that provides real-time updates about Dogecoin price and news. The bot runs on GitHub Actions, making it completely free to host.

## Features

- Real-time Dogecoin price updates
- Latest Dogecoin news from reliable sources
- Automatic updates every 30 minutes
- Subscribe/unsubscribe functionality
- Markdown formatting for better readability

## Commands

- `/start` - Start the bot and subscribe to updates
- `/help` - Show help message
- `/news` - Get the latest Dogecoin news
- `/price` - Get current Dogecoin price
- `/stop` - Unsubscribe from updates

## Setup Instructions

1. Fork this repository to your GitHub account

2. Set up your Telegram bot:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Create a new bot using the `/newbot` command
   - Copy the API token provided by BotFather

3. Add your bot token to GitHub repository:
   - Go to your forked repository's Settings
   - Click on "Secrets and variables" → "Actions"
   - Click "New repository secret"
   - Name: `TELEGRAM_BOT_TOKEN`
   - Value: Your bot token from BotFather
   - Click "Add secret"

4. Enable GitHub Actions:
   - Go to the "Actions" tab in your repository
   - Click "I understand my workflows, go ahead and enable them"

The bot will now run automatically every 30 minutes and send updates to all subscribed users.

## How It Works

- The bot uses GitHub Actions to run every 30 minutes
- It stores subscribed users in a file that persists between runs
- When it runs, it:
  1. Fetches the latest Dogecoin price from CoinMarketCap
  2. Fetches the latest news from NewsData.io
  3. Sends updates to all subscribed users

## Contributing

Feel free to submit issues and enhancement requests! 