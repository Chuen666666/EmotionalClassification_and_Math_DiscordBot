import gc
import json
import math
import os
import zipfile
from pathlib import Path
from threading import Thread

import discord
import requests
import torch
from discord.abc import GuildChannel, Messageable
from discord.ext import commands, tasks
from dotenv import load_dotenv
from flask import Flask
from transformers import BertForSequenceClassification, BertTokenizer


# 創建迷你網頁，使 Render 可運作
app = Flask(__name__)


@app.route('/')
def home():
    return "I'm alive!"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()


BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / 'bert_emotion_model'
PTH_PATH = BASE_DIR / 'bert_emotion_model.pth'

if os.path.exists('/etc/secrets/server_channel.json'):
    CONFIG_PATH = Path('/etc/secrets/server_channel.json')
elif (BASE_DIR / 'server_channel.json').exists():
    CONFIG_PATH = BASE_DIR / 'server_channel.json'
else:
    CONFIG_PATH = Path('server_channel.json')

try:
    with CONFIG_PATH.open('r', encoding='utf-8') as f:
        jdata = json.load(f)
    print(f'成功讀取設定檔：{CONFIG_PATH}')
except Exception as e:
    print(f'讀取設定檔失敗！路徑：{CONFIG_PATH}，錯誤：{e}')

if not os.getenv('RENDER'):
    load_dotenv(BASE_DIR / 'bot_token.env')

TOKEN = os.getenv('DISCORD_BOT_TOKEN')

if not TOKEN:
    load_dotenv(dotenv_path=BASE_DIR / 'bot_token.env')


