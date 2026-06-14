import sys
import asyncio
import random
import discord
import os
from discord.ext import commands
from fastapi import FastAPI
import uvicorn

# ─── 1. 建立 FastAPI 網頁伺服器 ───
app = FastAPI()

@app.get("/")
async def home():
    return {"status": "🤖 誰是臥底機器人 24 暢通運作中！"}

# ─── 2. Discord 機器人基本設定 ───
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

games = {}

WORD_BANK = [
    {"civilian": "珍珠奶茶", "undercover": "燕麥奶茶"},
    {"civilian": "麥當勞", "undercover": "肯德基"},
    {"civilian": "微積分", "undercover": "工程數學"},
    {"civilian": "周杰倫", "undercover": "王力宏"}
]

def get_game_state(guild_id):
    if guild_id not in games:
        games[guild_id] = {
            "is_active": False,
            "players": [],
            "words": {},
            "identities": {},
            "undercover_id": None,
            "voted_users": {}
        }
    return games[guild_id]

def reset_all_game(guild_id):
    if guild_id in games:
        del games[guild_id]

@bot.event
async def on_ready():
    print(f'🤖 誰是臥底主機已連線：{bot.user.name}')

@bot.command(name="報名")
async def sign_up(ctx):
    game = get_game_state(ctx.guild.id)
    if game["is_active"]:
        await ctx.send("⚠️ 遊戲正在進行，請稍候。")
        return
    if ctx.author in game["players"]:
        await ctx.send(f"❓ {ctx.author.mention} 你已經報名過囉！")
        return
    game["players"].append(ctx.author)
    await ctx.send(f"✅ {ctx.author.mention} 報名成功！目前人數：{len(game['players'])} 人")

@bot.command(name="開局")
async def start_game(ctx):
    game = get_game_state(ctx.guild.id)
    if game["is_active"]: return
    if len(game["players"]) < 3:
        await ctx.send(f"❌ 人數不足 3 人！(目前：{len(game['players'])}人)")
        return

    game["is_active"] = True
    game["voted_users"].clear()
    await ctx.send("🎲 **發牌中！請確認 Discord「私訊」！**")

    selected_pair = random.choice(WORD_BANK)
    undercover_player = random.choice(game["players"])
    game["undercover_id"] = undercover_player.id

    for player in game["players"]:
        if player.id == game["undercover_id"]:
            game["identities"][player.id] = "臥底"
            game["words"][player.id] = selected_pair["undercover"]
        else:
            game["identities"][player.id] = "平民"
            game["words"][player.id] = selected_pair["civilian"]
        try:
            await player.send(f"🤫 【神祕詞彙】這一局你拿到的是：**【 {game['words'][player.id]} 】**")
        except discord.Forbidden:
            await ctx.send(f"⚠️ 無法私訊給 {player.mention}！")

    names = "、".join([p.display_name for p in game["players"]])
    await ctx.send(f"🏁 **遊戲開始！**\n參賽者：{names}\n請輪流發言，投票請用 `!投 @同學`")

@bot.command(name="投")
async def vote_player(ctx, member: discord.Member = None):
    game = get_game_state(ctx.guild.id)
    if not game["is_active"] or ctx.author not in game["players"]: return
    if not member or member not in game["players"]:
        await ctx.send("❌ 請標記在場存活玩家！")
        return

    game["voted_users"][ctx.author.id] = member.id
    await ctx.send(f"🗳️ {ctx.author.mention} 已投票！ ({len(game['voted_users'])}/{len(game['players'])})")

    if len(game["voted_users"]) >= len(game["players"]):
        await ctx.send("🔔 **投票結束！系統計票中...**")
        await asyncio.sleep(1.5)

        vote_counts = {}
        for target_id in game["voted_users"].values():
            vote_counts[target_id] = vote_counts.get(target_id, 0) + 1

        highest_voted_id = max(vote_counts, key=vote_counts.get)
        eliminated = ctx.guild.get_member(highest_voted_id)

        await ctx.send(f"🪓 **{eliminated.display_name}** 獲得最高票，慘遭淘汰！")
        await check_win_condition(ctx, eliminated)

async def check_win_condition(ctx, eliminated):
    game = get_game_state(ctx.guild.id)
    if eliminated.id == game["undercover_id"]:
        await ctx.send(f"🎉 **【平民獲勝！】** 成功抓出臥底！")
        reset_all_game(ctx.guild.id)
        return

    game["players"].remove(eliminated)
    game["voted_users"].clear()
    
    if len(game["players"]) <= 2:
        undercover_mem = ctx.guild.get_member(game["undercover_id"])
        await ctx.send(f"😈 **【臥底獲勝！】** 臥底 {undercover_mem.mention} 活到了最後！")
        reset_all_game(ctx.guild.id)
    else:
        alive_names = "、".join([p.display_name for p in game["players"]])
        await ctx.send(f"⏳ 遊戲繼續！剩餘存活者：**{alive_names}**\n請開始下一輪投票。")

@bot.command(name="重置")
async def force_stop(ctx):
    reset_all_game(ctx.guild.id)
    await ctx.send("⏹️ 遊戲資料庫已清空重置。")

# ─── 3. 終極核心：用同一個異步事件循環啟動兩者 ───
async def main():
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ 錯誤：找不到環境變數 DISCORD_TOKEN")
        return

    # 設定 Uvicorn 網頁伺服器配置
    config = uvicorn.Config(app, host="0.0.0.0", port=10000, log_level="info")
    server = uvicorn.Server(config)

    # 同時併發運行：網頁伺服器 與 Discord 機器人
    await asyncio.gather(
        server.serve(),
        bot.start(TOKEN)
    )

if __name__ == "__main__":
    asyncio.run(main())
