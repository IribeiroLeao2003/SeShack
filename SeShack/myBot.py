
import discord
import openai
from discord.ext import commands
from dotenv import load_dotenv
import os 
import asyncio
from datetime import datetime, timezone, timedelta 
import random
import sqlite3

load_dotenv()
token = os.getenv('TOKEN')
print(f"Loaded token: {token}")
reminders = []


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
    "What the fuck ?", 
    "Is Colvin Drinking again ?"
]

bot = commands.Bot(command_prefix='!', intents=intents)


def setup_database():
    conn = sqlite3.connect('reminders.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (id INTEGER PRIMARY KEY, time TEXT, message TEXT, channel_id INTEGER)''')
    conn.commit()
    conn.close()

setup_database()

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
        conn.close()  


@bot.command(name='test_reminder', help='Lists reminders from the database and lets you choose one to test.')
async def test_reminder(ctx):
    
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
    await ctx.send(test_reminder_message)



@bot.command(name='8ball', help='Ask the Magic 8 Ball a question.')
async def eight_ball(ctx, *, question: str):
   
    response = random.choice(eight_ball_answers)
    await ctx.send(f"🎱 {response}")

@bot.command(name='active', help='Lists active members in the server with their status.')
async def active(ctx):
    if isinstance(ctx.channel, discord.abc.GuildChannel):
        
        active_members_str = ""
        for member in ctx.guild.members:
            if not member.bot and member.status in (discord.Status.online, discord.Status.idle, discord.Status.dnd):
                status_emoji = ""
                if member.status == discord.Status.dnd:
                    status_emoji = "🔴"  # Red circle for Do Not Disturb
                elif member.status == discord.Status.idle:
                    status_emoji = "🟡"  # Yellow circle for Idle
                elif member.status == discord.Status.online:
                    status_emoji = "🟢"  # Green circle for Online
                
                active_members_str += f"{status_emoji} {member.display_name}\n"
        
        
        if active_members_str:
            
            if len(active_members_str) > 2000:
                for chunk in [active_members_str[i:i+2000] for i in range(0, len(active_members_str), 2000)]:
                    await ctx.send(chunk)
            else:
                await ctx.send(active_members_str)
        else:
            await ctx.send('No active members found.')
    else:
        await ctx.send('This command can only be used in a server.')



@bot.command(name='dayscharlie', help="Counts the days since the server was created and mentions Charlie.")
async def days_since_charlie(ctx):
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
        reminders_str = "Scheduled Reminders:\n"
        for reminder in reminders:
            time, message, channel_id = reminder
            channel = bot.get_channel(channel_id)
            channel_name = channel.name if channel else 'Deleted Channel'
            reminders_str += f"Time: {time}, Message: \"{message}\", Channel: #{channel_name}\n"
        
        
        for chunk in [reminders_str[i:i+2000] for i in range(0, len(reminders_str), 2000)]:
            await ctx.send(chunk)
    else:
        await ctx.send("No reminders scheduled.")

@bot.command(name='hello', help='Greets the user.')
async def hello(ctx):
    await ctx.send('Hello!')

@bot.command(name='remove_reminder', help='Lists reminders and allows you to choose one to remove.')
async def remove_reminder(ctx):
    
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



@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    
    bot.loop.create_task(check_reminders())




bot.run(os.getenv('TOKEN'))