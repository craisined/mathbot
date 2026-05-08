import datetime
import discord
from discord.ext import commands, tasks
import dotenv
import events
import logging
import os

dotenv.load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

LOG_HANDLER = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='a')
ERROR_HANDLER = logging.StreamHandler()
ERROR_HANDLER.setLevel(logging.ERROR)
logging.basicConfig(level=logging.INFO, handlers=[LOG_HANDLER, ERROR_HANDLER], format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s', force=True)

class Bot(commands.Bot):
    async def setup_hook(self):
        await self.tree.sync()
        logging.info("commands synced successfully")

intents = discord.Intents.default()
intents.members, intents.message_content = True, True
bot = Bot(command_prefix="/", intents=intents)
event_manager = events.EventManager("events.json")
user_manager = events.UserManager("users.json")

@bot.tree.command(name="register", description="Register for an event")
async def register(interaction: discord.Interaction, name: str):
    name = name.lower().replace(" ", "-")
    event = event_manager.get_event(interaction.guild.id, name)
    if event is None:
        raise AttributeError("event not found")
    channel = interaction.guild.get_channel(event["channel"])
    role = interaction.guild.get_role(event["role"])
    member = interaction.guild.get_member(interaction.user.id)
    await member.add_roles(role)
    logging.info(f"registered {interaction.user} for event '{name}' in '{interaction.guild.name}'")
    await interaction.response.send_message(f"{interaction.user.mention} is now registered for {channel.mention}!", ephemeral=True)

@register.error
async def register_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.errors.CommandInvokeError) and isinstance(error.original, AttributeError):
        logging.warning(f"event not found for '{interaction.guild.name}'")
        await interaction.response.send_message(f"Event not found!", ephemeral=True)
    else:
        logging.error(f"an error occurred in register: {error}")
        await interaction.response.send_message("An error occurred!", ephemeral=True)

@bot.tree.command(name="unregister", description="Unregister from an event")
async def unregister(interaction: discord.Interaction, name: str):
    name = name.lower().replace(" ", "-")
    event = event_manager.get_event(interaction.guild.id, name)
    if event is None:
        raise AttributeError("event not found")
    channel = interaction.guild.get_channel(event["channel"])
    role = interaction.guild.get_role(event["role"])
    member = interaction.guild.get_member(interaction.user.id)
    await member.remove_roles(role)
    logging.info(f"unregistered {interaction.user} from event '{name}' in '{interaction.guild.name}'")
    await interaction.response.send_message(f"{interaction.user.mention} is no longer registered for {channel.mention}.", ephemeral=True)

@bot.tree.command(name="list_events", description="List all events")
async def list_events(interaction: discord.Interaction):
    events = event_manager.list_events(interaction.guild.id)
    if not events:
        await interaction.response.send_message("No events found!", ephemeral=True)
        return None
    event_list = "\n".join([f"- {event}" for event in events])
    message = discord.Embed(
        title="Current Events",
        description=event_list,
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=message, ephemeral=True)

@bot.tree.command(name="announce", description="Announce an event")
async def announce(interaction: discord.Interaction, title: str, content: str):
    announcement = discord.Embed(
        title=title,
        description=content,
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=announcement)

@bot.tree.command(name="email", description="Set user email")
async def email(interaction: discord.Interaction, email: str):
    user_manager.add_user(interaction.user.id, email)
    logging.info(f"set email for '{interaction.user}'")
    await interaction.response.send_message(f"Your email has been set to {email}.", ephemeral=True)

@bot.tree.command(name="new_event", description="Create a new event")
@discord.app_commands.checks.has_role("admin")
async def new_event(interaction: discord.Interaction, name: str):
    name = name.lower().replace(" ", "-")
    if event_manager.get_event(interaction.guild.id, name) is not None:
        await interaction.response.send_message(f"An event with the name '{name}' already exists!", ephemeral=True)
        return None

    event_category = discord.utils.get(interaction.guild.categories, name="Events")
    if event_category is None:
        event_category = await interaction.guild.create_category(name="Events")
    role = await interaction.guild.create_role(name=name)
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }
    channel = await event_category.create_text_channel(name=name, overwrites=overwrites)

    announcement = discord.Embed(
        title=f"Event {channel.mention}",
        description="Register using /register command!",
        color=discord.Color.blue()
    )
    announcement_channel = discord.utils.get(interaction.guild.channels, name="announcements")
    if announcement_channel is None:
        announcement_channel = await interaction.guild.create_text_channel(name="announcements")
    message = await announcement_channel.send(embed=announcement)

    event_manager.add_event(interaction.guild.id, name, channel.id, role.id, message.id)

    logging.info(f"created new event '{name}' for '{interaction.guild.name}'")
    await interaction.response.send_message(f"Successfully created {name}: {channel.mention}", ephemeral=True)

@new_event.error
async def new_event_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingRole):
        await interaction.response.send_message("Oops! You don't have permission to use this command.", ephemeral=True)
    elif isinstance(error.original, discord.Forbidden):
        logging.warning(f"permission error while creating event for '{interaction.guild.name}'")
        await interaction.response.send_message("I need permission to create channels!", ephemeral=True)
    elif isinstance(error, discord.app_commands.errors.CommandInvokeError) and isinstance(error.original, AttributeError):
        await interaction.response.send_message(f"This bot doesn't work outside a server!", ephemeral=True)
    else:
        logging.error(f"an error occurred in new_event: {error}")
        await interaction.response.send_message(f"An error occurred!", ephemeral=True)

