"""
Discord Bot: ระบบส่งรูปหลักฐาน (Loop/Airdrop) เพื่อขอแต้ม
------------------------------------------------------------
วิธีทำงาน:
1. แอดมินตั้งค่ารายชื่อผู้เล่นทั้งหมดไว้ล่วงหน้าด้วย /setplayers (วางทีเดียวทั้งลิสต์) หรือ /addplayer (เพิ่มทีละคน)
2. ผู้เล่นพิมพ์ /submit เลือกกิจกรรม (Loop/Airdrop/BMK/Skyfall/BlackMarket) + แนบรูปภาพ + พิมพ์ชื่อผู้เล่นได้สูงสุด 10 ช่อง
   (แต่ละช่องพิมพ์บางส่วนของชื่อแล้วบอทจะเดาชื่อเต็มจากลิสต์ให้เลือกได้เลย เหมือนตอนใช้ /score)
3. บอทจะส่งข้อความ (embed) ไปที่ "ห้องตรวจสอบ" พร้อมปุ่ม อนุมัติ / ปฏิเสธ แสดงรายชื่อทั้งหมดที่กรอกมา
4. แอดมินกดปุ่มอนุมัติครั้งเดียว -> ระบบบวกแต้มให้ "ทุกชื่อ" ตามจำนวนแต้มของกิจกรรมนั้น
5. ใช้ /score เช็คแต้มของชื่อใดชื่อหนึ่ง, /leaderboard ดูอันดับ, /addscore ให้แอดมินปรับแต้มมือ

ข้อมูลถูกเก็บในไฟล์ data/scores.json (ไม่ต้องใช้ฐานข้อมูลภายนอก)
"""

import os
import json
import uuid
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "")  # เว้นว่างได้ ถ้าจะใช้แค่สิทธิ์ Manage Server

# ห้องตรวจสอบแยกตามกิจกรรม ตั้งค่า ID ห้องของแต่ละกิจกรรมใน .env
ACTIVITY_CHANNELS = {
    "Loop": int(os.getenv("REVIEW_CHANNEL_LOOP", "0")),
    "Airdrop": int(os.getenv("REVIEW_CHANNEL_AIRDROP", "0")),
    "BMK": int(os.getenv("REVIEW_CHANNEL_BMK", "0")),
    "Skyfall": int(os.getenv("REVIEW_CHANNEL_SKYFALL", "0")),
    "BlackMarket": int(os.getenv("REVIEW_CHANNEL_BLACKMARKET", "0")),
}

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "scores.json")

os.makedirs(DATA_DIR, exist_ok=True)

# แต้มที่ได้ต่อกิจกรรม (ปรับตัวเลขตรงนี้ได้ตามต้องการ)
ACTIVITY_POINTS = {
    "Loop": 1,
    "Airdrop": 3,
    "BMK": 2,
    "Skyfall": 2,
    "BlackMarket": 2,
}

# รายชื่อเริ่มต้น ใช้ตอนยังไม่เคยมีไฟล์ data มาก่อน (แก้/เพิ่ม/ลบทีหลังได้ด้วย /setplayers, /addplayer, /renameplayer)
DEFAULT_PLAYERS = sorted([
    "Mayom Sync",
    "Highflex Diff",
    "Kim Stylepro",
    "Jingjing Hydra",
    "Lufer DOO",
    "Isawyouhappy Seqt",
    "Kamil Semipro",
    "Taro Young",
    "Park Justletmeknow",
    "ZynX Stark",
    "NamChai LBkazo",
    "Marin Cassano",
    "Ped Dieharrd",
    "Korn Sentai",
    "Perk Justletmeknow",
    "NongkaKidofrap Nowaja",
    "Adas Add",
    "Untouchable One",
    "Haider Dara",
    "Yumi Missyu",
    "Tatar Young",
    "iPhone Samsung",
])

# ---------- โหลด / บันทึกข้อมูล ----------

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"scores": {}, "pending": {}, "players": list(DEFAULT_PLAYERS)}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        loaded = json.load(f)
        loaded.setdefault("players", [])  # เผื่อไฟล์เก่าที่ยังไม่มีลิสต์ผู้เล่น
        return loaded

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

