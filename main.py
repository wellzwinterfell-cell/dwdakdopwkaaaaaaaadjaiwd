import nextcord, json, requests, re
from nextcord.ext import commands
import os
from dotenv import load_dotenv
import datetime
from nextcord import Embed, Color
import asyncio
from myserver import server_on


# โหลดค่าจากไฟล์ .env เข้าสู่ Environment Variables
load_dotenv()

bot, config = commands.Bot(command_prefix='flexzy!',help_command=None,intents=nextcord.Intents.all()), json.load(open('./config.json', 'r', encoding='utf-8'))



class MyEmbed(Embed):
    def __init__(self, userId: int, amount: str, roleid: str, typepay: int):
        super().__init__(
            description=                                f" **ขอบคุณที่ใช้บริการ yokfreeforyou** 💖\n\n"
                                f"👤 **ลูกค้า:** <@{userId}>\n"
                                f"⭐ **ยอดชำระ:** `{amount}` บาท\n"
                                f"🎁 **ได้รับยศ:** <@&{roleid}>\n\n"
                                f"อย่าลืมเช็คยศและสิทธิพิเศษของท่านที่ห้อง <#{config.get('roleCheckChannelId', '1269697650849091624')}> นะคะ!\n"
                                f"ขอให้มีความสุขกับคอนเทนต์สุดพิเศษจากเราค่ะ ✨"
        )
        self.color = 0x12ff00
        user = bot.get_user(int(userId))
        if user and user.avatar:
                self.set_thumbnail(url=user.avatar.url)

# --- UI Components สำหรับระบบเลือกยศ ---
class RoleSelect(nextcord.ui.Select):
    def __init__(self, eligible_roles, amount):
        options = [
            nextcord.SelectOption(label=role.name, description=f"เลือกเพื่อรับยศนี้", value=str(role.id))
            for role in eligible_roles
        ]
        super().__init__(placeholder="กรุณาเลือกยศที่ท่านต้องการ", min_values=1, max_values=1, options=options)
        self.amount = amount

    async def callback(self, interaction: nextcord.Interaction):
        await interaction.response.defer()
        selected_role_id = int(self.values[0])
        role_to_add = interaction.guild.get_role(selected_role_id)

        if role_to_add:
            await interaction.user.add_roles(role_to_add)
            # ปิด View เดิมและส่งข้อความยืนยันใหม่
            await interaction.edit_original_message(content=f"✅ **รับยศ `{role_to_add.name}` สำเร็จ!** ขอบคุณที่สนับสนุน **yokfreeforyou** นะคะ", view=None)
            await bot.get_channel(int(config['channelLog'])).send(embed=MyEmbed(interaction.user.id, self.amount, role_to_add.id, "ซองอั๋งเป๋า"))
        else:
            await interaction.edit_original_message(content="❌ เกิดข้อผิดพลาด: ไม่พบยศที่ท่านเลือก", view=None)

class RoleSelectView(nextcord.ui.View):
    def __init__(self, eligible_roles, amount, timeout=180):
        super().__init__(timeout=timeout)
        self.add_item(RoleSelect(eligible_roles, amount))

