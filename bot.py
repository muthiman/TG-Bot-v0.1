import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import aiohttp
import asyncio

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
COINMARKETCAP_API_KEY = os.getenv('COINMARKETCAP_API_KEY', "bd1eb80b-e7df-4547-85a4-9138db279efe")
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY', "pub_747026d7148da05676417a4f83d51505e3025")

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
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
        # Calculate time 1 hour ago
        one_hour_ago = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d-%H')
        
        url = (f"https://newsdata.io/api/1/news?"
               f"apikey={NEWSDATA_API_KEY}"
               f"&q=Dogecoin,DOGE,Doge"
               f"&language=en"
               f"&timeframe={one_hour_ago}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"API request failed with status {response.status}")
                    return []
                
                try:
                    data = await response.json()
                except Exception as e:
                    logger.error(f"Failed to parse API response: {e}")
                    return []
                
                if data.get('status') != 'success':
                    logger.error(f"API returned error status: {data.get('results', {}).get('message', 'Unknown error')}")
                    return []
                
                # Filter articles to ensure they're about Dogecoin cryptocurrency
                filtered_articles = []
                results = data.get('results', [])
                if not results:
                    logger.info("No articles found in API response")
                    return []
                
                for article in results:
                    if not isinstance(article, dict):
                        logger.warning(f"Skipping invalid article format: {type(article)}")
                        continue
                        
                    # Safely get text fields with empty string fallback
                    title = str(article.get('title', '')).lower()
                    description = str(article.get('description', '')).lower()
                    
                    # Check if required fields exist
                    if not article.get('title') or not article.get('link'):
                        logger.warning("Skipping article missing required fields")
                        continue
                    
                    # Check if the article is specifically about Dogecoin cryptocurrency
                    if 'dogecoin' in title or 'doge' in title or 'dogecoin' in description:
                        filtered_articles.append(article)
                
                logger.info(f"Successfully fetched {len(filtered_articles)} Dogecoin cryptocurrency articles from the last hour")
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
    try:
        title = str(article.get('title', 'No title available'))
        description = str(article.get('description', 'No description available'))
        link = str(article.get('link', ''))
        pub_date = str(article.get('pubDate', 'Date not available'))
        
        return (
            f"📰 *{title}*\n\n"
            f"{description}\n\n"
            f"🔗 [Read more]({link})\n"
            f"📅 Published: {pub_date}"
        )
    except Exception as e:
        logger.error(f"Error formatting news message: {e}")
        return "Error formatting article"

def start(update: Update, context: CallbackContext) -> None:
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
        
        update.message.reply_text(welcome_message)
        logger.info(f"Welcome message sent to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        update.message.reply_text("Sorry, something went wrong. Please try again later.")

def help_command(update: Update, context: CallbackContext) -> None:
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
        update.message.reply_text(help_text)
        logger.info(f"Help message sent to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        update.message.reply_text("Sorry, something went wrong. Please try again later.")

def stop(update: Update, context: CallbackContext) -> None:
    """Unsubscribe from updates."""
    try:
        logger.info(f"Stop command received from user {update.effective_user.id}")
        subscribed_users = load_subscribed_users()
        subscribed_users.discard(update.effective_chat.id)
        save_subscribed_users(subscribed_users)
        
        update.message.reply_text("You've been unsubscribed from Dogecoin updates. Send /start to subscribe again.")
        logger.info(f"User {update.effective_user.id} unsubscribed")
    except Exception as e:
        logger.error(f"Error in stop command: {e}")
        update.message.reply_text("Sorry, something went wrong. Please try again later.")

def price_command(update: Update, context: CallbackContext) -> None:
    """Send current Dogecoin price information."""
    try:
        logger.info(f"Price command received from user {update.effective_user.id}")
        update.message.reply_text("🔍 Fetching latest Dogecoin price...")
        
        price_data = asyncio.run(get_dogecoin_price())
        update.message.reply_text(
            format_price_message(price_data),
            parse_mode='Markdown'
        )
        
        logger.info(f"Price info sent to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in price command: {e}")
        update.message.reply_text("Sorry, something went wrong. Please try again later.")

def send_news(update: Update, context: CallbackContext) -> None:
    """Send latest Dogecoin news when the command /news is issued."""
    try:
        logger.info(f"News command received from user {update.effective_user.id}")
        update.message.reply_text("🔍 Fetching latest Dogecoin news...")
        
        # First send price update
        price_data = asyncio.run(get_dogecoin_price())
        update.message.reply_text(
            format_price_message(price_data),
            parse_mode='Markdown'
        )
        
        # Then send news
        articles = asyncio.run(fetch_dogecoin_news())
        
        if not articles:
            update.message.reply_text(
                "Sorry, I couldn't find any recent news about Dogecoin. Please try again later."
            )
            return

        # Send up to 5 most recent news items
        for article in articles[:5]:
            try:
                update.message.reply_text(
                    format_news_message(article),
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(f"Error sending news article: {e}")
        
        logger.info(f"News sent to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in news command: {e}")
        update.message.reply_text("Sorry, something went wrong. Please try again later.")

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
        
        logger.info(f"Sending updates to {len(subscribed_users)} users")
        
        for chat_id in subscribed_users:
            try:
                # Send price update
                bot.send_message(
                    chat_id=chat_id,
                    text=format_price_message(price_data),
                    parse_mode='Markdown'
                )
                
                if articles:
                    bot.send_message(
                        chat_id=chat_id,
                        text=f"🔄 Here are the Dogecoin news updates from the last hour ({len(articles)} articles found):"
                    )
                    
                    # Send all articles from the last hour
                    for article in articles:
                        try:
                            bot.send_message(
                                chat_id=chat_id,
                                text=format_news_message(article),
                                parse_mode='Markdown',
                                disable_web_page_preview=True
                            )
                        except Exception as e:
                            logger.error(f"Error sending news article: {e}")
                else:
                    bot.send_message(
                        chat_id=chat_id,
                        text="No new Dogecoin news in the last hour."
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

def main() -> None:
    """Start the bot."""
    try:
        # If running in GitHub Actions, just send updates and exit
        if os.getenv('GITHUB_ACTIONS'):
            logger.info("Running in GitHub Actions - sending scheduled update")
            asyncio.run(send_updates())
            return

        # Otherwise, run the bot normally for local testing
        updater = Updater(TELEGRAM_BOT_TOKEN)
        dispatcher = updater.dispatcher

        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("help", help_command))
        dispatcher.add_handler(CommandHandler("news", send_news))
        dispatcher.add_handler(CommandHandler("price", price_command))
        dispatcher.add_handler(CommandHandler("stop", stop))

        logger.info("Bot started successfully")
        
        updater.start_polling()
        updater.idle()
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

if __name__ == '__main__':
    main() 