# ---------- ตรวจสิทธิ์แอดมิน ----------

def is_admin(member: discord.Member) -> bool:
    if member.guild_permissions.manage_guild:
        return True
    if ADMIN_ROLE_NAME:
        return any(role.name == ADMIN_ROLE_NAME for role in member.roles)
    return False

# ---------- ตั้งค่าบอท ----------

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

class SetPlayersModal(discord.ui.Modal, title="ตั้งรายชื่อผู้เล่นทั้งหมด"):
    names_input = discord.ui.TextInput(
        label="รายชื่อผู้เล่น (1 บรรทัดต่อ 1 ชื่อ)",
        style=discord.TextStyle.paragraph,
        placeholder="Pream Blessedfinals\nMayom Sync\nHighflex Diff\n...",
        required=True,
        max_length=4000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        lines = [line.strip() for line in self.names_input.value.splitlines()]
        new_roster = sorted({line for line in lines if line})  # ตัดบรรทัดว่างและชื่อซ้ำออก

        data["players"] = new_roster
        save_data(data)

        await interaction.response.send_message(
            f"✅ ตั้งรายชื่อผู้เล่นใหม่เรียบร้อย ทั้งหมด **{len(new_roster)} คน**\n"
            + "\n".join(f"• {n}" for n in new_roster),
            ephemeral=True,
        )

# ---------- View ปุ่มอนุมัติ/ปฏิเสธ ----------

class ApprovalView(discord.ui.View):
    def __init__(self, submission_id: str):
        super().__init__(timeout=None)  # timeout=None = ปุ่มไม่หมดอายุ ใช้งานได้แม้บอทรีสตาร์ท
        self.submission_id = submission_id

        approve_btn = discord.ui.Button(
            label="อนุมัติ",
            style=discord.ButtonStyle.success,
            emoji="✅",
            custom_id=f"approve:{submission_id}",
        )
        reject_btn = discord.ui.Button(
            label="ปฏิเสธ",
            style=discord.ButtonStyle.danger,
            emoji="❌",
            custom_id=f"reject:{submission_id}",
        )
        approve_btn.callback = self.on_approve
        reject_btn.callback = self.on_reject
        self.add_item(approve_btn)
        self.add_item(reject_btn)

    async def _check_admin(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member) or not is_admin(interaction.user):
            await interaction.response.send_message(
                "❌ คุณไม่มีสิทธิ์อนุมัติ/ปฏิเสธรายการนี้", ephemeral=True
            )
            return False
        return True

    async def on_approve(self, interaction: discord.Interaction):
        if not await self._check_admin(interaction):
            return

        submission = data["pending"].get(self.submission_id)
        if submission is None:
            await interaction.response.send_message("รายการนี้ถูกดำเนินการไปแล้ว", ephemeral=True)
            return

        names = submission["names"]
        points = ACTIVITY_POINTS.get(submission.get("activity", ""), 1)
        summary_parts = []
        for name in names:
            data["scores"][name] = data["scores"].get(name, 0) + points
            summary_parts.append(f"{name}: {data['scores'][name]}")
        del data["pending"][self.submission_id]
        save_data(data)

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.set_footer(
            text=f"✅ อนุมัติโดย {interaction.user.display_name} (+{points} แต้ม/คน) | แต้มรวมล่าสุด: " + ", ".join(summary_parts)
        )
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_reject(self, interaction: discord.Interaction):
        if not await self._check_admin(interaction):
            return

        submission = data["pending"].get(self.submission_id)
        if submission is None:
            await interaction.response.send_message("รายการนี้ถูกดำเนินการไปแล้ว", ephemeral=True)
            return

        del data["pending"][self.submission_id]
        save_data(data)

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.set_footer(text=f"❌ ปฏิเสธโดย {interaction.user.display_name}")
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

# ---------- Events ----------

@bot.event
async def on_ready():
    # โหลดปุ่มของรายการที่ยังค้างอยู่กลับมา เผื่อบอทเพิ่งรีสตาร์ท
    for submission_id in list(data["pending"].keys()):
        bot.add_view(ApprovalView(submission_id))

    try:
        synced = await bot.tree.sync()
        print(f"ซิงค์คำสั่งสำเร็จ {len(synced)} คำสั่ง")
    except Exception as e:
        print(f"ซิงค์คำสั่งล้มเหลว: {e}")

    print(f"บอทออนไลน์แล้วในชื่อ {bot.user}")

# ---------- Slash Commands ----------

async def player_name_autocomplete(interaction: discord.Interaction, current: str):
    """ให้พิมพ์บางส่วนของชื่อแล้วบอทเดาชื่อเต็มจากลิสต์ผู้เล่นให้ (ช่วยหาชื่อตัวเองได้ง่ายขึ้น)"""
    current_lower = current.lower()
    matches = [p for p in data["players"] if current_lower in p.lower()]
    return [app_commands.Choice(name=p, value=p) for p in matches[:25]]

@bot.tree.command(name="submit", description="ส่งรูปหลักฐานเพื่อขอแต้ม (พิมพ์ชื่อแล้วเลือกจากที่ระบบเดาให้ได้ สูงสุด 10 คน)")
@app_commands.describe(
    activity="กิจกรรมที่เล่น",
    image="รูปแคปหน้าจอหลักฐาน",
    name1="ผู้เล่นคนที่ 1 (จำเป็น) พิมพ์บางส่วนแล้วเลือกจากลิสต์ที่ขึ้นมา",
    name2="ผู้เล่นคนที่ 2 (ถ้ามี)",
    name3="ผู้เล่นคนที่ 3 (ถ้ามี)",
    name4="ผู้เล่นคนที่ 4 (ถ้ามี)",
    name5="ผู้เล่นคนที่ 5 (ถ้ามี)",
    name6="ผู้เล่นคนที่ 6 (ถ้ามี)",
    name7="ผู้เล่นคนที่ 7 (ถ้ามี)",
    name8="ผู้เล่นคนที่ 8 (ถ้ามี)",
    name9="ผู้เล่นคนที่ 9 (ถ้ามี)",
    name10="ผู้เล่นคนที่ 10 (ถ้ามี)",
)
@app_commands.choices(activity=[
    app_commands.Choice(name="Loop", value="Loop"),
    app_commands.Choice(name="Airdrop", value="Airdrop"),
    app_commands.Choice(name="BMK", value="BMK"),
    app_commands.Choice(name="Skyfall", value="Skyfall"),
    app_commands.Choice(name="BlackMarket", value="BlackMarket"),
])
@app_commands.autocomplete(
    name1=player_name_autocomplete,
    name2=player_name_autocomplete,
    name3=player_name_autocomplete,
    name4=player_name_autocomplete,
    name5=player_name_autocomplete,
    name6=player_name_autocomplete,
    name7=player_name_autocomplete,
    name8=player_name_autocomplete,
    name9=player_name_autocomplete,
    name10=player_name_autocomplete,
)
async def submit(
    interaction: discord.Interaction,
    activity: app_commands.Choice[str],
    image: discord.Attachment,
    name1: str,
    name2: str = None,
    name3: str = None,
    name4: str = None,
    name5: str = None,
    name6: str = None,
    name7: str = None,
    name8: str = None,
    name9: str = None,
    name10: str = None,
):
    channel_id = ACTIVITY_CHANNELS.get(activity.value, 0)
    if channel_id == 0:
        await interaction.response.send_message(
            f"⚠️ ยังไม่ได้ตั้งค่าห้องตรวจสอบสำหรับกิจกรรม **{activity.value}** กรุณาแจ้งแอดมิน", ephemeral=True
        )
        return

    if not image.content_type or not image.content_type.startswith("image/"):
        await interaction.response.send_message("กรุณาแนบไฟล์รูปภาพเท่านั้น", ephemeral=True)
        return

    review_channel = bot.get_channel(channel_id)
    if review_channel is None:
        await interaction.response.send_message(
            f"⚠️ หาห้องตรวจสอบของกิจกรรม **{activity.value}** ไม่เจอ กรุณาแจ้งแอดมิน", ephemeral=True
        )
        return

    raw_names = [name1, name2, name3, name4, name5, name6, name7, name8, name9, name10]
    names = [n.strip() for n in raw_names if n and n.strip()]

    submission_id = str(uuid.uuid4())[:8]
    points = ACTIVITY_POINTS.get(activity.value, 1)
    names_display = "\n".join(f"• {n}" for n in names)

    embed = discord.Embed(
        title="📸 มีการส่งหลักฐานใหม่",
        description=(
            f"**กิจกรรม:** {activity.value} (+{points} แต้ม/คน)\n"
            f"**ผู้เล่น ({len(names)} คน):**\n{names_display}\n"
            f"**ผู้ส่ง:** {interaction.user.mention}"
        ),
        color=discord.Color.orange(),
    )
    embed.set_image(url=image.url)
    embed.set_footer(text="รอการตรวจสอบจากแอดมิน")

    view = ApprovalView(submission_id)
    msg = await review_channel.send(embed=embed, view=view)

    data["pending"][submission_id] = {
        "names": names,
        "activity": activity.value,
        "submitter_id": interaction.user.id,
        "message_id": msg.id,
        "channel_id": review_channel.id,
    }
    save_data(data)

    await interaction.response.send_message(
        f"✅ ส่งหลักฐาน **{activity.value}** (+{points} แต้ม/คน) ของ {', '.join(names)} เรียบร้อย รอแอดมินตรวจสอบก่อนได้แต้มนะครับ",
        ephemeral=True,
    )

@bot.tree.command(name="setplayers", description="[แอดมิน] ตั้งรายชื่อผู้เล่นทั้งหมดทีเดียว (วางทั้งลิสต์ในกล่องข้อความ)")
async def setplayers(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not is_admin(interaction.user):
        await interaction.response.send_message("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมิน", ephemeral=True)
        return

    modal = SetPlayersModal()
    # เติมรายชื่อปัจจุบันไว้ในกล่อง เผื่ออยากแก้ต่อจากของเดิมแทนที่จะพิมพ์ใหม่หมด
    if data["players"]:
        modal.names_input.default = "\n".join(data["players"])
    await interaction.response.send_modal(modal)

@bot.tree.command(name="addplayer", description="[แอดมิน] เพิ่มชื่อผู้เล่นเข้าลิสต์ให้เลือกตอน /submit")
@app_commands.describe(name="ชื่อผู้เล่นที่จะเพิ่ม")
async def addplayer(interaction: discord.Interaction, name: str):
    if not isinstance(interaction.user, discord.Member) or not is_admin(interaction.user):
        await interaction.response.send_message("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมิน", ephemeral=True)
        return

    name = name.strip()
    if name in data["players"]:
        await interaction.response.send_message(f"⚠️ มีชื่อ **{name}** อยู่ในลิสต์แล้ว", ephemeral=True)
        return

    data["players"].append(name)
    data["players"].sort()
    save_data(data)
    await interaction.response.send_message(
        f"✅ เพิ่ม **{name}** เข้าลิสต์แล้ว (ตอนนี้มีทั้งหมด {len(data['players'])} คน)"
    )

@bot.tree.command(name="removeplayer", description="[แอดมิน] ลบชื่อผู้เล่นออกจากลิสต์")
@app_commands.describe(name="ชื่อผู้เล่นที่จะลบ")
@app_commands.autocomplete(name=player_name_autocomplete)
async def removeplayer(interaction: discord.Interaction, name: str):
    if not isinstance(interaction.user, discord.Member) or not is_admin(interaction.user):
        await interaction.response.send_message("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมิน", ephemeral=True)
        return

    name = name.strip()
    if name not in data["players"]:
        await interaction.response.send_message(f"⚠️ ไม่พบชื่อ **{name}** ในลิสต์", ephemeral=True)
        return

    data["players"].remove(name)
    save_data(data)
    await interaction.response.send_message(f"✅ ลบ **{name}** ออกจากลิสต์แล้ว")

@bot.tree.command(name="renameplayer", description="[แอดมิน] เปลี่ยนชื่อผู้เล่น (เช่น เปลี่ยนจาก 'คนที่1' เป็นชื่อจริง) โดยแต้มเดิมยังอยู่")
@app_commands.describe(old_name="ชื่อเดิมที่จะเปลี่ยน", new_name="ชื่อใหม่ที่ต้องการ")
@app_commands.autocomplete(old_name=player_name_autocomplete)
async def renameplayer(interaction: discord.Interaction, old_name: str, new_name: str):
    if not isinstance(interaction.user, discord.Member) or not is_admin(interaction.user):
        await interaction.response.send_message("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมิน", ephemeral=True)
        return

    old_name = old_name.strip()
    new_name = new_name.strip()

    if old_name not in data["players"]:
        await interaction.response.send_message(f"⚠️ ไม่พบชื่อ **{old_name}** ในลิสต์", ephemeral=True)
        return

    # เปลี่ยนชื่อในลิสต์ผู้เล่น
    idx = data["players"].index(old_name)
    data["players"][idx] = new_name
    data["players"].sort()

    # ย้ายแต้มสะสมจากชื่อเดิมไปชื่อใหม่ (รวมกับแต้มที่มีอยู่แล้วถ้าชื่อใหม่มีอยู่ก่อน)
    old_points = data["scores"].pop(old_name, 0)
    if old_points:
        data["scores"][new_name] = data["scores"].get(new_name, 0) + old_points

    save_data(data)
    await interaction.response.send_message(
        f"✅ เปลี่ยนชื่อ **{old_name}** เป็น **{new_name}** เรียบร้อย (แต้มสะสม {data['scores'].get(new_name, 0)} แต้ม ยังอยู่ครบ)"
    )

@bot.tree.command(name="players", description="ดูรายชื่อผู้เล่นทั้งหมดที่เลือกได้ตอน /submit")
async def players(interaction: discord.Interaction):
    if not data["players"]:
        await interaction.response.send_message("ยังไม่มีรายชื่อผู้เล่นในระบบเลยครับ")
        return

    lines = "\n".join(f"• {n}" for n in data["players"])
    embed = discord.Embed(
        title=f"📋 รายชื่อผู้เล่นทั้งหมด ({len(data['players'])} คน)",
        description=lines,
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="score", description="เช็คแต้มของผู้เล่น")
@app_commands.describe(name="ชื่อผู้เล่นที่ต้องการเช็ค (พิมพ์บางส่วนแล้วเลือกจากลิสต์ที่ขึ้นมาได้)")
@app_commands.autocomplete(name=player_name_autocomplete)
async def score(interaction: discord.Interaction, name: str):
    points = data["scores"].get(name, 0)
    await interaction.response.send_message(f"🏆 **{name}** มีแต้มสะสม **{points}** แต้ม")

@bot.tree.command(name="leaderboard", description="ดูอันดับแต้มสูงสุด")
async def leaderboard(interaction: discord.Interaction):
    if not data["scores"]:
        await interaction.response.send_message("ยังไม่มีข้อมูลแต้มเลยครับ")
        return

    ranked = sorted(data["scores"].items(), key=lambda x: x[1], reverse=True)[:10]
    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, (name, pts) in enumerate(ranked):
        prefix = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{prefix} **{name}** — {pts} แต้ม")

    embed = discord.Embed(
        title="🏆 อันดับแต้มสูงสุด",
        description="\n".join(lines),
        color=discord.Color.gold(),
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="addscore", description="[แอดมิน] เพิ่ม/ลดแต้มให้ผู้เล่นด้วยตัวเอง")
@app_commands.describe(name="ชื่อผู้เล่น", amount="จำนวนแต้มที่จะเพิ่ม (ใส่ติดลบเพื่อลด)")
@app_commands.autocomplete(name=player_name_autocomplete)
async def addscore(interaction: discord.Interaction, name: str, amount: int):
    if not isinstance(interaction.user, discord.Member) or not is_admin(interaction.user):
        await interaction.response.send_message("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมิน", ephemeral=True)
        return

    data["scores"][name] = data["scores"].get(name, 0) + amount
    save_data(data)
    await interaction.response.send_message(
        f"ปรับแต้มของ **{name}** เรียบร้อย ตอนนี้มี **{data['scores'][name]}** แต้ม"
    )

# ---------- Run ----------

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("กรุณาตั้งค่า DISCORD_TOKEN ในไฟล์ .env ก่อนรันบอท")
    bot.run(TOKEN)
