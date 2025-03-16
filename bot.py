import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import aiohttp
import asyncio
import signal
import sys

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
COINMARKETCAP_API_KEY = os.getenv('COINMARKETCAP_API_KEY', "bd1eb80b-e7df-4547-85a4-9138db279efe")
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY', "pub_747026d7148da05676417a4f83d51505e3025")

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Store subscribed users in a file
SUBSCRIBED_USERS_FILE = 'subscribed_users.txt'

def load_subscribed_users():
    """Load subscribed users from file."""
    try:
        if os.path.exists(SUBSCRIBED_USERS_FILE):
            with open(SUBSCRIBED_USERS_FILE, 'r') as f:
                return set(int(line.strip()) for line in f if line.strip())
        return set()
    except Exception as e:
        logger.error(f"Error loading subscribed users: {e}")
        return set()

def save_subscribed_users(users):
    """Save subscribed users to file."""
    try:
        os.makedirs(os.path.dirname(SUBSCRIBED_USERS_FILE), exist_ok=True)
        with open(SUBSCRIBED_USERS_FILE, 'w') as f:
            for user_id in users:
                f.write(f"{user_id}\n")
    except Exception as e:
        logger.error(f"Error saving subscribed users: {e}")

async def get_dogecoin_price():
    """Fetch Dogecoin price data from CoinMarketCap."""
    try:
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
        parameters = {
            'symbol': 'DOGE',
            'convert': 'USD'
        }
        headers = {
            'X-CMC_PRO_API_KEY': COINMARKETCAP_API_KEY,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=parameters) as response:
                data = await response.json()
                
                if response.status == 200:
                    doge_data = data['data']['DOGE']
                    price = doge_data['quote']['USD']['price']
                    percent_change_24h = doge_data['quote']['USD']['percent_change_24h']
                    market_cap = doge_data['quote']['USD']['market_cap']
                    
                    return {
                        'price': price,
                        'percent_change_24h': percent_change_24h,
                        'market_cap': market_cap
                    }
    except Exception as e:
        logger.error(f"Error fetching Dogecoin price: {e}")
        return None

async def fetch_dogecoin_news():
    """Fetch news about Dogecoin from NewsData.io."""
    try:
        logger.info("Fetching news from NewsData.io")
        
        # Use a more specific query for Dogecoin cryptocurrency
        url = (f"https://newsdata.io/api/1/news?"
               f"apikey={NEWSDATA_API_KEY}"
               f"&q=Dogecoin cryptocurrency OR DOGE coin OR DOGE crypto"  # More specific terms
               f"&language=en")
        
        logger.info(f"Making request to: {url}")
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                response_text = await response.text()
                logger.info(f"Response status: {response.status}")
                logger.info(f"Response text: {response_text[:500]}")  # Log first 500 chars of response
                
                if response.status != 200:
                    logger.error(f"NewsData.io API error: Status {response.status}")
                    logger.error(f"Response: {response_text}")
                    return []
                
                try:
                    data = await response.json()
                except Exception as e:
                    logger.error(f"Failed to parse NewsData.io API response: {e}")
                    return []
                
                if not isinstance(data, dict) or data.get('status') != 'success':
                    logger.error(f"Invalid response from NewsData.io API: {data}")
                    return []
                
                results = data.get('results', [])
                if not isinstance(results, list):
                    logger.error("Invalid results format from NewsData.io API")
                    return []
                
                filtered_articles = []
                crypto_keywords = {'crypto', 'cryptocurrency', 'bitcoin', 'blockchain', 'trading', 'price', 'market', 'coin'}
                
                for article in results:
                    if not isinstance(article, dict):
                        continue
                    
                    # Get the original text fields without converting to lowercase
                    title = article.get('title', '')
                    description = article.get('description', '')
                    
                    # Check if required fields exist
                    if not title or not article.get('link'):
                        continue
                    
                    # Convert to lowercase only for comparison
                    title_lower = title.lower()
                    description_lower = description.lower() if description else ''
                    content = f"{title_lower} {description_lower}"
                    
                    # Check if it's specifically about Dogecoin cryptocurrency
                    is_about_doge = (
                        'dogecoin' in content or
                        ('doge' in content and any(kw in content for kw in crypto_keywords))
                    )
                    
                    if is_about_doge:
                        filtered_articles.append(article)
                        logger.info(f"Found relevant article: {title}")
                
                logger.info(f"Successfully fetched {len(filtered_articles)} Dogecoin articles")
                return filtered_articles
                
    except aiohttp.ClientError as e:
        logger.error(f"Network error while fetching news: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error while fetching news: {e}")
        return []

def format_price_message(price_data):
    """Format price data into a readable message."""
    if not price_data:
        return "Sorry, couldn't fetch Dogecoin price data at the moment."
    
    return (
        f"🐕 *Dogecoin Price Update*\n\n"
        f"💰 Price: ${price_data['price']:.6f}\n"
        f"📈 24h Change: {price_data['percent_change_24h']:.2f}%\n"
        f"💎 Market Cap: ${price_data['market_cap']:,.2f}"
    )