class BuyModal(nextcord.ui.Modal) :

   def __init__(self):
        super().__init__('กรอกลิ้งค์อั่งเปาของท่าน')
        self.a = nextcord.ui.TextInput(
            label = 'Truemoney Wallet Angpao',
            placeholder = 'https://gift.truemoney.com/campaign/?v=xxxxxxxxxxxxxxx',
            style = nextcord.TextInputStyle.short,
            required = True
        )
        self.add_item(self.a)

   async def callback(self, interaction: nextcord.Interaction):
        await interaction.response.defer(ephemeral=True)
        raw_input = str(self.a.value).strip()

        # --- ระบบเงินเทสสำหรับ Owner ---
        if raw_input.lower().startswith('test ') and str(interaction.user.id) == str(config['ownerId']):
            try:
                # ดึงจำนวนเงินจากคำสั่ง เช่น "test 99" -> 99
                test_amount = int(raw_input.split(' ')[1])
                roles_added = []
                
                # ค้นหายศที่ตรงกับราคา
                for roleData in config['roleSettings']:
                    if (test_amount == roleData['price']):
                        role = nextcord.utils.get(interaction.user.guild.roles, id=int(roleData['roleId']))
                        if role:
                            await interaction.user.add_roles(role)
                            roles_added.append(role)
                if roles_added:
                    await interaction.followup.send(content=f"✅ **[TEST MODE]** รับยศสำเร็จ!", ephemeral=True)
                    for role in roles_added:
                        await bot.get_channel(int(config['channelLog'])).send(embed=MyEmbed(interaction.user.id, test_amount, role.id, "เงินเทส"))
                        return
                await interaction.followup.send(content=f"⚠️ **[TEST MODE]** ไม่พบยศที่ตรงกับจำนวนเงิน `{test_amount}` บาท", ephemeral=True)
                return
            except (IndexError, ValueError):
                await interaction.followup.send(content="⚠️ **[TEST MODE]** รูปแบบคำสั่งไม่ถูกต้อง! กรุณาใช้ `test <จำนวนเงิน>` เช่น `test 99`", ephemeral=True)
                return

        link = raw_input.replace(' ', '')
        # Extract voucher code from the URL
        match = re.search(r'v=([a-zA-Z0-9]+)', link)
        if not match:
            await interaction.followup.send(content="⚠️ **รูปแบบลิงก์อั่งเปาไม่ถูกต้อง**\nกรุณาตรวจสอบและใช้ลิงก์ที่ถูกต้อง เช่น `https://gift.truemoney.com/campaign/?v=...`", ephemeral=True)
            return
        
        voucher_code = match.group(1)
        data = {
            'phone': config['phone'],
            'gift': voucher_code
        }
        headers = {
            'Content-Type': 'application/json'  
        }
        try:
            res = requests.post("https://api.mystrix2.me/truemoney", json=data, headers=headers)
            res.raise_for_status()  
        except requests.RequestException as e:
            # Handle non-2xx responses that raise_for_status() catches, like 404 or 500
            try:
                error_data = res.json()
                message = error_data.get('redeemResponse', {}).get('status', {}).get('message', f'API Error: {res.status_code}')
            except (json.JSONDecodeError, AttributeError):
                message = f'เกิดข้อผิดพลาดในการเชื่อมต่อ: {str(e)}'
            embed = nextcord.Embed(description=message, color=nextcord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        response_data = res.json()

        if res.status_code == 200 and 'data' in response_data:
            amount = float(response_data['data']['voucher']['amount_baht'])
            amount = int(amount)
            
            # ค้นหายศทั้งหมดที่ตรงกับราคา
            eligible_roles = []
            for roleData in config['roleSettings']:
                if (amount == roleData['price']):
                    role = nextcord.utils.get(interaction.user.guild.roles, id=int(roleData['roleId']))
                    if role:
                        eligible_roles.append(role)

            if len(eligible_roles) == 1:
                # กรณีมียศเดียว: ให้ยศอัตโนมัติ
                role_to_add = eligible_roles[0]
                await interaction.user.add_roles(role_to_add)
                await interaction.followup.send(content=f"✅ **รับยศสำเร็จ!** ขอบคุณที่สนับสนุน **yokfreeforyou** นะคะ <@{interaction.user.id}> สามารถตรวจสอบรายละเอียดได้ที่ <#{config['channelLog']}> ค่ะ", ephemeral=True)
                await bot.get_channel(int(config['channelLog'])).send(embed=MyEmbed(interaction.user.id, amount, role_to_add.id, "ซองอั๋งเป๋า"))
            elif len(eligible_roles) > 1:
                # กรณีมีหลายยศ: แสดงเมนูให้เลือก
                await interaction.followup.send(f"ยอดเงินของคุณ `{amount}` บาท สามารถเลือกรับยศได้ดังนี้:", view=RoleSelectView(eligible_roles, amount), ephemeral=True)
            else:
                # กรณีไม่มียศตรงกับราคา
                await interaction.followup.send(content=f"⚠️ **ไม่พบยศที่ตรงกับจำนวนเงิน**\nยอดของคุณคือ `{amount}` บาท กรุณาตรวจสอบราคายศและลองใหม่อีกครั้งนะคะ", ephemeral=True)
        else:
            message = response_data.get('redeemResponse', {}).get('status', {}).get('message', 'มีบางอย่างผิดพลาด กรุณาติดต่อแอดมินค่ะ')
            await interaction.followup.send(content=message, ephemeral=True)






class BuyView(nextcord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(nextcord.ui.Button(style=nextcord.ButtonStyle.link, label="ติดต่อ",emoji="<:staffnextcord:1227211076706369606>", url="https://discord.com/channels/1267373078477017199/1269697646482690087"))

    @nextcord.ui.button(label='🧧︲ เติมเงิน', custom_id='buyRole', style=nextcord.ButtonStyle.blurple)
    async def buyRole(self, button: nextcord.Button, interaction: nextcord.Interaction):
        await interaction.response.send_modal(BuyModal())

    @nextcord.ui.button(label='︲ราคายศทั้งหมด',emoji="🛒", custom_id='priceRole', style=nextcord.ButtonStyle.green)
    async def priceRole(self, button: nextcord.Button, interaction: nextcord.Interaction):
        description = ''
        for roleData in config['roleSettings']:
            description += f'💎 เติมเงิน **{roleData["price"]} บาท** รับยศสุดพิเศษ\n 𓆩⟡𓆪  <@&{roleData["roleId"]}> 🎁   \n₊✧────────────────✧₊∘\n'
        embed = nextcord.Embed(
            title='✨เรทราคายศสุดคุ้มจาก yokfreeforyou✨',
            color=nextcord.Color.from_rgb(93, 176, 242),
            description=f"เลือกแพ็คเกจที่ใช่ แล้วไปสนุกกับคอนเทนต์สุด Exclusive ได้เลย!\n\n{description}"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class setupView(nextcord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @nextcord.ui.button(label='︲เซฟยศ',
                        emoji="<a:botsever60:1184927829893337158>",
                        custom_id='market12',
                        style=nextcord.ButtonStyle.gray,
                        row=2)
    async def market12(self, button: nextcord.Button,
                        interaction: nextcord.Interaction):
                user = interaction.user
                role_data = [role.name for role in user.roles if "@everyone" not in role.name]
                file_path = f"saveroles/role_{user.id}.json" # FIX: Use user.id instead of user.name

                # Ensure the 'saveroles' directory exists
                os.makedirs("saveroles", exist_ok=True)

                try:
                    with open(file_path, "w", encoding='utf-8') as f:
                        json.dump(role_data, f)
                except Exception as e:
                    print(f"Error saving roles: {e}")
                    await interaction.response.send_message("An error occurred while saving roles.", ephemeral=True)
                    return
                embed = nextcord.Embed(title="💾 บันทึกข้อมูลยศสำเร็จ 💾", color=0xdddddd)
                # FIX: set_author was called twice. The second one is more descriptive.
                if user.avatar:
                    embed.set_author(name="yokfreeforyou | ระบบสำรองข้อมูลอัตโนมัติ", url="", icon_url=user.avatar.url)
                else:
                    embed.set_author(name="yokfreeforyou | ระบบสำรองข้อมูลอัตโนมัติ", url="", icon_url=interaction.guild.icon.url)
                embed.set_footer(icon_url=None, text=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                if interaction.user.avatar:
                        embed.set_thumbnail(url=interaction.user.avatar.url)
                formatted_roles = "\n".join(role_data)
                embed.add_field(name="ยศที่เชฟเสร็จสิ้น", value=f"```\n{formatted_roles}```", inline=False)
                await interaction.response.send_message(embed=embed, ephemeral=True)

            

    @nextcord.ui.button(label='︲รับยศคืน',
                        emoji="<a:botsever59:1184912878189416549>",
                        custom_id='market13',
                        style=nextcord.ButtonStyle.green,
                        row=2)
    async def market13(self, button: nextcord.Button,
                        interaction: nextcord.Interaction):
        user = interaction.user
        file_path = f"saveroles/role_{user.id}.json" # FIX: Use user.id instead of user.name
        try:
            with open(file_path, "r", encoding='utf-8') as f:
                role_data = json.load(f)
                for role_name in role_data:
                    roles = nextcord.utils.get(interaction.guild.roles, name=role_name)
                    if roles: # Check if role still exists before trying to add
                        await user.add_roles(roles)
            await interaction.response.send_message("```diff\n+ คืนยศทั้งหมดให้คุณเรียบร้อยแล้วค่ะ ยินดีต้อนรับกลับสู่ yokfreeforyou นะคะ\n```", ephemeral=True)
        except FileNotFoundError:
            await interaction.response.send_message("```diff\n- ขออภัยค่ะ ไม่พบข้อมูลการสำรองยศของคุณในระบบ\n```", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"```diff\n- เกิดข้อผิดพลาดบางอย่าง: {e}\n```", ephemeral=True)
@bot.event
async def on_ready():
    bot.add_view(BuyView())
    bot.add_view(setupView())
    print(f"""          LOGIN AS: {bot.user}
    Successfully reloaded application [/] commands.""")


 
@bot.slash_command(name='setup',description='✨ ติดตั้งระบบขายยศ')
async def setup(interaction: nextcord.Interaction):
    if (int(interaction.user.id) == int(config['ownerId'])):
        await interaction.channel.send(embed=nextcord.Embed(
            title=f'💖 ยินดีต้อนรับสู่ yokfreeforyou 💖',
            description='> 🪷 **ระบบซื้อยศอัตโนมัติ 24 ชั่วโมง** ✨\n\n```diff\n+ กดปุ่ม "🧧︲ เติมเงิน" เพื่อเริ่มต้นการสั่งซื้อ\n```\n```diff\n- กดปุ่ม "🛒︲ราคายศทั้งหมด" เพื่อดูแพ็คเกจสุดคุ้ม\n```\n> `รับยศเข้าตัวทันทีหลังชำระเงินสำเร็จ!` 🔞',
            color=nextcord.Color.green(),
        ).set_thumbnail(url=interaction.guild.icon.url)
        .set_footer(text=f"yokfreeforyou | คอมมูนิตี้ Vip ที่ดีที่สุดสำหรับคุณ", icon_url=interaction.guild.icon.url)
        .set_image(url="https://media.discordapp.net/attachments/1201027737004019782/1244129061194829897/unknown_3.jpg?ex=66a9ae7a&is=66a85cfa&hm=4ba1c4929589e76fefb10b08a1d1c86bf54c5de07aa7ce7673ace1fde7553335&=&format=webp&width=1313&height=656")
        , view=BuyView())
        await interaction.response.send_message((
        'Successfully reloaded application [/] commands.'
        ), ephemeral=True)
    else:
        await interaction.response.send_message((
           '🚫 คำสั่งนี้สำหรับเจ้าของเซิร์ฟเวอร์เท่านั้น'
        ), ephemeral=True)

@bot.slash_command(name='setupsaverole',description='✨ ติดตั้งระบบเชฟยศ')
async def setup(interaction: nextcord.Interaction):
    if (int(interaction.user.id) == int(config['ownerId'])):
      embed=nextcord.Embed(title="✨ ระบบสำรองข้อมูลยศ by yokfreeforyou ✨",description="หมดกังวลเรื่องดิสบิน หรือเผลอออกจากเซิร์ฟเวอร์! สำรองยศของคุณไว้กับเราได้เลย",color=0xff2c2c) # This line was already correct
      embed.set_author(name="yokfreeforyou", url="", icon_url=interaction.guild.icon.url)  
      embed.add_field(name="`💾` สำรองข้อมูลยศครั้งแรก `💾`", value="```diff\n+ กดปุ่ม (เซฟยศ) เพื่อบันทึกยศทั้งหมดที่คุณมี\n```", inline=True)
      embed.add_field(name="`🔄` รับยศที่เคยสำรองไว้คืน `🔄`", value="```diff\n+ กดปุ่ม (รับยศคืน) เพื่อรับยศทั้งหมดกลับคืนมา\n+ ใช้ในกรณีดิสบิน, ออกดิสโดยไม่ได้ตั้งใจ หรือเข้า-ออกใหม่\n```", inline=True)
      embed.add_field(name="`❗` คำแนะนำจากทีมงาน `❗`", value="```diff\n- หากพบปัญหาในการใช้งาน กรุณาติดต่อแอดมินทันที\n```", inline=False)
      embed.set_image(url="https://media.discordapp.net/attachments/1168490971990851645/1168892040562610278/standard.gif?ex=659d3e8b&is=658ac98b&hm=e69154a948fe7643d1a937f434e454f73fe55054c4e537ea214fda83ec983529&=")
      embed.set_image(url="https://media.discordapp.net/attachments/1168490971990851645/1168892040562610278/standard.gif?ex=65afb38b&is=659d3e8b&hm=7b3a9b1a593ef37cacfabb0d5d23086507dde08d4563b42c8bb22f60a527f9dc&=&width=585&height=75")
      await interaction.channel.send(embed=embed,view=setupView())
    else:
        await interaction.response.send_message((
           '🚫 คำสั่งนี้สำหรับเจ้าของเซิร์ฟเวอร์เท่านั้น'
        ), ephemeral=True)

@bot.slash_command(name='giverole', description='✨ (Admin) ให้ยศกับผู้ใช้โดยระบุยอดเงิน')
async def giverole(
    interaction: nextcord.Interaction,
    user: nextcord.Member = nextcord.SlashOption(
        name="user",
        description="ผู้ใช้ที่ต้องการให้ยศ",
        required=True
    ),
    amount: int = nextcord.SlashOption(
        name="amount",
        description="ยอดเงินที่เทียบเท่ากับราคายศ",
        required=True
    )
):
    # --- ตรวจสอบสิทธิ์ ---
    if str(interaction.user.id) != str(config['ownerId']):
        await interaction.response.send_message('🚫 คำสั่งนี้สำหรับเจ้าของเซิร์ฟเวอร์เท่านั้น', ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    # --- ค้นหาและเพิ่มยศ ---
    roles_to_add = []
    for roleData in config['roleSettings']:
        if amount == roleData['price']:
            role = nextcord.utils.get(interaction.guild.roles, id=int(roleData['roleId']))
            if role:
                roles_to_add.append(role)

    if not roles_to_add:
        await interaction.followup.send(f"⚠️ ไม่พบยศที่ตรงกับยอดเงิน `{amount}` บาท", ephemeral=True)
        return

    for role in roles_to_add:
        await user.add_roles(role)
        # ส่ง Log สำหรับแต่ละยศที่เพิ่ม
        await bot.get_channel(int(config['channelLog'])).send(embed=MyEmbed(user.id, amount, role.id, "Admin Gave"))

    await interaction.followup.send(f"✅ เพิ่มยศที่เกี่ยวข้องกับยอด `{amount}` บาท ให้กับ <@{user.id}> เรียบร้อยแล้ว", ephemeral=True)

server_on()

# ดึงค่า DISCORD_TOKEN จาก Environment Variable ที่โหลดมาจากไฟล์ .env
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(DISCORD_TOKEN)