def prepare_model():
    if not MODEL_DIR.exists() or not PTH_PATH.exists():
        url = os.getenv('MODEL_URL')
        if not url:
            print('找不到 MODEL_URL 環境變數，跳過下載')
            return

        print('下載模型中...')
        try:
            with requests.get(url, stream=True, timeout=(10, 60)) as response:
                response.raise_for_status()
                zip_tmp = BASE_DIR / 'model.zip'
                with zip_tmp.open('wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

            print('解壓中...')
            with zipfile.ZipFile(zip_tmp, 'r') as zip_ref:
                base_dir = BASE_DIR.resolve()
                for member in zip_ref.infolist():
                    target = (BASE_DIR / member.filename).resolve()
                    if target != base_dir and base_dir not in target.parents:
                        raise ValueError(f'壓縮檔包含不安全的路徑：{member.filename}')
                zip_ref.extractall(BASE_DIR)

            os.remove(zip_tmp)
            print('模型已就緒')

            gc.collect()
        except Exception as e:
            print(f'模型下載失敗：{e}')


prepare_model()
gc.collect()

try:
    print('正在讀取模型結構')
    tokenizer = BertTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
    model = BertForSequenceClassification.from_pretrained(
        MODEL_DIR, local_files_only=True
    )

    print('權重載入中（CPU）')
    state_dict = torch.load(
        PTH_PATH, map_location=torch.device('cpu'), weights_only=True
    )
    model.load_state_dict(state_dict)

    model.eval()
    print('模型載入成功')
except Exception as e:
    print(f'模型載入發生錯誤：{e}')

emotion_to_emoji = {'Positive': '👍', 'Neutral': None, 'Negative': '👎'}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


async def check_channel(ctx) -> bool:
    match ctx.command.name:
        case 'update':
            channel_id = jdata['UPDATE']
        case 'test_join' | 'test_leave':
            channel_id = jdata['TEST_IO']
        case _:
            channel_id = jdata['COMMAND']

    if ctx.channel.id != channel_id:
        msg = f'請至 <#{channel_id}> 使用此指令！'

        interaction = getattr(ctx, 'interaction', None)
        if interaction is not None:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            except Exception:
                await ctx.send(msg, delete_after=3)
        else:
            await ctx.send(msg, delete_after=3)
        return False

    return True


bot = commands.Bot(command_prefix='!', intents=intents)
bot.add_check(check_channel)


def gcd_(a, b, c) -> tuple[int, int, int]:
    value = math.gcd(math.gcd(abs(a), abs(b)), abs(c))
    a //= value
    b //= value
    c //= value
    return (a, b, c)


def int_(i: float) -> int | float:
    return int(i) if i.is_integer() else i


def str_(*i: str) -> tuple[float, ...]:
    result = []
    for j in (s.replace(' ', '') for s in i):
        try:
            result.append(float(j))
        except ValueError:
            a, b = map(float, j.split('/'))
            result.append(a / b)
    return tuple(result)


def readable(coef: int | float, var: str) -> str:
    match coef:
        case 0:
            return ''
        case 1 | 1.0:
            return var
        case -1 | -1.0:
            return f'-{var}'
        case _:
            return f'{int_(coef)}{var}'


def predict_emotion(sentence) -> str | None:
    inputs = tokenizer(
        sentence, return_tensors='pt', truncation=True, padding=True, max_length=128
    )
    with torch.no_grad():
        outputs = model(**inputs)
    logits = outputs.logits
    predicted_label = torch.argmax(logits, dim=1).item()
    emotion_labels = ['Positive', 'Neutral', 'Negative']
    emotion = emotion_labels[int(predicted_label)]
    return emotion_to_emoji.get(emotion)


async def update_member_count(guild):
    total_members = guild.member_count
    real_members = sum(1 for m in guild.members if not m.bot)
    bot_members = sum(1 for m in guild.members if m.bot)

    total_channel = bot.get_channel(jdata['TOTAL_PPL'])
    real_channel = bot.get_channel(jdata['REAL_PPL'])
    bot_channel = bot.get_channel(jdata['BOT_PPL'])

    if isinstance(total_channel, GuildChannel):
        await total_channel.edit(name=f'總人數：{total_members}')
    if isinstance(real_channel, GuildChannel):
        await real_channel.edit(name=f'真人：{real_members}')
    if isinstance(bot_channel, GuildChannel):
        await bot_channel.edit(name=f'機器人：{bot_members}')


@tasks.loop(minutes=10)
async def update_member_count_loop():
    guild = bot.guilds[0]
    await update_member_count(guild)


@bot.event
async def on_ready():
    channel = bot.get_channel(jdata['UPDATE'])
    try:
        synced = await bot.tree.sync()
        if isinstance(channel, Messageable):
            await channel.send(f'自動同步成功！同步了 {len(synced)} 條指令！')
    except Exception as e:
        if isinstance(channel, Messageable):
            await channel.send(f'自動同步失敗：{e}')
    finally:
        update_member_count_loop.start()


@bot.event
async def on_member_join(member):
    channel = bot.get_channel(jdata['JOIN'])

    if isinstance(channel, Messageable):
        await channel.send(f'**{member}** 加入了伺服器！')
        await update_member_count(member.guild)


@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(jdata['LEAVE'])

    if isinstance(channel, Messageable):
        await channel.send(f'**{member}** 離開了伺服器！')
        await update_member_count(member.guild)


@bot.command()
@commands.has_permissions(administrator=True)
async def update(ctx):
    try:
        synced = await bot.tree.sync()
        await ctx.send(f'指令同步成功！同步了 {len(synced)} 條指令！')
    except Exception as e:
        await ctx.send(f'指令同步失敗：{e}')


class FakeMember:
    def __init__(self, name, guild):
        self.name = name
        self.display_name = name
        self.guild = guild
        self.id = 123456789
        self.bot = False
        self.mention = f'<@{self.id}>'

    def __str__(self):
        return self.display_name


@bot.command()
@commands.has_permissions(administrator=True)
async def test_join(ctx):
    guild = ctx.guild
    fake_member = FakeMember('測試', guild)
    bot.dispatch('member_join', fake_member)


@bot.command()
@commands.has_permissions(administrator=True)
async def test_leave(ctx):
    guild = ctx.guild
    fake_member = FakeMember('測試', guild)
    bot.dispatch('member_remove', fake_member)


@bot.hybrid_command(name='二元一次方程式')
async def linear_equation_in_one_var(
    ctx,
    第一式的x項係數,  # noqa: N803
    第一式的y項係數,  # noqa: N803
    第一式的常數項,  # noqa: N803
    第二式的x項係數,  # noqa: N803
    第二式的y項係數,  # noqa: N803
    第二式的常數項,  # noqa: N803
):
    """請以"ax+by=c"的形式表達，接受整數、小數、分數"""

    (
        第一式的x項係數,  # noqa: N806
        第一式的y項係數,  # noqa: N806
        第一式的常數項,  # noqa: N806
        第二式的x項係數,  # noqa: N806
        第二式的y項係數,  # noqa: N806
        第二式的常數項,  # noqa: N806
    ) = str_(
        第一式的x項係數,
        第一式的y項係數,
        第一式的常數項,
        第二式的x項係數,
        第二式的y項係數,
        第二式的常數項,
    )

    d = 第一式的x項係數 * 第二式的y項係數 - 第二式的x項係數 * 第一式的y項係數
    dx = 第一式的常數項 * 第二式的y項係數 - 第二式的常數項 * 第一式的y項係數
    dy = 第一式的x項係數 * 第二式的常數項 - 第二式的x項係數 * 第一式的常數項

    first = f'{readable(第一式的x項係數, "x")}{"+" if 第一式的y項係數 > 0 and 第一式的x項係數 else ""}\
{readable(第一式的y項係數, "y")} = {int_(第一式的常數項)}'
    second = f'{readable(第二式的x項係數, "x")}{"+" if 第二式的y項係數 > 0 and 第二式的x項係數 else ""}\
{readable(第二式的y項係數, "y")} = {int_(第二式的常數項)}'
    await ctx.send(f'{first}\n{second}')

    if d != 0:
        await ctx.send(f'x = {int_(dx / d)}, y = {int_(dy / d)}')
    elif dx == dy == 0:
        await ctx.send('有無限多組解')
    else:
        await ctx.send('無解')


@bot.hybrid_command(name='一元一次_二次方程式')
async def linear_quadratic_equation_in_one_var(ctx, x平方項係數, x項係數, 常數項):  # noqa: N803
    """請以"ax^2+bx+c=0"的形式表達，接受整數、小數、分數"""

    x平方項係數, x項係數, 常數項 = str_(x平方項係數, x項係數, 常數項)  # noqa: N806
    d = x項係數**2 - 4 * x平方項係數 * 常數項

    await ctx.send(
        f'{readable(x平方項係數, "x^2")}{"+" if x項係數 > 0 and x平方項係數 else ""}\
{readable(x項係數, "x")}{"+" if 常數項 > 0 and (x平方項係數 or x項係數) else ""}{int_(常數項)}=0'
    )

    if x平方項係數 == 0 and x項係數 != 0:
        await ctx.send(f'x = {int_(-常數項 / x項係數)}')
    elif x平方項係數 != 0:
        if d > 0:
            a1 = (-x項係數 + math.sqrt(d)) / (2 * x平方項係數)
            a2 = (-x項係數 - math.sqrt(d)) / (2 * x平方項係數)
            await ctx.send(f'x = {int_(a1)}, {int_(a2)}')
        elif d == 0:
            await ctx.send(f'x = {int_(-x項係數 / (2 * x平方項係數))}(重根)')
        else:
            await ctx.send('無實根')
    else:
        await ctx.send('你是來亂的嗎？')


@bot.hybrid_command(name='等差數列')
async def arthmetic_sequence(
    ctx,
    數列中的任意值,  # noqa: N803
    該值的項數: int,  # noqa: N803
    公差,  # noqa: N803
    想求的項數: int,  # noqa: N803
):
    """數列中的任意值與公差之輸入，接受整數、小數、分數"""
    數列中的任意值, 公差 = str_(數列中的任意值, 公差)  # noqa: N806
    await ctx.send(f'a_n = {int_(數列中的任意值 + (想求的項數 - 該值的項數) * 公差)}')


@bot.hybrid_command(name='等差級數')
async def arithmetic_series(ctx, 首項, 末項, 項數: int):  # noqa: N803
    """首項與末項之輸入，接受整數、小數、分數"""
    首項, 末項 = str_(首項, 末項)  # noqa: N806
    await ctx.send(f'S_n = {int_(項數 * (首項 + 末項) / 2)}')


@bot.hybrid_command(name='等比數列')
async def geometric_sequence(
    ctx,
    數列中的任意值,  # noqa: N803
    該值的項數: int,  # noqa: N803
    公比,  # noqa: N803
    想求的項數: int,  # noqa: N803
):
    """數列中的任意值與公比之輸入，接受整數、小數、分數"""
    數列中的任意值, 公比 = str_(數列中的任意值, 公比)  # noqa: N806
    await ctx.send(f'a_n = {int_(數列中的任意值 * 公比 ** (想求的項數 - 該值的項數))}')


@bot.hybrid_command(name='等比級數')
async def geometric_series(ctx, 首項, 公比, 項數: int):  # noqa: N803
    """數列中的首項與公比之輸入，接受整數、小數、分數"""
    首項, 公比 = str_(首項, 公比)  # noqa: N806
    await ctx.send(
        f'S_n = {
            int_(項數 * 首項)
            if 公比 == 1.0
            else int_((首項 * (1 - (公比**項數))) / (1 - 公比))
        }'
    )