def format_news_message(article):
    """Format a news article into a readable message."""
    return (
        f"📰 *{article['title']}*\n\n"
        f"{article.get('description', 'No description available.')}\n\n"
        f"🔗 [Read more]({article['link']})\n"
        f"📅 Published: {article.get('pubDate', 'Date not available')}"
    )

async def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    try:
        logger.info(f"Start command received from user {update.effective_user.id}")
        welcome_message = (
            "👋 Welcome to the Dogecoin News Bot!\n\n"
            "I'll keep you updated with the latest news and price updates about Dogecoin. "
            "Use /help to see available commands."
        )
        
        # Add user to subscribed users
        subscribed_users = load_subscribed_users()
        subscribed_users.add(update.effective_chat.id)
        save_subscribed_users(subscribed_users)
        
        await update.message.reply_text(welcome_message)
        logger.info(f"Welcome message sent to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text("Sorry, something went wrong. Please try again later.")

async def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    try:
        logger.info(f"Help command received from user {update.effective_user.id}")
        help_text = (
            "🤖 Available commands:\n\n"
            "/start - Start the bot and subscribe to updates\n"
            "/help - Show this help message\n"
            "/news - Get the latest Dogecoin news\n"
            "/price - Get current Dogecoin price\n"
            "/stop - Unsubscribe from updates"
        )
        await update.message.reply_text(help_text)
        logger.info(f"Help message sent to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await update.message.reply_text("Sorry, something went wrong. Please try again later.")

async def stop(update: Update, context: CallbackContext) -> None:
    """Unsubscribe from updates."""
    try:
        logger.info(f"Stop command received from user {update.effective_user.id}")
        subscribed_users = load_subscribed_users()
        subscribed_users.discard(update.effective_chat.id)
        save_subscribed_users(subscribed_users)
        
        await update.message.reply_text("You've been unsubscribed from Dogecoin updates. Send /start to subscribe again.")
        logger.info(f"User {update.effective_user.id} unsubscribed")
    except Exception as e:
        logger.error(f"Error in stop command: {e}")
        await update.message.reply_text("Sorry, something went wrong. Please try again later.")

async def price_command(update: Update, context: CallbackContext) -> None:
    """Send current Dogecoin price information."""
    try:
        logger.info(f"Price command received from user {update.effective_user.id}")
        message = await update.message.reply_text("🔍 Fetching latest Dogecoin price...")
        
        price_data = await get_dogecoin_price()
        await message.edit_text(
            format_price_message(price_data),
            parse_mode='Markdown'
        )
        
        logger.info(f"Price info sent to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in price command: {e}")
        await update.message.reply_text("Sorry, something went wrong. Please try again later.")

async def send_news(update: Update, context: CallbackContext) -> None:
    """Send latest Dogecoin news when the command /news is issued."""
    try:
        logger.debug(f"Starting news command for user {update.effective_user.id}")
        message = await update.message.reply_text("🔍 Fetching latest Dogecoin news...")
        
        # First send price update
        logger.debug("Fetching price data...")
        price_data = await get_dogecoin_price()
        if price_data:
            logger.debug(f"Price data received: {price_data}")
            try:
                await update.message.reply_text(
                    format_price_message(price_data),
                    parse_mode='Markdown'
                )
                logger.debug("Price message sent successfully")
            except Exception as e:
                logger.error(f"Failed to send price message: {str(e)}")
        
        # Then send news
        logger.debug("Fetching news articles...")
        articles = await fetch_dogecoin_news()
        logger.debug(f"Fetched {len(articles)} articles")
        
        if not articles:
            logger.error("No articles found in the API response")
            await message.edit_text(
                "Sorry, I couldn't find any recent news about Dogecoin. Please try again later."
            )
            return

        # Send up to 5 most recent news items
        sent_count = 0
        for article in articles[:5]:
            try:
                title = article.get('title', '').replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
                description = article.get('description', 'No description available.')
                if description:
                    description = description.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
                link = article.get('link', '')
                pub_date = article.get('pubDate', 'Date not available')
                
                news_message = (
                    f"📰 *{title}*\n\n"
                    f"{description}\n\n"
                    f"🔗 {link}\n"
                    f"📅 Published: {pub_date}"
                )
                
                try:
                    await update.message.reply_text(
                        news_message,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                    sent_count += 1
                except Exception as md_error:
                    logger.error(f"Failed to send with Markdown: {str(md_error)}")
                    # If Markdown fails, send without formatting
                    simple_message = (
                        f"📰 {article.get('title', '')}\n\n"
                        f"{article.get('description', 'No description available.')}\n\n"
                        f"🔗 {article.get('link', '')}\n"
                        f"📅 Published: {article.get('pubDate', 'Date not available')}"
                    )
                    await update.message.reply_text(
                        simple_message,
                        disable_web_page_preview=True
                    )
                    sent_count += 1
            except Exception as e:
                logger.error(f"Error sending news article: {str(e)}")
                continue
        
        if sent_count > 0:
            logger.info(f"Successfully sent {sent_count} articles to user {update.effective_user.id}")
            await message.delete()
        else:
            logger.error("Failed to send any articles despite having them")
            await message.edit_text(
                "Sorry, I had trouble sending the news articles. Please try again later."
            )
            
    except Exception as e:
        logger.error(f"Error in news command: {str(e)}")
        await update.message.reply_text("Sorry, something went wrong. Please try again later.")

async def send_updates():
    """Send updates to all subscribed users."""
    try:
        logger.info("Starting scheduled update")
        subscribed_users = load_subscribed_users()
        
        if not subscribed_users:
            logger.info("No subscribed users")
            return
            
        # Create bot instance
        bot = Updater(TELEGRAM_BOT_TOKEN).bot
        
        # Fetch updates
        price_data = await get_dogecoin_price()
        articles = await fetch_dogecoin_news()
        
        if not articles:
            logger.info("No articles found for update")
            return

        logger.info(f"Sending updates to {len(subscribed_users)} users")
        
        for chat_id in subscribed_users:
            try:
                # Send price update
                bot.send_message(
                    chat_id=chat_id,
                    text=format_price_message(price_data),
                    parse_mode='Markdown'
                )
                
                bot.send_message(
                    chat_id=chat_id,
                    text="🔄 Here's your Dogecoin news update:"
                )
                
                # Send the most recent news item
                article = articles[0]
                bot.send_message(
                    chat_id=chat_id,
                    text=format_news_message(article),
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                logger.info(f"Update sent to chat {chat_id}")
            except Exception as e:
                logger.error(f"Error sending update to {chat_id}: {e}")
                # If we get a chat not found error, remove the user from subscribed users
                if "chat not found" in str(e).lower():
                    subscribed_users.discard(chat_id)
                    save_subscribed_users(subscribed_users)
    except Exception as e:
        logger.error(f"Error in send_updates: {e}")

async def test_news_fetch():
    """Test function to fetch and print news articles."""
    print("Testing news fetch...")
    articles = await fetch_dogecoin_news()
    print(f"\nFound {len(articles)} articles:")
    for article in articles:
        print("\n-------------------")
        print(f"Title: {article.get('title')}")
        print(f"Description: {article.get('description')}")
        print(f"Link: {article.get('link')}")
        print(f"Published: {article.get('pubDate')}")
    return articles

def main() -> None:
    """Start the bot."""
    try:
        # If running in GitHub Actions, just send updates and exit
        if os.getenv('GITHUB_ACTIONS'):
            asyncio.run(send_updates())
            return

        # Create pid file to prevent multiple instances
        pid_file = 'bot.pid'
        if os.path.exists(pid_file):
            with open(pid_file, 'r') as f:
                old_pid = int(f.read().strip())
                try:
                    # Check if process with this PID exists
                    os.kill(old_pid, 0)
                    logger.error(f"Bot is already running with PID {old_pid}")
                    sys.exit(1)  # Exit if another instance is running
                except OSError:
                    # Process not found, we can continue
                    pass
        
        # Write current PID
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))

        # Create event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Set up the bot
        updater = Updater(TELEGRAM_BOT_TOKEN)
        dispatcher = updater.dispatcher

        # Ensure no webhook is configured
        updater.bot.delete_webhook()

        # Add command handlers
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("help", help_command))
        dispatcher.add_handler(CommandHandler("news", send_news))
        dispatcher.add_handler(CommandHandler("price", price_command))
        dispatcher.add_handler(CommandHandler("stop", stop))

        # Add error handler
        async def error_handler(update: Update, context: CallbackContext) -> None:
            logger.error(f"Update {update} caused error {context.error}")
            if update and update.effective_message:
                await update.effective_message.reply_text("Sorry, something went wrong. Please try again later.")

        dispatcher.add_error_handler(error_handler)

        def shutdown(signum, frame):
            logger.info("Received shutdown signal")
            updater.stop()
            if os.path.exists(pid_file):
                os.remove(pid_file)
            logger.info("Bot shutdown complete")
            sys.exit(0)

        # Register shutdown handlers
        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        async def run_bot():
            # Start the bot
            updater.start_polling(drop_pending_updates=True)
            
            # Run hourly updates
            while True:
                try:
                    await send_updates()
                except Exception as e:
                    logger.error(f"Error in hourly update: {e}")
                await asyncio.sleep(3600)

        # Run everything in the event loop
        try:
            logger.info("Bot starting...")
            loop.run_until_complete(run_bot())
        finally:
            loop.close()
            if os.path.exists(pid_file):
                os.remove(pid_file)

    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        if os.path.exists(pid_file):
            os.remove(pid_file)
        sys.exit(1)  # Exit with error code

if __name__ == '__main__':
    if os.getenv('TEST_NEWS'):
        asyncio.run(test_news_fetch())
    else:
        main() 