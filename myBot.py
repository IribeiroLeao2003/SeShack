
import discord
import openai
from discord.ext import commands
from dotenv import load_dotenv
import os 
import asyncio
from datetime import datetime, timezone, timedelta 
import random
import sqlite3
import logging
import atexit
import sys

import yt_dlp as youtube_dl

load_dotenv()
token = os.getenv('TOKEN')
print(f"Loaded token: {token}")
reminders = []
queues = {}

logging.basicConfig(filename='command_logs.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s', 
                    datefmt='%Y-%m-%d %H:%M:%S')



intents = discord.Intents.default()  
intents.presences = True
intents.messages = True 
intents.message_content = True
intents.members = True 
eight_ball_answers = [
    "It is certain.",
    "It is decidedly so.",
    "Without a doubt.",
    "Yes – definitely.",
    "You may rely on it.",
    "As I see it, yes.",
    "Most likely.",
    "Outlook good.",
    "Yes.",
    "Signs point to yes.",
    "Reply hazy, try again.",
    "Ask again later.",
    "Better not tell you now.",
    "Cannot predict now.",
    "Concentrate and ask again.",
    "Don't count on it.",
    "My reply is no.",
    "My sources say no.",
    "Outlook not so good.",
    "Very doubtful.", 
    "Nuh uh.",  
    "Is Colvin Drinking again ?"
]

youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

bot = commands.Bot(command_prefix='!', intents=intents)