@bot.tree.command(name="remove_event", description="Remove an event")
@discord.app_commands.checks.has_role("admin")
async def remove_event(interaction: discord.Interaction, name: str):
    name = name.lower().replace(" ", "-")
    event = event_manager.get_event(interaction.guild.id, name)
    if event is None:
        raise AttributeError("event not found")
    channel = interaction.guild.get_channel(event["channel"])
    role = interaction.guild.get_role(event["role"])
    if channel is not None:
        await channel.delete()
    if role is not None:
        await role.delete()

    announcement_channel = discord.utils.get(interaction.guild.channels, name="announcements")
    if announcement_channel is not None:
        message = await announcement_channel.fetch_message(event["message"])
        if message is not None:
            await announcement_channel.delete_messages([message])

    event_manager.remove_event(interaction.guild.id, name)
    logging.info(f"removed event '{name}' for {interaction.guild.name}")
    await interaction.response.send_message(f"Event '{name}' has been removed.", ephemeral=True)

@remove_event.error
async def remove_event_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingRole):
        await interaction.response.send_message("Oops! You don't have permission to use this command.", ephemeral=True)
    elif isinstance(error.original, discord.Forbidden):
        logging.warning(f"permission error while removing event for {interaction.guild.name}")
        await interaction.response.send_message("I need permission to delete channels/roles!", ephemeral=True)
    elif isinstance(error, discord.app_commands.errors.CommandInvokeError) and isinstance(error.original, AttributeError):
        logging.warning(f"event not found for {interaction.guild.name}")
        await interaction.response.send_message(f"Event not found!", ephemeral=True)
    else:
        logging.error(f"an error occurred in remove_event: {error}")
        await interaction.response.send_message(f"An error occurred!", ephemeral=True)

@bot.tree.command(name="archive_event", description="Archive an event (moves channel and deletes role and info)")
@discord.app_commands.checks.has_role("admin")
async def archive_event(interaction: discord.Interaction, name: str):
    name = name.lower().replace(" ", "-")
    event = event_manager.get_event(interaction.guild.id, name)
    if event is None:
        raise AttributeError("event not found")

    past_category = discord.utils.get(interaction.guild.categories, name="Past Events")
    if past_category is None:
        past_category = await interaction.guild.create_category(name="Past Events")

    channel = interaction.guild.get_channel(event["channel"])
    role = interaction.guild.get_role(event["role"])
    if channel is not None:
        await channel.edit(category=past_category, sync_permissions=True)
    if role is not None:
        await role.delete()

    announcement_channel = discord.utils.get(interaction.guild.channels, name="announcements")
    if announcement_channel is not None:
        message = await announcement_channel.fetch_message(event["message"])
        if message is not None:
            await announcement_channel.delete_messages([message])

    event_manager.remove_event(interaction.guild.id, name)
    logging.info(f"archived event '{name}' for '{interaction.guild.name}'")
    await interaction.response.send_message(f"Event '{name}' has been archived.", ephemeral=True)

@archive_event.error
async def archive_event_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingRole):
        await interaction.response.send_message("Oops! You don't have permission to use this command.", ephemeral=True)
    elif isinstance(error.original, discord.Forbidden):
        logging.warning(f"permission error while archiving event for '{interaction.guild.name}'")
        await interaction.response.send_message("I need permission to move channels and delete roles!", ephemeral=True)
    elif isinstance(error, discord.app_commands.errors.CommandInvokeError) and isinstance(error.original, AttributeError):
        logging.warning(f"event not found for '{interaction.guild.name}'")
        await interaction.response.send_message(f"Event not found!", ephemeral=True)
    else:
        logging.error(f"an error occurred in archive_event: {error}")
        await interaction.response.send_message(f"An error occurred!", ephemeral=True)

@bot.tree.command(name="edit_event_info", description="Edit an event's info")
@discord.app_commands.checks.has_role("admin")
async def edit_event_info(interaction: discord.Interaction, name: str, attribute: str, info: str):
    name = name.lower().replace(" ", "-")
    event = event_manager.get_event(interaction.guild.id, name)
    if event is None:
        raise AttributeError("event not found")

    announcement_channel = discord.utils.get(interaction.guild.channels, name="announcements")
    if announcement_channel is None:
        announcement_channel = await interaction.guild.create_text_channel(name="announcements")

    message = await announcement_channel.fetch_message(event["message"])

    announcement = message.embeds[0]
    if announcement.description is not None:
        announcement.description += f"\n- {attribute}: {info}"
    else:
        announcement.description = f"- {attribute}: {info}"
    await message.edit(embed=announcement)
    await interaction.response.send_message(f"Event '{name}' info updated with '{attribute}: {info}'.", ephemeral=True)

@edit_event_info.error
async def edit_event_info_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingRole):
        await interaction.response.send_message("Oops! You don't have permission to use this command.", ephemeral=True)
    elif isinstance(error.original, discord.Forbidden):
        logging.warning(f"permission error while editing event info for '{interaction.guild.name}'")
        await interaction.response.send_message("I need permission to edit messages!", ephemeral=True)
    elif isinstance(error, discord.app_commands.errors.CommandInvokeError) and isinstance(error.original, AttributeError):
        logging.warning(f"event not found for '{interaction.guild.name}'")
        await interaction.response.send_message(f"Event not found!", ephemeral=True)
    else:
        logging.error(f"an error occurred in edit_event_info: {error}")
        await interaction.response.send_message(f"An error occurred!", ephemeral=True)

bot.run(TOKEN, log_handler=None)