@bot.hybrid_command(name='階乘')
async def factorial(ctx, 整數: int):  # noqa: N803
    """計算1*2*3*...*n"""
    await ctx.send(f'{整數}! = {math.factorial(整數)}')


@bot.hybrid_command(name='組合數')
async def combination(ctx, n: int, k: int):
    """計算(n!)/(k!(n-k)!)，或俗稱Cn取k"""
    await ctx.send(f'C{n}取{k} = {math.comb(n, k)}')


@bot.hybrid_command(name='指數')
async def exponent(ctx, 底數, 指數):  # noqa: N803
    """底數與指數之輸入，接受整數、小數、分數"""
    底數, 指數 = str_(底數, 指數)  # noqa: N806
    await ctx.send(
        f'{int_(底數) if 底數 >= 0 else f"({int_(底數)})"} ^ {int_(指數)} = {
            int_(底數**指數)
        }'
    )


@bot.hybrid_command(name='開n次方根')
async def nth_root(ctx, 底數, n):  # noqa: N803
    """底數與n之輸入，接受整數、小數、分數"""
    底數, n = str_(底數, n)  # noqa: N806
    await ctx.send(
        f'{int_(底數)}的{int_(n)}次方根 = {int_(底數 ** (1 / n))}'
        if 底數 > 0
        else '開n次方根時 底數須為正'
    )


