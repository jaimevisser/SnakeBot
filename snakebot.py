import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

import discord
from discord.ext import commands

from snakebot import Config, TicketManager, TicketAlreadyExistsError, QuestionManager

os.makedirs("data/logs", exist_ok=True)
filehandler = RotatingFileHandler(filename="data/logs/snakebot.log", mode="w", maxBytes=1024 * 50, backupCount=4)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s:%(message)s",
                    handlers=[filehandler])

logger = logging.getLogger('snakebot')

intents = discord.Intents.default()
intents.message_content = True  # Required to read message content
intents.dm_messages = True      # Required to receive DMs
bot = discord.Bot(intents=intents)

config = Config()
question_manager = QuestionManager(bot, config)
ticket_manager = TicketManager(bot, question_manager)

question_manager.get_ticket = ticket_manager.get_user_ticket
question_manager.save_tickets = ticket_manager.save


logger.info("Ticket manager initialized")

# Simple ping command to verify the bot is working
@bot.slash_command(description="Replies with pong!")
async def ping(ctx):
    await ctx.respond(f"Pong! Latency: {round(bot.latency * 1000)}ms")

async def find_button_message(channel, button_id="request_boa_button"):
    try:
        # Fetch recent messages in the channel
        async for message in channel.history(limit=100):
            # Check if message is from our bot and contains a button with our custom ID
            if message.author == bot.user and message.components:
                for row in message.components:
                    for component in row.children:
                        if hasattr(component, 'custom_id') and component.custom_id == button_id:
                            logger.info(f"Found existing button message in channel {channel.name}")
                            return message
        return None
    except Exception as e:
        logger.error(f"Error while checking for existing button messages: {e}")
        return None

@bot.slash_command(description="Cancel your current BOA request (must be used in DM)")
async def cancel(ctx):
    if ctx.guild is not None:
        await ctx.respond("You can only use this command in a DM with the bot.", ephemeral=True)
        return
    user_id = str(ctx.author.id)
    ticket = ticket_manager.get_user_ticket(user_id)
    if not ticket:
        await ctx.respond("You do not have an open BOA request.", ephemeral=True)
        return
    ticket_manager.remove_ticket(user_id)
    await ctx.respond("Your BOA request has been cancelled.", ephemeral=True)

async def post_button_message(channel, button_label="Request a BOA", button_id="request_boa_button", message_text="Click the button below to request a BOA:"):
    try:
        # Create a button with green color (success style)
        button = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label=button_label,
            custom_id=button_id
        )
        
        # Create a View and add the button
        view = discord.ui.View(timeout=None)
        view.add_item(button)
        
        # Send the message with the button
        message = await channel.send(message_text, view=view)
        logger.info(f"Button message sent to channel {channel.name}")
        return message
    except Exception as e:
        logger.error(f"Failed to send button message: {e}")
        return None

async def handle_boa_button_press(interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        ticket = ticket_manager.create_ticket(str(interaction.user.id))
        try:
            await interaction.user.send(f"Hello {interaction.user.mention}! You requested a BOA. How can I help you?")
            await interaction.followup.send("I've sent you a DM!", ephemeral=True)
            logger.info(f"User {interaction.user} requested a BOA")
        except Exception as e:
            await interaction.followup.send(
                "I couldn't send you a DM. Please make sure you have DMs enabled for this server.", 
                ephemeral=True
            )
            logger.error(f"Failed to send DM to {interaction.user}: {e}")
            return
        await question_manager.ask_next_question(str(interaction.user.id))
    except TicketAlreadyExistsError as e:
        try:
            await interaction.user.send(
                f"Hello {interaction.user.mention}! Your BOA request is still in the queue. "
            )
            await interaction.followup.send("You already have an active request.", ephemeral=True)
        except:
            await interaction.followup.send(
                f"You already have an active BOA request in the queue.", 
                ephemeral=True
            )

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        if interaction.data.get('custom_id') == 'request_boa_button':
            await handle_boa_button_press(interaction)
            return
        await question_manager.on_interaction(interaction)

@bot.event
async def on_ready():
    logger.info(f'Bot connected as {bot.user} (ID: {bot.user.id})')
    logger.info(f'Connected to {len(bot.guilds)} servers')
    
    # If no channel ID is configured, we don't need to do anything with buttons
    if not config.channel_id:
        return
        
    # Try to get the channel where the button should be placed
    try:
        channel = bot.get_channel(int(config.channel_id))
        if not channel:
            logger.error(f"Could not find channel with ID: {config.channel_id}")
            return
    except Exception as e:
        logger.error(f"Failed to get channel: {e}")
        return
    
    # Check if there's already a button message in the channel
    existing_button_message = await find_button_message(channel)
    
    # If we found an existing button message, we're done
    if existing_button_message:
        logger.info(f"Using existing button message in channel {channel.name}")
        return
    
    # Create a new button message since we didn't find an existing one
    await post_button_message(channel)

@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
        
    await question_manager.on_message(message)

# Load token and run bot
logger.info("Bot token loaded, connecting to Discord...")
bot.run(config.token)