def setup_database():
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (id INTEGER PRIMARY KEY, time TEXT, message TEXT, channel_id INTEGER)''')
    conn.commit()
    conn.close()

setup_database()
bot.remove_command('help')


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # Take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

    

def next_weekday(weekday_str):
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    today = datetime.now(timezone.utc)
    today_weekday = today.weekday()
    days_ahead = weekdays.index(weekday_str) - today_weekday
    if days_ahead <= 0:  
        days_ahead += 7
    next_day = today + timedelta(days=days_ahead)
    return next_day.replace(hour=0, minute=0, second=0, microsecond=0) 


@bot.command(name='echo', help='Repeats what you say and deletes your message.')
async def echo(ctx, *, message: str):
    await ctx.message.delete()
    await ctx.send(message)  


@bot.command(name='remindme', help='Starts an interactive session to set a reminder. First, ask for the day of the week.')
async def set_reminder(ctx):

    logging.info(f"{ctx.author} initiated set_reminder command.")
   
    await ctx.send("For which day of the week would you like to set the reminder? (Please respond with the abbreviated day, e.g., Mon, Tue, Wed)")
    
    day_msg = await bot.wait_for('message', check=lambda message: message.author == ctx.author and message.channel == ctx.channel, timeout=60.0)
    if day_msg.content.capitalize()[:3] not in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        await ctx.send("Invalid day. Please use the abbreviated form (e.g., Mon, Tue, Wed).")
        return
    reminder_time = next_weekday(day_msg.content.capitalize()[:3])
    
    await ctx.send("Would you like this reminder to be repeated every week? Type `yes` or `no`.")
    repeat_msg = await bot.wait_for('message', check=lambda message: message.author == ctx.author and message.channel == ctx.channel, timeout=30.0)
    repeat = repeat_msg.content.lower().startswith('y')

    
    text_channels = ctx.guild.text_channels
    channels_str = "Please type the name of the channel you want the reminder in from the list below:\n"
    for channel in text_channels:
        channels_str += f"- {channel.name}\n"
    await ctx.send(channels_str)

    await ctx.send("Now, type the exact name of the channel you chose.")
    channel_msg = await bot.wait_for('message', check=lambda message: message.author == ctx.author and message.channel == ctx.channel, timeout=60.0)
    selected_channel = discord.utils.get(ctx.guild.text_channels, name=channel_msg.content)
    if not selected_channel:
        await ctx.send("Channel not found. Please ensure you've typed the channel name exactly as it appears in the list.")
        return

    await ctx.send("What would you like to be reminded about?")
    reminder_msg = await bot.wait_for('message', check=lambda message: message.author == ctx.author and message.channel == ctx.channel, timeout=60.0)

     
    reminder_time_str = reminder_time.strftime('%Y-%m-%d %H:%M:%S')
    
    
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    
    
    sql = '''INSERT INTO reminders (time, message, channel_id) VALUES (?, ?, ?)'''
    reminder_data = (reminder_time_str, reminder_msg.content, selected_channel.id)
    
    
    try:
        c.execute(sql, reminder_data)
        conn.commit()  
        await ctx.send("Your reminder has been set successfully.")
        
    except sqlite3.Error as e:
        await ctx.send("An error occurred while setting your reminder.")
        print(f"SQLite error: {e}")
    finally:
         
        logging.info(f"Reminder set by {ctx.author}.")
        conn.close()  


@bot.command(name='test_reminder', help='Lists reminders from the database and lets you choose one to test.')
async def test_reminder(ctx):
    logging.info(f"{ctx.author} initiated test_reminder command.")
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("SELECT id, time, message FROM reminders ORDER BY time")
    reminders = c.fetchall()
    conn.close()
    
    
    if not reminders:
        await ctx.send("No reminders found in the database.")
        return

    
    reminder_list_str = "Please select a reminder to test by typing its number:\n"
    for idx, reminder in enumerate(reminders, start=1):
        time, message = reminder[1], reminder[2]
        reminder_list_str += f"{idx}. Time: {time}, Message: \"{message}\"\n"
    
    await ctx.send(reminder_list_str)

    
    try:
        selection_msg = await bot.wait_for('message', check=lambda message: message.author == ctx.author and message.channel == ctx.channel, timeout=60.0)
        selection = int(selection_msg.content) - 1  
        if selection < 0 or selection >= len(reminders):
            await ctx.send("Invalid selection.")
            return
    except ValueError:
        await ctx.send("Please enter a valid number.")
        return
    except asyncio.TimeoutError:
        await ctx.send("You took too long to respond.")
        return

    
    _, test_time, test_message = reminders[selection]
    test_reminder_message = f"@here Test Reminder (Scheduled for {test_time}): {test_message}"
    logging.info(f"Test reminder executed by {ctx.author}.")
    await ctx.send(test_reminder_message)



@bot.command(name='8ball', help='Ask the Magic 8 Ball a question.')
async def eight_ball(ctx, *, question: str):
    response = random.choice(eight_ball_answers)
    embed = discord.Embed(
        
        color=discord.Color.dark_blue()
    )
    
    embed.add_field(name="Answer", value="🎱" + response, inline=False)
    
    
    

    logging.info(f"8Ball used by {ctx.author}, question: '{question}' - response: '{response}'.")
    await ctx.send(embed=embed)




def check_queue(ctx, id):
    if queues[id]:
        voice_client = ctx.guild.voice_client
        source = queues[id].pop(0)
        player = discord.FFmpegPCMAudio(source, **ffmpeg_options)

        def after_playing(err):
            if len(queues[id]) > 0:
                check_queue(ctx, id)
            else:
                asyncio.run_coroutine_threadsafe(voice_client.disconnect(), bot.loop)

        voice_client.play(player, after=after_playing)

@bot.command(name='active', help='Lists active members in the server with their status.')
async def active(ctx):
    if isinstance(ctx.channel, discord.abc.GuildChannel):
        embed = discord.Embed(title="Active Members", description="Here are the members currently active in the server:", color=discord.Color.green())
        
        for member in ctx.guild.members:
            if not member.bot and member.status in (discord.Status.online, discord.Status.idle, discord.Status.dnd):
                status_emoji = "🟢" if member.status == discord.Status.online else "🟡" if member.status == discord.Status.idle else "🔴"
                embed.add_field(name=member.display_name, value=f"{status_emoji} {str(member.status).title()}", inline=True)
        
        await ctx.send(embed=embed)
    else:
        await ctx.send('This command can only be used in a server.')




@bot.command(name='dayscharlie', help="Counts the days since the server was created and mentions Charlie.")
async def days_since_charlie(ctx):
    logging.info(f"{ctx.author} requested for days_since_charlie")
    if isinstance(ctx.channel, discord.abc.GuildChannel):
        
        charlie = discord.utils.find(lambda m: m.name == 'amourshippercharlie8912', ctx.guild.members)
        
        if charlie:
            
            creation_date = ctx.guild.created_at
            
            now = datetime.now(timezone.utc)
           
            delta = now - creation_date
            
            await ctx.send(f"{delta.days} days since {charlie.mention} has spoken.(Come back king)")
        else:
            await ctx.send("Charlie could not be found in this server.")
    else:
        await ctx.send("This command can only be used in a server.")


@bot.command(name='serverday', help='Displays the day the server was created.')
async def server_day(ctx):
    logging.info(f"{ctx.author} requested for server_day")
    if isinstance(ctx.channel, discord.abc.GuildChannel):
        creation_date = ctx.guild.created_at
        formatted_date = creation_date.strftime('%B %d, %Y')
        await ctx.send(f'This server was created on {formatted_date}.')
    else:
        await ctx.send('This command can only be used in a server.')

@bot.command(name='showreminders', help='Shows all scheduled reminders.')
async def show_reminders(ctx):
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("SELECT time, message, channel_id FROM reminders ORDER BY time")
    reminders = c.fetchall()
    conn.close()
    
    if reminders:
        embed = discord.Embed(title="Scheduled Reminders", description="Here are all the scheduled reminders:", color=discord.Color.blue())
        for reminder in reminders:
            time, message, channel_id = reminder
            channel = bot.get_channel(channel_id)
            channel_name = channel.name if channel else 'Deleted Channel'
            embed.add_field(name=f"Reminder for {channel_name}", value=f"Time: {time}\nMessage: {message}", inline=False)
        
        await ctx.send(embed=embed)
    else:
        await ctx.send("No reminders scheduled.")


@bot.command(name='hello', help='Greets the user.')
async def hello(ctx):
    logging.info(f"{ctx.author} requested for hello")
    await ctx.send('Hello!')

@bot.command(name='remove_reminder', help='Lists reminders and allows you to choose one to remove.')
async def remove_reminder(ctx):
    logging.info(f"{ctx.author} requested for remove_reminder")
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("SELECT id, time, message FROM reminders ORDER BY time")
    reminders = c.fetchall()
    conn.close()
    
    
    if not reminders:
        await ctx.send("No reminders found in the database.")
        return

    
    reminder_list_str = "Please select a reminder to remove by typing its number:\n"
    for idx, reminder in enumerate(reminders, start=1):
        id, time, message = reminder
        reminder_list_str += f"{idx}. [ID: {id}] Time: {time}, Message: \"{message}\"\n"


    logging.info(f"{ctx.author} requested for removed reminder of id {id} and text of {message}")
    await ctx.send(reminder_list_str)

    
    try:
        selection_msg = await bot.wait_for('message', check=lambda message: message.author == ctx.author and message.channel == ctx.channel, timeout=60.0)
        selection = int(selection_msg.content) - 1  
        if selection < 0 or selection >= len(reminders):
            await ctx.send("Invalid selection.")
            return
    except ValueError:
        await ctx.send("Please enter a valid number.")
        return
    except asyncio.TimeoutError:
        await ctx.send("You took too long to respond.")
        return

    
    reminder_to_remove = reminders[selection]
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    c.execute("DELETE FROM reminders WHERE id = ?", (reminder_to_remove[0],))
    conn.commit()
    conn.close()

    await ctx.send(f"Reminder [ID: {reminder_to_remove[0]}] has been successfully removed.")


async def check_reminders():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect('reminders.db')
        c = conn.cursor()
        c.execute("SELECT id, message, channel_id FROM reminders WHERE time <= ?", (now,))
        due_reminders = c.fetchall()
        
        for reminder in due_reminders:
            _, message, channel_id = reminder
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(message)
                
                c.execute("DELETE FROM reminders WHERE id = ?", (reminder[0],))
        
        conn.commit()
        conn.close()
        await asyncio.sleep(60)



@bot.command(name='play', help='Plays a video from YouTube')
async def play(ctx, *, url: str):
    async with ctx.typing():
        player = await YTDLSource.from_url(url, loop=bot.loop)
        ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

    await ctx.send(f'**Now playing:** {player.title}')

@bot.command(name='help', help='Shows this help message')
async def help(ctx):
    embed = discord.Embed(
        title="Bot Commands Help",
        description="Here's a list of all commands grouped by category.",
        color=discord.Color.blue()
    )
    
    
    embed.add_field(name="General", value="`!hello` - Greets the user.\n`!active` - Lists active members.", inline=False)
    embed.add_field(name="Music", value="`!play <URL>` - Plays a video from YouTube.\n`!queue` - Displays the current music queue.\n`!skip` - Skips the current song being played.\n`!clear` - Clears the current queue.\n`!join` - Joins a voice channel.\n`!leave` - Leaves the voice channel.", inline=False)
    embed.add_field(name="Reminders", value="`!remindme` - Starts an interactive session to set a reminder.\n`!showreminders` - Shows all scheduled reminders.\n`!remove_reminder` - Lists reminders and allows you to choose one to remove.", inline=False)
    embed.add_field(name="Fun", value="`!8ball <question>` - Ask the Magic 8 Ball a question.\n`!echo <message>` - Repeats what you say and deletes your message.", inline=False)
    
    embed.set_footer(text="Use !help <command> for more details on a command.")

    await ctx.send(embed=embed)


@bot.command(name='queue', help='Displays the current music queue.')
async def queue_(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues:
        await ctx.send(f'Current queue: {[YTDLSource.data["title"] for url in queues[guild_id]]}')
    else:
        await ctx.send('The queue is currently empty.')

@bot.command(name='skip', help='Skips the current song being played.')
async def skip(ctx):
    ctx.voice_client.stop()
    check_queue(ctx, ctx.guild.id)

@bot.command(name='clear', help='Clears the current queue.')
async def clear(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues:
        queues[guild_id] = []
        await ctx.send('The queue has been cleared.')
    else:
        await ctx.send('The queue is already empty.')

@bot.command(name='join', help='Joins a voice channel')
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send("You are not connected to a voice channel.")
        return

    channel = ctx.message.author.voice.channel
    await channel.connect()

@bot.command(name='leave', help='Clears the queue and leaves the voice channel')
async def leave(ctx):
    if ctx.voice_client is None:
        await ctx.send("I'm not connected to a voice channel.")
    else:
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnected from the voice channel.")


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    logging.info("Bot has started and is ready.")
    bot.loop.create_task(check_reminders())

def log_bot_shutdown():
    logging.info("Bot is shutting down.")

atexit.register(log_bot_shutdown)


def log_unhandled_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = log_unhandled_exception

if __name__ == '__main__':
    try:
        bot.run(os.getenv('TOKEN'))
    except Exception as e:
        logging.critical("Bot crashed due to an unhandled exception.", exc_info=(type(e), e, e.__traceback__))
          