@bot.hybrid_command(name='對數')
async def log(ctx, 底數, 真數):  # noqa: N803
    '''底數與真數接受整數、小數、分數，底數接受"e"'''
    真數 = int_(*str_(真數))  # noqa: N806
    match 底數:
        case 'e':
            await ctx.send(f'ln{真數} = {int_(math.log(真數))}')
        case '2':
            await ctx.send(f'log_2({真數}) = {int_(math.log2(真數))}')
        case '10':
            await ctx.send(f'log{真數} = {int_(math.log10(真數))}')
        case _:
            底數 = str_(底數)[0]  # noqa: N806
            await ctx.send(f'log_{int_(底數)}({真數}) = {int_(math.log(真數, 底數))}')


@bot.hybrid_command(name='畢氏定理')
async def pythagorean_theorem(ctx, 短股, 長股, 斜邊):  # noqa: N803
    """想計算的邊以半形"?"輸入，數字輸入接受整數、小數、分數"""
    try:
        if 短股 == '?':
            長股, 斜邊 = str_(長股, 斜邊)  # noqa: N806
            短股 = math.sqrt(斜邊**2 - 長股**2)  # noqa: N806
        elif 長股 == '?':
            短股, 斜邊 = str_(短股, 斜邊)  # noqa: N806
            長股 = math.sqrt(斜邊**2 - 短股**2)  # noqa: N806
        elif 斜邊 == '?':
            長股, 短股 = str_(長股, 短股)  # noqa: N806
            斜邊 = math.sqrt(長股**2 + 短股**2)  # noqa: N806
        else:
            await ctx.send('輸入的值有誤')
            return
        短股, 長股, 斜邊 = map(int_, (短股, 長股, 斜邊))  # noqa: N806
        await ctx.send(f'{短股 = }, {長股 = }, {斜邊 = }')
    except ValueError:
        await ctx.send('邊長資料有誤')


@bot.hybrid_command(name='三角函數')
async def trigonometric(ctx, 對邊, 斜邊, 鄰邊):  # noqa: N803
    """三角形的三邊長度之輸入，接受整數、小數、分數"""
    對邊, 斜邊, 鄰邊 = str_(對邊, 斜邊, 鄰邊)  # noqa: N806
    if 對邊 + 斜邊 > 鄰邊 and 對邊 + 鄰邊 > 斜邊 and 斜邊 + 鄰邊 > 對邊:
        await ctx.send(f"""sin = {int_(對邊 / 斜邊)}, cos = {int_(鄰邊 / 斜邊)},
tan = {int_(對邊 / 鄰邊)}, cot = {int_(鄰邊 / 對邊)},
sec = {int_(斜邊 / 鄰邊)}, csc = {int_(斜邊 / 對邊)}""")
    else:
        await ctx.send('邊長資料有誤')


@bot.event
async def on_message(msg):
    if msg.author == bot.user:
        return
    if msg.channel.id == jdata['CHAT']:
        emoji = predict_emotion(msg.content)
        if emoji is None:
            print('情緒辨識結果：Neutral')
            return
        await msg.add_reaction(emoji)
        print(
            f'情緒辨識結果：{"Positive" if emoji == emotion_to_emoji["Positive"] else "Negative"}'
        )
    await bot.process_commands(msg)


if __name__ == '__main__':
    if TOKEN:
        keep_alive()
        bot.run(TOKEN)
    else:
        print('錯誤！找不到 TOKEN！')
